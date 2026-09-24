import logging
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from db import db

logger = logging.getLogger(__name__)


def configured() -> bool:
    return bool(os.environ.get("WHATSAPP_ACCESS_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))


def mode() -> str:
    return "cloud" if configured() else "mock"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits and not digits.startswith("55") and len(digits) <= 11:
        digits = "55" + digits
    return digits


def wa_link(phone: str, text: str) -> str:
    return f"https://wa.me/{normalize_phone(phone)}?text={quote(text)}"


def fmt_date(d: str) -> str:
    return "/".join(reversed(d.split("-")))


def confirmation_text(tenant: dict, b: dict, deposit_amount: float | None = None) -> str:
    first = b["client_name"].split()[0]
    msg = (f"Olá {first}! Recebemos seu agendamento de {b['service_name']} "
           f"no dia {fmt_date(b['date'])} às {b['time']} no {tenant['name']}. ")
    if deposit_amount:
        msg += f"Você pode garantir seu horário pagando um sinal de R$ {deposit_amount:.2f}. ".replace(".", ",")
    return msg + "Responda SIM para confirmar. 💅"


def confirmed_text(tenant: dict, b: dict) -> str:
    first = b["client_name"].split()[0]
    return (f"{first}, seu horário de {b['service_name']} em {fmt_date(b['date'])} às {b['time']} "
            f"está confirmado no {tenant['name']}! Até lá ✨")


def reminder_text(tenant: dict, b: dict) -> str:
    first = b["client_name"].split()[0]
    return (f"Oi {first}! Passando pra lembrar do seu horário de {b['service_name']} amanhã "
            f"({fmt_date(b['date'])}) às {b['time']} no {tenant['name']}. Confirma pra mim? 💅")


async def _post_meta(to: str, body: str) -> dict:
    version = os.environ.get("WHATSAPP_API_VERSION", "v22.0")
    url = f"https://graph.facebook.com/{version}/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages"
    template = os.environ.get("WHATSAPP_TEMPLATE_NAME")
    if template:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                   "template": {"name": template,
                                "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANG", "pt_BR")},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": body}]}]}}
    else:
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                   "type": "text", "text": {"preview_url": False, "body": body}}
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(url, json=payload,
                         headers={"Authorization": f"Bearer {os.environ['WHATSAPP_ACCESS_TOKEN']}"})
    if r.is_error:
        try:
            err = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            err = r.text
        raise RuntimeError(err)
    return r.json()


async def send_message(tenant_id: str, to: str, body: str, kind: str, ref_id: str) -> dict:
    key = f"{kind}:{ref_id}"
    existing = await db.messages.find_one({"idempotency_key": key, "status": {"$in": ["sent", "mock"]}}, {"_id": 0})
    if existing:
        return existing
    doc = {
        "id": str(uuid.uuid4()), "tenant_id": tenant_id, "to": normalize_phone(to), "body": body,
        "kind": kind, "ref_id": ref_id, "idempotency_key": key, "mode": mode(),
        "status": "mock", "message_id": None, "error": None,
        "wa_link": wa_link(to, body),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if configured():
        try:
            res = await _post_meta(doc["to"], body)
            doc["status"] = "sent"
            doc["message_id"] = res.get("messages", [{}])[0].get("id")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"WhatsApp send failed: {e}")
            doc["status"] = "failed"
            doc["error"] = str(e)[:300]
    await db.messages.insert_one(doc)
    doc.pop("_id", None)
    return doc
