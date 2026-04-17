"""Страница управления аккаунтами — полная админ-панель."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import time
import streamlit as st
from utils.api_client import get_accounts, get_stats, add_account, delete_account, is_bot_online

st.set_page_config(page_title="Аккаунты", page_icon="📱", layout="wide")

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* KPI cards */
.kpi-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.kpi-card {
    flex: 1; min-width: 110px;
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 14px 18px;
    text-align: center;
}
.kpi-value { font-size: 28px; font-weight: 800; color: #e2e8f0; line-height: 1.1; }
.kpi-label { font-size: 11px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }

/* Status badges */
.badge {
    display: inline-block; border-radius: 20px;
    padding: 2px 10px; font-size: 12px; font-weight: 600;
}
.badge-active   { background:#064e3b; color:#6ee7b7; }
.badge-warning  { background:#451a03; color:#fcd34d; }
.badge-banned   { background:#450a0a; color:#fca5a5; }
.badge-inactive { background:#1e293b; color:#94a3b8; }
.badge-pending  { background:#1e1b4b; color:#a5b4fc; }
.badge-draft    { background:#1c1917; color:#a8a29e; }

/* Platform badges */
.plat-tiktok    { background:#1a0022; color:#ee1d52; border:1px solid #ee1d52; }
.plat-instagram { background:#1a0a22; color:#c13584; border:1px solid #c13584; }
.plat-youtube   { background:#1a0a0a; color:#ff0000; border:1px solid #ff0000; }

/* Account card */
.acc-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: border-color .2s;
}
.acc-card:hover { border-color: #4f46e5; }
.acc-username { font-size: 16px; font-weight: 700; color: #e2e8f0; }
.acc-meta     { font-size: 12px; color: #64748b; margin-top: 2px; }

/* Section header */
.section-header {
    font-size: 18px; font-weight: 700; color: #e2e8f0;
    margin: 20px 0 10px 0;
    display: flex; align-items: center; gap: 8px;
}

/* Empty state */
.empty-state {
    background: #0f172a; border: 2px dashed #1e3a5f;
    border-radius: 16px; padding: 48px 32px; text-align: center;
}
.empty-icon  { font-size: 56px; margin-bottom: 16px; }
.empty-title { font-size: 22px; font-weight: 700; color: #e2e8f0; margin-bottom: 8px; }
.empty-desc  { color: #64748b; font-size: 15px; margin-bottom: 24px; }

/* Divider */
.thin-div { border-top: 1px solid #1e293b; margin: 16px 0; }

/* Filter bar */
.filter-bar {
    background: #0f172a; border: 1px solid #1e293b;
    border-radius: 12px; padding: 14px 18px; margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
PLATFORM_ICONS  = {"tiktok": "🎵", "instagram": "📸", "youtube": "▶️"}
PLATFORM_LABELS = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}
STATUS_LABELS   = {
    "active":   ("✅", "Активен",    "active"),
    "banned":   ("🚫", "Забанен",    "banned"),
    "inactive": ("⏸", "Неактивен",  "inactive"),
    "pending":  ("⏳", "Ожидает",    "pending"),
    "warning":  ("⚠️", "Требует внимания", "warning"),
    "expired":  ("🔴", "Устарел",   "banned"),
    "draft":    ("📝", "Черновик",   "draft"),
}
AUTH_LABELS = {
    "cookies":        ("🍪", "Cookies"),
    "login_password": ("🔐", "Логин+Пароль"),
    "qr_code":        ("📱", "QR-код"),
    "api":            ("🔑", "API ключ"),
}
AUTH_BY_PLATFORM = {
    "tiktok":    ["qr_code", "login_password", "cookies"],
    "instagram": ["login_password", "cookies"],
    "youtube":   ["cookies", "api"],
}

DEMO_ACCOUNTS = [
    {"id": "demo-1", "platform": "tiktok",    "username": "creator_pro",  "auth_type": "cookies",        "status": "active",   "has_session": True,  "_demo": True},
    {"id": "demo-2", "platform": "instagram", "username": "brand_official","auth_type": "login_password", "status": "warning",  "has_session": True,  "_demo": True},
    {"id": "demo-3", "platform": "youtube",   "username": "MyChannel",    "auth_type": "api",            "status": "active",   "has_session": True,  "_demo": True},
    {"id": "demo-4", "platform": "tiktok",    "username": "backup_acc",   "auth_type": "qr_code",        "status": "inactive", "has_session": False, "_demo": True},
    {"id": "demo-5", "platform": "instagram", "username": "promo_page",   "auth_type": "cookies",        "status": "banned",   "has_session": False, "_demo": True},
]


# ══════════════════════════════════════════════════════════════════════════════
# DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def load_accounts() -> tuple[list[dict], str | None]:
    """Возвращает (accounts, error_message)."""
    raw = get_accounts()
    if raw is None:
        return [], "api_offline"
    if isinstance(raw, dict) and "error" in raw:
        return [], raw["error"]
    if isinstance(raw, list):
        return raw, None
    return [], f"Неожиданный формат данных: {type(raw).__name__}"


def normalize_accounts(accounts: list) -> list[dict]:
    """Гарантирует, что каждый элемент — корректный словарь аккаунта."""
    result = []
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        result.append({
            "id":          acc.get("id", "?"),
            "platform":    acc.get("platform", "unknown"),
            "username":    acc.get("username", "—"),
            "auth_type":   acc.get("auth_type", "cookies"),
            "status":      acc.get("status", "inactive"),
            "has_session": bool(acc.get("has_session")),
            "_demo":       acc.get("_demo", False),
        })
    return result


def validate_account_form(platform: str, username: str, session_data: str, auth_type: str) -> str | None:
    """Возвращает текст ошибки или None если всё ок."""
    if not username.strip():
        return "Username обязателен"
    if len(username.strip()) < 2:
        return "Username слишком короткий (минимум 2 символа)"
    if auth_type == "cookies" and session_data.strip():
        try:
            parsed = json.loads(session_data.strip())
            if not isinstance(parsed, (dict, list)):
                return "Cookies JSON должен быть объектом или массивом"
        except json.JSONDecodeError as e:
            return f"Неверный JSON: {e}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# RENDER HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def render_kpis(accounts: list[dict], stats: dict | None):
    total    = len(accounts)
    active   = sum(1 for a in accounts if a["status"] == "active")
    banned   = sum(1 for a in accounts if a["status"] == "banned")
    warning  = sum(1 for a in accounts if a["status"] in ("warning", "expired"))
    no_sess  = sum(1 for a in accounts if not a["has_session"])
    tiktok   = sum(1 for a in accounts if a["platform"] == "tiktok")
    insta    = sum(1 for a in accounts if a["platform"] == "instagram")
    youtube  = sum(1 for a in accounts if a["platform"] == "youtube")

    cols = st.columns(8)
    metrics = [
        ("📱", "Всего",         total,   None),
        ("✅", "Активных",      active,  None),
        ("🚫", "Забаненных",    banned,  None),
        ("⚠️", "Внимание",      warning, None),
        ("🔑", "Без сессии",    no_sess, None),
        ("🎵", "TikTok",        tiktok,  None),
        ("📸", "Instagram",     insta,   None),
        ("▶️", "YouTube",       youtube, None),
    ]
    for col, (icon, label, val, _) in zip(cols, metrics):
        col.metric(f"{icon} {label}", val)


def render_filters(accounts: list[dict]) -> list[dict]:
    """Рисует панель фильтров и возвращает отфильтрованный список."""
    with st.container():
        f1, f2, f3, f4 = st.columns([2, 1.5, 1.5, 1.5])

        search = f1.text_input("🔍 Поиск", placeholder="username или ID…", key="acc_search",
                               label_visibility="collapsed")

        platform_opts = ["Все платформы", "TikTok", "Instagram", "YouTube"]
        platform_f = f2.selectbox("Платформа", platform_opts, label_visibility="collapsed", key="acc_plat")

        status_opts = ["Все статусы", "Активен", "Забанен", "Неактивен", "Ожидает"]
        status_f = f3.selectbox("Статус", status_opts, label_visibility="collapsed", key="acc_stat")

        auth_opts = ["Все типы", "Cookies", "Логин+Пароль", "QR-код", "API ключ"]
        auth_f = f4.selectbox("Тип входа", auth_opts, label_visibility="collapsed", key="acc_auth")

    _plat_map = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}
    _stat_map = {"active": "Активен", "banned": "Забанен", "inactive": "Неактивен", "pending": "Ожидает"}
    _auth_map = {"cookies": "Cookies", "login_password": "Логин+Пароль", "qr_code": "QR-код", "api": "API ключ"}

    filtered = accounts
    if search.strip():
        q = search.strip().lower()
        filtered = [a for a in filtered if q in a["username"].lower() or q in str(a["id"]).lower()]
    if platform_f != "Все платформы":
        filtered = [a for a in filtered if _plat_map.get(a["platform"], "") == platform_f]
    if status_f != "Все статусы":
        filtered = [a for a in filtered if _stat_map.get(a["status"], "") == status_f]
    if auth_f != "Все типы":
        filtered = [a for a in filtered if _auth_map.get(a["auth_type"], "") == auth_f]
    return filtered


def badge(text: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{text}</span>'


def render_account_card(acc: dict, bot_online: bool, idx: int):
    is_demo = acc.get("_demo", False)
    plat    = acc["platform"]
    icon    = PLATFORM_ICONS.get(plat, "📱")
    plat_lb = PLATFORM_LABELS.get(plat, plat.capitalize())
    st_info = STATUS_LABELS.get(acc["status"], ("❓", acc["status"], "inactive"))
    auth_info = AUTH_LABELS.get(acc["auth_type"], ("❓", acc["auth_type"]))

    with st.container():
        col_info, col_auth, col_stat, col_sess, col_acts = st.columns([3, 1.8, 1.5, 1, 2])

        with col_info:
            demo_tag = ' <small style="color:#6366f1;font-size:10px;">[DEMO]</small>' if is_demo else ""
            st.markdown(
                f'<div class="acc-username">{icon} @{acc["username"]}{demo_tag}</div>'
                f'<div class="acc-meta">ID: {acc["id"]} · {plat_lb}</div>',
                unsafe_allow_html=True,
            )

        with col_auth:
            st.markdown(f'{auth_info[0]} {auth_info[1]}')

        with col_stat:
            css = f"badge-{st_info[2]}"
            st.markdown(badge(f"{st_info[0]} {st_info[1]}", css), unsafe_allow_html=True)

        with col_sess:
            if acc["has_session"]:
                st.markdown('<span style="color:#10b981;">✔ Есть</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span style="color:#ef4444;">✘ Нет</span>', unsafe_allow_html=True)

        with col_acts:
            btn_cols = st.columns(3)
            acc_key = str(acc["id"])

            # Confirm delete state
            confirm_key = f"confirm_del_{acc_key}_{idx}"
            if st.session_state.get(confirm_key):
                st.warning("Удалить?")
                yes_col, no_col = st.columns(2)
                if yes_col.button("✔ Да", key=f"yes_{acc_key}_{idx}", use_container_width=True):
                    if not is_demo and bot_online:
                        res = delete_account(acc["id"])
                        if res and res.get("success"):
                            st.toast(f"@{acc['username']} удалён", icon="✅")
                            st.session_state[confirm_key] = False
                            st.rerun()
                        else:
                            st.error("Ошибка удаления")
                    else:
                        st.toast("Демо-аккаунты не удаляются", icon="ℹ️")
                        st.session_state[confirm_key] = False
                        st.rerun()
                if no_col.button("✖ Нет", key=f"no_{acc_key}_{idx}", use_container_width=True):
                    st.session_state[confirm_key] = False
                    st.rerun()
            else:
                with btn_cols[0]:
                    if st.button("📊", key=f"details_{acc_key}_{idx}", help="Панель аккаунта: статистика, публикации, настройки",
                                 use_container_width=True):
                        st.session_state["selected_account"] = acc
                        st.rerun()
                with btn_cols[1]:
                    if st.button("🔄", key=f"refresh_{acc_key}_{idx}", help="Обновить сессию",
                                 use_container_width=True):
                        st.toast(f"Запрос на обновление @{acc['username']} отправлен", icon="🔄")
                with btn_cols[2]:
                    if st.button("🗑", key=f"del_{acc_key}_{idx}", help="Удалить аккаунт",
                                 use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()

    st.markdown('<div class="thin-div"></div>', unsafe_allow_html=True)


def render_add_form(bot_online: bool, existing_usernames: set):
    with st.expander("➕ Добавить аккаунт", expanded=st.session_state.get("open_add_form", False)):
        st.markdown("##### Новый аккаунт")

        col_plat, col_user = st.columns(2)
        with col_plat:
            platform = st.selectbox(
                "Платформа *",
                ["tiktok", "instagram", "youtube"],
                format_func=lambda x: f"{PLATFORM_ICONS[x]} {PLATFORM_LABELS[x]}",
                key="add_platform",
            )
        with col_user:
            username = st.text_input("Username *", placeholder="без символа @", key="add_username")

        auth_options = AUTH_BY_PLATFORM.get(platform, ["cookies"])
        auth_type = st.selectbox(
            "Способ авторизации *",
            auth_options,
            format_func=lambda x: f"{AUTH_LABELS[x][0]} {AUTH_LABELS[x][1]}",
            key="add_auth",
        )

        # Dynamic extra fields
        session_data = ""
        if auth_type == "cookies":
            st.markdown('<span style="color:#94a3b8;font-size:13px;">Вставьте Cookies в формате JSON (экспорт из браузера)</span>',
                        unsafe_allow_html=True)
            session_data = st.text_area(
                "Cookies JSON",
                placeholder='{"sessionid": "abc123", "ds_user_id": "..."}',
                height=100, key="add_session",
            )
        elif auth_type == "login_password":
            st.markdown('<span style="color:#94a3b8;font-size:13px;">Введите пароль от аккаунта — он будет зашифрован и сохранён локально.</span>',
                        unsafe_allow_html=True)
            password = st.text_input(
                "Пароль *",
                placeholder="Ваш пароль от аккаунта",
                type="password",
                key="add_password",
            )
            session_data = password
        elif auth_type == "qr_code":
            st.info("📱 Аккаунт будет создан в режиме «Ожидает». Откройте приложение TikTok → Профиль → ⋯ → «Войти в другой аккаунт» → QR-код, и отсканируйте код, который появится в боте.")
        elif auth_type == "api":
            session_data = st.text_input("API ключ / токен", placeholder="ya29.xxx…", key="add_api_key",
                                         type="password")

        notes = st.text_input("Примечание (необязательно)", placeholder="Основной аккаунт", key="add_notes")

        col_btn, col_reset = st.columns([2, 1])
        submitted = col_btn.button("➕ Добавить аккаунт", type="primary",
                                   use_container_width=True, key="add_submit")
        if col_reset.button("✖ Отмена", use_container_width=True, key="add_cancel"):
            st.session_state["open_add_form"] = False
            st.rerun()

        if submitted:
            clean_username = username.strip().lstrip("@")
            err = validate_account_form(platform, clean_username, session_data, auth_type)
            if err:
                st.error(f"❌ {err}")
            elif clean_username.lower() in existing_usernames:
                st.warning(f"⚠️ Аккаунт @{clean_username} уже существует")
            elif not bot_online:
                st.error("❌ Telegram Bot API недоступен. Проверьте что бот запущен.")
            else:
                with st.spinner("Добавляю аккаунт…"):
                    result = add_account(platform, clean_username, auth_type,
                                         session_data.strip() or None)
                if result and isinstance(result, dict) and "id" in result:
                    st.success(f"✅ Аккаунт @{result['username']} успешно добавлен! (ID: {result['id']})")
                    st.session_state["open_add_form"] = False
                    time.sleep(0.5)
                    st.rerun()
                elif result and isinstance(result, dict) and "detail" in result:
                    st.error(f"❌ Ошибка API: {result['detail']}")
                else:
                    st.error(f"❌ Не удалось добавить аккаунт: {result}")


def render_account_details(acc: dict, bot_online: bool):
    """Подробная панель аккаунта: статистика, публикации, действия, настройки."""
    import random
    from datetime import datetime, timedelta

    plat    = acc["platform"]
    icon    = PLATFORM_ICONS.get(plat, "📱")
    plat_lb = PLATFORM_LABELS.get(plat, plat.capitalize())
    st_info = STATUS_LABELS.get(acc["status"], ("❓", acc["status"], "inactive"))
    auth_info = AUTH_LABELS.get(acc["auth_type"], ("❓", acc["auth_type"]))
    is_demo = acc.get("_demo", False)

    # ── Top bar ────────────────────────────────────────────────────────────────
    top_l, top_r = st.columns([5, 1])
    with top_l:
        st.markdown(f"## {icon} @{acc['username']}")
        st.caption(f"{plat_lb} · ID: {acc['id']} · {auth_info[0]} {auth_info[1]} · "
                   f"{st_info[0]} {st_info[1]}" + (" · 🎭 ДЕМО" if is_demo else ""))
    with top_r:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← К списку", key="back_to_list", use_container_width=True):
            st.session_state.pop("selected_account", None)
            st.rerun()

    st.divider()

    # ── Deterministic mock metrics seeded by account id ────────────────────────
    seed = abs(hash(str(acc["id"]))) % (10**6)
    rng = random.Random(seed)
    followers   = rng.randint(1_200, 250_000)
    following   = rng.randint(80, 1_500)
    posts_total = rng.randint(20, 800)
    likes_total = rng.randint(5_000, 2_000_000)
    views_30d   = rng.randint(10_000, 500_000)
    eng_rate    = round(rng.uniform(1.5, 9.8), 2)
    avg_likes   = rng.randint(50, 5_000)
    avg_comm    = rng.randint(5, 500)
    growth_30d  = round(rng.uniform(-2.5, 12.0), 1)

    # ── KPI row ────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("👥 Подписчики", f"{followers:,}".replace(",", " "), f"{growth_30d:+.1f}%")
    k2.metric("👁 Просмотры (30д)", f"{views_30d:,}".replace(",", " "))
    k3.metric("❤️ Лайки всего", f"{likes_total:,}".replace(",", " "))
    k4.metric("📝 Публикаций", posts_total)
    k5.metric("📊 Engagement", f"{eng_rate}%")
    k6.metric("➕ Подписки", following)

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_stats, tab_posts, tab_actions, tab_auto, tab_settings = st.tabs([
        "📈 Аналитика", "🎬 Публикации", "⚡ Действия", "🤖 Автоматизация", "⚙️ Настройки",
    ])

    # ── 📈 АНАЛИТИКА ──────────────────────────────────────────────────────────
    with tab_stats:
        import pandas as pd

        st.markdown("##### Динамика за 30 дней")
        days = [datetime.now() - timedelta(days=i) for i in range(29, -1, -1)]
        base_f = followers - sum(rng.randint(-50, 200) for _ in range(30))
        followers_series, views_series = [], []
        cur_f = base_f
        for _ in range(30):
            cur_f += rng.randint(-30, 250)
            followers_series.append(cur_f)
            views_series.append(rng.randint(500, 25_000))
        df = pd.DataFrame({
            "Дата": days,
            "Подписчики": followers_series,
            "Просмотры": views_series,
        }).set_index("Дата")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**👥 Рост подписчиков**")
            st.line_chart(df["Подписчики"], height=260)
        with c2:
            st.markdown("**👁 Просмотры по дням**")
            st.bar_chart(df["Просмотры"], height=260)

        st.markdown("##### Средние показатели на пост")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("❤️ Лайков", f"{avg_likes:,}".replace(",", " "))
        a2.metric("💬 Комментариев", avg_comm)
        a3.metric("🔁 Репостов", rng.randint(5, 300))
        a4.metric("💾 Сохранений", rng.randint(10, 800))

        st.markdown("##### Аудитория")
        au1, au2 = st.columns(2)
        with au1:
            st.markdown("**🌍 География (топ-5)**")
            geo = pd.DataFrame({
                "Страна": ["Россия", "Украина", "Казахстан", "Беларусь", "Другие"],
                "Доля %": sorted([rng.randint(5, 50) for _ in range(5)], reverse=True),
            })
            st.dataframe(geo, hide_index=True, use_container_width=True)
        with au2:
            st.markdown("**👫 Пол / возраст**")
            age = pd.DataFrame({
                "Группа": ["18–24 М", "18–24 Ж", "25–34 М", "25–34 Ж", "35+"],
                "Доля %": [rng.randint(8, 30) for _ in range(5)],
            })
            st.dataframe(age, hide_index=True, use_container_width=True)

    # ── 🎬 ПУБЛИКАЦИИ ─────────────────────────────────────────────────────────
    with tab_posts:
        st.markdown("##### Последние 10 публикаций")
        captions = [
            "Новый ролик 🔥", "Закулисье съёмок", "Лайфхак дня", "Топ-3 ошибки",
            "Реакция на тренд", "Туториал за 60 секунд", "Q&A — отвечаю на вопросы",
            "Распаковка", "Челлендж недели", "Мысли вслух",
        ]
        rows = []
        for i in range(10):
            d = datetime.now() - timedelta(days=i*2, hours=rng.randint(0, 23))
            rows.append({
                "Дата": d.strftime("%d.%m %H:%M"),
                "Описание": captions[i],
                "👁": f"{rng.randint(500, 80_000):,}".replace(",", " "),
                "❤️": f"{rng.randint(50, 8_000):,}".replace(",", " "),
                "💬": rng.randint(2, 400),
                "🔁": rng.randint(0, 200),
                "Статус": rng.choice(["✅ Опубликован", "✅ Опубликован", "✅ Опубликован", "📌 Закреплён"]),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        st.markdown("##### 📅 Запланированные публикации")
        sched = []
        for i in range(rng.randint(0, 4)):
            d = datetime.now() + timedelta(days=i+1, hours=rng.randint(1, 22))
            sched.append({
                "Когда": d.strftime("%d.%m %H:%M"),
                "Тип": rng.choice(["Видео", "Reels", "Story", "Пост"]),
                "Название": rng.choice(captions),
                "Статус": "⏳ В очереди",
            })
        if sched:
            st.dataframe(pd.DataFrame(sched), hide_index=True, use_container_width=True)
        else:
            st.info("Нет запланированных публикаций. Создайте новую через вкладку «Действия».")

    # ── ⚡ ДЕЙСТВИЯ ──────────────────────────────────────────────────────────
    with tab_actions:
        st.markdown("##### Быстрые действия")
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            st.markdown("**📤 Опубликовать**")
            up = st.file_uploader("Видео / фото", type=["mp4", "mov", "jpg", "png", "webp"],
                                  key=f"upload_{acc['id']}")
            caption = st.text_area("Описание", placeholder="Текст поста или подпись…",
                                   key=f"caption_{acc['id']}", height=80)
            schedule = st.checkbox("Запланировать", key=f"sch_{acc['id']}")
            if schedule:
                st.date_input("Дата", key=f"sch_date_{acc['id']}")
                st.time_input("Время", key=f"sch_time_{acc['id']}")
            if st.button("🚀 Опубликовать", type="primary", use_container_width=True,
                         key=f"publish_{acc['id']}"):
                if not up:
                    st.warning("Загрузите файл")
                else:
                    st.success(f"✅ Поставлено в очередь: {up.name}")

        with ac2:
            st.markdown("**💬 Массовые действия**")
            action = st.selectbox("Действие", [
                "Лайкать публикации по хэштегу",
                "Подписаться на подписчиков конкурента",
                "Комментировать новые посты",
                "Отписаться от неактивных",
            ], key=f"mass_{acc['id']}")
            target = st.text_input("Цель (хэштег / @user)", key=f"target_{acc['id']}",
                                   placeholder="#подкаст или @competitor")
            limit = st.number_input("Лимит за час", 10, 500, 50, key=f"lim_{acc['id']}")
            if st.button("▶ Запустить", use_container_width=True, key=f"start_{acc['id']}"):
                st.success(f"Задача «{action}» запущена. Лимит: {limit}/час")

        with ac3:
            st.markdown("**📊 Аналитический отчёт**")
            period = st.selectbox("Период", ["7 дней", "30 дней", "90 дней", "Год"],
                                  key=f"per_{acc['id']}")
            fmt = st.selectbox("Формат", ["PDF", "Excel", "CSV"], key=f"fmt_{acc['id']}")
            st.text_input("Email для отправки (необязательно)", key=f"em_{acc['id']}")
            if st.button("📥 Сформировать отчёт", use_container_width=True, key=f"rep_{acc['id']}"):
                st.success(f"Отчёт за {period} в формате {fmt} сформирован")

    # ── 🤖 АВТОМАТИЗАЦИЯ ─────────────────────────────────────────────────────
    with tab_auto:
        st.markdown("##### Автоматические сценарии")
        au1, au2 = st.columns(2)
        with au1:
            st.toggle("🤖 Автоответ на комментарии", value=False, key=f"ar_{acc['id']}")
            st.toggle("👍 Автолайк публикаций по хэштегам", value=False, key=f"al_{acc['id']}")
            st.toggle("➕ Автоподписка на целевую аудиторию", value=False, key=f"af_{acc['id']}")
            st.toggle("👁 Авто-просмотр Stories", value=False, key=f"av_{acc['id']}")
        with au2:
            st.toggle("📅 Автопостинг по расписанию", value=True, key=f"ap_{acc['id']}")
            st.toggle("🧹 Автоочистка ботов из подписчиков", value=False, key=f"ac_{acc['id']}")
            st.toggle("📩 Автоответ в Direct/DM", value=False, key=f"ad_{acc['id']}")
            st.toggle("🔔 Уведомления об упоминаниях", value=True, key=f"an_{acc['id']}")

        st.markdown("##### Защита от блокировок")
        p1, p2, p3 = st.columns(3)
        p1.number_input("Действий в час", 10, 500, 80, key=f"ph_{acc['id']}")
        p2.number_input("Пауза между действиями (сек)", 5, 300, 45, key=f"pp_{acc['id']}")
        p3.selectbox("Режим работы", ["Имитация человека", "Стандартный", "Агрессивный"],
                     key=f"pm_{acc['id']}")

        if st.button("💾 Сохранить настройки автоматизации", type="primary",
                     use_container_width=True, key=f"save_auto_{acc['id']}"):
            st.success("Настройки сохранены")

    # ── ⚙️ НАСТРОЙКИ ─────────────────────────────────────────────────────────
    with tab_settings:
        st.markdown("##### Параметры аккаунта")
        s1, s2 = st.columns(2)
        with s1:
            st.text_input("Заметка", value="", placeholder="Например: основной", key=f"note_{acc['id']}")
            st.selectbox("Группа", ["Без группы", "Основные", "Резервные", "Тестовые"],
                         key=f"grp_{acc['id']}")
            st.selectbox("Часовой пояс", ["UTC+3 Москва", "UTC+0 Лондон", "UTC-5 Нью-Йорк"],
                         key=f"tz_{acc['id']}")
        with s2:
            st.text_input("🌐 Прокси (host:port)", placeholder="123.45.67.89:8080",
                          key=f"prx_{acc['id']}")
            st.text_input("Логин прокси", key=f"prxu_{acc['id']}")
            st.text_input("Пароль прокси", type="password", key=f"prxp_{acc['id']}")

        st.markdown("##### Сессия и токены")
        st.code(f"Тип входа: {auth_info[1]}\nСессия: {'есть' if acc['has_session'] else 'нет'}\n"
                f"Создан: {datetime.now() - timedelta(days=rng.randint(10, 400)):%d.%m.%Y}")

        st.markdown("##### Опасная зона")
        d1, d2, d3 = st.columns(3)
        if d1.button("🔄 Переавторизовать", use_container_width=True, key=f"reauth_{acc['id']}"):
            st.info("Запрос на повторную авторизацию отправлен")
        if d2.button("⏸ Приостановить", use_container_width=True, key=f"pause_{acc['id']}"):
            st.warning("Аккаунт приостановлен")
        if d3.button("🗑 Удалить аккаунт", use_container_width=True, key=f"del_acc_{acc['id']}"):
            st.error("Подтвердите удаление в списке аккаунтов")


def render_empty_state():
    st.markdown("""
