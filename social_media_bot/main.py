import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.database import init_db

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

    logger.info("Starting Telegram bot polling...")
    from bot.bot import create_bot, create_dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=["message", "callback_query"]))
    logger.info("Telegram bot started")

    yield

    logger.info("Shutting down...")
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

    app.include_router(accounts_router, prefix="/api")
    app.include_router(stats_router, prefix="/api")

    @app.get("/", tags=["health"])
    async def health_check():
        return {
            "status": "ok",
            "service": "Social Media Automation Platform",
            "version": "1.0.0",
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
