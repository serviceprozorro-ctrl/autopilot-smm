import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Account

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", summary="Get accounts statistics summary")
async def get_stats_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    total_result = await db.execute(select(func.count(Account.id)))
    total = total_result.scalar() or 0

    by_platform_result = await db.execute(
        select(Account.platform, func.count(Account.id)).group_by(Account.platform)
    )
    by_platform = {row[0]: row[1] for row in by_platform_result.all()}

    by_status_result = await db.execute(
        select(Account.status, func.count(Account.id)).group_by(Account.status)
    )
    by_status = {row[0]: row[1] for row in by_status_result.all()}

    return {
        "total_accounts": total,
        "by_platform": {
            "tiktok": by_platform.get("tiktok", 0),
            "instagram": by_platform.get("instagram", 0),
            "youtube": by_platform.get("youtube", 0),
        },
        "by_status": {
            "active": by_status.get("active", 0),
            "banned": by_status.get("banned", 0),
            "inactive": by_status.get("inactive", 0),
        },
        "automation_enabled": False,
        "scheduled_posts": 0,
    }