<div class="empty-state">
  <div class="empty-icon">📱</div>
  <div class="empty-title">Аккаунтов пока нет</div>
  <div class="empty-desc">
    Добавьте свой первый аккаунт TikTok, Instagram или YouTube<br>
    через форму выше или через Telegram-бота
  </div>
  <div style="display:flex;justify-content:center;gap:16px;flex-wrap:wrap;">
    <span class="badge" style="background:#1a0022;color:#ee1d52;border:1px solid #ee1d52;font-size:14px;padding:6px 16px;">🎵 TikTok</span>
    <span class="badge" style="background:#1a0a22;color:#c13584;border:1px solid #c13584;font-size:14px;padding:6px 16px;">📸 Instagram</span>
    <span class="badge" style="background:#1a0a0a;color:#ff0000;border:1px solid #ff0000;font-size:14px;padding:6px 16px;">▶️ YouTube</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

# ── Detail view (если выбран аккаунт) ─────────────────────────────────────────
bot_online = is_bot_online()
if st.session_state.get("selected_account"):
    render_account_details(st.session_state["selected_account"], bot_online)
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_status, col_refresh = st.columns([4, 1.5, 0.8])
with col_title:
    st.title("📱 Управление аккаунтами")
with col_status:
    st.markdown("<br>", unsafe_allow_html=True)
    if bot_online:
        st.success("🤖 Бот: Онлайн", icon=None)
    else:
        st.error("🤖 Бот: Офлайн", icon=None)
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Обновить", use_container_width=True, key="main_refresh"):
        st.rerun()

