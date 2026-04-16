import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.api_client import get_accounts, get_stats, add_account, delete_account, is_bot_online

st.set_page_config(page_title="Аккаунты", page_icon="📱", layout="wide")
st.title("📱 Управление аккаунтами")

if not is_bot_online():
    st.error("⚠️ Social Media Bot API недоступен. Убедитесь, что бот запущен на порту 3000.")
    st.stop()

# ── Stats bar ─────────────────────────────────────────────────────────────────
stats = get_stats()
if stats:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Всего", stats.get("total_accounts", 0))
    c2.metric("✅ Активных", stats["by_status"].get("active", 0))
    c3.metric("🎵 TikTok", stats["by_platform"].get("tiktok", 0))
    c4.metric("📸 Instagram", stats["by_platform"].get("instagram", 0))
    c5.metric("▶️ YouTube", stats["by_platform"].get("youtube", 0))
    st.divider()

# ── Add account form ──────────────────────────────────────────────────────────
with st.expander("➕ Добавить аккаунт", expanded=False):
    with st.form("add_account_form"):
        col1, col2 = st.columns(2)
        with col1:
            platform = st.selectbox("Платформа", ["tiktok", "instagram", "youtube"],
                                    format_func=lambda x: {"tiktok":"🎵 TikTok","instagram":"📸 Instagram","youtube":"▶️ YouTube"}[x])
            username = st.text_input("Username (без @)")
        with col2:
            auth_options = {
                "tiktok": ["qr_code", "login_password", "cookies"],
                "instagram": ["login_password", "cookies"],
                "youtube": ["cookies", "api"],
            }
            auth_labels = {
                "cookies": "🍪 Cookies / Session",
                "login_password": "🔐 Логин + Пароль",
                "qr_code": "📱 QR-код",
                "api": "🔑 API ключ",
            }
            auth_type = st.selectbox(
                "Способ авторизации",
                auth_options.get(platform, ["cookies"]),
                format_func=lambda x: auth_labels.get(x, x),
            )
            session_data = st.text_area("Cookies JSON / API ключ (необязательно)", height=80,
                                         placeholder='{"sessionid": "abc123"}')

        submitted = st.form_submit_button("➕ Добавить", type="primary", use_container_width=True)
        if submitted:
            if not username.strip():
                st.error("❗ Введите username")
            else:
                result = add_account(platform, username.strip().lstrip("@"), auth_type, session_data.strip())
                if result and "id" in result:
                    st.success(f"✅ Аккаунт @{result['username']} добавлен! ID: {result['id']}")
                    st.rerun()
                elif result:
                    st.error(f"❌ Ошибка: {result}")
                else:
                    st.error("❌ Не удалось подключиться к API бота")

# ── Accounts table ────────────────────────────────────────────────────────────
st.subheader("📋 Список аккаунтов")
accounts = get_accounts()

if not accounts:
    st.info("Аккаунтов нет. Добавьте первый аккаунт выше или через Telegram-бота.")
else:
    platform_icons = {"tiktok": "🎵 TikTok", "instagram": "📸 Instagram", "youtube": "▶️ YouTube"}
    status_icons = {"active": "✅ Активен", "banned": "🚫 Забанен", "inactive": "⏸ Неактивен", "pending": "⏳ Ожидает"}
    auth_icons = {"cookies": "🍪 Cookies", "login_password": "🔐 Логин+Пароль", "qr_code": "📱 QR-код", "api": "🔑 API"}

    for acc in accounts:
        with st.container():
            col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 1, 1])
            col1.markdown(f"`#{acc['id']}`")
            col2.markdown(f"**{platform_icons.get(acc['platform'], acc['platform'])}**")
            col3.markdown(f"@{acc['username']}")
            col4.markdown(auth_icons.get(acc["auth_type"], acc["auth_type"]))
            col5.markdown(status_icons.get(acc["status"], acc["status"]))
            with col6:
                if st.button("🗑", key=f"del_{acc['id']}", help=f"Удалить @{acc['username']}"):
                    result = delete_account(acc["id"])
                    if result and result.get("success"):
                        st.success(f"Аккаунт #{acc['id']} удалён")
                        st.rerun()
                    else:
                        st.error("Ошибка удаления")
            st.divider()
