"""АИ-помощник на базе Claude с tool calling для управления панелью.

Использует Replit AI Integrations прокси (env vars автоматически).
"""
import os
import json
import logging
from typing import Any, Generator

from anthropic import Anthropic

from utils import api_client

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """Ты — АИ-помощник второго пилота в платформе AutoPilot для управления
SMM-аккаунтами в TikTok, Instagram и YouTube. Общайся на русском, кратко и дружелюбно.

Ты можешь:
• смотреть статистику и список аккаунтов
• добавлять и удалять аккаунты
• планировать публикации (контент-план)
• писать тексты постов и подбирать хэштеги
• давать идеи контента и стратегические советы

Используй инструменты когда нужно реальное действие. Перед удалением аккаунтов или
постов всегда подтверждай у пользователя. Если просят сгенерировать текст —
делай это сам без инструментов. Когда показываешь данные из инструмента, форматируй
красиво (списки, таблицы), не вываливай сырой JSON.
"""

TOOLS = [
    {
        "name": "list_accounts",
        "description": "Получить список всех подключённых аккаунтов (id, платформа, username, статус).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_stats",
        "description": "Получить общую статистику: всего аккаунтов, по статусам, по платформам.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_account",
        "description": "Добавить новый аккаунт в систему.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["tiktok", "instagram", "youtube"]},
                "username": {"type": "string"},
                "auth_type": {"type": "string", "enum": ["cookies", "login_password"]},
                "session_data": {"type": "string", "description": "Cookies JSON или login:password"},
            },
            "required": ["platform", "username", "auth_type"],
        },
    },
    {
        "name": "delete_account",
        "description": "Удалить аккаунт по ID. Перед вызовом обязательно подтвердить у пользователя.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "integer"}},
            "required": ["account_id"],
        },
    },
    {
        "name": "list_posts",
        "description": "Получить список запланированных/опубликованных постов.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "Опционально — фильтр по аккаунту"},
                "status_filter": {
                    "type": "string",
                    "enum": ["scheduled", "publishing", "published", "failed", "cancelled"],
                },
            },
        },
    },
    {
        "name": "schedule_post",
        "description": (
            "Запланировать публикацию для одного или нескольких аккаунтов. "
            "scheduled_at в формате ISO 'YYYY-MM-DDTHH:MM:SS'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account_ids": {"type": "array", "items": {"type": "integer"}},
                "scheduled_at": {"type": "string"},
                "caption": {"type": "string"},
                "hashtags": {"type": "string"},
                "media_path": {"type": "string", "description": "Путь к ранее загруженному файлу"},
                "media_kind": {"type": "string", "enum": ["video", "image", "reels", "story"]},
            },
            "required": ["account_ids", "scheduled_at"],
        },
    },
    {
        "name": "delete_post",
        "description": "Удалить запланированный пост. Подтвердить у пользователя.",
        "input_schema": {
            "type": "object",
            "properties": {"post_id": {"type": "integer"}},
            "required": ["post_id"],
        },
    },
    {
        "name": "run_post_now",
        "description": "Запустить публикацию поста немедленно, не ждать времени из расписания.",
        "input_schema": {
            "type": "object",
            "properties": {"post_id": {"type": "integer"}},
            "required": ["post_id"],
        },
    },
]


def _execute_tool(name: str, args: dict) -> Any:
    """Выполнить вызов инструмента и вернуть результат."""
    try:
        if name == "list_accounts":
            data = api_client.get_accounts() or []
            return [{"id": a.get("id"), "platform": a.get("platform"),
                     "username": a.get("username"), "status": a.get("status"),
                     "auth_type": a.get("auth_type"), "has_session": a.get("has_session")}
                    for a in data if isinstance(a, dict)]
        if name == "get_stats":
            return api_client.get_stats() or {}
        if name == "add_account":
            return api_client.add_account(
                platform=args["platform"], username=args["username"],
                auth_type=args["auth_type"], session_data=args.get("session_data", ""))
        if name == "delete_account":
            return api_client.delete_account(int(args["account_id"]))
        if name == "list_posts":
            return api_client.list_posts(
                account_id=args.get("account_id"),
                status_filter=args.get("status_filter"))
        if name == "schedule_post":
            return api_client.create_posts(
                account_ids=args["account_ids"],
                scheduled_at=args["scheduled_at"],
                caption=args.get("caption", ""),
                hashtags=args.get("hashtags", ""),
                media_path=args.get("media_path"),
                media_kind=args.get("media_kind", "video"))
        if name == "delete_post":
            return api_client.delete_post(int(args["post_id"]))
        if name == "run_post_now":
            return api_client.run_post_now(int(args["post_id"]))
        return {"error": f"Неизвестный инструмент: {name}"}
    except Exception as e:
        logger.exception("Tool error: %s", name)
        return {"error": str(e)}


def get_client() -> Anthropic:
    base_url = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
    api_key = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("AI Integrations не настроены: нет AI_INTEGRATIONS_ANTHROPIC_*")
    return Anthropic(base_url=base_url, api_key=api_key)


def chat(messages: list[dict]) -> Generator[dict, None, None]:
    """Главный цикл агента: вызывает Claude, при необходимости — инструменты,
    повторяет до финального ответа.

    Yields events:
      {"type": "text", "text": str}
      {"type": "tool_use", "name": str, "input": dict}
      {"type": "tool_result", "name": str, "result": Any}
      {"type": "done", "messages": list}  — обновлённая история
    """
    client = get_client()
    history = list(messages)

    # До 6 итераций tool-use
    for _iteration in range(6):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )

        # Сохраняем ответ ассистента в историю
        assistant_blocks = []
        text_parts = []
        tool_calls = []

        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
                assistant_blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_calls.append(block)
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        history.append({"role": "assistant", "content": assistant_blocks})

        if text_parts:
            yield {"type": "text", "text": "\n".join(text_parts)}

        if resp.stop_reason != "tool_use" or not tool_calls:
            yield {"type": "done", "messages": history}
            return

        # Выполняем инструменты и добавляем tool_result
        tool_results_block = []
        for tc in tool_calls:
            yield {"type": "tool_use", "name": tc.name, "input": tc.input}
            result = _execute_tool(tc.name, tc.input)
            yield {"type": "tool_result", "name": tc.name, "result": result}
            tool_results_block.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        history.append({"role": "user", "content": tool_results_block})

    yield {"type": "done", "messages": history}