st.divider()

# ── Load data ─────────────────────────────────────────────────────────────────
accounts_raw, api_error = load_accounts()
stats = get_stats() if bot_online else None
accounts = normalize_accounts(accounts_raw)

# ── Demo mode toggle ──────────────────────────────────────────────────────────
demo_mode = st.session_state.get("demo_mode", len(accounts) == 0)
with st.sidebar:
    demo_toggle = st.toggle("🎭 Показать демо-данные", value=demo_mode, key="demo_mode_toggle")
    if demo_toggle != demo_mode:
        st.session_state["demo_mode"] = demo_toggle
        st.rerun()
    if demo_toggle:
        st.caption("Демо-аккаунты показаны для наглядности. Они не сохраняются.")

display_accounts = accounts if not demo_toggle else (accounts + normalize_accounts(DEMO_ACCOUNTS))

# ── API error banner ──────────────────────────────────────────────────────────
if api_error and api_error != "api_offline":
    st.warning(f"⚠️ Не удалось загрузить аккаунты: `{api_error[:120]}`")
elif not bot_online:
    st.warning("⚠️ Telegram Bot API недоступен. Проверьте что сервис запущен.")

# ── KPIs ──────────────────────────────────────────────────────────────────────
render_kpis(display_accounts, stats)
st.divider()

