from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Account


def accounts_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="accounts:add"))
    builder.row(InlineKeyboardButton(text="📋 Список аккаунтов", callback_data="accounts:list"))
    builder.row(InlineKeyboardButton(text="❌ Удалить аккаунт", callback_data="accounts:delete_prompt"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:main"))
    return builder.as_markup()


def platform_choice_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎵 TikTok", callback_data="platform:tiktok"))
    builder.row(InlineKeyboardButton(text="📸 Instagram", callback_data="platform:instagram"))
    builder.row(InlineKeyboardButton(text="▶️ YouTube", callback_data="platform:youtube"))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="accounts:cancel"))
    return builder.as_markup()


def auth_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🍪 Cookies (рекомендуется)", callback_data="auth:cookies"))
    builder.row(InlineKeyboardButton(text="🔑 API ключ", callback_data="auth:api"))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="accounts:cancel"))
    return builder.as_markup()


def accounts_delete_list_kb(accounts: List[Account]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        platform_icons = {"tiktok": "🎵", "instagram": "📸", "youtube": "▶️"}
        icon = platform_icons.get(acc.platform, "📱")
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} [{acc.id}] @{acc.username} ({acc.platform})",
                callback_data=f"delete:{acc.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu:accounts"))
    return builder.as_markup()


def confirm_delete_kb(account_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{account_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="menu:accounts"),
    )
    return builder.as_markup()


def back_to_accounts_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 В меню аккаунтов", callback_data="menu:accounts"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return builder.as_markup()
