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


def auth_type_kb(platform: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if platform == "tiktok":
        builder.row(InlineKeyboardButton(
            text="📱 QR-код (рекомендуется)", callback_data="auth:qr_code"
        ))
        builder.row(InlineKeyboardButton(
            text="🔐 Логин + Пароль", callback_data="auth:login_password"
        ))
        builder.row(InlineKeyboardButton(
            text="🍪 Cookies / Session Token", callback_data="auth:cookies"
        ))
    elif platform == "instagram":
        builder.row(InlineKeyboardButton(
            text="🔐 Логин + Пароль", callback_data="auth:login_password"
        ))
        builder.row(InlineKeyboardButton(
            text="🍪 Cookies / Session Token", callback_data="auth:cookies"
        ))
    else:
        # YouTube
        builder.row(InlineKeyboardButton(
            text="🍪 Cookies / Session Token", callback_data="auth:cookies"
        ))
        builder.row(InlineKeyboardButton(
            text="🔑 API ключ (OAuth2)", callback_data="auth:api"
        ))

    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="accounts:cancel"))
    return builder.as_markup()


def qr_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Я отсканировал QR", callback_data="qr:scanned"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="accounts:cancel"),
    )
    return builder.as_markup()


def accounts_delete_list_kb(accounts: List[Account]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    platform_icons = {"tiktok": "🎵", "instagram": "📸", "youtube": "▶️"}
    status_icons = {"active": "✅", "banned": "🚫", "inactive": "⏸", "pending": "⏳"}
    for acc in accounts:
        icon = platform_icons.get(acc.platform, "📱")
        s_icon = status_icons.get(acc.status, "❓")
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {s_icon} [{acc.id}] @{acc.username}",
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
