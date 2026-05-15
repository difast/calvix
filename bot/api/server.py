import json
import os
import logging
from aiohttp import web
from bot.models.database import AsyncSessionLocal
from bot.models.business import Business
from sqlalchemy import select, update, delete

logger = logging.getLogger(__name__)

API_SECRET = os.environ.get("API_SECRET", "calvix-admin-secret")

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


@require_auth
async def list_businesses(request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Business).order_by(Business.id))
        businesses = result.scalars().all()
        data = [
            {
                "id": b.id,
                "name": b.name,
                "bot_token": b.bot_token,
                "system_prompt": b.system_prompt,
                "welcome_message": b.welcome_message or "",
                "manager_link": b.manager_link or "",
                "is_active": b.is_active,
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
    return cors(web.json_response({"id": biz_id, "message": "Бизнес создан, боты перезагружены"}, status=201))


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
        await session.execute(
            update(Business).where(Business.id == biz_id).values(**fields)
        )
        await session.commit()

    await _reload_bots()
    return cors(web.json_response({"message": "Обновлено, боты перезагружены"}))


@require_auth
async def delete_business(request):
    biz_id = int(request.match_info["id"])
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Business).where(Business.id == biz_id))
        await session.commit()

    await _reload_bots()
    return cors(web.json_response({"message": "Удалено, боты перезагружены"}))


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


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{path_info:.*}", handle_options)
    app.router.add_get("/api/businesses", list_businesses)
    app.router.add_post("/api/businesses", create_business)
    app.router.add_put("/api/businesses/{id}", update_business)
    app.router.add_delete("/api/businesses/{id}", delete_business)
    app.router.add_post("/api/reload", reload_bots)
    return app
