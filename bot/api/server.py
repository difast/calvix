import csv
import io
import json
import os
import logging
import hashlib
import hmac
import base64
import time
import secrets
from datetime import datetime
from aiohttp import web
from sqlalchemy import select, update, delete, func, text
from bot.models.database import AsyncSessionLocal
from bot.models.business import Business
from bot.models.lead import Lead
from bot.models.message import Message
from bot.models.booking import Booking
from bot.models.user import User
from bot.models.settings import Setting

logger = logging.getLogger(__name__)

API_SECRET = os.environ.get("API_SECRET", "calvix-admin-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "calvix2025")
JWT_SECRET = os.environ.get("JWT_SECRET", "calvix-jwt-secret-2025")

DASHBOARD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "dashboard.html",
)

_multibot_manager = None


def set_manager(manager):
    global _multibot_manager
    _multibot_manager = manager


# ─── Password utils ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{base64.b64encode(dk).decode()}"


def verify_password(stored: str, password: str) -> bool:
    try:
        salt, stored_b64 = stored.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return base64.b64encode(dk).decode() == stored_b64
    except Exception:
        return False


# ─── JWT utils ────────────────────────────────────────────────────────────────

def create_user_token(user_id: int, business_id) -> str:
    payload = {"user_id": user_id, "business_id": business_id, "exp": int(time.time()) + 86400 * 30}
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(JWT_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def verify_user_token(token: str):
    try:
        data, sig = token.rsplit(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padding = 4 - len(data) % 4
        payload = json.loads(base64.urlsafe_b64decode(data + ("=" * padding if padding != 4 else "")))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ─── Auth decorators ──────────────────────────────────────────────────────────

def require_auth(handler):
    async def wrapper(request):
        secret = request.headers.get("X-API-Secret", "")
        if secret != API_SECRET:
            return cors(web.json_response({"error": "Не авторизован"}, status=401))
        return await handler(request)
    return wrapper


def require_user_auth(handler):
    async def wrapper(request):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "").strip()
        payload = verify_user_token(token)
        if not payload or not payload.get("user_id"):
            return cors(web.json_response({"error": "Не авторизован"}, status=401))
        request["user_payload"] = payload
        return await handler(request)
    return wrapper


def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Secret, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


async def handle_options(request):
    return cors(web.Response(status=200))


# ─── Dashboard serve ──────────────────────────────────────────────────────────

async def serve_dashboard(request):
    if os.path.exists(DASHBOARD_PATH):
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(
            text=content,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return web.Response(text="<h1>Dashboard not found</h1>", content_type="text/html", status=404)


# ─── Admin login ──────────────────────────────────────────────────────────────

async def admin_login(request):
    body = await request.json()
    if body.get("password") == ADMIN_PASSWORD:
        return cors(web.json_response({"ok": True, "secret": API_SECRET}))
    return cors(web.json_response({"error": "Неверный пароль"}, status=401))


# ─── User auth ────────────────────────────────────────────────────────────────

async def user_register(request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower() or None
    phone = (body.get("phone") or "").strip() or None
    password = (body.get("password") or "").strip()
    full_name = (body.get("full_name") or "").strip() or None

    if not (email or phone):
        return cors(web.json_response({"error": "Email или телефон обязателен"}, status=400))
    if not password or len(password) < 6:
        return cors(web.json_response({"error": "Пароль минимум 6 символов"}, status=400))

    async with AsyncSessionLocal() as session:
        if email:
            cnt = await session.scalar(select(func.count()).select_from(User).where(User.email == email))
            if cnt:
                return cors(web.json_response({"error": "Email уже зарегистрирован"}, status=409))
        if phone:
            cnt = await session.scalar(select(func.count()).select_from(User).where(User.phone == phone))
            if cnt:
                return cors(web.json_response({"error": "Телефон уже зарегистрирован"}, status=409))

        user = User(email=email, phone=phone, password_hash=hash_password(password), full_name=full_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id, business_id = user.id, user.business_id

    token = create_user_token(user_id, business_id)
    return cors(web.json_response({
        "token": token, "user_id": user_id, "business_id": business_id,
        "email": email, "phone": phone, "full_name": full_name, "business_name": None,
        "company": None, "bio": None, "socials": {},
    }, status=201))


async def user_login(request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower() or None
    phone = (body.get("phone") or "").strip() or None
    password = (body.get("password") or "").strip()

    if not (email or phone) or not password:
        return cors(web.json_response({"error": "Заполните все поля"}, status=400))

    async with AsyncSessionLocal() as session:
        if email:
            result = await session.execute(select(User).where(User.email == email))
        else:
            result = await session.execute(select(User).where(User.phone == phone))
        user = result.scalar_one_or_none()

        if not user or not verify_password(user.password_hash, password):
            return cors(web.json_response({"error": "Неверный логин или пароль"}, status=401))
        if not user.is_active:
            return cors(web.json_response({"error": "Аккаунт заблокирован"}, status=403))

        business_name = None
        if user.business_id:
            biz = await session.get(Business, user.business_id)
            business_name = biz.name if biz else None

    import json as _json
    socials = {}
    if user.socials:
        try:
            socials = _json.loads(user.socials)
        except Exception:
            pass
    token = create_user_token(user.id, user.business_id)
    return cors(web.json_response({
        "token": token, "user_id": user.id, "business_id": user.business_id,
        "email": user.email, "phone": user.phone, "full_name": user.full_name,
        "company": user.company, "bio": user.bio, "socials": socials,
        "business_name": business_name,
    }))


@require_user_auth
async def user_me(request):
    payload = request["user_payload"]
    async with AsyncSessionLocal() as session:
        user = await session.get(User, payload["user_id"])
        if not user:
            return cors(web.json_response({"error": "Не найден"}, status=404))
        business_name = None
        if user.business_id:
            biz = await session.get(Business, user.business_id)
            business_name = biz.name if biz else None

    import json as _json
    socials = {}
    if user.socials:
        try:
            socials = _json.loads(user.socials)
        except Exception:
            pass
    token = create_user_token(user.id, user.business_id)
    return cors(web.json_response({
        "token": token, "user_id": user.id, "business_id": user.business_id,
        "email": user.email, "phone": user.phone, "full_name": user.full_name,
        "company": user.company, "bio": user.bio, "socials": socials,
        "business_name": business_name,
    }))


# ─── User profile / password ──────────────────────────────────────────────────

@require_user_auth
async def update_profile(request):
    payload = request["user_payload"]
    body = await request.json()
    async with AsyncSessionLocal() as session:
        user = await session.get(User, payload["user_id"])
        if not user:
            return cors(web.json_response({"error": "Не найден"}, status=404))
        if "full_name" in body: user.full_name = body["full_name"]
        if "company" in body: user.company = body["company"]
        if "bio" in body: user.bio = body["bio"]
        if "socials" in body:
            import json as _json
            user.socials = _json.dumps(body["socials"], ensure_ascii=False)
        await session.commit()
    return cors(web.json_response({"ok": True}))


@require_user_auth
async def change_user_password(request):
    payload = request["user_payload"]
    body = await request.json()
    new_pw = (body.get("new_password") or "").strip()
    if len(new_pw) < 6:
        return cors(web.json_response({"error": "Минимум 6 символов"}, status=400))
    async with AsyncSessionLocal() as session:
        user = await session.get(User, payload["user_id"])
        if not user:
            return cors(web.json_response({"error": "Не найден"}, status=404))
        user.password_hash = hash_password(new_pw)
        await session.commit()
    return cors(web.json_response({"ok": True}))


# ─── Admin user management ────────────────────────────────────────────────────

@require_auth
async def admin_list_users(request):
    import json as _json
    search = request.rel_url.query.get("search", "").strip().lower()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()
        data = []
        for u in users:
            if search and search not in (u.full_name or "").lower() and search not in (u.phone or "").lower():
                continue
            biz_name = None
            if u.business_id:
                biz = await session.get(Business, u.business_id)
                biz_name = biz.name if biz else None
            socials = {}
            if u.socials:
                try: socials = _json.loads(u.socials)
                except: pass
            data.append({
                "id": u.id, "full_name": u.full_name, "phone": u.phone,
                "email": u.email, "company": u.company, "bio": u.bio,
                "socials": socials, "business_id": u.business_id,
                "business_name": biz_name, "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })
    return cors(web.json_response({"users": data}))


@require_auth
async def change_admin_password(request):
    global ADMIN_PASSWORD
    body = await request.json()
    new_pw = (body.get("new_password") or "").strip()
    if len(new_pw) < 6:
        return cors(web.json_response({"error": "Минимум 6 символов"}, status=400))
    ADMIN_PASSWORD = new_pw
    return cors(web.json_response({"ok": True, "note": "Пароль изменён до перезапуска"}))


# ─── Businesses ───────────────────────────────────────────────────────────────

@require_auth
async def list_businesses(request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Business).order_by(Business.id))
        businesses = result.scalars().all()

        stats = {}
        for b in businesses:
            total = await session.scalar(
                select(func.count()).select_from(Lead).where(Lead.business_id == b.id)
            )
            hot = await session.scalar(
                select(func.count()).select_from(Lead).where(Lead.business_id == b.id, Lead.status == "HOT")
            )
            bookings = await session.scalar(
                select(func.count()).select_from(Booking).where(Booking.business_id == b.id)
            )
            stats[b.id] = {"total_leads": total, "hot_leads": hot, "bookings": bookings}

        data = [
            {
                "id": b.id,
                "name": b.name,
                "bot_token": b.bot_token,
                "system_prompt": b.system_prompt,
                "welcome_message": b.welcome_message or "",
                "manager_link": b.manager_link or "",
                "is_active": b.is_active,
                "stats": stats.get(b.id, {}),
            }
            for b in businesses
        ]
    return cors(web.json_response(data))


@require_auth
async def create_business(request):
    body = await request.json()
    token = body.get("bot_token", "").strip()
    name = body.get("name", "").strip()
    prompt = body.get("system_prompt", "").strip()
    welcome = body.get("welcome_message", "").strip()
    manager = body.get("manager_link", "@akovpyat").strip()
    is_active = body.get("is_active", True)

    if not token or not name or not prompt:
        return cors(web.json_response({"error": "bot_token, name, system_prompt обязательны"}, status=400))

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Business).where(Business.bot_token == token))
        if existing.scalar_one_or_none():
            return cors(web.json_response({"error": "Бот с таким токеном уже существует"}, status=409))

        b = Business(
            bot_token=token, name=name, system_prompt=prompt,
            welcome_message=welcome or None, manager_link=manager, is_active=is_active,
        )
        session.add(b)
        await session.commit()
        await session.refresh(b)
        biz_id = b.id

    await _reload_bots()
    return cors(web.json_response({"id": biz_id, "message": "Бизнес создан"}, status=201))


@require_auth
async def update_business(request):
    biz_id = int(request.match_info["id"])
    body = await request.json()

    fields = {}
    for key in ("name", "bot_token", "system_prompt", "welcome_message", "manager_link", "is_active"):
        if key in body:
            fields[key] = body[key]

    if not fields:
        return cors(web.json_response({"error": "Нет полей для обновления"}, status=400))

    async with AsyncSessionLocal() as session:
        await session.execute(update(Business).where(Business.id == biz_id).values(**fields))
        await session.commit()

    await _reload_bots()
    return cors(web.json_response({"message": "Обновлено"}))


@require_auth
async def delete_business(request):
    biz_id = int(request.match_info["id"])
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Business).where(Business.id == biz_id))
        await session.commit()

    await _reload_bots()
    return cors(web.json_response({"message": "Удалено"}))


# ─── Leads ────────────────────────────────────────────────────────────────────

@require_auth
async def list_leads(request):
    q = request.rel_url.query
    business_id = q.get("business_id")
    status = q.get("status")
    date_from = q.get("date_from")
    date_to = q.get("date_to")
    page = int(q.get("page", 1))
    per_page = int(q.get("per_page", 50))

    async with AsyncSessionLocal() as session:
        stmt = select(Lead).order_by(Lead.created_at.desc())
        if business_id:
            stmt = stmt.where(Lead.business_id == int(business_id))
        if status:
            stmt = stmt.where(Lead.status == status)
        if date_from:
            stmt = stmt.where(Lead.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            stmt = stmt.where(Lead.created_at <= datetime.fromisoformat(date_to))

        total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
        result = await session.execute(stmt.offset((page - 1) * per_page).limit(per_page))
        leads = result.scalars().all()

        biz_ids = list({l.business_id for l in leads})
        biz_result = await session.execute(select(Business).where(Business.id.in_(biz_ids)))
        biz_map = {b.id: b.name for b in biz_result.scalars().all()}

        data = [
            {
                "id": l.id,
                "business_id": l.business_id,
                "business_name": biz_map.get(l.business_id, ""),
                "telegram_id": l.telegram_id,
                "username": l.username or "",
                "full_name": l.full_name or "",
                "status": l.status or "COLD",
                "phone": l.phone or "",
                "last_active": l.last_active.isoformat() if l.last_active else None,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ]
    return cors(web.json_response({"leads": data, "total": total, "page": page, "per_page": per_page}))


@require_auth
async def export_leads_csv(request):
    q = request.rel_url.query
    business_id = q.get("business_id")
    status = q.get("status")

    async with AsyncSessionLocal() as session:
        stmt = select(Lead, Business.name).join(Business, Lead.business_id == Business.id)
        if business_id:
            stmt = stmt.where(Lead.business_id == int(business_id))
        if status:
            stmt = stmt.where(Lead.status == status)
        stmt = stmt.order_by(Lead.created_at.desc())
        result = await session.execute(stmt)
        rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Бизнес", "Имя", "Username", "Телефон", "Статус", "Дата"])
    for lead, biz_name in rows:
        writer.writerow([
            lead.id, biz_name, lead.full_name or "", lead.username or "",
            lead.phone or "", lead.status or "COLD",
            lead.created_at.strftime("%d.%m.%Y %H:%M") if lead.created_at else "",
        ])

    return cors(web.Response(
        body=output.getvalue().encode("utf-8-sig"),
        content_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    ))


@require_auth
async def get_lead_history(request):
    lead_id = int(request.match_info["id"])
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.lead_id == lead_id).order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()
        data = [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in messages
        ]
    return cors(web.json_response(data))


@require_auth
async def update_lead_status(request):
    lead_id = int(request.match_info["id"])
    body = await request.json()
    status = body.get("status")
    if status not in ("HOT", "WARM", "COLD"):
        return cors(web.json_response({"error": "Статус должен быть HOT, WARM или COLD"}, status=400))

    async with AsyncSessionLocal() as session:
        await session.execute(update(Lead).where(Lead.id == lead_id).values(status=status))
        await session.commit()
    return cors(web.json_response({"message": f"Статус изменён на {status}"}))


# ─── Bookings ─────────────────────────────────────────────────────────────────

@require_auth
async def list_bookings(request):
    q = request.rel_url.query
    business_id = q.get("business_id")
    status = q.get("status")

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Booking, Lead.full_name, Lead.username, Lead.phone, Business.name)
            .outerjoin(Lead, Booking.lead_id == Lead.id)
            .join(Business, Booking.business_id == Business.id)
            .order_by(Booking.created_at.desc())
        )
        if business_id:
            stmt = stmt.where(Booking.business_id == int(business_id))
        if status:
            stmt = stmt.where(Booking.status == status)

        result = await session.execute(stmt)
        rows = result.all()
        data = [
            {
                "id": b.id,
                "business_id": b.business_id,
                "business_name": biz_name or "",
                "full_name": full_name or "",
                "username": username or "",
                "phone": b.phone or phone or "",
                "scheduled_at": b.scheduled_at.isoformat() if b.scheduled_at else None,
                "status": b.status or "pending",
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b, full_name, username, phone, biz_name in rows
        ]
    return cors(web.json_response(data))


@require_auth
async def update_booking_status(request):
    booking_id = int(request.match_info["id"])
    body = await request.json()
    status = body.get("status")
    if status not in ("pending", "done", "cancelled"):
        return cors(web.json_response({"error": "Статус: pending, done, cancelled"}, status=400))

    async with AsyncSessionLocal() as session:
        await session.execute(update(Booking).where(Booking.id == booking_id).values(status=status))
        await session.commit()
    return cors(web.json_response({"message": f"Статус изменён на {status}"}))


# ─── Analytics ────────────────────────────────────────────────────────────────

@require_auth
async def analytics_funnel(request):
    business_id = request.rel_url.query.get("business_id")

    async with AsyncSessionLocal() as session:
        base = select(func.count()).select_from(Lead)
        if business_id:
            base = base.where(Lead.business_id == int(business_id))

        total = await session.scalar(base)
        warm = await session.scalar(base.where(Lead.status.in_(["WARM", "HOT"])))
        hot = await session.scalar(base.where(Lead.status == "HOT"))

        booking_stmt = select(func.count()).select_from(Booking)
        if business_id:
            booking_stmt = booking_stmt.where(Booking.business_id == int(business_id))
        booked = await session.scalar(booking_stmt)
        done = await session.scalar(booking_stmt.where(Booking.status == "done"))

    return cors(web.json_response({
        "stages": [
            {"label": "Всего лидов", "value": total or 0, "color": "#6366f1"},
            {"label": "Заинтересованы (WARM+)", "value": warm or 0, "color": "#f59e0b"},
            {"label": "HOT лиды", "value": hot or 0, "color": "#ef4444"},
            {"label": "Записались на созвон", "value": booked or 0, "color": "#10b981"},
            {"label": "Созвон проведён", "value": done or 0, "color": "#059669"},
        ]
    }))


@require_auth
async def analytics_leads_by_day(request):
    business_id = request.rel_url.query.get("business_id")
    days = int(request.rel_url.query.get("days", 14))

    async with AsyncSessionLocal() as session:
        biz_filter = f"AND business_id = {int(business_id)}" if business_id else ""
        stmt = text(f"""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM leads
            WHERE created_at >= NOW() - INTERVAL '{int(days)} days'
            {biz_filter}
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """)
        result = await session.execute(stmt)
        data = [{"day": str(r.day), "count": int(r.cnt)} for r in result.all()]

    return cors(web.json_response(data))


@require_auth
async def analytics_trigger_words(request):
    business_id = request.rel_url.query.get("business_id")

    async with AsyncSessionLocal() as session:
        stmt = select(Message.content).where(Message.role == "user")
        if business_id:
            stmt = stmt.where(Message.business_id == int(business_id))
        stmt = stmt.limit(1000)
        result = await session.execute(stmt)
        messages = [r[0] for r in result.all()]

    HOT_KEYWORDS = [
        "купить", "записаться", "хочу начать", "сколько стоит",
        "цена", "стоимость", "оплатить", "запишите", "давайте",
        "готов", "когда можно", "как записаться", "хочу", "запиши",
    ]
    counts = {}
    for msg in messages:
        tl = msg.lower()
        for kw in HOT_KEYWORDS:
            if kw in tl:
                counts[kw] = counts.get(kw, 0) + 1

    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return cors(web.json_response([{"word": w, "count": c} for w, c in sorted_words]))


# ─── Platform ─────────────────────────────────────────────────────────────────

@require_auth
async def platform_status(request):
    async with AsyncSessionLocal() as session:
        businesses = (await session.execute(select(Business))).scalars().all()
        total_leads = await session.scalar(select(func.count()).select_from(Lead))
        total_hot = await session.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == "HOT")
        )
        total_bookings = await session.scalar(select(func.count()).select_from(Booking))
        total_users = await session.scalar(select(func.count()).select_from(User))

        active_ids = set(_multibot_manager.bots.keys()) if _multibot_manager else set()
        bots_status = [
            {"id": b.id, "name": b.name, "is_active": b.is_active, "online": b.id in active_ids}
            for b in businesses
        ]

    return cors(web.json_response({
        "bots": bots_status,
        "total_leads": total_leads,
        "total_hot": total_hot,
        "total_bookings": total_bookings,
        "total_users": total_users,
        "active_bots": len(active_ids),
    }))


