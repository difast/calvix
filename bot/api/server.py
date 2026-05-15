import csv
import io
import json
import os
import logging
from datetime import datetime, timedelta
from aiohttp import web
from sqlalchemy import select, update, delete, func, text
from bot.models.database import AsyncSessionLocal
from bot.models.business import Business
from bot.models.lead import Lead
from bot.models.message import Message
from bot.models.booking import Booking

logger = logging.getLogger(__name__)

API_SECRET = os.environ.get("API_SECRET", "calvix-admin-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "calvix2025")

_multibot_manager = None


def set_manager(manager):
    global _multibot_manager
    _multibot_manager = manager


def require_auth(handler):
    async def wrapper(request):
        secret = request.headers.get("X-API-Secret") or request.rel_url.query.get("secret")
        if secret != API_SECRET:
            return web.json_response({"error": "Unauthorized"}, status=401)
        return await handler(request)
    return wrapper


def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Secret"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


async def handle_options(request):
    return cors(web.Response(status=200))


# ─── Auth ───────────────────────────────────────────────────────────────────

async def admin_login(request):
    body = await request.json()
    if body.get("password") == ADMIN_PASSWORD:
        return cors(web.json_response({"ok": True, "secret": API_SECRET}))
    return cors(web.json_response({"error": "Неверный пароль"}, status=401))


# ─── Businesses ──────────────────────────────────────────────────────────────

@require_auth
async def list_businesses(request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Business).order_by(Business.id))
        businesses = result.scalars().all()

        # Статистика по каждому бизнесу
        stats = {}
        for b in businesses:
            total = await session.scalar(
                select(func.count()).select_from(Lead).where(Lead.business_id == b.id)
            )
            hot = await session.scalar(
                select(func.count()).select_from(Lead).where(
                    Lead.business_id == b.id, Lead.status == "HOT"
                )
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
            welcome_message=welcome or None, manager_link=manager, is_active=is_active
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


# ─── Leads ───────────────────────────────────────────────────────────────────

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

        total = await session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        result = await session.execute(stmt.offset((page - 1) * per_page).limit(per_page))
        leads = result.scalars().all()

        # Подтягиваем имена бизнесов
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
async def get_lead_history(request):
    lead_id = int(request.match_info["id"])
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message)
            .where(Message.lead_id == lead_id)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()
        data = [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
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
        await session.execute(
            update(Lead).where(Lead.id == lead_id).values(status=status)
        )
        await session.commit()
    return cors(web.json_response({"message": f"Статус изменён на {status}"}))


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
            lead.created_at.strftime("%d.%m.%Y %H:%M") if lead.created_at else ""
        ])

    return cors(web.Response(
        body=output.getvalue().encode("utf-8-sig"),
        content_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"}
    ))


# ─── Bookings ────────────────────────────────────────────────────────────────

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
        await session.execute(
            update(Booking).where(Booking.id == booking_id).values(status=status)
        )
        await session.commit()
    return cors(web.json_response({"message": f"Статус созвона изменён на {status}"}))


# ─── Analytics ───────────────────────────────────────────────────────────────

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
            {"label": "Всего лидов", "value": total, "color": "#6366f1"},
            {"label": "Заинтересованы (WARM+)", "value": warm, "color": "#f59e0b"},
            {"label": "HOT лиды", "value": hot, "color": "#ef4444"},
            {"label": "Записались на созвон", "value": booked, "color": "#10b981"},
            {"label": "Созвон проведён", "value": done, "color": "#059669"},
        ]
    }))


@require_auth
async def analytics_leads_by_day(request):
    business_id = request.rel_url.query.get("business_id")
    days = int(request.rel_url.query.get("days", 14))

    async with AsyncSessionLocal() as session:
        stmt = text("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM leads
            WHERE created_at >= NOW() - INTERVAL ':days days'
            {biz_filter}
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        """.replace(
            "{biz_filter}",
            f"AND business_id = {int(business_id)}" if business_id else ""
        ).replace(":days", str(days)))

        result = await session.execute(stmt)
        rows = result.all()
        data = [{"day": str(r.day), "count": r.cnt} for r in rows]

    return cors(web.json_response(data))


@require_auth
async def analytics_trigger_words(request):
    business_id = request.rel_url.query.get("business_id")

    async with AsyncSessionLocal() as session:
        # Берём последние сообщения от пользователей и считаем триггерные слова
        stmt = select(Message.content).where(Message.role == "user")
        if business_id:
            stmt = stmt.where(Message.business_id == int(business_id))
        stmt = stmt.limit(1000)

        result = await session.execute(stmt)
        messages = [r[0] for r in result.all()]

    HOT_KEYWORDS = [
        "купить", "записаться", "хочу начать", "сколько стоит",
        "цена", "стоимость", "оплатить", "запишите", "давайте",
        "готов", "когда можно", "как записаться", "хочу", "запиши"
    ]

    counts = {}
    for msg in messages:
        text_lower = msg.lower()
        for kw in HOT_KEYWORDS:
            if kw in text_lower:
                counts[kw] = counts.get(kw, 0) + 1

    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return cors(web.json_response([{"word": w, "count": c} for w, c in sorted_words]))


# ─── Platform ────────────────────────────────────────────────────────────────

@require_auth
async def platform_status(request):
    async with AsyncSessionLocal() as session:
        businesses = (await session.execute(select(Business))).scalars().all()
        total_leads = await session.scalar(select(func.count()).select_from(Lead))
        total_hot = await session.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == "HOT")
        )
        total_bookings = await session.scalar(select(func.count()).select_from(Booking))

        bots_status = []
        active_ids = set(_multibot_manager.bots.keys()) if _multibot_manager else set()
        for b in businesses:
            bots_status.append({
                "id": b.id,
                "name": b.name,
                "is_active": b.is_active,
                "online": b.id in active_ids,
            })

    return cors(web.json_response({
        "bots": bots_status,
        "total_leads": total_leads,
        "total_hot": total_hot,
        "total_bookings": total_bookings,
        "active_bots": len(active_ids),
    }))


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


# ─── Router ──────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)

    # Auth
    app.router.add_post("/api/login", admin_login)

    # Businesses
    app.router.add_get("/api/businesses", list_businesses)
    app.router.add_post("/api/businesses", create_business)
    app.router.add_put("/api/businesses/{id}", update_business)
    app.router.add_delete("/api/businesses/{id}", delete_business)

    # Leads
    app.router.add_get("/api/leads", list_leads)
    app.router.add_get("/api/leads/{id}/history", get_lead_history)
    app.router.add_put("/api/leads/{id}/status", update_lead_status)
    app.router.add_get("/api/leads/export", export_leads_csv)

    # Bookings
    app.router.add_get("/api/bookings", list_bookings)
    app.router.add_put("/api/bookings/{id}/status", update_booking_status)

    # Analytics
    app.router.add_get("/api/analytics/funnel", analytics_funnel)
    app.router.add_get("/api/analytics/leads-by-day", analytics_leads_by_day)
    app.router.add_get("/api/analytics/trigger-words", analytics_trigger_words)

    # Platform
    app.router.add_get("/api/platform/status", platform_status)

    # Utils
    app.router.add_post("/api/reload", reload_bots)

    return app
