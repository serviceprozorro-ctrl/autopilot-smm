import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.auth import require_auth, render_user_menu
require_auth()
"""АИ-помощник — чат с tool calling, вложениями, кнопками-вариантами,
правой панелью проектов и историей (как ChatGPT)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import uuid
from pathlib import Path
import streamlit as st

from utils.ai_agent import chat, parse_options
from utils.api_client import is_bot_online
from utils import chat_store

st.set_page_config(page_title="АИ-помощник", page_icon="🤖", layout="wide")
render_user_menu()

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.option-chip       { display:inline-block; padding:6px 14px; margin:3px;
                     background:#1e293b; border:1px solid #334155;
                     border-radius:20px; font-size:13px; color:#cbd5e1; }
.intg-card         { background:#0f172a; border:1px solid #1e293b;
                     border-radius:8px; padding:6px 10px; margin-bottom:5px;
                     display:flex; justify-content:space-between; align-items:center;
                     font-size:12px; }
.intg-on  { color:#6ee7b7; font-weight:600; }
.intg-off { color:#94a3b8; }
.attach-pill       { display:inline-block; background:#1e1b4b; color:#a5b4fc;
                     border-radius:8px; padding:4px 10px; margin:2px;
                     font-size:12px; font-weight:600; }

/* Right-panel ChatGPT-like */
.right-panel {
    background:#0b1224; border:1px solid #1e293b; border-radius:14px;
    padding:14px; height: calc(100vh - 140px); overflow-y:auto;
}
.rp-section-title {
    font-size:11px; color:#64748b; text-transform:uppercase;
    letter-spacing:.5px; margin:14px 0 6px 0; font-weight:700;
}
.chat-pill {
    background:#0f172a; border:1px solid #1e293b; border-radius:10px;
    padding:8px 10px; margin-bottom:5px; font-size:13px;
}
.chat-pill.active { border-color:#6366f1; background:#1e1b4b; }
.proj-dot { display:inline-block; width:8px; height:8px;
            border-radius:50%; margin-right:6px; vertical-align:middle; }
</style>
""", unsafe_allow_html=True)

bot_ok = is_bot_online()

# ── State init ──────────────────────────────────────────────────────────────
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []
if "ai_display" not in st.session_state:
    st.session_state.ai_display = []
if "ai_pending_attachments" not in st.session_state:
    st.session_state.ai_pending_attachments = []
if "agent_active_chat_id" not in st.session_state:
    st.session_state.agent_active_chat_id = None
if "agent_filter_project" not in st.session_state:
    st.session_state.agent_filter_project = "__any__"

UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "agent"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ─────────────────────────────────────────────────────────────────

def load_chat(chat_id: str):
    c = chat_store.get_chat(chat_id)
    if not c:
        return
    st.session_state.agent_active_chat_id = chat_id
    st.session_state.ai_messages = c.get("messages", [])
    st.session_state.ai_display = c.get("display", [])


def new_chat(project_id: str | None = None):
    c = chat_store.create_chat(project_id=project_id, title="Новый чат")
    st.session_state.agent_active_chat_id = c["id"]
    st.session_state.ai_messages = []
    st.session_state.ai_display = []
    st.session_state.ai_pending_attachments = []


def persist_active():
    cid = st.session_state.agent_active_chat_id
    if not cid:
        return
    title = None
    for d in st.session_state.ai_display:
        if d["role"] == "user" and d.get("text"):
            title = chat_store.auto_title(d["text"])
            break
    chat_store.save_chat(cid, st.session_state.ai_messages,
                         st.session_state.ai_display, title=title)


# Если нет активного чата — создаём
if not st.session_state.agent_active_chat_id:
    new_chat(None)

