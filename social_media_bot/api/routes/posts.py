"""API для запланированных публикаций (контент-плана)."""
import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import Account, ScheduledPost, PostStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])

MEDIA_DIR = Path(__file__).resolve().parents[2] / "uploads"
MEDIA_DIR.mkdir(exist_ok=True)


class ScheduledPostResponse(BaseModel):
    id: int
    account_id: int
    platform: str
    username: Optional[str] = None
    media_path: Optional[str] = None
    media_kind: str
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    scheduled_at: datetime
    status: str
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    extra_options: Optional[dict] = None

    model_config = {"from_attributes": True}


class CreatePostRequest(BaseModel):
    account_ids: List[int]
    scheduled_at: datetime
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    media_path: Optional[str] = None
    media_kind: str = "video"
    extra_options: Optional[dict] = None

    @field_validator("account_ids")
    @classmethod
    def _at_least_one(cls, v):
        if not v:
            raise ValueError("Нужен хотя бы один account_id")
        return v


class UpdatePostRequest(BaseModel):
    scheduled_at: Optional[datetime] = None
    caption: Optional[str] = None
    hashtags: Optional[str] = None
    media_path: Optional[str] = None
    media_kind: Optional[str] = None
    status: Optional[str] = None


def _to_response(post: ScheduledPost, username: Optional[str] = None) -> ScheduledPostResponse:
    extras = None
    if post.extra_options:
        try:
            extras = json.loads(post.extra_options)
        except Exception:
            extras = None
    return ScheduledPostResponse(
        id=post.id,
        account_id=post.account_id,
        platform=post.platform,
        username=username,
        media_path=post.media_path,
        media_kind=post.media_kind,
        caption=post.caption,
        hashtags=post.hashtags,
        scheduled_at=post.scheduled_at,
        status=post.status,
        error_message=post.error_message,
        published_at=post.published_at,
        extra_options=extras,
    )


@router.post("/upload", summary="Загрузить медиафайл для публикаций")
async def upload_media(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(400, "Файл без имени")
    ext = Path(file.filename).suffix.lower() or ""
    if ext not in {".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        raise HTTPException(400, f"Неподдерживаемый формат: {ext}")
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = MEDIA_DIR / fname
    with fpath.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    size = fpath.stat().st_size
    return {
        "media_path": str(fpath),
        "filename": file.filename,
        "size": size,
        "kind": "video" if ext in {".mp4", ".mov", ".m4v", ".webm"} else "image",
    }


@router.post("/", response_model=List[ScheduledPostResponse], status_code=201,
             summary="Создать публикации (одну или сразу для нескольких аккаунтов)")
async def create_posts(
    payload: CreatePostRequest,
    db: AsyncSession = Depends(get_db),
) -> List[ScheduledPostResponse]:
    # Получаем аккаунты
    acc_stmt = select(Account).where(Account.id.in_(payload.account_ids))
    res = await db.execute(acc_stmt)
    accounts = res.scalars().all()
    if not accounts:
        raise HTTPException(404, "Ни один из указанных аккаунтов не найден")
    by_id = {a.id: a for a in accounts}

    # Нормализуем дату в UTC
    sched = payload.scheduled_at
    if sched.tzinfo is None:
        sched = sched.replace(tzinfo=timezone.utc)

    extras_json = json.dumps(payload.extra_options) if payload.extra_options else None

    created: List[ScheduledPost] = []
    for acc_id in payload.account_ids:
        acc = by_id.get(acc_id)
        if not acc:
            continue
        post = ScheduledPost(
            account_id=acc.id,
            platform=acc.platform,
            media_path=payload.media_path,
            media_kind=payload.media_kind,
            caption=payload.caption,
            hashtags=payload.hashtags,
            scheduled_at=sched,
            status=PostStatus.SCHEDULED,
            extra_options=extras_json,
        )
        db.add(post)
        created.append(post)

    await db.commit()
    for p in created:
        await db.refresh(p)

    return [_to_response(p, by_id[p.account_id].username) for p in created]


@router.get("/", response_model=List[ScheduledPostResponse], summary="Список запланированных публикаций")
async def list_posts(
    account_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
) -> List[ScheduledPostResponse]:
    stmt = select(ScheduledPost).order_by(ScheduledPost.scheduled_at.asc()).limit(limit)
    if account_id:
        stmt = stmt.where(ScheduledPost.account_id == account_id)
    if status_filter:
        stmt = stmt.where(ScheduledPost.status == status_filter)
    res = await db.execute(stmt)
    posts = res.scalars().all()

    # Подтягиваем usernames
    if posts:
        acc_ids = list({p.account_id for p in posts})
        acc_res = await db.execute(select(Account).where(Account.id.in_(acc_ids)))
        accounts = {a.id: a for a in acc_res.scalars().all()}
    else:
        accounts = {}

    return [_to_response(p, accounts.get(p.account_id).username if accounts.get(p.account_id) else None)
            for p in posts]


@router.patch("/{post_id}", response_model=ScheduledPostResponse, summary="Обновить публикацию")
async def update_post(
    post_id: int,
    payload: UpdatePostRequest,
    db: AsyncSession = Depends(get_db),
) -> ScheduledPostResponse:
    res = await db.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, f"Пост #{post_id} не найден")

    if payload.scheduled_at is not None:
        sched = payload.scheduled_at
        if sched.tzinfo is None:
            sched = sched.replace(tzinfo=timezone.utc)
        post.scheduled_at = sched
    if payload.caption is not None:
        post.caption = payload.caption
    if payload.hashtags is not None:
        post.hashtags = payload.hashtags
    if payload.media_path is not None:
        post.media_path = payload.media_path
    if payload.media_kind is not None:
        post.media_kind = payload.media_kind
    if payload.status is not None:
        post.status = payload.status

    await db.commit()
    await db.refresh(post)

    acc_res = await db.execute(select(Account).where(Account.id == post.account_id))
    acc = acc_res.scalar_one_or_none()
    return _to_response(post, acc.username if acc else None)


@router.delete("/{post_id}", summary="Удалить публикацию")
async def delete_post(post_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    res = await db.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, f"Пост #{post_id} не найден")
    await db.delete(post)
    await db.commit()
    return {"success": True, "id": post_id}


@router.post("/{post_id}/run-now", response_model=ScheduledPostResponse,
             summary="Опубликовать прямо сейчас (помещает в очередь немедленно)")
async def run_post_now(post_id: int, db: AsyncSession = Depends(get_db)) -> ScheduledPostResponse:
    res = await db.execute(select(ScheduledPost).where(ScheduledPost.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, f"Пост #{post_id} не найден")
    post.scheduled_at = datetime.now(timezone.utc)
    post.status = PostStatus.SCHEDULED
    post.error_message = None
    await db.commit()
    await db.refresh(post)
    acc_res = await db.execute(select(Account).where(Account.id == post.account_id))
    acc = acc_res.scalar_one_or_none()
    return _to_response(post, acc.username if acc else None)
