from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import hmac
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from datetime import time as dtime
from zoneinfo import ZoneInfo

import bcrypt
import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, EmailStr
from starlette.middleware.cors import CORSMiddleware

import whatsapp as wa
from db import (
    DEFAULT_SLUG,
    PUBLIC_FIELDS,
    client,
    db,
    get_tenant_by_id,
    get_tenant_by_slug,
    with_defaults,
)
from payments import deposit_amount
from payments import router as payments_router

app = FastAPI(title="Salão PWA API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Auth utils ----------------
JWT_ALGORITHM = "HS256"

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_principal(request: Request, user=Depends(get_current_user)) -> dict:
    """Resolves the active tenant. Superadmin may switch tenant via X-Tenant (slug) header."""
    tenant_id = user.get("tenant_id")
    if user.get("role") == "superadmin":
        slug = request.headers.get("X-Tenant")
        if slug:
            tenant_id = (await get_tenant_by_slug(slug))["id"]
    if not tenant_id:
        raise HTTPException(403, "Usuário sem salão vinculado")
    return {**user, "tenant_id": tenant_id}

def require_superadmin(user=Depends(get_current_user)) -> dict:
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Apenas o super-admin pode fazer isso")
    return user

# ---------------- Models ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ServiceIn(BaseModel):
    name: str
    description: str | None = ""
    price: float
    duration_min: int
    image_url: str | None = ""
    active: bool = True

class BookingIn(BaseModel):
    service_id: str
    date: str
    time: str
    client_name: str
    client_phone: str
    client_email: str | None = ""
    notes: str | None = ""

class BookingStatusIn(BaseModel):
    status: str

class BlockIn(BaseModel):
    date: str
    time: str | None = None
    reason: str | None = ""

class SettingsIn(BaseModel):
    name: str | None = None
    category: str | None = None
    tagline: str | None = None
    hero_title: str | None = None
    hero_subtitle: str | None = None
    hero_image: str | None = None
    gallery: list[str] | None = None
    address: str | None = None
    instagram: str | None = None
    phone_display: str | None = None
    whatsapp: str | None = None
    open_hour: int | None = None
    close_hour: int | None = None
    slot_minutes: int | None = None
    deposit_enabled: bool | None = None
    deposit_percent: float | None = None
    testimonial: str | None = None
    testimonial_author: str | None = None

class TenantIn(BaseModel):
    slug: str
    name: str
    category: str | None = "Beleza"
    whatsapp: str | None = ""
    owner_name: str
    owner_email: EmailStr
    owner_password: str

# ---------------- Helpers ----------------
def tz_of(tenant: dict) -> ZoneInfo:
    try:
        return ZoneInfo(tenant.get("timezone") or "America/Sao_Paulo")
    except Exception:
        return ZoneInfo("America/Sao_Paulo")

def local_now(tenant: dict) -> datetime:
    return datetime.now(tz_of(tenant)).replace(tzinfo=None)

def public_tenant(t: dict) -> dict:
    out = {k: t.get(k) for k in PUBLIC_FIELDS}
    out["whatsapp_mode"] = wa.mode()
    return out

async def upsert_client(tenant_id: str, name: str, phone: str, email: str):
    await db.clients.update_one(
        {"tenant_id": tenant_id, "phone": phone},
        {"$set": {"name": name, "email": email},
         "$setOnInsert": {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "phone": phone,
                          "created_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"bookings_count": 1}},
        upsert=True,
    )

async def send_reminders_for_tenant(tenant: dict) -> dict:
    tomorrow = (local_now(tenant).date() + timedelta(days=1)).isoformat()
    items = await db.bookings.find(
        {"tenant_id": tenant["id"], "date": tomorrow, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}
    ).to_list(500)
    results = {"date": tomorrow, "total": len(items), "sent": 0, "mock": 0, "failed": 0, "skipped": 0}
    for b in items:
        before = await db.messages.find_one({"idempotency_key": f"reminder:{b['id']}"})
        msg = await wa.send_message(tenant["id"], b["client_phone"], wa.reminder_text(tenant, b), "reminder", b["id"])
        if before:
            results["skipped"] += 1
        else:
            results[msg["status"]] = results.get(msg["status"], 0) + 1
    return results

async def run_all_reminders(run_id: str):
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(500)
    summary = []
    for t in tenants:
        t = with_defaults(t)
        r = await send_reminders_for_tenant(t)
        summary.append({"tenant": t["slug"], **r})
    await db.cron_runs.update_one({"run_id": run_id}, {"$set": {"finished_at": datetime.now(timezone.utc).isoformat(),
                                                                "summary": summary}})
    logger.info(f"Reminders cron finished: {summary}")

# ---------------- Auth endpoints ----------------
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = create_access_token(user["id"], user["email"])
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True,
                        samesite="none", max_age=43200, path="/")
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"],
                                     "role": user["role"], "tenant_id": user.get("tenant_id")}}

