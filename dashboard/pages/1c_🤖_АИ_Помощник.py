"""АИ-помощник второго пилота — чат с tool calling, вложениями и интеграциями."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import uuid
import time
from pathlib import Path
import streamlit as st

from utils.ai_agent import chat, parse_options
from utils.api_client import is_bot_online

st.set_page_config(page_title="АИ-помощник", page_icon="🤖", layout="wide")

# ── CSS для кнопок-вариантов и интеграций ───────────────────────────────────
st.markdown("""
<style>
.option-chip {
    display:inline-block; padding:6px 14px; margin:3px;
    background:#1e293b; border:1px solid #334155;
    border-radius:20px; font-size:13px; color:#cbd5e1;
}
.option-chip.selected {
    background:#4338ca; border-color:#6366f1; color:#fff;
}
.intg-card {
    background:#0f172a; border:1px solid #1e293b;
    border-radius:10px; padding:8px 12px; margin-bottom:6px;
    display:flex; justify-content:space-between; align-items:center;
    font-size:13px;
}
.intg-on  { color:#6ee7b7; font-weight:600; }
.intg-off { color:#94a3b8; }
.attach-pill {
    display:inline-block; background:#1e1b4b; color:#a5b4fc;
    border-radius:8px; padding:4px 10px; margin:2px;
    font-size:12px; font-weight:600;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 АИ-помощник — Второй пилот")
st.caption("Управляй платформой через чат: статистика, посты, идеи, "
           "поиск в интернете, Telegram-уведомления, анализ файлов.")

bot_ok = is_bot_online()
if not bot_ok:
    st.warning("⚠️ Бот недоступен — часть инструментов не сработает.")

# ── State ───────────────────────────────────────────────────────────────────
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []
if "ai_display" not in st.session_state:
    st.session_state.ai_display = []
if "ai_pending_attachments" not in st.session_state:
    st.session_state.ai_pending_attachments = []  # [{name, path, kind, url}]
if "ai_selected_options" not in st.session_state:
    st.session_state.ai_selected_options = {}     # {msg_idx: set(options)}

UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "agent"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Sidebar: интеграции и примеры ───────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Интеграции")

    integrations = [
        ("📱 Telegram",  bool(os.environ.get("TELEGRAM_BOT_TOKEN")),  "уведомления админу"),
        ("🔍 Grok Web",  bool(os.environ.get("XAI_API_KEY")),         "поиск в интернете"),
        ("🧠 Claude",    bool(os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")), "мозг агента + vision"),
        ("🎨 Grok Image",bool(os.environ.get("XAI_API_KEY")),         "генерация изображений"),
        ("🤖 Bot API",   bot_ok,                                       "управление аккаунтами"),
    ]
    for name, on, desc in integrations:
        cls = "intg-on" if on else "intg-off"
        ico = "✅" if on else "○"
        st.markdown(
            f'<div class="intg-card"><span>{name}<br>'
            f'<small style="color:#64748b;">{desc}</small></span>'
            f'<span class="{cls}">{ico}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### 🎛 Управление")
    if st.button("🗑 Очистить чат", use_container_width=True):
        st.session_state.ai_messages = []
        st.session_state.ai_display = []
        st.session_state.ai_pending_attachments = []
        st.session_state.ai_selected_options = {}
        st.rerun()

    st.divider()
    st.markdown("### 💡 Примеры")
    examples = [
        "Покажи статистику и аналитику",
        "Найди тренды TikTok за последнюю неделю",
        "Придумай 5 идей видео для бьюти-блогера",
        "Отправь мне в Telegram отчёт по аккаунтам",
        "Что мне делать сегодня?",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state._pending_input = ex
            st.rerun()

# ── Render history ──────────────────────────────────────────────────────────
TOOL_LABELS = {
    "list_accounts": "📋 Список аккаунтов",
    "get_stats": "📊 Статистика",
    "add_account": "➕ Добавление аккаунта",
    "delete_account": "🗑 Удаление аккаунта",
    "list_posts": "📅 Список постов",
    "schedule_post": "📤 Планирование",
    "delete_post": "🗑 Удаление поста",
    "run_post_now": "▶️ Публикация сейчас",
    "analytics_overview": "📈 Аналитика",
    "send_telegram_notification": "📱 Telegram-уведомление",
    "fetch_url": "🌐 Чтение страницы",
    "web_search": "🔍 Поиск в интернете",
    "analyze_image": "🖼 Анализ изображения",
}


def render_options_block(idx: int, opt_data: dict):
    """Кнопки-варианты с мульти/одиночным выбором + свой ответ."""
    multi = opt_data["multi"]
    options = opt_data["options"]
    sel_key = f"opts_sel_{idx}"
    if sel_key not in st.session_state:
        st.session_state[sel_key] = set()
    selected = st.session_state[sel_key]

    st.markdown(
        f'<div style="font-size:12px;color:#64748b;margin-top:6px;">'
        f'{"Выберите один или несколько вариантов:" if multi else "Выберите один вариант:"}'
        f'</div>', unsafe_allow_html=True,
    )

    cols_per_row = 2
    rows = [options[i:i + cols_per_row] for i in range(0, len(options), cols_per_row)]
    for r_i, row in enumerate(rows):
        cols = st.columns(cols_per_row)
        for c_i, opt in enumerate(row):
            is_sel = opt in selected
            label = ("✓ " if is_sel else "○ ") + opt
            btn_type = "primary" if is_sel else "secondary"
            if cols[c_i].button(label, key=f"opt_{idx}_{r_i}_{c_i}",
                                 use_container_width=True, type=btn_type):
                if multi:
                    if is_sel:
                        selected.discard(opt)
                    else:
                        selected.add(opt)
                else:
                    selected.clear()
                    selected.add(opt)
                st.rerun()

    if multi and len(options) > 1:
        all_btn_col, send_col = st.columns([1, 2])
        if all_btn_col.button("☑ Выбрать все", key=f"opt_all_{idx}",
                               use_container_width=True):
            for o in options:
                selected.add(o)
            st.rerun()
        if send_col.button(
            f"📨 Отправить выбор ({len(selected)})",
            key=f"opt_send_{idx}", use_container_width=True,
            disabled=len(selected) == 0, type="primary",
        ):
            st.session_state._pending_input = "Выбираю: " + "; ".join(sorted(selected))
            st.session_state[sel_key] = set()
            st.rerun()
    else:
        if st.button(
            "📨 Отправить выбор",
            key=f"opt_send_{idx}", use_container_width=True,
            disabled=len(selected) == 0, type="primary",
        ):
            st.session_state._pending_input = "Выбираю: " + "; ".join(sorted(selected))
            st.session_state[sel_key] = set()
            st.rerun()

    custom = st.text_input(
        "Или напишите свой ответ", key=f"opt_custom_{idx}",
        placeholder="Свой вариант…", label_visibility="collapsed",
    )
    if custom and st.button("➤ Отправить свой", key=f"opt_send_custom_{idx}"):
        st.session_state._pending_input = custom
        st.session_state[sel_key] = set()
        st.rerun()


for idx, entry in enumerate(st.session_state.ai_display):
    with st.chat_message(entry["role"]):
        if entry.get("attachments"):
            chips = "".join(
                f'<span class="attach-pill">📎 {a["name"]}</span>'
                for a in entry["attachments"]
            )
            st.markdown(chips, unsafe_allow_html=True)
        if entry.get("text"):
            st.markdown(entry["text"])
        for t in entry.get("tools", []):
            with st.expander(f"🔧 {t['label']}", expanded=False):
                st.json(t["result"])
        if entry.get("options"):
            render_options_block(idx, entry["options"])

# ── Панель вложений (под историей, перед инпутом) ──────────────────────────
with st.expander(
    f"📎 Вложения ({len(st.session_state.ai_pending_attachments)})",
    expanded=bool(st.session_state.ai_pending_attachments),
):
    a1, a2 = st.columns(2)

    with a1:
        st.markdown("**Файл (фото / видео / документ)**")
        uploaded = st.file_uploader(
            "upload", type=["jpg", "jpeg", "png", "webp", "gif",
                            "mp4", "mov", "webm",
                            "pdf", "txt", "csv", "json"],
            label_visibility="collapsed", key=f"upl_{len(st.session_state.ai_pending_attachments)}",
        )
        if uploaded:
            ext = Path(uploaded.name).suffix.lower()
            kind = "image" if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else \
                   "video" if ext in {".mp4", ".mov", ".webm"} else "file"
            saved = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
            saved.write_bytes(uploaded.getvalue())
            st.session_state.ai_pending_attachments.append({
                "name": uploaded.name, "path": str(saved), "kind": kind, "url": None,
            })
            st.rerun()

    with a2:
        st.markdown("**Ссылка / URL**")
        link = st.text_input("link", placeholder="https://…",
                             label_visibility="collapsed", key="att_link_input")
        if st.button("➕ Прикрепить ссылку", use_container_width=True,
                     disabled=not link.strip()):
            st.session_state.ai_pending_attachments.append({
                "name": link.strip()[:60], "path": None, "kind": "url",
                "url": link.strip(),
            })
            st.rerun()

    if st.session_state.ai_pending_attachments:
        st.markdown("---")
        for i, att in enumerate(st.session_state.ai_pending_attachments):
            ico = {"image": "🖼", "video": "🎬", "url": "🔗", "file": "📄"}.get(att["kind"], "📎")
            cc1, cc2 = st.columns([6, 1])
            cc1.markdown(f'<span class="attach-pill">{ico} {att["name"]}</span>',
                          unsafe_allow_html=True)
            if cc2.button("✖", key=f"rm_att_{i}"):
                st.session_state.ai_pending_attachments.pop(i)
                st.rerun()

# ── Input ───────────────────────────────────────────────────────────────────
prompt = st.chat_input("Напиши команду или вопрос…")
if "_pending_input" in st.session_state:
    prompt = st.session_state.pop("_pending_input")

if prompt:
    attachments = list(st.session_state.ai_pending_attachments)
    st.session_state.ai_pending_attachments = []

    # Формируем сообщение для LLM с описанием вложений
    user_text_for_llm = prompt
    if attachments:
        meta_lines = []
        for a in attachments:
            if a["kind"] == "url":
                meta_lines.append(f'Прикреплена ссылка: {a["url"]}')
            elif a["kind"] == "image":
                meta_lines.append(f'Прикреплён файл: {a["path"]} (изображение, имя: {a["name"]})')
            elif a["kind"] == "video":
                meta_lines.append(f'Прикреплён файл: {a["path"]} (видео, имя: {a["name"]})')
            else:
                meta_lines.append(f'Прикреплён файл: {a["path"]} (документ, имя: {a["name"]})')
        user_text_for_llm = prompt + "\n\n[" + " | ".join(meta_lines) + "]"

    with st.chat_message("user"):
        if attachments:
            chips = "".join(
                f'<span class="attach-pill">📎 {a["name"]}</span>' for a in attachments
            )
            st.markdown(chips, unsafe_allow_html=True)
        st.markdown(prompt)

    st.session_state.ai_display.append({
        "role": "user", "text": prompt, "tools": [], "attachments": attachments,
    })
    st.session_state.ai_messages.append({"role": "user", "content": user_text_for_llm})

    # Запускаем агента
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        tools_used = []
        full_text_chunks = []

        try:
            for event in chat(st.session_state.ai_messages):
                if event["type"] == "text":
                    full_text_chunks.append(event["text"])
                    # Скрываем <options> блок при стриме
                    preview = "\n\n".join(full_text_chunks)
                    preview_clean, _ = parse_options(preview)
                    text_placeholder.markdown(preview_clean)
                elif event["type"] == "tool_use":
                    label = TOOL_LABELS.get(event["name"], f"🔧 {event['name']}…")
                    st.info(f"{label}…")
                elif event["type"] == "tool_result":
                    result = event["result"]
                    label = TOOL_LABELS.get(event["name"], event["name"])
                    tools_used.append({"label": label, "result": result})
                    with st.expander(f"✅ {label}", expanded=False):
                        st.json(result)
                elif event["type"] == "done":
                    st.session_state.ai_messages = event["messages"]
        except Exception as e:
            st.error(f"❌ Ошибка АИ-помощника: {e}")
            full_text_chunks.append(f"Ошибка: {e}")

        full_text = "\n\n".join(full_text_chunks)
        clean_text, options_data = parse_options(full_text)

        st.session_state.ai_display.append({
            "role": "assistant",
            "text": clean_text,
            "tools": tools_used,
            "options": options_data,
            "attachments": [],
        })
        st.rerun()
