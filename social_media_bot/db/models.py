from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Integer, String, Text, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Platform(str, PyEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class AuthType(str, PyEnum):
    COOKIES = "cookies"
    LOGIN_PASSWORD = "login_password"
    QR_CODE = "qr_code"
    API = "api"


class AccountStatus(str, PyEnum):
    ACTIVE = "active"
    BANNED = "banned"
    INACTIVE = "inactive"
    PENDING = "pending"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default=AuthType.COOKIES)
    session_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} platform={self.platform} username={self.username}>"


class PostStatus(str, PyEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="video")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=PostStatus.SCHEDULED, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ScheduledPost id={self.id} acc={self.account_id} at={self.scheduled_at} status={self.status}>"


class PortfolioItem(Base):
    """Образ/фото для визуальной идентичности аккаунта или бренда."""
    __tablename__ = "portfolio_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Образ")
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="upload")  # upload|grok|profile
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0..10
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # для вариаций
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PortfolioItem id={self.id} title={self.title}>"


class AccountStatsSnapshot(Base):
    """Снимок статистики аккаунта на момент времени."""
    __tablename__ = "account_stats_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    followers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    following: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    def __repr__(self) -> str:
        return f"<Stats acc={self.account_id} followers={self.followers}>"


class User(Base):
    """Пользователь панели управления (email/пароль или Google OAuth)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")  # user|admin
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
