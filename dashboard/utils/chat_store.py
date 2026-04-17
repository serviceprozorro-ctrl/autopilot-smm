"""Хранилище истории чатов и проектов для АИ-помощника (JSON-файл)."""
import json
import uuid
from pathlib import Path
from datetime import datetime
from threading import Lock

STORE_PATH = Path(__file__).parent.parent / "data" / "agent_store.json"
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = Lock()


def _load() -> dict:
    if not STORE_PATH.exists():
        return {"projects": [], "chats": []}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"projects": [], "chats": []}


def _save(data: dict) -> None:
    STORE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


# ── Проекты ─────────────────────────────────────────────────────────────────
def list_projects() -> list[dict]:
    return _load().get("projects", [])


def create_project(name: str, color: str = "#6366f1",
                   instructions: str = "") -> dict:
    with _lock:
        data = _load()
        proj = {
            "id": uuid.uuid4().hex[:8],
            "name": name.strip() or "Без имени",
            "color": color,
            "instructions": instructions.strip(),
            "created_at": datetime.utcnow().isoformat(),
        }
        data["projects"].append(proj)
        _save(data)
        return proj


def delete_project(project_id: str) -> None:
    with _lock:
        data = _load()
        data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
        # чаты проекта переносим в "Без проекта"
        for c in data["chats"]:
            if c.get("project_id") == project_id:
                c["project_id"] = None
        _save(data)


def get_project(project_id: str | None) -> dict | None:
    if not project_id:
        return None
    for p in _load().get("projects", []):
        if p["id"] == project_id:
            return p
    return None


# ── Чаты ────────────────────────────────────────────────────────────────────
def list_chats(project_id: str | None = "__any__") -> list[dict]:
    """project_id="__any__" — все. None — без проекта."""
    chats = _load().get("chats", [])
    if project_id != "__any__":
        chats = [c for c in chats if c.get("project_id") == project_id]
    chats.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return chats


def get_chat(chat_id: str) -> dict | None:
    for c in _load().get("chats", []):
        if c["id"] == chat_id:
            return c
    return None


def create_chat(project_id: str | None = None, title: str = "Новый чат") -> dict:
    with _lock:
        data = _load()
        now = datetime.utcnow().isoformat()
        chat = {
            "id": uuid.uuid4().hex[:10],
            "title": title,
            "project_id": project_id,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "display": [],
        }
        data["chats"].append(chat)
        _save(data)
        return chat


def save_chat(chat_id: str, messages: list, display: list,
              title: str | None = None,
              project_id: str | None = "__keep__") -> None:
    with _lock:
        data = _load()
        for c in data["chats"]:
            if c["id"] == chat_id:
                c["messages"] = messages
                c["display"] = display
                c["updated_at"] = datetime.utcnow().isoformat()
                if title:
                    c["title"] = title[:80]
                if project_id != "__keep__":
                    c["project_id"] = project_id
                _save(data)
                return


def delete_chat(chat_id: str) -> None:
    with _lock:
        data = _load()
        data["chats"] = [c for c in data["chats"] if c["id"] != chat_id]
        _save(data)


def auto_title(text: str) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= 60:
        return text
    return text[:57] + "…"
