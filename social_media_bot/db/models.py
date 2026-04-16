from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Platform(str, PyEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class AuthType(str, PyEnum):
    COOKIES = "cookies"
    API = "api"


class AccountStatus(str, PyEnum):
    ACTIVE = "active"
    BANNED = "banned"
    INACTIVE = "inactive"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default=AuthType.COOKIES)
    session_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=AccountStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} platform={self.platform} username={self.username}>"
