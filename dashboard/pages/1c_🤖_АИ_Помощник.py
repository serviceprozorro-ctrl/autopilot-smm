"""АИ-помощник второго пилота — чат с tool calling для управления панелью."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import streamlit as st

from utils.ai_agent import chat
from utils.api_client import is_bot_online

st.set_page_config(page_title="АИ-помощник", page_icon="🤖", layout="wide")
st.title("🤖 АИ-помощник — Второй пилот")
st.caption("Управляй платформой через чат: спрашивай статистику, планируй посты, "
           "добавляй аккаунты, генерируй идеи контента.")

bot_ok = is_bot_online()
if not bot_ok:
    st.warning("⚠️ Бот недоступен — часть инструментов не сработает.")

# ── State ───────────────────────────────────────────────────────────────────
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []  # [{role, content}]
if "ai_display" not in st.session_state:
    st.session_state.ai_display = []   # [{role, text, tools}]

with st.sidebar:
    st.markdown("### 🤖 Управление")
    if st.button("🗑 Очистить чат", use_container_width=True):
        st.session_state.ai_messages = []
        st.session_state.ai_display = []
        st.rerun()
    st.divider()
    st.markdown("**Что я умею:**")
    st.caption("• Список аккаунтов и статистика")
    st.caption("• Добавление/удаление аккаунтов")
    st.caption("• Планирование постов")
    st.caption("• Запуск публикаций сейчас")
    st.caption("• Тексты, идеи, хэштеги")
    st.divider()
    st.markdown("**Примеры запросов:**")
    examples = [
        "Покажи статистику",
        "Сколько у меня TikTok аккаунтов?",
        "Придумай 5 идей видео для бьюти-блогера",
        "Напиши описание для видео про путешествие в Сочи",
        "Список запланированных постов",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state._pending_input = ex
            st.rerun()

# ── Render history ──────────────────────────────────────────────────────────
TOOL_LABELS = {
    "list_accounts": "📋 Получаю список аккаунтов…",
    "get_stats": "📊 Получаю статистику…",
    "add_account": "➕ Добавляю аккаунт…",
    "delete_account": "🗑 Удаляю аккаунт…",
    "list_posts": "📅 Получаю список постов…",
    "schedule_post": "📤 Планирую публикацию…",
    "delete_post": "🗑 Удаляю пост…",
    "run_post_now": "▶️ Запускаю публикацию сейчас…",
}

for entry in st.session_state.ai_display:
    with st.chat_message(entry["role"]):
        if entry.get("text"):
            st.markdown(entry["text"])
        for t in entry.get("tools", []):
            with st.expander(f"🔧 {t['label']}", expanded=False):
                st.json(t["result"])

# ── Input ───────────────────────────────────────────────────────────────────
prompt = st.chat_input("Напиши команду или вопрос…")
if "_pending_input" in st.session_state:
    prompt = st.session_state.pop("_pending_input")

if prompt:
    # Показываем сообщение пользователя
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.ai_display.append({"role": "user", "text": prompt, "tools": []})
    st.session_state.ai_messages.append({"role": "user", "content": prompt})

    # Запускаем агента
    with st.chat_message("assistant"):
        text_placeholder = st.empty()
        tools_used = []
        full_text_chunks = []

        try:
            for event in chat(st.session_state.ai_messages):
                if event["type"] == "text":
                    full_text_chunks.append(event["text"])
                    text_placeholder.markdown("\n\n".join(full_text_chunks))
                elif event["type"] == "tool_use":
                    label = TOOL_LABELS.get(event["name"], f"🔧 {event['name']}…")
                    st.info(label)
                elif event["type"] == "tool_result":
                    result = event["result"]
                    label = TOOL_LABELS.get(event["name"], event["name"]).rstrip("…")
                    tools_used.append({"label": label, "result": result})
                    with st.expander(f"✅ {label} — результат", expanded=False):
                        st.json(result)
                elif event["type"] == "done":
                    st.session_state.ai_messages = event["messages"]
        except Exception as e:
            st.error(f"❌ Ошибка АИ-помощника: {e}")
            full_text_chunks.append(f"Ошибка: {e}")

        st.session_state.ai_display.append({
            "role": "assistant",
            "text": "\n\n".join(full_text_chunks),
            "tools": tools_used,
        })