# ─── Helpers ──────────────────────────────────────────────────────────────────

@require_auth
async def reload_bots(request):
    await _reload_bots()
    return cors(web.json_response({"message": "Боты перезагружены"}))


async def _reload_bots():
    if _multibot_manager:
        try:
            await _multibot_manager.reload()
            logger.info("Боты перезагружены через API")
        except Exception as e:
            logger.error(f"Ошибка перезагрузки через API: {e}")


# ─── Settings ─────────────────────────────────────────────────────────────────

DEFAULT_KEYWORDS = {
    "hot": "купить, цена, оплатить, договор, счет, покупка, хочу заказать, нужен срочно, записаться, хочу записаться, созвон, встретиться, позвоните, демо, покажите, запишите, запись, хочу попробовать, когда можно начать, как записаться, хочу начать, готов начать, оформить",
    "warm": "интересно, расскажите, как работает, пример, сравнение, стоимость, есть ли скидка, возможно ли, автоматизация, хочу узнать, подробнее, а если, сколько стоит, какая цена, что входит, расскажи",
    "cold": "не надо, не интересно, потом, не сейчас, не нужно, отпишитесь, спам, отказаться",
}

DEFAULT_TEMPLATES = json.dumps([
    {"id": 1, "name": "Предложение созвона", "text": "Давайте обсудим детали на созвоне — это займёт 15–20 минут. Когда вам удобно?"},
    {"id": 2, "name": "Возражение: дорого", "text": "Понимаю. Давайте разберём что именно входит в стоимость — думаю, увидите что это выгодно."},
    {"id": 3, "name": "Возражение: подумаю", "text": "Конечно, не тороплю. Если появятся вопросы — я здесь. Могу отправить подробную информацию?"},
    {"id": 4, "name": "Прощание", "text": "Спасибо за обращение! Если появятся вопросы — пишите. 🚀"},
])


