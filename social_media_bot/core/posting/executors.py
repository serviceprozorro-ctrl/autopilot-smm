"""Платформенные исполнители публикаций.

Каркас для Playwright-автоматизации. Сейчас работает в режиме «эмуляции» —
имитирует открытие браузера, загрузку, проверку и помечает пост как опубликованный.
Реальные Playwright-сценарии добавляются точечно в каждый из методов publish_*.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Включить реальный Playwright можно установкой переменной окружения
USE_REAL_PLAYWRIGHT = os.environ.get("USE_REAL_PLAYWRIGHT", "0") == "1"


@dataclass
class PublishRequest:
    account_id: int
    platform: str
    username: str
    session_data: Optional[str]
    media_path: Optional[str]
    media_kind: str  # video|image|reels|story
    caption: Optional[str]
    hashtags: Optional[str]


@dataclass
class PublishResult:
    success: bool
    external_id: Optional[str] = None
    error: Optional[str] = None


class BaseExecutor:
    platform: str = "base"

    async def publish(self, req: PublishRequest) -> PublishResult:
        if USE_REAL_PLAYWRIGHT:
            return await self._publish_real(req)
        return await self._publish_simulated(req)

    async def _publish_simulated(self, req: PublishRequest) -> PublishResult:
        logger.info("[%s] [SIM] Публикация для @%s: media=%s caption=%r",
                    self.platform, req.username, req.media_path,
                    (req.caption or "")[:50])
        # Имитируем работу: открытие браузера, авторизацию, загрузку
        await asyncio.sleep(1.0)
        if not req.session_data and not req.media_path:
            return PublishResult(success=False, error="Нет ни сессии, ни медиа — не могу публиковать")
        # Эмулируем успех
        external_id = f"sim_{self.platform}_{req.account_id}_{int(asyncio.get_event_loop().time())}"
        logger.info("[%s] [SIM] ✅ Опубликовано, external_id=%s", self.platform, external_id)
        return PublishResult(success=True, external_id=external_id)

    async def _publish_real(self, req: PublishRequest) -> PublishResult:
        # Сюда подключается реальный Playwright-сценарий конкретной платформы
        raise NotImplementedError(f"Real Playwright executor for {self.platform} not implemented yet")


class TikTokExecutor(BaseExecutor):
    platform = "tiktok"


class InstagramExecutor(BaseExecutor):
    platform = "instagram"


class YouTubeExecutor(BaseExecutor):
    platform = "youtube"


def get_executor(platform: str) -> BaseExecutor:
    return {
        "tiktok": TikTokExecutor(),
        "instagram": InstagramExecutor(),
        "youtube": YouTubeExecutor(),
    }.get(platform, BaseExecutor())
