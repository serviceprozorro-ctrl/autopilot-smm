import logging
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Account, AccountStatus

logger = logging.getLogger(__name__)


async def create_account(
    db: AsyncSession,
    platform: str,
    username: str,
    auth_type: str,
    session_data: Optional[str] = None,
) -> Account:
    account = Account(
        platform=platform,
        username=username,
        auth_type=auth_type,
        session_data=session_data,
        status=AccountStatus.ACTIVE,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    logger.info("Created account id=%s platform=%s username=%s", account.id, platform, username)
    return account


async def get_all_accounts(db: AsyncSession) -> List[Account]:
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    return list(result.scalars().all())


async def get_account_by_id(db: AsyncSession, account_id: int) -> Optional[Account]:
    result = await db.execute(select(Account).where(Account.id == account_id))
    return result.scalar_one_or_none()


async def get_accounts_by_platform(db: AsyncSession, platform: str) -> List[Account]:
    result = await db.execute(
        select(Account).where(Account.platform == platform).order_by(Account.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_account(db: AsyncSession, account_id: int) -> bool:
    result = await db.execute(delete(Account).where(Account.id == account_id))
    await db.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info("Deleted account id=%s", account_id)
    return deleted


async def update_account_status(
    db: AsyncSession, account_id: int, status: str
) -> Optional[Account]:
    account = await get_account_by_id(db, account_id)
    if not account:
        return None
    account.status = status
    await db.commit()
    await db.refresh(account)
    logger.info("Updated account id=%s status=%s", account_id, status)
    return account
