"""Settings API — save bot token, reload config, restart bot."""
import asyncio
import logging
import os
import re
import signal
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


# ── helpers ──────────────────────────────────────────────────────────────────

def _mask(token: str) -> str:
    if not token or len(token) < 10:
        return "***"
    return token[:6] + "…" + token[-4:]


def _read_env() -> dict[str, str]:
    """Return all key=value pairs from .env file."""
    result: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _write_env(data: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in data.items()]
    ENV_PATH.write_text("\n".join(lines) + "\n")


async def _validate_token(token: str) -> dict:
    """Call Telegram getMe to verify a token."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
            data = r.json()
            if data.get("ok"):
                return {"ok": True, "bot": data["result"]}
            return {"ok": False, "description": data.get("description", "Invalid token")}
    except Exception as e:
        return {"ok": False, "description": str(e)}


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
async def get_settings():
    """Return current settings (token is masked)."""
    from config import settings as cfg

    env = _read_env()
    raw_token = env.get("TELEGRAM_BOT_TOKEN") or cfg.telegram_bot_token
    has_token = bool(raw_token)

    bot_info = None
    if has_token:
        result = await _validate_token(raw_token)
        if result["ok"]:
            bot_info = result["bot"]

    return {
        "has_token": has_token,
        "token_masked": _mask(raw_token) if has_token else None,
        "bot_info": bot_info,
        "api_url": "http://localhost:3000",
        "db_url": cfg.bot_database_url,
    }


class SaveSettingsRequest(BaseModel):
    token: str


@router.post("/validate")
async def validate_token(req: SaveSettingsRequest):
    """Check if a token is valid WITHOUT saving it."""
    result = await _validate_token(req.token.strip())
    return result


@router.post("")
async def save_settings(req: SaveSettingsRequest):
    """Save token to .env file, then restart process so bot picks it up."""
    token = req.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token cannot be empty")

    # Validate before saving
    result = await _validate_token(token)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("description", "Invalid token"))

    # Write to .env
    env = _read_env()
    env["TELEGRAM_BOT_TOKEN"] = token
    _write_env(env)

    # Also update os.environ so sub-processes see it immediately
    os.environ["TELEGRAM_BOT_TOKEN"] = token

    logger.info("Token saved to .env — scheduling restart in 2 s")

    # Restart: send SIGTERM to self; workflow manager will restart
    async def _deferred_restart():
        await asyncio.sleep(2)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_deferred_restart())

    return {
        "ok": True,
        "message": "Token saved. Bot is restarting…",
        "bot_info": result.get("bot"),
    }
