import base64
import json
import logging
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key_bytes = settings.secret_key.encode()
    # Pad or truncate to 32 bytes, then base64-encode for Fernet
    key_32 = key_bytes[:32].ljust(32, b"0")
    fernet_key = base64.urlsafe_b64encode(key_32)
    return Fernet(fernet_key)


def encrypt_session_data(data: Dict[str, Any]) -> str:
    """Encrypt session data (cookies/tokens) before storing."""
    try:
        fernet = _get_fernet()
        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        encrypted = fernet.encrypt(json_bytes)
        return encrypted.decode("utf-8")
    except Exception as exc:
        logger.error("Failed to encrypt session data: %s", exc)
        raise


def decrypt_session_data(encrypted: str) -> Optional[Dict[str, Any]]:
    """Decrypt session data retrieved from the database."""
    try:
        fernet = _get_fernet()
        decrypted_bytes = fernet.decrypt(encrypted.encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))
    except InvalidToken:
        logger.error("Invalid token when decrypting session data")
        return None
    except Exception as exc:
        logger.error("Failed to decrypt session data: %s", exc)
        return None


def validate_cookies_json(raw: str) -> Optional[Dict[str, Any]]:
    """Validate that the provided string is valid JSON (cookies dict)."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except json.JSONDecodeError:
        return None
