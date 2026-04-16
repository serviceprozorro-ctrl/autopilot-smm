import logging
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.models import Account, Platform, AuthType
from utils.security import encrypt_session_data, decrypt_session_data, validate_cookies_json

logger = logging.getLogger(__name__)

PLATFORM_LABELS: Dict[str, str] = {
    Platform.TIKTOK: "TikTok",
    Platform.INSTAGRAM: "Instagram",
    Platform.YOUTUBE: "YouTube",
}

STATUS_EMOJI: Dict[str, str] = {
    "active": "✅",
    "banned": "🚫",
    "inactive": "⏸",
}


class AccountManager:
    """High-level business logic for account management."""

    @staticmethod
    async def add_account(
        db: AsyncSession,
        platform: str,
        username: str,
        auth_type: str,
        raw_session_data: Optional[str] = None,
    ) -> Account:
        if platform not in [p.value for p in Platform]:
            raise ValueError(f"Unsupported platform: {platform}")
        if auth_type not in [a.value for a in AuthType]:
            raise ValueError(f"Unsupported auth type: {auth_type}")

        encrypted: Optional[str] = None
        if raw_session_data:
            parsed = validate_cookies_json(raw_session_data)
            if parsed is None:
                raise ValueError("session_data must be valid JSON object (cookies dict)")
            encrypted = encrypt_session_data(parsed)

        account = await crud.create_account(
            db=db,
            platform=platform,
            username=username,
            auth_type=auth_type,
            session_data=encrypted,
        )
        return account

    @staticmethod
    async def list_accounts(db: AsyncSession) -> List[Account]:
        return await crud.get_all_accounts(db)

    @staticmethod
    async def remove_account(db: AsyncSession, account_id: int) -> bool:
        return await crud.delete_account(db, account_id)

    @staticmethod
    async def get_account_session(db: AsyncSession, account_id: int) -> Optional[Dict[str, Any]]:
        account = await crud.get_account_by_id(db, account_id)
        if not account or not account.session_data:
            return None
        return decrypt_session_data(account.session_data)

    @staticmethod
    def format_account_summary(account: Account) -> str:
        status_emoji = STATUS_EMOJI.get(account.status, "❓")
        platform_label = PLATFORM_LABELS.get(account.platform, account.platform.capitalize())
        return (
            f"{status_emoji} <b>{platform_label}</b> — @{account.username}\n"
            f"   ID: {account.id} | Auth: {account.auth_type} | Status: {account.status}"
        )

    @staticmethod
    def format_accounts_list(accounts: List[Account]) -> str:
        if not accounts:
            return "📭 Аккаунты не добавлены."
        lines = ["<b>📋 Список аккаунтов:</b>\n"]
        for acc in accounts:
            platform_label = PLATFORM_LABELS.get(acc.platform, acc.platform.capitalize())
            status_emoji = STATUS_EMOJI.get(acc.status, "❓")
            lines.append(
                f"{status_emoji} [{acc.id}] <b>{platform_label}</b> — @{acc.username} ({acc.auth_type})"
            )
        return "\n".join(lines)
