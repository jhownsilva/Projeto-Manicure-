import os

from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

DEFAULT_SLUG = os.environ.get("DEFAULT_TENANT_SLUG", "gel-beauty")

TENANT_DEFAULTS = {
    "name": "Meu Salão",
    "category": "Beleza",
    "tagline": "Estúdio de beleza",
    "hero_title": "Cuidado premium, do seu jeito.",
    "hero_subtitle": "Agende em 3 passos, direto do seu celular.",
    "hero_image": "https://images.unsplash.com/photo-1610992015762-45dca7fa3a85?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200",
    "gallery": [],
    "address": "",
    "instagram": "",
    "phone_display": "",
    "whatsapp": "5511999999999",
    "timezone": "America/Sao_Paulo",
    "open_hour": 9,
    "close_hour": 19,
    "slot_minutes": 30,
    "deposit_enabled": False,
    "deposit_percent": 30,
    "testimonial": "",
    "testimonial_author": "",
}

PUBLIC_FIELDS = ["id", "slug", *TENANT_DEFAULTS.keys()]


def with_defaults(t: dict) -> dict:
    return {**TENANT_DEFAULTS, **{k: v for k, v in t.items() if v is not None}}


async def get_tenant_by_slug(slug: str) -> dict:
    if slug == "default":
        slug = DEFAULT_SLUG
    t = await db.tenants.find_one({"slug": slug}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Salão não encontrado")
    return with_defaults(t)


async def get_tenant_by_id(tenant_id: str) -> dict:
    t = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Salão não encontrado")
    return with_defaults(t)
