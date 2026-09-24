from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta, time as dtime
from typing import Optional

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr

# ---------------- MongoDB ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ---------------- App ----------------
app = FastAPI(title="Studio Gel & Beauty API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Auth utils ----------------
JWT_ALGORITHM = "HS256"

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# ---------------- Models ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ServiceIn(BaseModel):
    name: str
    description: Optional[str] = ""
    price: float
    duration_min: int
    image_url: Optional[str] = ""
    active: bool = True

class Service(ServiceIn):
    id: str

class BookingIn(BaseModel):
    service_id: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    client_name: str
    client_phone: str
    client_email: Optional[str] = ""
    notes: Optional[str] = ""

class BookingStatusIn(BaseModel):
    status: str  # pending | confirmed | cancelled | completed

class BlockIn(BaseModel):
    date: str  # YYYY-MM-DD
    time: Optional[str] = None  # if None, blocks whole day
    reason: Optional[str] = ""

# ---------------- Config ----------------
OPEN_HOUR = 9
CLOSE_HOUR = 19
SLOT_MINUTES = 30

def get_salon_info():
    return {
        "name": os.environ.get("SALON_NAME", "Studio Gel & Beauty"),
        "whatsapp": os.environ.get("SALON_WHATSAPP", "5511999999999"),
        "open_hour": OPEN_HOUR,
        "close_hour": CLOSE_HOUR,
        "slot_minutes": SLOT_MINUTES,
    }

# ---------------- Auth endpoints ----------------
@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = create_access_token(user["id"], user["email"])
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}}