async def get_settings_keywords(request):
    async with AsyncSessionLocal() as session:
        result = {}
        for k in ["keywords_hot", "keywords_warm", "keywords_cold"]:
            row = await session.scalar(select(Setting).where(Setting.key == k))
            ktype = k.replace("keywords_", "")
            result[ktype] = row.value if row else DEFAULT_KEYWORDS.get(ktype, "")
    return cors(web.json_response(result))


async def post_settings_keywords(request):
    body = await request.json()
    async with AsyncSessionLocal() as session:
        for ktype in ["hot", "warm", "cold"]:
            val = body.get(ktype, "").strip()
            if not val:
                continue
            key = f"keywords_{ktype}"
            row = await session.scalar(select(Setting).where(Setting.key == key))
            if row:
                row.value = val
            else:
                session.add(Setting(key=key, value=val))
        await session.commit()
    # Invalidate cache in lead_scoring
    from bot.services.lead_scoring import LeadScoringService
    LeadScoringService.invalidate_cache()
    return cors(web.json_response({"ok": True}))


async def get_settings_templates(request):
    async with AsyncSessionLocal() as session:
        row = await session.scalar(select(Setting).where(Setting.key == "templates"))
        val = row.value if row else DEFAULT_TEMPLATES
    try:
        data = json.loads(val)
    except Exception:
        data = []
    return cors(web.json_response({"templates": data}))