# ── Sidebar (минимальный — только интеграции) ──────────────────────────────
with st.sidebar:
    st.markdown("### 🔌 Интеграции")
    integrations = [
        ("📱 Telegram",   bool(os.environ.get("TELEGRAM_BOT_TOKEN"))),
        ("🔍 Grok Web",   bool(os.environ.get("XAI_API_KEY"))),
        ("🧠 Claude",     bool(os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY"))),
        ("🎨 Grok Image", bool(os.environ.get("XAI_API_KEY"))),
        ("🤖 Bot API",    bot_ok),
    ]
    for name, on in integrations:
        cls, ico = ("intg-on", "✅") if on else ("intg-off", "○")
        st.markdown(
            f'<div class="intg-card"><span>{name}</span>'
            f'<span class="{cls}">{ico}</span></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.markdown("### 💡 Примеры")
    examples = [
        "Покажи статистику и аналитику",
        "Найди тренды TikTok за неделю",
        "Придумай 5 идей видео для бьюти-блогера",
        "Отправь мне в Telegram отчёт",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state._pending_input = ex
            st.rerun()


# ── Main layout: chat + right panel ────────────────────────────────────────
col_chat, col_right = st.columns([3, 1], gap="medium")

# ════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — projects + history (ChatGPT-style)
# ════════════════════════════════════════════════════════════════════════════
with col_right:
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)

    if st.button("➕ Новый чат", use_container_width=True, type="primary",
                 key="rp_new_chat"):
        active = chat_store.get_chat(st.session_state.agent_active_chat_id)
        proj_id = active.get("project_id") if active else None
        new_chat(proj_id)
        st.rerun()

    # ── Projects ───────────────────────────────────────────────────────────
    st.markdown('<div class="rp-section-title">📁 Проекты</div>',
                unsafe_allow_html=True)
    projects = chat_store.list_projects()

    proj_filter_options = [("__any__", "Все чаты"), (None, "Без проекта")]
    proj_filter_options += [(p["id"], p["name"]) for p in projects]

    cur = st.session_state.agent_filter_project
    cur_idx = next((i for i, (v, _) in enumerate(proj_filter_options) if v == cur), 0)
    sel_label = st.selectbox(
        "Фильтр",
        [name for _, name in proj_filter_options],
        index=cur_idx, label_visibility="collapsed", key="rp_proj_filter",
    )
    new_filter = next(v for v, n in proj_filter_options if n == sel_label)
    if new_filter != st.session_state.agent_filter_project:
        st.session_state.agent_filter_project = new_filter
        st.rerun()

    # Перенести активный чат в выбранный проект
    active_chat = chat_store.get_chat(st.session_state.agent_active_chat_id)
    if active_chat:
        cur_proj = active_chat.get("project_id")
        proj_assign_options = [(None, "— без проекта —")] + [(p["id"], p["name"]) for p in projects]
        cur_assign_idx = next((i for i, (v, _) in enumerate(proj_assign_options) if v == cur_proj), 0)
        sel_assign = st.selectbox(
            "Этот чат → проект",
            [name for _, name in proj_assign_options],
            index=cur_assign_idx, key="rp_assign_proj",
        )
        new_assign = next(v for v, n in proj_assign_options if n == sel_assign)
        if new_assign != cur_proj:
            chat_store.save_chat(active_chat["id"],
                                 active_chat["messages"], active_chat["display"],
                                 project_id=new_assign)
            st.rerun()

    with st.expander("➕ Создать проект"):
        new_name = st.text_input("Название", key="rp_new_proj_name",
                                  placeholder="Например: Бьюти-блог")
        new_color = st.color_picker("Цвет", "#6366f1", key="rp_new_proj_color")
        new_instr = st.text_area(
            "Инструкции для агента (опционально)",
            placeholder="Стиль, ToV, целевая аудитория…",
            key="rp_new_proj_instr", height=70,
        )
        if st.button("Создать", use_container_width=True,
                      disabled=not new_name.strip(), key="rp_new_proj_btn"):
            chat_store.create_project(new_name, new_color, new_instr)
            st.rerun()

    if projects:
        for p in projects:
            pcol1, pcol2 = st.columns([5, 1])
            pcol1.markdown(
                f'<div class="chat-pill"><span class="proj-dot" '
                f'style="background:{p["color"]};"></span>{p["name"]}</div>',
                unsafe_allow_html=True,
            )
            if pcol2.button("✖", key=f"rp_del_p_{p['id']}",
                             help="Удалить проект"):
                chat_store.delete_project(p["id"])
                if st.session_state.agent_filter_project == p["id"]:
                    st.session_state.agent_filter_project = "__any__"
                st.rerun()

    # ── Chats history ──────────────────────────────────────────────────────
    st.markdown('<div class="rp-section-title">💬 История чатов</div>',
                unsafe_allow_html=True)

    chats = chat_store.list_chats(st.session_state.agent_filter_project)
    if not chats:
        st.caption("Нет сохранённых чатов")
    else:
        for c in chats[:50]:
            is_active = c["id"] == st.session_state.agent_active_chat_id
            pdot = ""
            if c.get("project_id"):
                pr = chat_store.get_project(c["project_id"])
                if pr:
                    pdot = f'<span class="proj-dot" style="background:{pr["color"]};"></span>'
            cc1, cc2 = st.columns([5, 1])
            with cc1:
                btn_label = ("● " if is_active else "○ ") + (c.get("title") or "Без названия")[:40]
                if st.button(btn_label, key=f"rp_load_{c['id']}",
                              use_container_width=True,
                              type=("primary" if is_active else "secondary")):
                    persist_active()
                    load_chat(c["id"])
                    st.rerun()
            if cc2.button("✖", key=f"rp_del_c_{c['id']}", help="Удалить чат"):
                chat_store.delete_chat(c["id"])
                if is_active:
                    st.session_state.agent_active_chat_id = None
                    st.session_state.ai_messages = []
                    st.session_state.ai_display = []
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# CHAT COLUMN
# ════════════════════════════════════════════════════════════════════════════
with col_chat:
    active = chat_store.get_chat(st.session_state.agent_active_chat_id)
    project = chat_store.get_project(active.get("project_id")) if active else None

    h1, h2 = st.columns([5, 1])
    with h1:
        title = active.get("title") if active else "Новый чат"
        proj_tag = f' · <span style="color:{project["color"]};">📁 {project["name"]}</span>' if project else ""
        st.markdown(f'## 🤖 {title}<span style="font-size:13px;color:#94a3b8;">{proj_tag}</span>',
                    unsafe_allow_html=True)
    with h2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑 Очистить", use_container_width=True, key="clear_chat"):
            st.session_state.ai_messages = []
            st.session_state.ai_display = []
            st.session_state.ai_pending_attachments = []
            persist_active()
            st.rerun()

    if not bot_ok:
        st.warning("⚠️ Бот недоступен — часть инструментов не сработает.")

    # ── Render history ─────────────────────────────────────────────────────
    TOOL_LABELS = {
        "list_accounts": "📋 Список аккаунтов", "get_stats": "📊 Статистика",
        "add_account": "➕ Добавление", "delete_account": "🗑 Удаление",
        "list_posts": "📅 Посты", "schedule_post": "📤 Планирование",
        "delete_post": "🗑 Удаление поста", "run_post_now": "▶️ Публикация",
        "analytics_overview": "📈 Аналитика",
        "send_telegram_notification": "📱 Telegram",
        "fetch_url": "🌐 Чтение страницы", "web_search": "🔍 Поиск",
        "analyze_image": "🖼 Анализ изображения",
    }

    def render_options_block(idx: int, opt_data: dict):
        multi = opt_data["multi"]
        options = opt_data["options"]
        sel_key = f"opts_sel_{st.session_state.agent_active_chat_id}_{idx}"
        if sel_key not in st.session_state:
            st.session_state[sel_key] = set()
        selected = st.session_state[sel_key]

        st.markdown(
            f'<div style="font-size:12px;color:#64748b;margin-top:6px;">'
            f'{"Выберите один или несколько:" if multi else "Выберите один:"}</div>',
            unsafe_allow_html=True,
        )

        cpr = 2
        rows = [options[i:i + cpr] for i in range(0, len(options), cpr)]
        for r_i, row in enumerate(rows):
            cols = st.columns(cpr)
            for c_i, opt in enumerate(row):
                is_sel = opt in selected
                label = ("✓ " if is_sel else "○ ") + opt
                if cols[c_i].button(label, key=f"opt_{idx}_{r_i}_{c_i}",
                                     use_container_width=True,
                                     type=("primary" if is_sel else "secondary")):
                    if multi:
                        (selected.discard if is_sel else selected.add)(opt)
                    else:
                        selected.clear(); selected.add(opt)
                    st.rerun()

        if multi and len(options) > 1:
            ac, sc = st.columns([1, 2])
            if ac.button("☑ Все", key=f"opt_all_{idx}", use_container_width=True):
                selected.update(options); st.rerun()
            if sc.button(f"📨 Отправить ({len(selected)})", key=f"opt_send_{idx}",
                          use_container_width=True, type="primary",
                          disabled=len(selected) == 0):
                st.session_state._pending_input = "Выбираю: " + "; ".join(sorted(selected))
                st.session_state[sel_key] = set()
                st.rerun()
        else:
            if st.button("📨 Отправить", key=f"opt_send_{idx}",
                          use_container_width=True, type="primary",
                          disabled=len(selected) == 0):
                st.session_state._pending_input = "Выбираю: " + "; ".join(sorted(selected))
                st.session_state[sel_key] = set()
                st.rerun()

        custom = st.text_input("Свой ответ", key=f"opt_custom_{idx}",
                                placeholder="Свой вариант…",
                                label_visibility="collapsed")
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

    # ── Attachments panel ──────────────────────────────────────────────────
    with st.expander(
        f"📎 Вложения ({len(st.session_state.ai_pending_attachments)})",
        expanded=bool(st.session_state.ai_pending_attachments),
    ):
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**Файл (фото / видео / документ)**")
            uploaded = st.file_uploader(
                "upload",
                type=["jpg", "jpeg", "png", "webp", "gif",
                      "mp4", "mov", "webm",
                      "pdf", "txt", "csv", "json"],
                label_visibility="collapsed",
                key=f"upl_{len(st.session_state.ai_pending_attachments)}",
            )
            if uploaded:
                ext = Path(uploaded.name).suffix.lower()
                kind = ("image" if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
                        else "video" if ext in {".mp4", ".mov", ".webm"}
                        else "file")
                saved = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
                saved.write_bytes(uploaded.getvalue())
                st.session_state.ai_pending_attachments.append({
                    "name": uploaded.name, "path": str(saved),
                    "kind": kind, "url": None,
                })
                st.rerun()
        with a2:
            st.markdown("**Ссылка / URL**")
            link = st.text_input("link", placeholder="https://…",
                                  label_visibility="collapsed",
                                  key="att_link_input")
            if st.button("➕ Прикрепить ссылку", use_container_width=True,
                          disabled=not link.strip()):
                st.session_state.ai_pending_attachments.append({
                    "name": link.strip()[:60], "path": None,
                    "kind": "url", "url": link.strip(),
                })
                st.rerun()

        if st.session_state.ai_pending_attachments:
            st.markdown("---")
            for i, att in enumerate(st.session_state.ai_pending_attachments):
                ico = {"image": "🖼", "video": "🎬", "url": "🔗",
                       "file": "📄"}.get(att["kind"], "📎")
                cc1, cc2 = st.columns([6, 1])
                cc1.markdown(f'<span class="attach-pill">{ico} {att["name"]}</span>',
                              unsafe_allow_html=True)
                if cc2.button("✖", key=f"rm_att_{i}"):
                    st.session_state.ai_pending_attachments.pop(i)
                    st.rerun()

    # ── Input ──────────────────────────────────────────────────────────────
    prompt = st.chat_input("Напиши команду или вопрос…")
    if "_pending_input" in st.session_state:
        prompt = st.session_state.pop("_pending_input")

    if prompt:
        attachments = list(st.session_state.ai_pending_attachments)
        st.session_state.ai_pending_attachments = []

        user_text_for_llm = prompt
        if attachments:
            meta = []
            for a in attachments:
                if a["kind"] == "url":
                    meta.append(f'Прикреплена ссылка: {a["url"]}')
                elif a["kind"] == "image":
                    meta.append(f'Прикреплён файл: {a["path"]} (изображение)')
                elif a["kind"] == "video":
                    meta.append(f'Прикреплён файл: {a["path"]} (видео)')
                else:
                    meta.append(f'Прикреплён файл: {a["path"]} (документ)')
            user_text_for_llm = prompt + "\n\n[" + " | ".join(meta) + "]"

        # Проектные инструкции — добавляем системный префикс в первое сообщение
        if project and project.get("instructions") and not st.session_state.ai_messages:
            user_text_for_llm = (
                f"[Контекст проекта «{project['name']}»: {project['instructions']}]\n\n"
                + user_text_for_llm
            )

        with st.chat_message("user"):
            if attachments:
                st.markdown(
                    "".join(f'<span class="attach-pill">📎 {a["name"]}</span>'
                            for a in attachments),
                    unsafe_allow_html=True,
                )
            st.markdown(prompt)

        st.session_state.ai_display.append({
            "role": "user", "text": prompt, "tools": [],
            "attachments": attachments,
        })
        st.session_state.ai_messages.append({
            "role": "user", "content": user_text_for_llm,
        })

        with st.chat_message("assistant"):
            text_placeholder = st.empty()
            tools_used = []
            full_text_chunks = []
            try:
                for event in chat(st.session_state.ai_messages):
                    if event["type"] == "text":
                        full_text_chunks.append(event["text"])
                        prev, _ = parse_options("\n\n".join(full_text_chunks))
                        text_placeholder.markdown(prev)
                    elif event["type"] == "tool_use":
                        st.info(f"{TOOL_LABELS.get(event['name'], event['name'])}…")
                    elif event["type"] == "tool_result":
                        label = TOOL_LABELS.get(event["name"], event["name"])
                        tools_used.append({"label": label, "result": event["result"]})
                        with st.expander(f"✅ {label}", expanded=False):
                            st.json(event["result"])
                    elif event["type"] == "done":
                        st.session_state.ai_messages = event["messages"]
            except Exception as e:
                st.error(f"❌ Ошибка АИ-помощника: {e}")
                full_text_chunks.append(f"Ошибка: {e}")

            full_text = "\n\n".join(full_text_chunks)
            clean_text, options_data = parse_options(full_text)
            st.session_state.ai_display.append({
                "role": "assistant", "text": clean_text,
                "tools": tools_used, "options": options_data,
                "attachments": [],
            })
            persist_active()
            st.rerun()
