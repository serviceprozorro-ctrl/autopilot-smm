from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📱 Аккаунты", callback_data="menu:accounts"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="menu:stats"))
    builder.row(InlineKeyboardButton(text="🚀 Автопостинг", callback_data="menu:autopost"))
    return builder.as_markup()
