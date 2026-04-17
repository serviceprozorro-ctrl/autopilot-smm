import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from db.database import init_db

WEBAPP_DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "localhost")
WEBAPP_URL = f"https://{WEBAPP_DOMAIN}:3000/app"
MINI_APP_DIR = Path(__file__).parent / "mini_app"

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database ready")

    # Запускаем фоновый планировщик публикаций
    from core.posting.scheduler import start_scheduler, stop_scheduler
    start_scheduler()

    logger.info("Starting Telegram bot polling...")
    from bot.bot import create_bot, create_dispatcher
    from aiogram.types import MenuButtonWebApp, WebAppInfo
    bot = create_bot()
    dp = create_dispatcher()

    polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=["message", "callback_query"]))
    logger.info("Telegram bot started")

    # Set bot menu button → opens Mini Web App
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🚀 Открыть AutoPilot",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        )
        logger.info("Mini Web App menu button set: %s", WEBAPP_URL)
    except Exception as e:
        logger.warning("Could not set menu button: %s", e)

    yield

    logger.info("Shutting down...")
    try:
        stop_scheduler()
    except Exception:
        pass
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    await bot.session.close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Social Media Automation Platform",
        description="API для управления аккаунтами TikTok, Instagram и YouTube",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes.accounts import router as accounts_router
    from api.routes.stats import router as stats_router
    from api.routes.settings import router as settings_router
    from api.routes.posts import router as posts_router

    app.include_router(accounts_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")
    app.include_router(posts_router, prefix="/api")
    app.include_router(settings_router)

    # Serve Mini Web App static assets
    if (MINI_APP_DIR / "assets").exists():
        app.mount("/app/assets", StaticFiles(directory=str(MINI_APP_DIR / "assets")), name="mini_app_assets")

    @app.get("/app", response_class=HTMLResponse, tags=["mini_app"])
    async def mini_app():
        """Telegram Mini Web App entry point."""
        html_file = MINI_APP_DIR / "index.html"
        if html_file.exists():
            return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Mini App not found</h1>", status_code=404)

    @app.get("/", tags=["health"])
    async def health_check():
        return {
            "status": "ok",
            "service": "Social Media Automation Platform",
            "version": "1.0.0",
            "mini_app_url": WEBAPP_URL,
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
