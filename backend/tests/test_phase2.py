"""Phase 2 backend tests: multi-tenant, deposit (Stripe), whatsapp mock, cron reminders."""
import os
import time
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://book-salon-64.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPERADMIN = ("jonathan.alexandre20@gmail.com", "Salao@2026")
OWNER = ("barbearia@demo.com", "Barber@2026")

# Cron secret from backend/.env
def _cron_secret():
    with open("/app/backend/.env") as f:
        for line in f:
            if line.startswith("WEBHOOK_CRON_SECRET"):
                return line.split("=", 1)[1].strip().strip('"')
    return ""

CRON_SECRET = _cron_secret()


@pytest.fixture(scope="session")
def super_token():
    r = requests.post(f"{API}/auth/login", json={"email": SUPERADMIN[0], "password": SUPERADMIN[1]})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def owner_token():
    r = requests.post(f"{API}/auth/login", json={"email": OWNER[0], "password": OWNER[1]})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(tok, extra=None):
    h = {"Authorization": f"Bearer {tok}"}
    if extra:
        h.update(extra)
    return h


# ---------- Public multi-tenant ----------
class TestPublicTenants:
    def test_gel_beauty_salon(self):
        r = requests.get(f"{API}/public/gel-beauty/salon")
        assert r.status_code == 200
        d = r.json()
        assert d["slug"] == "gel-beauty"
        assert d["deposit_enabled"] is True
        assert d["deposit_percent"] == 30
        assert d["whatsapp_mode"] == "mock"

    def test_barbearia_salon(self):
        r = requests.get(f"{API}/public/barbearia-vintage/salon")
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "Barbearia Vintage"
        assert d["deposit_enabled"] is False

    def test_unknown_slug_404(self):
        r = requests.get(f"{API}/public/slug-inexistente-qa/salon")
        assert r.status_code == 404

    def test_barber_services(self):
        r = requests.get(f"{API}/public/barbearia-vintage/services")
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert {"Corte Clássico", "Barba Completa", "Corte + Barba"}.issubset(names)


# ---------- Booking + Deposit ----------
@pytest.fixture(scope="session")
def gel_service():
    r = requests.get(f"{API}/public/gel-beauty/services")
    assert r.status_code == 200
    return r.json()[0]


@pytest.fixture(scope="session")
def barber_service():
    r = requests.get(f"{API}/public/barbearia-vintage/services")
    return r.json()[0]


def _future_slot(slug, service_id, days=2):
    d = (date.today() + timedelta(days=days)).isoformat()
    r = requests.get(f"{API}/public/{slug}/services/{service_id}/slots", params={"date": d})
    assert r.status_code == 200
    for s in r.json()["slots"]:
        if s["available"]:
            return d, s["time"]
    raise RuntimeError("no slot")


