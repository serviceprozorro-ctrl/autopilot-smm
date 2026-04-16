import json
import logging
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from db import crud
from db.models import Account, Platform, AuthType, AccountStatus
from utils.security import encrypt_session_data, decrypt_session_data, validate_cookies_json

logger = logging.getLogger(__name__)

PLATFORM_LABELS: Dict[str, str] = {
    Platform.TIKTOK: "TikTok",
    Platform.INSTAGRAM: "Instagram",
    Platform.YOUTUBE: "YouTube",
}

AUTH_LABELS: Dict[str, str] = {
    AuthType.COOKIES: "🍪 Cookies",
    AuthType.LOGIN_PASSWORD: "🔐 Логин/Пароль",
    AuthType.QR_CODE: "📱 QR-код",
    AuthType.API: "🔑 API ключ",
}

STATUS_EMOJI: Dict[str, str] = {
    "active": "✅",
    "banned": "🚫",
    "inactive": "⏸",
    "pending": "⏳",
}


class AccountManager:

    @staticmethod
    async def add_account_cookies(
        db: AsyncSession,
        platform: str,
        username: str,
        raw_cookies: Optional[str] = None,
    ) -> Account:
        encrypted: Optional[str] = None
        if raw_cookies and raw_cookies.strip() not in ("{}", ""):
            parsed = validate_cookies_json(raw_cookies)
            if parsed is None:
                raise ValueError("session_data должен быть валидным JSON-объектом (словарь cookies)")
            encrypted = encrypt_session_data(parsed)

        return await crud.create_account(
            db=db,
            platform=platform,
            username=username,
            auth_type=AuthType.COOKIES,
            session_data=encrypted,
            status=AccountStatus.ACTIVE,
        )

    @staticmethod
    async def add_account_login_password(
        db: AsyncSession,
        platform: str,
        username: str,
        password: str,
    ) -> Account:
        if not password:
            raise ValueError("Пароль не может быть пустым")

        encrypted_password = encrypt_session_data({"password": password})

        return await crud.create_account(
            db=db,
            platform=platform,
            username=username,
            auth_type=AuthType.LOGIN_PASSWORD,
            session_data=None,
            password_data=encrypted_password,
            status=AccountStatus.ACTIVE,
        )

    @staticmethod
    async def add_account_qr_pending(
        db: AsyncSession,
        platform: str,
        username: str,
        qr_token: str,
    ) -> Account:
        """Create account record while waiting for QR scan confirmation."""
        token_data = encrypt_session_data({"qr_token": qr_token})
        return await crud.create_account(
            db=db,
            platform=platform,
            username=username or "unknown",
            auth_type=AuthType.QR_CODE,
            session_data=token_data,
            status=AccountStatus.PENDING,
        )

    @staticmethod
    async def confirm_qr_account(
        db: AsyncSession,
        account_id: int,
        username: str,
        session_cookies: Dict[str, Any],
    ) -> Optional[Account]:
        """After successful QR scan: update username and store real session."""
        account = await crud.get_account_by_id(db, account_id)
        if not account:
            return None
        account.username = username or account.username
        encrypted = encrypt_session_data(session_cookies)
        account.session_data = encrypted
        account.status = AccountStatus.ACTIVE
        await db.commit()
        await db.refresh(account)
        return account

    @staticmethod
    async def add_account_api(
        db: AsyncSession,
        platform: str,
        username: str,
        api_key: str,
    ) -> Account:
        encrypted = encrypt_session_data({"api_key": api_key})
        return await crud.create_account(
            db=db,
            platform=platform,
            username=username,
            auth_type=AuthType.API,
            session_data=encrypted,
            status=AccountStatus.ACTIVE,
        )

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
    def format_account_card(account: Account) -> str:
        status_emoji = STATUS_EMOJI.get(account.status, "❓")
        platform_label = PLATFORM_LABELS.get(account.platform, account.platform.capitalize())
        auth_label = AUTH_LABELS.get(account.auth_type, account.auth_type)
        has_session = "✔" if account.session_data else "✘"
        return (
            f"{status_emoji} <b>{platform_label}</b> — @{account.username}\n"
            f"   ID: <code>{account.id}</code>  |  {auth_label}  |  Сессия: {has_session}"
        )

    @staticmethod
    def format_accounts_list(accounts: List[Account]) -> str:
        if not accounts:
            return "📭 Аккаунты не добавлены."

        by_platform: Dict[str, List[Account]] = {}
        for acc in accounts:
            by_platform.setdefault(acc.platform, []).append(acc)

        lines = [f"<b>📋 Аккаунты ({len(accounts)} шт.)</b>\n"]
        for platform, accs in by_platform.items():
            label = PLATFORM_LABELS.get(platform, platform.capitalize())
            lines.append(f"<b>{label}:</b>")
            for acc in accs:
                s = STATUS_EMOJI.get(acc.status, "❓")
                auth = AUTH_LABELS.get(acc.auth_type, acc.auth_type)
                lines.append(f"  {s} [{acc.id}] @{acc.username} — {auth}")
            lines.append("")
        return "\n".join(lines).rstrip()
