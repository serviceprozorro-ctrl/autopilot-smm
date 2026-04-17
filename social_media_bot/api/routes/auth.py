"""Авторизация: регистрация по email/паролю и Google OAuth."""
import os
import re
import time
import secrets
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db as get_session
from db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT secret из env (SESSION_SECRET) или дефолт для dev
JWT_SECRET = os.environ.get("SESSION_SECRET") or "dev-secret-change-me"
JWT_ALG = "HS256"
TOKEN_TTL_DAYS = 30


# ── Schemas ────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    google_id: str
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None
    avatar_url: str | None
    role: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ── Helpers ────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def make_token(user_id: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + TOKEN_TTL_DAYS * 86400,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except Exception:
        return None


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нет токена")
    token = authorization.split(" ", 1)[1].strip()
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невалидный токен")
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден")
    return user


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    email = req.email.lower().strip()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Пользователь с таким email уже существует")

    user = User(
        email=email,
        name=req.name or email.split("@")[0],
        password_hash=hash_password(req.password),
        role="admin" if (await _is_first_user(session)) else "user",
        last_login_at=datetime.utcnow(),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return AuthResponse(token=make_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    email = req.email.lower().strip()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Аккаунт отключён")
    user.last_login_at = datetime.utcnow()
    await session.commit()
    return AuthResponse(token=make_token(user.id), user=UserOut.model_validate(user))


@router.post("/google", response_model=AuthResponse)
async def google_login(
    req: GoogleLoginRequest,
    x_internal_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Принимает уже верифицированные данные пользователя Google от Streamlit OIDC.
    Защищён shared-secret — вызов разрешён только из доверенной серверной части,
    т.к. Streamlit сам валидирует ID-токен Google на стороне сервера."""
    if not x_internal_secret or x_internal_secret != JWT_SECRET:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Запрещено")
    email = req.email.lower().strip()
    # Ищем сначала по google_id, потом по email
    user = (await session.execute(
        select(User).where(User.google_id == req.google_id)
    )).scalar_one_or_none()
    if not user:
        user = (await session.execute(
            select(User).where(User.email == email)
        )).scalar_one_or_none()

    if user:
        # Привязываем google_id если ещё нет
        if not user.google_id:
            user.google_id = req.google_id
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        user.last_login_at = datetime.utcnow()
    else:
        user = User(
            email=email,
            name=req.name or email.split("@")[0],
            google_id=req.google_id,
            avatar_url=req.avatar_url,
            role="admin" if (await _is_first_user(session)) else "user",
            last_login_at=datetime.utcnow(),
        )
        session.add(user)

    await session.commit()
    await session.refresh(user)
    return AuthResponse(token=make_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


async def _is_first_user(session: AsyncSession) -> bool:
    from sqlalchemy import func as sa_func
    cnt = (await session.execute(select(sa_func.count(User.id)))).scalar()
    return (cnt or 0) == 0