class TestBookingDeposit:
    booking_id = None
    session_id = None

    def test_create_gel_booking_with_deposit(self, gel_service):
        d, t = _future_slot("gel-beauty", gel_service["id"], days=3)
        payload = {"service_id": gel_service["id"], "date": d, "time": t,
                   "client_name": f"TEST QA {uuid.uuid4().hex[:6]}",
                   "client_phone": "+5511911112222"}
        r = requests.post(f"{API}/public/gel-beauty/bookings", json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["booking"]["deposit_status"] == "none"
        expected = round(gel_service["price"] * 0.3, 2)
        assert j["booking"]["deposit_amount"] == expected
        assert j["whatsapp_mode"] == "mock"
        assert "wa.me" in j["whatsapp_link"]
        assert j["deposit"]["enabled"] is True
        TestBookingDeposit.booking_id = j["booking"]["id"]

    def test_whatsapp_mock_message_stored(self, super_token):
        assert TestBookingDeposit.booking_id
        time.sleep(3)
        r = requests.get(f"{API}/messages?limit=100", headers=auth(super_token))
        assert r.status_code == 200
        found = [m for m in r.json()
                 if m.get("ref_id") == TestBookingDeposit.booking_id and m["kind"] == "booking_created"]
        assert found, "booking_created message not found"
        assert found[0]["status"] == "mock"

    def test_create_deposit_checkout(self):
        assert TestBookingDeposit.booking_id
        r = requests.post(f"{API}/public/gel-beauty/bookings/{TestBookingDeposit.booking_id}/deposit",
                          json={"origin_url": BASE_URL})
        assert r.status_code == 200, r.text
        j = r.json()
        assert "checkout.stripe.com" in j["checkout_url"]
        assert j["session_id"].startswith("cs_")
        TestBookingDeposit.session_id = j["session_id"]

    def test_payment_status_pending(self):
        assert TestBookingDeposit.session_id
        r = requests.get(f"{API}/payments/status/{TestBookingDeposit.session_id}")
        assert r.status_code == 200
        assert r.json()["payment_status"] == "pending"

    def test_deposit_nonexistent_booking(self):
        r = requests.post(f"{API}/public/gel-beauty/bookings/does-not-exist/deposit",
                          json={"origin_url": BASE_URL})
        assert r.status_code == 404

    def test_deposit_disabled_for_barber(self, barber_service):
        d, t = _future_slot("barbearia-vintage", barber_service["id"], days=4)
        r = requests.post(f"{API}/public/barbearia-vintage/bookings",
                          json={"service_id": barber_service["id"], "date": d, "time": t,
                                "client_name": "TEST QA Barber", "client_phone": "+5511922223333"})
        assert r.status_code == 200
        bid = r.json()["booking"]["id"]
        assert r.json()["deposit"]["enabled"] is False
        r2 = requests.post(f"{API}/public/barbearia-vintage/bookings/{bid}/deposit",
                           json={"origin_url": BASE_URL})
        assert r2.status_code == 400


# ---------- Cron ----------
class TestCron:
    def test_no_auth_401(self):
        r = requests.post(f"{API}/cron/reminders", json={})
        assert r.status_code == 401

    def test_wrong_auth_401(self):
        r = requests.post(f"{API}/cron/reminders", json={},
                          headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401

    def test_correct_auth_ok_and_idempotent(self, super_token):
        run_id = f"qa-run-{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/cron/reminders", json={"run_id": run_id},
                          headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        r2 = requests.post(f"{API}/cron/reminders", json={"run_id": run_id},
                           headers={"Authorization": f"Bearer {CRON_SECRET}"})
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True

        time.sleep(3)
        r3 = requests.get(f"{API}/cron/runs", headers=auth(super_token))
        assert r3.status_code == 200
        runs = r3.json()
        assert any(x["run_id"] == run_id for x in runs)


# ---------- Tenant scoping / roles ----------
class TestTenantScoping:
    def test_owner_forbidden_tenants(self, owner_token):
        r = requests.get(f"{API}/admin/tenants", headers=auth(owner_token))
        assert r.status_code == 403

    def test_owner_sees_only_own_services(self, owner_token):
        r = requests.get(f"{API}/services", headers=auth(owner_token))
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert "Corte Clássico" in names
        assert "Alongamento em Gel" not in names

    def test_owner_ignores_x_tenant_header(self, owner_token):
        # owner tries to switch to gel-beauty via header (must be ignored)
        r = requests.get(f"{API}/services", headers=auth(owner_token, {"X-Tenant": "gel-beauty"}))
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert "Alongamento em Gel" not in names

    def test_superadmin_switch_tenant(self, super_token):
        r_gel = requests.get(f"{API}/services", headers=auth(super_token, {"X-Tenant": "gel-beauty"}))
        r_bar = requests.get(f"{API}/services", headers=auth(super_token, {"X-Tenant": "barbearia-vintage"}))
        assert r_gel.status_code == 200 and r_bar.status_code == 200
        gel_names = {s["name"] for s in r_gel.json()}
        bar_names = {s["name"] for s in r_bar.json()}
        assert "Alongamento em Gel" in gel_names
        assert "Corte Clássico" in bar_names
        assert gel_names.isdisjoint(bar_names)


# ---------- Settings ----------
class TestSettings:
    def test_deposit_percent_validation(self, super_token):
        r = requests.put(f"{API}/settings", json={"deposit_percent": 0},
                         headers=auth(super_token, {"X-Tenant": "gel-beauty"}))
        assert r.status_code == 400

    def test_update_and_revert_deposit_percent(self, super_token):
        h = auth(super_token, {"X-Tenant": "gel-beauty"})
        r = requests.put(f"{API}/settings", json={"deposit_percent": 20}, headers=h)
        assert r.status_code == 200
        assert r.json()["deposit_percent"] == 20
        # verify public endpoint
        r2 = requests.get(f"{API}/public/gel-beauty/salon")
        assert r2.json()["deposit_percent"] == 20
        # revert
        r3 = requests.put(f"{API}/settings", json={"deposit_percent": 30}, headers=h)
        assert r3.status_code == 200
        assert r3.json()["deposit_percent"] == 30


# ---------- Superadmin tenant CRUD ----------
class TestSuperAdmin:
    slug = None

    def test_create_and_delete_tenant(self, super_token):
        slug = f"qa-dentista-{uuid.uuid4().hex[:6]}"
        TestSuperAdmin.slug = slug
        payload = {"slug": slug, "name": "QA Dentista", "category": "Odonto",
                   "whatsapp": "5511900000000", "owner_name": "QA Owner",
                   "owner_email": f"qa-{uuid.uuid4().hex[:6]}@qa.com",
                   "owner_password": "Test@1234"}
        r = requests.post(f"{API}/admin/tenants", json=payload, headers=auth(super_token))
        assert r.status_code == 200, r.text
        assert r.json()["slug"] == slug
        tid = r.json()["id"]

        # appears in list
        rl = requests.get(f"{API}/admin/tenants", headers=auth(super_token))
        assert any(t["slug"] == slug for t in rl.json())

        # public shows empty services
        rs = requests.get(f"{API}/public/{slug}/services")
        assert rs.status_code == 200 and rs.json() == []

        # delete
        rd = requests.delete(f"{API}/admin/tenants/{tid}", headers=auth(super_token))
        assert rd.status_code == 200

    def test_cannot_delete_default(self, super_token):
        # find default
        r = requests.get(f"{API}/admin/tenants", headers=auth(super_token))
        default = next(t for t in r.json() if t["slug"] == "gel-beauty")
        r2 = requests.delete(f"{API}/admin/tenants/{default['id']}", headers=auth(super_token))
        assert r2.status_code == 400


# ---------- Booking status confirmed → message ----------
class TestConfirmMessage:
    def test_confirm_booking_generates_message(self, super_token, gel_service):
        d, t = _future_slot("gel-beauty", gel_service["id"], days=5)
        b = requests.post(f"{API}/public/gel-beauty/bookings",
                          json={"service_id": gel_service["id"], "date": d, "time": t,
                                "client_name": "TEST Confirm QA", "client_phone": "+5511933334444"})
        bid = b.json()["booking"]["id"]
        h = auth(super_token, {"X-Tenant": "gel-beauty"})
        r = requests.put(f"{API}/bookings/{bid}/status", json={"status": "confirmed"}, headers=h)
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"
        time.sleep(3)
        m = requests.get(f"{API}/messages?limit=100", headers=h).json()
        assert any(x["ref_id"] == bid and x["kind"] == "confirmed" for x in m)


# ---------- Regression: blocks & service tenant scoping ----------
class TestRegression:
    def test_blocks_crud_and_scoped(self, super_token):
        h = auth(super_token, {"X-Tenant": "gel-beauty"})
        d = (date.today() + timedelta(days=10)).isoformat()
        r = requests.post(f"{API}/blocks", json={"date": d, "time": "10:00", "reason": "TEST"}, headers=h)
        assert r.status_code == 200
        bid = r.json()["id"]
        r2 = requests.get(f"{API}/blocks", headers=h)
        assert any(x["id"] == bid for x in r2.json())
        rd = requests.delete(f"{API}/blocks/{bid}", headers=h)
        assert rd.status_code == 200

    def test_service_created_in_barber_not_in_gel_public(self, owner_token):
        # owner is barbearia
        name = f"TEST Service {uuid.uuid4().hex[:5]}"
        r = requests.post(f"{API}/services", json={"name": name, "price": 10, "duration_min": 30,
                                                   "active": True},
                          headers=auth(owner_token))
        assert r.status_code == 200
        sid = r.json()["id"]
        gel_public = requests.get(f"{API}/public/gel-beauty/services").json()
        assert not any(s["id"] == sid for s in gel_public)
        # cleanup
        requests.delete(f"{API}/services/{sid}", headers=auth(owner_token))