@api.post("/auth/logout")
async def logout(response: Response, user=Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

# ---------------- Public endpoints ----------------
@api.get("/salon")
async def salon_info():
    return get_salon_info()

@api.get("/services")
async def list_services(all: bool = False):
    q = {} if all else {"active": True}
    items = await db.services.find(q, {"_id": 0}).sort("price", 1).to_list(200)
    return items

@api.get("/services/{service_id}/slots")
async def available_slots(service_id: str, date_str: str = None, date: str = None):
    day = date_str or date
    svc = await db.services.find_one({"id": service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Serviço não encontrado")
    if not day:
        raise HTTPException(400, "Data obrigatória")
    try:
        d = datetime.strptime(day, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(400, "Data inválida")

    # existing bookings for the date (not cancelled)
    bookings = await db.bookings.find(
        {"date": day, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}
    ).to_list(500)
    blocks = await db.blocks.find({"date": day}, {"_id": 0}).to_list(200)

    full_day_blocked = any(b.get("time") in (None, "") for b in blocks)
    if full_day_blocked:
        return {"date": day, "slots": []}

    booked_times = set()
    for b in bookings:
        # mark starting slot as booked (simple demo model)
        booked_times.add(b["time"])
    blocked_times = {b["time"] for b in blocks if b.get("time")}

    slots = []
    cur = datetime.combine(d, dtime(OPEN_HOUR, 0))
    end = datetime.combine(d, dtime(CLOSE_HOUR, 0))
    while cur + timedelta(minutes=svc["duration_min"]) <= end:
        hhmm = cur.strftime("%H:%M")
        available = hhmm not in booked_times and hhmm not in blocked_times
        # also mark past times as unavailable for today
        if d == datetime.now().date() and cur <= datetime.now():
            available = False
        slots.append({"time": hhmm, "available": available})
        cur += timedelta(minutes=SLOT_MINUTES)
    return {"date": day, "slots": slots}

@api.post("/bookings")
async def create_booking(body: BookingIn):
    svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Serviço não encontrado")
    # check conflict
    existing = await db.bookings.find_one({
        "date": body.date, "time": body.time,
        "status": {"$in": ["pending", "confirmed"]},
    })
    if existing:
        raise HTTPException(409, "Horário já reservado")
    block = await db.blocks.find_one({"date": body.date, "time": {"$in": [None, "", body.time]}})
    if block:
        raise HTTPException(409, "Horário bloqueado pelo salão")

    booking_id = str(uuid.uuid4())
    doc = {
        "id": booking_id,
        "service_id": body.service_id,
        "service_name": svc["name"],
        "service_price": svc["price"],
        "service_duration": svc["duration_min"],
        "date": body.date,
        "time": body.time,
        "client_name": body.client_name.strip(),
        "client_phone": body.client_phone.strip(),
        "client_email": (body.client_email or "").strip().lower(),
        "notes": body.notes or "",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one(doc)

    # upsert client
    await db.clients.update_one(
        {"phone": doc["client_phone"]},
        {"$set": {"name": doc["client_name"], "email": doc["client_email"]},
         "$setOnInsert": {"id": str(uuid.uuid4()), "phone": doc["client_phone"],
                          "created_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"bookings_count": 1}},
        upsert=True,
    )
    doc.pop("_id", None)
    salon = get_salon_info()
    msg = (f"Olá! Gostaria de confirmar meu agendamento de {svc['name']} "
           f"no dia {body.date} às {body.time} para {body.client_name}.")
    from urllib.parse import quote
    wa_link = f"https://wa.me/{salon['whatsapp']}?text={quote(msg)}"
    return {"booking": doc, "whatsapp_link": wa_link}

# ---------------- Admin endpoints ----------------
@api.post("/services", dependencies=[Depends(get_current_user)])
async def create_service(body: ServiceIn):
    sid = str(uuid.uuid4())
    doc = {"id": sid, **body.model_dump()}
    await db.services.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.put("/services/{service_id}", dependencies=[Depends(get_current_user)])
async def update_service(service_id: str, body: ServiceIn):
    res = await db.services.update_one({"id": service_id}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Serviço não encontrado")
    doc = await db.services.find_one({"id": service_id}, {"_id": 0})
    return doc

@api.delete("/services/{service_id}", dependencies=[Depends(get_current_user)])
async def delete_service(service_id: str):
    await db.services.delete_one({"id": service_id})
    return {"ok": True}

@api.get("/bookings", dependencies=[Depends(get_current_user)])
async def list_bookings(from_date: Optional[str] = None, to_date: Optional[str] = None,
                        status: Optional[str] = None):
    q: dict = {}
    if from_date and to_date:
        q["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        q["date"] = {"$gte": from_date}
    if status:
        q["status"] = status
    items = await db.bookings.find(q, {"_id": 0}).sort([("date", 1), ("time", 1)]).to_list(1000)
    return items

@api.put("/bookings/{booking_id}/status", dependencies=[Depends(get_current_user)])
async def update_booking_status(booking_id: str, body: BookingStatusIn):
    if body.status not in {"pending", "confirmed", "cancelled", "completed"}:
        raise HTTPException(400, "Status inválido")
    res = await db.bookings.update_one({"id": booking_id}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(404, "Agendamento não encontrado")
    doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    return doc

@api.get("/clients", dependencies=[Depends(get_current_user)])
async def list_clients():
    clients = await db.clients.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    # attach history counts and last visit
    for c in clients:
        last = await db.bookings.find_one(
            {"client_phone": c["phone"]}, {"_id": 0}, sort=[("date", -1)]
        )
        c["last_visit"] = last["date"] if last else None
    return clients

@api.get("/clients/{phone}/history", dependencies=[Depends(get_current_user)])
async def client_history(phone: str):
    items = await db.bookings.find({"client_phone": phone}, {"_id": 0}).sort("date", -1).to_list(500)
    return items

@api.get("/blocks", dependencies=[Depends(get_current_user)])
async def list_blocks():
    items = await db.blocks.find({}, {"_id": 0}).sort("date", 1).to_list(500)
    return items

@api.post("/blocks", dependencies=[Depends(get_current_user)])
async def create_block(body: BlockIn):
    doc = {"id": str(uuid.uuid4()), **body.model_dump()}
    await db.blocks.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.delete("/blocks/{block_id}", dependencies=[Depends(get_current_user)])
async def delete_block(block_id: str):
    await db.blocks.delete_one({"id": block_id})
    return {"ok": True}

@api.get("/stats", dependencies=[Depends(get_current_user)])
async def stats():
    today = datetime.now().date().isoformat()
    start_week = (datetime.now().date() - timedelta(days=datetime.now().weekday())).isoformat()
    end_week = (datetime.now().date() + timedelta(days=6 - datetime.now().weekday())).isoformat()
    start_month = datetime.now().date().replace(day=1).isoformat()

    today_count = await db.bookings.count_documents({"date": today, "status": {"$ne": "cancelled"}})
    week_count = await db.bookings.count_documents({"date": {"$gte": start_week, "$lte": end_week}, "status": {"$ne": "cancelled"}})
    month_bookings = await db.bookings.find(
        {"date": {"$gte": start_month}, "status": {"$in": ["confirmed", "completed"]}}, {"_id": 0}
    ).to_list(1000)
    revenue = sum(b.get("service_price", 0) for b in month_bookings)
    clients_count = await db.clients.count_documents({})
    return {
        "today": today_count,
        "week": week_count,
        "month_revenue": revenue,
        "clients": clients_count,
    }

@api.get("/reminders", dependencies=[Depends(get_current_user)])
async def reminders():
    """Simulated reminders queue: bookings for tomorrow, pending confirmation."""
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    items = await db.bookings.find(
        {"date": tomorrow, "status": {"$in": ["pending", "confirmed"]}}, {"_id": 0}
    ).sort("time", 1).to_list(200)
    salon = get_salon_info()
    from urllib.parse import quote
    for it in items:
        msg = (f"Oi {it['client_name'].split()[0]}! Passando pra lembrar do seu horário "
               f"de {it['service_name']} amanhã ({it['date']}) às {it['time']} no {salon['name']}. "
               f"Confirma pra mim? 💅")
        it["whatsapp_link"] = f"https://wa.me/55{it['client_phone'].replace(chr(43),'').replace(' ','').replace('-','').replace('(','').replace(')','')}?text={quote(msg)}"
        it["preview"] = msg
    return {"date": tomorrow, "items": items}

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Seed ----------------
async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower().strip()
    name = os.environ.get("ADMIN_NAME", "Admin")
    pw = os.environ["ADMIN_PASSWORD"]
    existing = await db.users.find_one({"email": email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": email, "name": name,
            "password_hash": hash_password(pw), "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Admin seed created: {email}")
    elif not verify_password(pw, existing["password_hash"]):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pw)}})
        logger.info(f"Admin password updated for {email}")

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

async def seed_services():
    count = await db.services.count_documents({})
    if count == 0:
        for s in DEFAULT_SERVICES:
            await db.services.insert_one({"id": str(uuid.uuid4()), "active": True, **s})
        logger.info("Default services seeded")

async def seed_demo_bookings():
    count = await db.bookings.count_documents({})
    if count > 0:
        return
    svcs = await db.services.find({}, {"_id": 0}).to_list(20)
    if not svcs:
        return
    today = datetime.now().date()
    demo = [
        (today, "10:00", "Marina Souza", "+5511988887777", "confirmed", svcs[0]),
        (today, "14:30", "Beatriz Lima", "+5511977776666", "pending", svcs[2]),
        (today + timedelta(days=1), "11:00", "Camila Ferreira", "+5511966665555", "confirmed", svcs[1]),
        (today + timedelta(days=1), "15:00", "Ana Paula", "+5511955554444", "pending", svcs[3]),
        (today + timedelta(days=2), "09:30", "Julia Costa", "+5511944443333", "confirmed", svcs[4]),
    ]
    for d, t, name, phone, status, svc in demo:
        doc = {
            "id": str(uuid.uuid4()),
            "service_id": svc["id"], "service_name": svc["name"],
            "service_price": svc["price"], "service_duration": svc["duration_min"],
            "date": d.isoformat(), "time": t,
            "client_name": name, "client_phone": phone, "client_email": "",
            "notes": "", "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.bookings.insert_one(doc)
        await db.clients.update_one(
            {"phone": phone},
            {"$set": {"name": name, "email": ""},
             "$setOnInsert": {"id": str(uuid.uuid4()), "phone": phone,
                              "created_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"bookings_count": 1}},
            upsert=True,
        )
    logger.info("Demo bookings seeded")

@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.services.create_index("id", unique=True)
    await db.bookings.create_index([("date", 1), ("time", 1)])
    await db.clients.create_index("phone", unique=True)
    await seed_admin()
    await seed_services()
    await seed_demo_bookings()

@app.on_event("shutdown")
async def on_shutdown():
    client.close()
