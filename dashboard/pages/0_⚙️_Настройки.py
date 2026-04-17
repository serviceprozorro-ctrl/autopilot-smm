import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.auth import require_auth, render_user_menu
require_auth()
"""Settings page — configure Telegram Bot token."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import requests
import time

st.set_page_config(
    page_title="Настройки — AutoPilot",
    page_icon="⚙️",
    layout="centered",
)
render_user_menu()

BOT_API = "http://localhost:3000"

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.token-card {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
    border: 1px solid #4f46e5;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
}
.bot-card {
    background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
    border: 1px solid #10b981;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.status-dot-green { color: #10b981; font-size: 22px; }
.status-dot-red   { color: #ef4444; font-size: 22px; }
.info-row { margin: 6px 0; color: #d1fae5; font-size: 15px; }
.info-label { color: #6ee7b7; font-weight: 600; }
.step-box {
    background: #0f172a;
    border-left: 4px solid #6366f1;
    border-radius: 0 8px 8px 0;
    padding: 12px 18px;
    margin: 8px 0;
    font-size: 14px;
    color: #cbd5e1;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def _api_get(path: str):
    try:
        r = requests.get(f"{BOT_API}{path}", timeout=6)
        return r.json() if r.ok else None
    except Exception:
        return None


def _api_post(path: str, data: dict):
    try:
        r = requests.post(f"{BOT_API}{path}", json=data, timeout=10)
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)}


def _bot_online() -> bool:
    try:
        r = requests.get(f"{BOT_API}/", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚙️ Настройки AutoPilot")
st.markdown("Здесь вы настраиваете **Telegram-бота**, который управляет вашими аккаунтами.")
st.divider()

# ── Current bot status ────────────────────────────────────────────────────────
bot_online = _bot_online()
current = _api_get("/api/settings") if bot_online else None

if bot_online and current:
    bot_info = current.get("bot_info")
    if bot_info:
        username = bot_info.get("username", "")
        first_name = bot_info.get("first_name", "")
        bot_id = bot_info.get("id", "")
        st.markdown(f"""
<div class="bot-card">
  <span class="status-dot-green">🤖</span>
  <div>
    <div style="font-size:18px;font-weight:700;color:#d1fae5;">@{username} — {first_name}</div>
    <div class="info-row"><span class="info-label">ID:</span> {bot_id}</div>
    <div class="info-row"><span class="info-label">Токен:</span> {current.get("token_masked","—")}</div>
    <div class="info-row" style="color:#6ee7b7;">✅ Бот работает</div>
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        has_token = current.get("has_token")
        if has_token:
            st.warning(f"🔑 Токен сохранён ({current.get('token_masked')}), но бот не отвечает на запросы Telegram.")
        else:
            st.info("🔑 Токен ещё не настроен. Введите токен ниже.")
else:
    st.error("🔴 Сервис бота недоступен (порт 3000). Проверьте, запущен ли «Social Media Bot» workflow.")

st.divider()

# ── Token form ────────────────────────────────────────────────────────────────
st.markdown("### 🔑 Токен Telegram-бота")

with st.expander("📖 Как получить токен?", expanded=False):
    st.markdown("""
<div class="step-box">1️⃣ Откройте Telegram и найдите <b>@BotFather</b></div>
<div class="step-box">2️⃣ Отправьте команду <code>/newbot</code></div>
<div class="step-box">3️⃣ Придумайте имя и username (должен заканчиваться на <code>bot</code>)</div>
<div class="step-box">4️⃣ BotFather пришлёт токен вида <code>123456789:AAF…</code> — скопируйте его сюда</div>
""", unsafe_allow_html=True)

st.markdown('<div class="token-card">', unsafe_allow_html=True)

token_input = st.text_input(
    "Вставьте токен бота",
    value="",
    type="password",
    placeholder="123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    help="Токен выдаёт @BotFather в Telegram",
    label_visibility="collapsed",
)

col_check, col_save, col_clear = st.columns([1, 1, 0.5])

with col_check:
    check_btn = st.button("🔍 Проверить токен", use_container_width=True, type="secondary")
with col_save:
    save_btn = st.button("💾 Сохранить и запустить", use_container_width=True, type="primary")
with col_clear:
    clear_btn = st.button("🗑", use_container_width=True, help="Очистить поле")

st.markdown("</div>", unsafe_allow_html=True)

# ── Check token ───────────────────────────────────────────────────────────────
if check_btn:
    if not token_input.strip():
        st.warning("Введите токен")
    else:
        with st.spinner("Проверяю токен через Telegram API…"):
            result = _api_post("/api/settings/validate", {"token": token_input.strip()})
        if result and result.get("ok"):
            b = result.get("bot", {})
            st.success(f"✅ Токен рабочий! Бот: **@{b.get('username')}** ({b.get('first_name')})")
        else:
            desc = result.get("description", "Неизвестная ошибка") if result else "Нет ответа от сервиса"
            st.error(f"❌ Токен недействителен: {desc}")

# ── Save token ────────────────────────────────────────────────────────────────
if save_btn:
    if not token_input.strip():
        st.warning("⚠️ Введите токен перед сохранением")
    elif not bot_online:
        st.error("❌ Сервис бота недоступен — нельзя сохранить настройки")
    else:
        with st.spinner("Проверяю и сохраняю токен…"):
            result = _api_post("/api/settings", {"token": token_input.strip()})

        if result and result.get("ok"):
            b = result.get("bot_info") or {}
            st.success(f"✅ Токен сохранён! Бот @{b.get('username', '…')} перезапускается…")
            with st.spinner("Ожидаю перезапуска бота (до 10 сек)…"):
                time.sleep(4)
                for _ in range(3):
                    time.sleep(2)
                    if _bot_online():
                        break
            st.balloons()
            st.success("🚀 Бот перезапущен с новым токеном!")
            st.rerun()
        else:
            desc = ""
            if result:
                raw = result.get("description") or result.get("detail") or str(result)
                # translate common English API errors
                desc = str(raw).replace("Unauthorized", "Неверный токен").replace(
                    "Not Found", "Не найдено").replace("Bad Request", "Неверный запрос")
            else:
                desc = "Нет ответа от сервиса"
            st.error(f"❌ Ошибка: {desc}")

if clear_btn:
    st.rerun()

st.divider()

# ── About section ─────────────────────────────────────────────────────────────
st.markdown("### ℹ️ О платформе")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("""
| Компонент | Значение |
|-----------|----------|
| Dashboard | Streamlit (порт **5000**) |
| Bot API | FastAPI (порт **3000**) |
| База данных | SQLite (encrypted) |
| Авторизация | Fernet (AES-128) |
""")
with col_b:
    st.markdown("""
| Поддерживаемые платформы | |
|--------------------------|--|
| 🎵 TikTok | ✅ |
| 📸 Instagram | ✅ |
| ▶️ YouTube | ✅ |

| Методы входа | |
|-------------|--|
| 🍪 Cookies | ✅ |
| 📱 QR-код | ✅ |
| 🔐 Login+Pass | ✅ |
| 🔑 API ключ | ✅ |
""")
