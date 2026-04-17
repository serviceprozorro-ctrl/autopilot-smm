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
• смотреть статистику, аналитику и список аккаунтов
• добавлять и удалять аккаунты
• планировать публикации (контент-план)
• писать тексты постов и подбирать хэштеги
• давать идеи контента и стратегические советы
• отправлять уведомления админу через Telegram-бота
• искать информацию в интернете
• анализировать прикреплённые пользователем фото и видео

ИНТЕРАКТИВНЫЕ ВАРИАНТЫ ОТВЕТА:
Когда нужно уточнить выбор у пользователя или предложить несколько направлений
работы — оформляй варианты в специальном блоке в КОНЦЕ сообщения:

<options multi="true">
- Сделать пост в TikTok
- Запустить рекламу
- Проанализировать конкурентов
</options>

multi="true" — пользователь может выбрать несколько вариантов;
multi="false" — только один. Всегда давай 2–6 коротких вариантов (до 60 символов).
Не используй блок если уточнение не нужно.

Когда пользователь прикрепил файл (фото/видео) — путь приходит в его сообщении
как "Прикреплён файл: …". Используй analyze_image для разбора фото.
Когда пользователь дал ссылку — используй fetch_url чтобы прочитать содержимое.

Используй инструменты только когда нужно реальное действие или данные.
Перед удалением аккаунтов или постов всегда подтверждай. Когда показываешь
данные — форматируй красиво (списки, таблицы), не вываливай сырой JSON.
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
    {
        "name": "analytics_overview",
        "description": "Аналитика: подписчики/посты/ER по всем аккаунтам (последний снимок).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_telegram_notification",
        "description": (
            "Отправить уведомление админу через Telegram-бота. Используй для "
            "напоминаний, отчётов, уведомлений о готовности контента."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Текст сообщения (поддерживает Markdown)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Загрузить содержимое страницы по URL и вернуть очищенный текст. "
            "Используй для анализа конкурентов, статей, новостей."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Поиск в интернете через Grok (xAI) с актуальными данными. "
            "Используй для свежих трендов, новостей, информации о людях/компаниях."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "analyze_image",
        "description": (
            "Анализ прикреплённого изображения: что на фото, качество, идеи "
            "для контента, описание для поста."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Путь к загруженному файлу"},
                "question": {"type": "string", "description": "Что именно нужно понять"},
            },
            "required": ["image_path"],
        },
    },
]


def _send_telegram(text: str) -> dict:
    import requests
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return {"error": "TELEGRAM_BOT_TOKEN не задан"}
    chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    if not chat_id:
        try:
            updates = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates", timeout=5
            ).json()
            for u in (updates.get("result") or [])[::-1]:
                msg = u.get("message") or u.get("edited_message")
                if msg and msg.get("chat", {}).get("id"):
                    chat_id = msg["chat"]["id"]
                    break
        except Exception as e:
            return {"error": f"Не удалось определить chat_id: {e}"}
    if not chat_id:
        return {"error": "Нет chat_id админа. Напиши боту в Telegram любое сообщение."}
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        ).json()
        if r.get("ok"):
            return {"sent": True, "chat_id": chat_id, "message_id": r["result"]["message_id"]}
        return {"error": r.get("description", "unknown")}
    except Exception as e:
        return {"error": str(e)}


def _fetch_url(url: str) -> dict:
    import requests
    try:
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 AutoPilotBot/1.0"})
        r.raise_for_status()
        text = r.text
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            for s in soup(["script", "style", "noscript"]):
                s.decompose()
            text = soup.get_text(separator="\n", strip=True)
        except Exception:
            pass
        return {"url": url, "text": text[:8000], "truncated": len(text) > 8000}
    except Exception as e:
        return {"error": str(e), "url": url}


def _web_search(query: str) -> dict:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        return {"error": "XAI_API_KEY не задан"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        r = client.chat.completions.create(
            model="grok-2-latest",
            messages=[
                {"role": "system", "content": "Ищи актуальную информацию в интернете. Отвечай кратко с фактами."},
                {"role": "user", "content": query},
            ],
            max_tokens=800,
        )
        return {"query": query, "answer": r.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}


def _analyze_image(image_path: str, question: str | None = None) -> dict:
    import base64, mimetypes
    try:
        if not os.path.exists(image_path):
            return {"error": f"Файл не найден: {image_path}"}
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        client = get_client()
        q = question or "Опиши что на изображении, оцени качество, предложи 3 идеи для поста."
        r = client.messages.create(
            model=MODEL, max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                    {"type": "text", "text": q},
                ],
            }],
        )
        return {"description": "".join(b.text for b in r.content if b.type == "text")}
    except Exception as e:
        return {"error": str(e)}


def parse_options(text: str) -> tuple[str, dict | None]:
    """Извлекает блок <options multi="..."> в конце сообщения.
    Возвращает (текст_без_блока, {multi: bool, options: list[str]} | None)."""
    import re
    m = re.search(
        r'<options(?:\s+multi=["\'](true|false)["\'])?\s*>(.*?)</options>',
        text, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return text, None
    multi = (m.group(1) or "true").lower() == "true"
    body = m.group(2)
    opts = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            opts.append(line.lstrip("-*• ").strip())
    if not opts:
        return text, None
    cleaned = (text[:m.start()] + text[m.end():]).strip()
    return cleaned, {"multi": multi, "options": opts}


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
        if name == "analytics_overview":
            return api_client.analytics_overview() or {}
        if name == "send_telegram_notification":
            return _send_telegram(args["text"])
        if name == "fetch_url":
            return _fetch_url(args["url"])
        if name == "web_search":
            return _web_search(args["query"])
        if name == "analyze_image":
            return _analyze_image(args["image_path"], args.get("question"))
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
