"""Фоновый планировщик публикаций.

Работает поверх APScheduler в asyncio. Каждые 30 секунд опрашивает БД и
запускает публикации, у которых scheduled_at <= now().
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import Account, ScheduledPost, PostStatus
from core.posting.executors import PublishRequest, get_executor

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


async def _process_due_posts() -> None:
    """Берёт все запланированные посты, у которых время пришло, и публикует их."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(ScheduledPost).where(
                ScheduledPost.status == PostStatus.SCHEDULED,
                ScheduledPost.scheduled_at <= now,
            ).limit(20)
            result = await db.execute(stmt)
            due_posts = result.scalars().all()

            if not due_posts:
                return

            logger.info("[Scheduler] Найдено %d пост(ов) к публикации", len(due_posts))

            for post in due_posts:
                # Помечаем как PUBLISHING сразу, чтобы не подхватить дважды
                post.status = PostStatus.PUBLISHING
                await db.commit()

                # Получаем аккаунт
                acc_stmt = select(Account).where(Account.id == post.account_id)
                acc_res = await db.execute(acc_stmt)
                account = acc_res.scalar_one_or_none()

                if not account:
                    post.status = PostStatus.FAILED
                    post.error_message = f"Аккаунт #{post.account_id} не найден"
                    await db.commit()
                    continue

                req = PublishRequest(
                    account_id=account.id,
                    platform=account.platform,
                    username=account.username,
                    session_data=account.session_data,
                    media_path=post.media_path,
                    media_kind=post.media_kind,
                    caption=post.caption,
                    hashtags=post.hashtags,
                )

                try:
                    executor = get_executor(account.platform)
                    res = await executor.publish(req)
                    if res.success:
                        post.status = PostStatus.PUBLISHED
                        post.published_at = datetime.now(timezone.utc)
                        post.error_message = None
                    else:
                        post.status = PostStatus.FAILED
                        post.error_message = res.error or "Неизвестная ошибка"
                except Exception as e:
                    logger.exception("Ошибка публикации поста #%s", post.id)
                    post.status = PostStatus.FAILED
                    post.error_message = str(e)
                finally:
                    await db.commit()
        except Exception:
            logger.exception("[Scheduler] Ошибка в _process_due_posts")
            await db.rollback()


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _process_due_posts,
        trigger="interval",
        seconds=30,
        id="process_due_posts",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("[Scheduler] Планировщик публикаций запущен (опрос каждые 30 сек)")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Планировщик остановлен")
        _scheduler = None
