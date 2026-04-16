import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    from bot.handlers import accounts as accounts_handler
    from bot.handlers import start as start_handler

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(start_handler.router)
    dp.include_router(accounts_handler.router)

    logger.info("Dispatcher configured with routers: start, accounts")
    return dp