async def post_settings_templates(request):
    body = await request.json()
    templates = body.get("templates", [])
    async with AsyncSessionLocal() as session:
        row = await session.scalar(select(Setting).where(Setting.key == "templates"))
        val = json.dumps(templates, ensure_ascii=False)
        if row:
            row.value = val
        else:
            session.add(Setting(key="templates", value=val))
        await session.commit()
    return cors(web.json_response({"ok": True}))


# ─── Router ───────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()

    # Dashboard
    app.router.add_get("/", serve_dashboard)
    app.router.add_get("/dashboard", serve_dashboard)

    # Admin login
    app.router.add_post("/api/login", admin_login)

    # User auth
    app.router.add_post("/api/auth/register", user_register)
    app.router.add_post("/api/auth/login", user_login)
    app.router.add_get("/api/auth/me", user_me)
    app.router.add_put("/api/auth/profile", update_profile)
    app.router.add_put("/api/auth/password", change_user_password)
    app.router.add_route("OPTIONS", "/api/auth/profile", handle_options)
    app.router.add_route("OPTIONS", "/api/auth/password", handle_options)

    # Admin user management
    app.router.add_get("/api/admin/users", admin_list_users)
    app.router.add_put("/api/admin/password", change_admin_password)
    app.router.add_post("/api/admin/password", change_admin_password)
    app.router.add_route("OPTIONS", "/api/admin/users", handle_options)
    app.router.add_route("OPTIONS", "/api/admin/password", handle_options)

    # Businesses (admin)
    app.router.add_get("/api/businesses", list_businesses)
    app.router.add_post("/api/businesses", create_business)
    app.router.add_put("/api/businesses/{id}", update_business)
    app.router.add_delete("/api/businesses/{id}", delete_business)

    # Leads (admin) — export BEFORE {id} routes
    app.router.add_get("/api/leads/export", export_leads_csv)
    app.router.add_get("/api/leads", list_leads)
    app.router.add_get("/api/leads/{id}/history", get_lead_history)
    app.router.add_put("/api/leads/{id}/status", update_lead_status)

    # Bookings (admin)
    app.router.add_get("/api/bookings", list_bookings)
    app.router.add_put("/api/bookings/{id}/status", update_booking_status)

    # Analytics (admin)
    app.router.add_get("/api/analytics/funnel", analytics_funnel)
    app.router.add_get("/api/analytics/leads-by-day", analytics_leads_by_day)
    app.router.add_get("/api/analytics/trigger-words", analytics_trigger_words)

    # Platform
    app.router.add_get("/api/platform/status", platform_status)

    # Utils
    app.router.add_post("/api/reload", reload_bots)

    # Settings
    app.router.add_get("/api/settings/keywords", get_settings_keywords)
    app.router.add_post("/api/settings/keywords", post_settings_keywords)
    app.router.add_get("/api/settings/templates", get_settings_templates)
    app.router.add_post("/api/settings/templates", post_settings_templates)
    app.router.add_route("OPTIONS", "/api/settings/keywords", handle_options)
    app.router.add_route("OPTIONS", "/api/settings/templates", handle_options)

    # OPTIONS после всех маршрутов чтобы не перехватывал GET
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)

    return app
