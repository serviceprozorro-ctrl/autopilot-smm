import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

WEBAPP_DOMAIN = os.environ.get("REPLIT_DEV_DOMAIN", "localhost")
WEBAPP_URL = f"https://{WEBAPP_DOMAIN}:3000/app"


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🌐 Открыть AutoPilot",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )
    builder.row(InlineKeyboardButton(text="📱 Аккаунты", callback_data="menu:accounts"))
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats"),
        InlineKeyboardButton(text="🚀 Автопостинг", callback_data="menu:autopost"),
    )
    return builder.as_markup()