@api.post("/auth/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(p=Depends(get_principal)):
    tenant = await get_tenant_by_id(p["tenant_id"])
    out = {**p, "tenant": public_tenant(tenant)}
    if p.get("role") == "superadmin":
        out["tenants"] = [{"id": t["id"], "slug": t["slug"], "name": t.get("name")}
                          for t in await db.tenants.find({}, {"_id": 0, "id": 1, "slug": 1, "name": 1}).to_list(500)]
    return out

# ---------------- Public (tenant-scoped) endpoints ----------------
@api.get("/public/{slug}/salon")
async def salon_info(slug: str):
    return public_tenant(await get_tenant_by_slug(slug))

@api.get("/public/{slug}/services")
async def list_public_services(slug: str):
    t = await get_tenant_by_slug(slug)
    return await db.services.find({"tenant_id": t["id"], "active": True}, {"_id": 0}).sort("price", 1).to_list(200)

@api.get("/public/{slug}/services/{service_id}/slots")
async def available_slots(slug: str, service_id: str, date: str = None):
    t = await get_tenant_by_slug(slug)
    svc = await db.services.find_one({"id": service_id, "tenant_id": t["id"]}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Serviço não encontrado")
    if not date:
        raise HTTPException(400, "Data obrigatória")
    try:
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Data inválida")

    bookings = await db.bookings.find({"tenant_id": t["id"], "date": date,
                                       "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}).to_list(500)
    blocks = await db.blocks.find({"tenant_id": t["id"], "date": date}, {"_id": 0}).to_list(200)
    if any(b.get("time") in (None, "") for b in blocks):
        return {"date": date, "slots": []}
    booked = {b["time"] for b in bookings}
    blocked = {b["time"] for b in blocks if b.get("time")}

    now = local_now(t)
    slots = []
    cur = datetime.combine(d, dtime(int(t["open_hour"]), 0))
    end = datetime.combine(d, dtime(int(t["close_hour"]), 0))
    while cur + timedelta(minutes=svc["duration_min"]) <= end:
        hhmm = cur.strftime("%H:%M")
        available = hhmm not in booked and hhmm not in blocked and not (d == now.date() and cur <= now)
        slots.append({"time": hhmm, "available": available})
        cur += timedelta(minutes=int(t["slot_minutes"]))
    return {"date": date, "slots": slots}

@api.post("/public/{slug}/bookings")
async def create_booking(slug: str, body: BookingIn, background: BackgroundTasks):
    t = await get_tenant_by_slug(slug)
    svc = await db.services.find_one({"id": body.service_id, "tenant_id": t["id"]}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Serviço não encontrado")
    if await db.bookings.find_one({"tenant_id": t["id"], "date": body.date, "time": body.time,
                                   "status": {"$in": ["pending", "confirmed"]}}):
        raise HTTPException(409, "Horário já reservado")
    if await db.blocks.find_one({"tenant_id": t["id"], "date": body.date, "time": {"$in": [None, "", body.time]}}):
        raise HTTPException(409, "Horário bloqueado pelo salão")

    dep = deposit_amount(t, svc["price"]) if t.get("deposit_enabled") else 0
    doc = {
        "id": str(uuid.uuid4()), "tenant_id": t["id"],
        "service_id": svc["id"], "service_name": svc["name"], "service_price": svc["price"],
        "service_duration": svc["duration_min"], "date": body.date, "time": body.time,
        "client_name": body.client_name.strip(), "client_phone": body.client_phone.strip(),
        "client_email": (body.client_email or "").strip().lower(), "notes": body.notes or "",
        "status": "pending", "deposit_status": "none", "deposit_amount": dep,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one(doc)
    doc.pop("_id", None)
    await upsert_client(t["id"], doc["client_name"], doc["client_phone"], doc["client_email"])

    client_msg = wa.confirmation_text(t, doc, dep or None)
    background.add_task(wa.send_message, t["id"], doc["client_phone"], client_msg, "booking_created", doc["id"])
    owner_msg = (f"Olá! Gostaria de confirmar meu agendamento de {svc['name']} "
                 f"no dia {wa.fmt_date(body.date)} às {body.time} para {doc['client_name']}.")
    return {"booking": doc, "whatsapp_link": wa.wa_link(t["whatsapp"], owner_msg),
            "whatsapp_mode": wa.mode(),
            "deposit": {"enabled": bool(t.get("deposit_enabled")), "amount": dep, "percent": t.get("deposit_percent")}}

# ---------------- Admin (tenant-scoped) endpoints ----------------
@api.get("/services")
async def list_services(all: bool = False, p=Depends(get_principal)):
    q = {"tenant_id": p["tenant_id"]}
    if not all:
        q["active"] = True
    return await db.services.find(q, {"_id": 0}).sort("price", 1).to_list(200)

@api.post("/services")
async def create_service(body: ServiceIn, p=Depends(get_principal)):
    doc = {"id": str(uuid.uuid4()), "tenant_id": p["tenant_id"], **body.model_dump()}
    await db.services.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.put("/services/{service_id}")
async def update_service(service_id: str, body: ServiceIn, p=Depends(get_principal)):
    res = await db.services.update_one({"id": service_id, "tenant_id": p["tenant_id"]}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Serviço não encontrado")
    return await db.services.find_one({"id": service_id}, {"_id": 0})

@api.delete("/services/{service_id}")
async def delete_service(service_id: str, p=Depends(get_principal)):
    await db.services.delete_one({"id": service_id, "tenant_id": p["tenant_id"]})
    return {"ok": True}

@api.get("/bookings")
async def list_bookings(from_date: str | None = None, to_date: str | None = None,
                        status: str | None = None, p=Depends(get_principal)):
    q: dict = {"tenant_id": p["tenant_id"]}
    if from_date and to_date:
        q["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        q["date"] = {"$gte": from_date}
    if status:
        q["status"] = status
    return await db.bookings.find(q, {"_id": 0}).sort([("date", 1), ("time", 1)]).to_list(1000)

@api.put("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, body: BookingStatusIn, background: BackgroundTasks,
                                p=Depends(get_principal)):
    if body.status not in {"pending", "confirmed", "cancelled", "completed"}:
        raise HTTPException(400, "Status inválido")
    res = await db.bookings.update_one({"id": booking_id, "tenant_id": p["tenant_id"]}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(404, "Agendamento não encontrado")
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if body.status == "confirmed":
        tenant = await get_tenant_by_id(p["tenant_id"])
        background.add_task(wa.send_message, tenant["id"], doc["client_phone"], wa.confirmed_text(tenant, doc),
                            "confirmed", doc["id"])
    return doc

@api.get("/clients")
async def list_clients(p=Depends(get_principal)):
    clients = await db.clients.find({"tenant_id": p["tenant_id"]}, {"_id": 0}).sort("name", 1).to_list(1000)
    for c in clients:
        last = await db.bookings.find_one({"tenant_id": p["tenant_id"], "client_phone": c["phone"]},
                                          {"_id": 0}, sort=[("date", -1)])
        c["last_visit"] = last["date"] if last else None
    return clients

@api.get("/clients/{phone}/history")
async def client_history(phone: str, p=Depends(get_principal)):
    return await db.bookings.find({"tenant_id": p["tenant_id"], "client_phone": phone}, {"_id": 0}).sort("date", -1).to_list(500)

@api.get("/blocks")
async def list_blocks(p=Depends(get_principal)):
    return await db.blocks.find({"tenant_id": p["tenant_id"]}, {"_id": 0}).sort("date", 1).to_list(500)

@api.post("/blocks")
async def create_block(body: BlockIn, p=Depends(get_principal)):
    doc = {"id": str(uuid.uuid4()), "tenant_id": p["tenant_id"], **body.model_dump()}
    await db.blocks.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.delete("/blocks/{block_id}")
async def delete_block(block_id: str, p=Depends(get_principal)):
    await db.blocks.delete_one({"id": block_id, "tenant_id": p["tenant_id"]})
    return {"ok": True}

@api.get("/stats")
async def stats(p=Depends(get_principal)):
    tenant = await get_tenant_by_id(p["tenant_id"])
    now = local_now(tenant)
    today = now.date()
    start_week = (today - timedelta(days=today.weekday())).isoformat()
    end_week = (today + timedelta(days=6 - today.weekday())).isoformat()
    start_month = today.replace(day=1).isoformat()
    tid = p["tenant_id"]
    today_count = await db.bookings.count_documents({"tenant_id": tid, "date": today.isoformat(), "status": {"$ne": "cancelled"}})
    week_count = await db.bookings.count_documents({"tenant_id": tid, "date": {"$gte": start_week, "$lte": end_week}, "status": {"$ne": "cancelled"}})
    month = await db.bookings.find({"tenant_id": tid, "date": {"$gte": start_month},
                                    "status": {"$in": ["confirmed", "completed"]}}, {"_id": 0}).to_list(1000)
    deposits = await db.bookings.find({"tenant_id": tid, "deposit_status": "paid", "date": {"$gte": start_month}},
                                      {"_id": 0, "deposit_amount": 1}).to_list(1000)
    return {
        "today": today_count, "week": week_count,
        "month_revenue": sum(b.get("service_price", 0) for b in month),
        "deposits_month": round(sum(d.get("deposit_amount", 0) for d in deposits), 2),
        "clients": await db.clients.count_documents({"tenant_id": tid}),
    }

@api.get("/settings")
async def get_settings(p=Depends(get_principal)):
    return public_tenant(await get_tenant_by_id(p["tenant_id"]))

@api.put("/settings")
async def update_settings(body: SettingsIn, p=Depends(get_principal)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    if "deposit_percent" in data and not (0 < data["deposit_percent"] <= 100):
        raise HTTPException(400, "Percentual do sinal deve estar entre 1 e 100")
    if "open_hour" in data or "close_hour" in data:
        t = await get_tenant_by_id(p["tenant_id"])
        oh = data.get("open_hour", t["open_hour"]); ch = data.get("close_hour", t["close_hour"])
        if not (0 <= oh < ch <= 24):
            raise HTTPException(400, "Horário de funcionamento inválido")
    if data:
        await db.tenants.update_one({"id": p["tenant_id"]}, {"$set": data})
    return public_tenant(await get_tenant_by_id(p["tenant_id"]))

@api.get("/messages")
async def list_messages(limit: int = 50, p=Depends(get_principal)):
    return await db.messages.find({"tenant_id": p["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 200))

@api.get("/whatsapp/status")
async def whatsapp_status(p=Depends(get_principal)):
    return {"mode": wa.mode(), "configured": wa.configured()}

@api.get("/reminders")
async def reminders(p=Depends(get_principal)):
    tenant = await get_tenant_by_id(p["tenant_id"])
    tomorrow = (local_now(tenant).date() + timedelta(days=1)).isoformat()
    items = await db.bookings.find({"tenant_id": tenant["id"], "date": tomorrow,
                                    "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}).sort("time", 1).to_list(200)
    for it in items:
        msg = wa.reminder_text(tenant, it)
        it["preview"] = msg
        it["whatsapp_link"] = wa.wa_link(it["client_phone"], msg)
        sent = await db.messages.find_one({"idempotency_key": f"reminder:{it['id']}"}, {"_id": 0, "status": 1, "created_at": 1})
        it["reminder_status"] = sent["status"] if sent else None
    return {"date": tomorrow, "items": items, "mode": wa.mode()}

@api.post("/reminders/run")
async def run_reminders_now(p=Depends(get_principal)):
    tenant = await get_tenant_by_id(p["tenant_id"])
    return await send_reminders_for_tenant(tenant)

# ---------------- Superadmin: tenants ----------------
SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,40}[a-z0-9])?$")

@api.get("/admin/tenants", dependencies=[Depends(require_superadmin)])
async def list_tenants():
    tenants = await db.tenants.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    out = []
    for t in tenants:
        t = with_defaults(t)
        owner = await db.users.find_one({"tenant_id": t["id"], "role": {"$in": ["owner", "superadmin"]}}, {"_id": 0, "email": 1, "name": 1})
        out.append({**public_tenant(t), "owner": owner,
                    "bookings_count": await db.bookings.count_documents({"tenant_id": t["id"]}),
                    "services_count": await db.services.count_documents({"tenant_id": t["id"]})})
    return out

@api.post("/admin/tenants", dependencies=[Depends(require_superadmin)])
async def create_tenant(body: TenantIn):
    slug = body.slug.lower().strip()
    if not SLUG_RE.match(slug) or slug == "default":
        raise HTTPException(400, "Slug inválido (use letras minúsculas, números e hífens)")
    if await db.tenants.find_one({"slug": slug}):
        raise HTTPException(409, "Slug já em uso")
    email = body.owner_email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "E-mail já cadastrado")
    if len(body.owner_password) < 6:
        raise HTTPException(400, "Senha deve ter ao menos 6 caracteres")
    tenant = {"id": str(uuid.uuid4()), "slug": slug, "name": body.name.strip(), "category": body.category,
              "tagline": body.category, "whatsapp": wa.normalize_phone(body.whatsapp) or "5511999999999",
              "created_at": datetime.now(timezone.utc).isoformat()}
    await db.tenants.insert_one(tenant)
    await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "name": body.owner_name.strip(),
                               "password_hash": hash_password(body.owner_password), "role": "owner",
                               "tenant_id": tenant["id"], "created_at": datetime.now(timezone.utc).isoformat()})
    tenant.pop("_id", None)
    return public_tenant(with_defaults(tenant))

@api.delete("/admin/tenants/{tenant_id}", dependencies=[Depends(require_superadmin)])
async def delete_tenant(tenant_id: str):
    t = await db.tenants.find_one({"id": tenant_id})
    if not t:
        raise HTTPException(404, "Salão não encontrado")
    if t["slug"] == DEFAULT_SLUG:
        raise HTTPException(400, "O salão padrão não pode ser removido")
    for coll in (db.services, db.bookings, db.clients, db.blocks, db.messages):
        await coll.delete_many({"tenant_id": tenant_id})
    await db.users.delete_many({"tenant_id": tenant_id, "role": "owner"})
    await db.tenants.delete_one({"id": tenant_id})
    return {"ok": True}

# ---------------- Cron ----------------
@api.post("/cron/reminders")
async def cron_reminders(request: Request, background: BackgroundTasks):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token or not hmac.compare_digest(token, os.environ["WEBHOOK_CRON_SECRET"]):
        raise HTTPException(401, "Unauthorized")
    try:
        envelope = await request.json()
    except Exception:
        envelope = {}
    run_id = request.headers.get("X-Webhook-Id") or (envelope or {}).get("run_id") or str(uuid.uuid4())
    if await db.cron_runs.find_one({"run_id": run_id}):
        return {"ok": True, "duplicate": True}
    await db.cron_runs.insert_one({"run_id": run_id, "job": "reminders",
                                   "started_at": datetime.now(timezone.utc).isoformat()})
    background.add_task(run_all_reminders, run_id)
    return {"ok": True, "run_id": run_id}

@api.get("/cron/runs")
async def cron_runs(p=Depends(get_principal)):
    return await db.cron_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(20)

app.include_router(api)
app.include_router(payments_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Seed & migration ----------------
DEFAULT_SERVICES = [
    {"name": "Alongamento em Gel", "description": "Alongamento em fibra + acabamento em gel duradouro.",
     "price": 180.0, "duration_min": 120,
     "image_url": "https://images.unsplash.com/photo-1610992015836-7c249d75782d?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NjZ8MHwxfHNlYXJjaHw0fHxnZWwlMjBuYWlscyUyMG1hbmljdXJlJTIwc2Fsb24lMjBsdXh1cnl8ZW58MHx8fHwxNzkwMjg4MDI0fDA&ixlib=rb-4.1.0&q=85"},
    {"name": "Banho de Gel", "description": "Fortalecimento e brilho intenso na unha natural.",
     "price": 120.0, "duration_min": 90,
     "image_url": "https://images.pexels.com/photos/3997384/pexels-photo-3997384.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"},
    {"name": "Manicure Express", "description": "Cutilagem completa + esmaltação tradicional.",
     "price": 55.0, "duration_min": 45,
     "image_url": "https://images.unsplash.com/photo-1632345031435-8727f6897d53?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NjZ8MHwxfHNlYXJjaHwxfHxnZWwlMjBuYWlscyUyMG1hbmljdXJlJTIwc2Fsb24lMjBsdXh1cnl8ZW58MHx8fHwxNzkwMjg4MDI0fDA&ixlib=rb-4.1.0&q=85"},
    {"name": "Nail Art Luxo", "description": "Design personalizado com pedrarias e acabamento premium.",
     "price": 220.0, "duration_min": 150,
     "image_url": "https://images.unsplash.com/photo-1772322586785-3a34772cbc61?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODd8MHwxfHNlYXJjaHwxfHxuYWlsJTIwYXJ0JTIwYmVhdXR5JTIwc2Fsb24lMjBlbGVnYW50fGVufDB8fHx8MTc5MDI4ODAyNHww&ixlib=rb-4.1.0&q=85"},
    {"name": "Retirada de Gel", "description": "Remoção segura e hidratação profunda das unhas.",
     "price": 60.0, "duration_min": 45,
     "image_url": "https://images.pexels.com/photos/3997381/pexels-photo-3997381.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"},
]

DEFAULT_GALLERY = [
    "https://images.unsplash.com/photo-1610992015762-45dca7fa3a85?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NjZ8MHwxfHNlYXJjaHwyfHxnZWwlMjBuYWlscyUyMG1hbmljdXJlJTIwc2Fsb24lMjBsdXh1cnl8ZW58MHx8fHwxNzkwMjg4MDI0fDA&ixlib=rb-4.1.0&q=85",
    "https://images.pexels.com/photos/38784151/pexels-photo-38784151.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "https://images.pexels.com/photos/3997381/pexels-photo-3997381.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
    "https://images.pexels.com/photos/34885842/pexels-photo-34885842.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
]

BARBER_SERVICES = [
    {"name": "Corte Clássico", "description": "Corte na tesoura e máquina com acabamento na navalha.", "price": 55.0, "duration_min": 45,
     "image_url": "https://images.unsplash.com/photo-1503951914875-452162b0f3f1?auto=format&fit=crop&q=80&w=900"},
    {"name": "Barba Completa", "description": "Toalha quente, navalha e hidratação.", "price": 45.0, "duration_min": 30,
     "image_url": "https://images.unsplash.com/photo-1621605815971-fbc98d665033?auto=format&fit=crop&q=80&w=900"},
    {"name": "Corte + Barba", "description": "Combo completo com finalização premium.", "price": 90.0, "duration_min": 75,
     "image_url": "https://images.unsplash.com/photo-1599351431202-1e0f0137899a?auto=format&fit=crop&q=80&w=900"},
]

async def seed_tenants() -> dict:
    default = await db.tenants.find_one({"slug": DEFAULT_SLUG}, {"_id": 0})
    if not default:
        default = {
            "id": str(uuid.uuid4()), "slug": DEFAULT_SLUG,
            "name": os.environ.get("SALON_NAME", "Studio Gel & Beauty"), "category": "Manicure em gel",
            "tagline": "Estúdio de manicure em gel",
            "hero_title": "Unhas que brilham, autoestima que encanta.",
            "hero_subtitle": "Um cuidado premium para suas mãos, com finalização em gel de longa duração. Agende em 3 passos, direto do seu celular.",
            "gallery": DEFAULT_GALLERY, "address": "Rua das Flores, 123 · São Paulo · SP",
            "instagram": "@studiogelbeauty", "phone_display": "(11) 99999-9999",
            "whatsapp": os.environ.get("SALON_WHATSAPP", "5511999999999"),
            "deposit_enabled": True, "deposit_percent": 30,
            "testimonial": "Nunca tinha visto minhas unhas tão bonitas. O acabamento em gel dura semanas e o atendimento é impecável.",
            "testimonial_author": "Marina S.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.tenants.insert_one(default)
        default.pop("_id", None)
        logger.info("Default tenant created")

    barber = await db.tenants.find_one({"slug": "barbearia-vintage"})
    if not barber:
        bid = str(uuid.uuid4())
        await db.tenants.insert_one({
            "id": bid, "slug": "barbearia-vintage", "name": "Barbearia Vintage", "category": "Barbearia",
            "tagline": "Barbearia clássica", "hero_title": "Estilo clássico, atitude moderna.",
            "hero_subtitle": "Corte, barba e boa conversa. Agende seu horário em segundos.",
            "hero_image": "https://images.unsplash.com/photo-1585747860715-2ba37e788b70?auto=format&fit=crop&q=80&w=1200",
            "gallery": [s["image_url"] for s in BARBER_SERVICES],
            "address": "Av. Paulista, 1000 · São Paulo · SP", "instagram": "@barbeariavintage",
            "phone_display": "(11) 98888-7777", "whatsapp": "5511988887777",
            "open_hour": 10, "close_hour": 20, "deposit_enabled": False, "deposit_percent": 20,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        for s in BARBER_SERVICES:
            await db.services.insert_one({"id": str(uuid.uuid4()), "tenant_id": bid, "active": True, **s})
        if not await db.users.find_one({"email": "barbearia@demo.com"}):
            await db.users.insert_one({"id": str(uuid.uuid4()), "email": "barbearia@demo.com", "name": "Carlos Barber",
                                       "password_hash": hash_password("Barber@2026"), "role": "owner", "tenant_id": bid,
                                       "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Demo tenant barbearia-vintage created")
    return default

async def seed_admin(default_tenant: dict):
    email = os.environ["ADMIN_EMAIL"].lower().strip()
    pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "name": os.environ.get("ADMIN_NAME", "Admin"),
                                   "password_hash": hash_password(pw), "role": "superadmin",
                                   "tenant_id": default_tenant["id"],
                                   "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Admin seed created: {email}")
    else:
        upd = {"role": "superadmin", "tenant_id": existing.get("tenant_id") or default_tenant["id"]}
        if not verify_password(pw, existing["password_hash"]):
            upd["password_hash"] = hash_password(pw)
        await db.users.update_one({"email": email}, {"$set": upd})

async def migrate_tenant_ids(default_tenant: dict):
    for coll in (db.services, db.bookings, db.clients, db.blocks):
        r = await coll.update_many({"tenant_id": {"$exists": False}}, {"$set": {"tenant_id": default_tenant["id"]}})
        if r.modified_count:
            logger.info(f"Migrated {r.modified_count} docs in {coll.name}")
    await db.bookings.update_many({"deposit_status": {"$exists": False}}, {"$set": {"deposit_status": "none", "deposit_amount": 0}})

async def seed_services(default_tenant: dict):
    if await db.services.count_documents({"tenant_id": default_tenant["id"]}) == 0:
        for s in DEFAULT_SERVICES:
            await db.services.insert_one({"id": str(uuid.uuid4()), "tenant_id": default_tenant["id"], "active": True, **s})
        logger.info("Default services seeded")

async def seed_demo_bookings(default_tenant: dict):
    tid = default_tenant["id"]
    if await db.bookings.count_documents({"tenant_id": tid}) > 0:
        return
    svcs = await db.services.find({"tenant_id": tid}, {"_id": 0}).to_list(20)
    if not svcs:
        return
    today = local_now(with_defaults(default_tenant)).date()
    demo = [
        (today, "10:00", "Marina Souza", "+5511988887777", "confirmed", svcs[0]),
        (today, "14:30", "Beatriz Lima", "+5511977776666", "pending", svcs[2]),
        (today + timedelta(days=1), "11:00", "Camila Ferreira", "+5511966665555", "confirmed", svcs[1]),
        (today + timedelta(days=1), "15:00", "Ana Paula", "+5511955554444", "pending", svcs[3]),
        (today + timedelta(days=2), "09:30", "Julia Costa", "+5511944443333", "confirmed", svcs[4]),
    ]
    for d, t, name, phone, status, svc in demo:
        await db.bookings.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tid, "service_id": svc["id"], "service_name": svc["name"],
            "service_price": svc["price"], "service_duration": svc["duration_min"], "date": d.isoformat(), "time": t,
            "client_name": name, "client_phone": phone, "client_email": "", "notes": "", "status": status,
            "deposit_status": "none", "deposit_amount": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await upsert_client(tid, name, phone, "")
    logger.info("Demo bookings seeded")

@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.tenants.create_index("slug", unique=True)
    await db.services.create_index("id", unique=True)
    await db.bookings.create_index([("tenant_id", 1), ("date", 1), ("time", 1)])
    await db.messages.create_index("idempotency_key")
    await db.payment_transactions.create_index("session_id", unique=True)
    try:
        await db.clients.drop_index("phone_1")
    except Exception:
        pass
    default = await seed_tenants()
    await migrate_tenant_ids(default)
    await db.clients.create_index([("tenant_id", 1), ("phone", 1)], unique=True)
    await seed_admin(default)
    await seed_services(default)
    await seed_demo_bookings(default)

@app.on_event("shutdown")
async def on_shutdown():
    client.close()
