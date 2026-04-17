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


def list_posts(account_id: int = None, status_filter: str = None) -> Any:
    params = []
    if account_id:
        params.append(f"account_id={account_id}")
    if status_filter:
        params.append(f"status_filter={status_filter}")
    qs = "?" + "&".join(params) if params else ""
    return _get(f"/posts/{qs}")


def create_posts(account_ids: list, scheduled_at: str, caption: str = "",
                 hashtags: str = "", media_path: str = None,
                 media_kind: str = "video", extra_options: dict = None) -> Any:
    payload = {
        "account_ids": account_ids,
        "scheduled_at": scheduled_at,
        "caption": caption or None,
        "hashtags": hashtags or None,
        "media_path": media_path,
        "media_kind": media_kind,
        "extra_options": extra_options,
    }
    return _post("/posts/", payload)


def update_post(post_id: int, **fields) -> Any:
    try:
        r = requests.patch(f"{BOT_API_BASE}/posts/{post_id}", json=fields, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return {"error": str(e)}


def delete_post(post_id: int) -> Any:
    return _delete(f"/posts/{post_id}")


def run_post_now(post_id: int) -> Any:
    return _post(f"/posts/{post_id}/run-now", {})


def upload_media(file_bytes: bytes, filename: str) -> Any:
    try:
        files = {"file": (filename, file_bytes)}
        r = requests.post(f"{BOT_API_BASE}/posts/upload", files=files, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return {"error": str(e)}


def is_bot_online() -> bool:
    try:
        r = requests.get("http://localhost:3000/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
