"""HTTP client for Social Media Bot FastAPI backend."""
import requests
from typing import Any, Dict, List, Optional

BOT_API_BASE = "http://localhost:3000/api"
TIMEOUT = 8


def _get(path: str) -> Any:
    try:
        r = requests.get(f"{BOT_API_BASE}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return {"error": str(e)}


def _post(path: str, data: Dict) -> Any:
    try:
        r = requests.post(f"{BOT_API_BASE}{path}", json=data, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return {"error": str(e)}


def _delete(path: str) -> Any:
    try:
        r = requests.delete(f"{BOT_API_BASE}{path}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return {"error": str(e)}


def get_accounts() -> Optional[List[Dict]]:
    return _get("/accounts/list")


def get_stats() -> Optional[Dict]:
    return _get("/stats/summary")


def add_account(platform: str, username: str, auth_type: str, session_data: str = "") -> Any:
    payload = {
        "platform": platform,
        "username": username,
        "auth_type": auth_type,
        "session_data": session_data or None,
    }
    return _post("/accounts/add", payload)


def delete_account(account_id: int) -> Any:
    return _delete(f"/accounts/{account_id}")


def is_bot_online() -> bool:
    try:
        r = requests.get("http://localhost:3000/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
