"""API для аналитики аккаунтов: снимки статистики и история."""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Account, AccountStatsSnapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


class StatsSnapshotResponse(BaseModel):
    id: int
    account_id: int
    followers: int
    following: int
    posts_count: int
    likes_total: int
    avg_views: int
    engagement_rate: float
    captured_at: str


class AccountStatsResponse(BaseModel):
    account_id: int
    platform: str
    username: str
    latest: Optional[StatsSnapshotResponse]
    history: List[StatsSnapshotResponse]
    growth_followers_7d: int
    growth_followers_30d: int


def _to_resp(s: AccountStatsSnapshot) -> StatsSnapshotResponse:
    return StatsSnapshotResponse(
        id=s.id, account_id=s.account_id, followers=s.followers,
        following=s.following, posts_count=s.posts_count,
        likes_total=s.likes_total, avg_views=s.avg_views,
        engagement_rate=s.engagement_rate,
        captured_at=s.captured_at.isoformat() if s.captured_at else "",
    )


@router.get("/account/{account_id}", response_model=AccountStatsResponse)
async def get_account_analytics(account_id: int, db: AsyncSession = Depends(get_db)):
    acc = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not acc:
        raise HTTPException(404, "Аккаунт не найден")

    snaps = (await db.execute(
        select(AccountStatsSnapshot)
        .where(AccountStatsSnapshot.account_id == account_id)
        .order_by(desc(AccountStatsSnapshot.captured_at))
        .limit(60)
    )).scalars().all()

    latest = _to_resp(snaps[0]) if snaps else None
    now = datetime.utcnow()

    def _growth(days: int) -> int:
        if not snaps:
            return 0
        target = now - timedelta(days=days)
        old = next(
            (s for s in snaps if s.captured_at and s.captured_at.replace(tzinfo=None) <= target),
            snaps[-1],
        )
        return (snaps[0].followers - old.followers) if old else 0

    return AccountStatsResponse(
        account_id=account_id, platform=acc.platform, username=acc.username,
        latest=latest, history=[_to_resp(s) for s in snaps],
        growth_followers_7d=_growth(7), growth_followers_30d=_growth(30),
    )


class CreateSnapshotRequest(BaseModel):
    account_id: int
    followers: int = 0
    following: int = 0
    posts_count: int = 0
    likes_total: int = 0
    avg_views: int = 0
    engagement_rate: float = 0.0
    raw_data: Optional[dict] = None


@router.post("/snapshot", response_model=StatsSnapshotResponse)
async def create_snapshot(payload: CreateSnapshotRequest, db: AsyncSession = Depends(get_db)):
    acc = (await db.execute(select(Account).where(Account.id == payload.account_id))).scalar_one_or_none()
    if not acc:
        raise HTTPException(404, "Аккаунт не найден")

    snap = AccountStatsSnapshot(
        account_id=payload.account_id, followers=payload.followers,
        following=payload.following, posts_count=payload.posts_count,
        likes_total=payload.likes_total, avg_views=payload.avg_views,
        engagement_rate=payload.engagement_rate,
        raw_data=json.dumps(payload.raw_data, ensure_ascii=False) if payload.raw_data else None,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return _to_resp(snap)


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    """Общая аналитика по всем аккаунтам — последний снимок каждого."""
    accounts = (await db.execute(select(Account))).scalars().all()
    result = []
    total_followers = 0
    for acc in accounts:
        latest = (await db.execute(
            select(AccountStatsSnapshot)
            .where(AccountStatsSnapshot.account_id == acc.id)
            .order_by(desc(AccountStatsSnapshot.captured_at))
            .limit(1)
        )).scalar_one_or_none()
        followers = latest.followers if latest else 0
        total_followers += followers
        result.append({
            "account_id": acc.id, "platform": acc.platform, "username": acc.username,
            "followers": followers,
            "posts_count": latest.posts_count if latest else 0,
            "engagement_rate": latest.engagement_rate if latest else 0.0,
            "last_update": latest.captured_at.isoformat() if latest else None,
        })
    return {
        "total_followers": total_followers,
        "total_accounts": len(accounts),
        "accounts": result,
    }