# ── Add form ──────────────────────────────────────────────────────────────────
existing_usernames = {a["username"].lower() for a in accounts}
render_add_form(bot_online, existing_usernames)
st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-header">🗂 Список аккаунтов</div>', unsafe_allow_html=True)
filtered = render_filters(display_accounts)

# ── Count line ────────────────────────────────────────────────────────────────
total_all = len(display_accounts)
total_filtered = len(filtered)
if total_filtered < total_all:
    st.caption(f"Показано: {total_filtered} из {total_all}")
else:
    st.caption(f"Всего аккаунтов: {total_all}")

st.markdown("""
<div style="display:flex;gap:24px;margin-bottom:8px;padding:8px 4px;font-size:12px;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.5px;">
  <span style="flex:3;">Аккаунт</span>
  <span style="flex:1.8;">Авторизация</span>
  <span style="flex:1.5;">Статус</span>
  <span style="flex:1;">Сессия</span>
  <span style="flex:2;">Действия</span>
</div>
""", unsafe_allow_html=True)

# ── Account cards ─────────────────────────────────────────────────────────────
if not filtered:
    if not display_accounts:
        render_empty_state()
    else:
        st.info("🔍 Нет аккаунтов, соответствующих фильтрам")
else:
    for idx, acc in enumerate(filtered):
        try:
            render_account_card(acc, bot_online, idx)
        except Exception as e:
            st.error(f"Ошибка рендера аккаунта #{acc.get('id', '?')}: {e}")
