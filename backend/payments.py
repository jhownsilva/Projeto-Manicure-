import logging
import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

import whatsapp as wa
from db import db, get_tenant_by_id, get_tenant_by_slug

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/api")


def deposit_amount(tenant: dict, price: float) -> float:
    return round(price * float(tenant.get("deposit_percent") or 0) / 100, 2)


class CheckoutIn(BaseModel):
    origin_url: str


@router.post("/public/{slug}/bookings/{booking_id}/deposit")
async def create_deposit_checkout(slug: str, booking_id: str, body: CheckoutIn):
    tenant = await get_tenant_by_slug(slug)
    booking = await db.bookings.find_one({"id": booking_id, "tenant_id": tenant["id"]}, {"_id": 0})
    if not booking:
        raise HTTPException(404, "Agendamento não encontrado")
    if not tenant.get("deposit_enabled"):
        raise HTTPException(400, "Sinal não habilitado para este salão")
    if booking.get("deposit_status") == "paid":
        raise HTTPException(400, "Sinal já pago")
    amount = deposit_amount(tenant, booking["service_price"])
    if amount < 1:
        raise HTTPException(400, "Valor do sinal inválido")
    origin = body.origin_url.rstrip("/")
    base = f"{origin}/s/{tenant['slug']}"
    kwargs = dict(
        mode="payment",
        line_items=[{
            "quantity": 1,
            "price_data": {
                "currency": "brl",
                "unit_amount": int(round(amount * 100)),
                "product_data": {
                    "name": f"Sinal · {booking['service_name']}",
                    "description": f"{tenant['name']} · {wa.fmt_date(booking['date'])} às {booking['time']}",
                },
            },
        }],
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/agendar?cancelled=1",
        metadata={"booking_id": booking_id, "tenant_id": tenant["id"], "kind": "deposit"},
    )
    try:
        session = stripe.checkout.Session.create(**kwargs)
    except stripe.error.StripeError as e:
        raise HTTPException(502, f"Erro ao iniciar pagamento: {getattr(e, 'user_message', None) or str(e)}")

    now = datetime.now(timezone.utc)
    await db.payment_transactions.insert_one({
        "session_id": session.id, "booking_id": booking_id, "tenant_id": tenant["id"],
        "amount": amount, "currency": "brl", "status": "initiated", "payment_status": "pending",
        "created_at": now, "updated_at": now,
    })
    await db.bookings.update_one({"id": booking_id}, {"$set": {"deposit_status": "pending", "deposit_amount": amount,
                                                                "deposit_session_id": session.id}})
    return {"checkout_url": session.url, "session_id": session.id, "amount": amount}


async def mark_paid(session_id: str, payment_intent: str | None = None) -> dict | None:
    res = await db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "stripe_payment_intent_id": payment_intent,
                  "updated_at": datetime.now(timezone.utc)}},
        projection={"_id": 0},
    )
    if not res:
        return None
    await db.bookings.update_one({"id": res["booking_id"]},
                                 {"$set": {"deposit_status": "paid", "deposit_paid_at": datetime.now(timezone.utc).isoformat(),
                                           "status": "confirmed"}})
    booking = await db.bookings.find_one({"id": res["booking_id"]}, {"_id": 0})
    tenant = await get_tenant_by_id(res["tenant_id"])
    await wa.send_message(tenant["id"], booking["client_phone"], wa.confirmed_text(tenant, booking),
                          "confirmed", booking["id"])
    return res


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, background: BackgroundTasks):
    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Transação não encontrada")
    if record.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await mark_paid(session_id, s.payment_intent)
                record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            elif s.status == "expired":
                await db.payment_transactions.update_one({"session_id": session_id},
                                                         {"$set": {"status": "expired", "payment_status": "expired"}})
                record["status"] = record["payment_status"] = "expired"
        except stripe.error.StripeError:
            pass
    booking = await db.bookings.find_one({"id": record["booking_id"]}, {"_id": 0})
    tenant = await get_tenant_by_id(record["tenant_id"])
    return {"session_id": session_id, "status": record["status"], "payment_status": record["payment_status"],
            "amount": record["amount"], "booking": booking, "tenant_slug": tenant["slug"], "tenant_name": tenant["name"]}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):
        raise HTTPException(400, "Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    now = datetime.now(timezone.utc)
    if t in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if obj.get("payment_status", "paid") == "paid":
            await mark_paid(obj["id"], obj.get("payment_intent"))
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"status": "failed", "payment_status": "failed", "updated_at": now}})
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"status": "expired", "payment_status": "expired", "updated_at": now}})
    elif t == "charge.refunded":
        await db.payment_transactions.update_one({"stripe_payment_intent_id": obj.get("payment_intent")},
            {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": now}})
    return {"status": "ok"}
