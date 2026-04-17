"""Контент-план: календарь публикаций для всех аккаунтов."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, time as dtime, timezone
from collections import defaultdict
from calendar import monthrange

import pandas as pd
import streamlit as st

from utils.api_client import (
    get_accounts, list_posts, create_posts, delete_post, run_post_now,
    update_post, upload_media, is_bot_online,
)

st.set_page_config(page_title="Контент-план", page_icon="📅", layout="wide")

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.cp-day {
  background:#0f172a; border:1px solid #1e293b; border-radius:10px;
  padding:8px; min-height:110px; font-size:12px;
}
.cp-day-other { opacity:.35; }
.cp-day-today { border:2px solid #6366f1; }
.cp-day-num { font-weight:700; color:#94a3b8; font-size:12px; margin-bottom:6px; }
.cp-pill {
  display:block; padding:2px 6px; margin-bottom:3px; border-radius:6px;
  font-size:11px; color:#e2e8f0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
}
.cp-pill-tiktok    { background:#581c2c; }
.cp-pill-instagram { background:#3b0a3b; }
.cp-pill-youtube   { background:#5a1717; }
.cp-pill-published { opacity:.5; text-decoration:line-through; }
.cp-pill-failed    { background:#451a03 !important; color:#fcd34d; }
.cp-header {
  font-weight:700; color:#94a3b8; font-size:12px; text-align:center;
  padding:6px 0; text-transform:uppercase; letter-spacing:.5px;
}
.status-badge {
  display:inline-block; padding:2px 10px; border-radius:12px;
  font-size:11px; font-weight:600;
}
.status-scheduled  { background:#1e3a8a; color:#bfdbfe; }
.status-publishing { background:#7c2d12; color:#fed7aa; }
.status-published  { background:#064e3b; color:#6ee7b7; }
.status-failed     { background:#7f1d1d; color:#fca5a5; }
.status-cancelled  { background:#1e293b; color:#94a3b8; }
.status-draft      { background:#1c1917; color:#a8a29e; }
</style>
""", unsafe_allow_html=True)

PLATFORM_ICONS = {"tiktok": "🎵", "instagram": "📸", "youtube": "▶️"}
PLATFORM_LABELS = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}
STATUS_LABELS = {
    "scheduled":  ("⏳", "Запланирован"),
    "publishing": ("📤", "Публикуется"),
    "published":  ("✅", "Опубликован"),
    "failed":     ("❌", "Ошибка"),
    "cancelled":  ("🚫", "Отменён"),
    "draft":      ("📝", "Черновик"),
}
WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ── Header ───────────────────────────────────────────────────────────────────
bot_online = is_bot_online()
col_t, col_s, col_r = st.columns([4, 1.5, 0.8])
with col_t:
    st.title("📅 Контент-план")
    st.caption("Планируйте публикации для всех аккаунтов в одном месте. Движок публикации работает в фоне.")
with col_s:
    st.markdown("<br>", unsafe_allow_html=True)
    if bot_online:
        st.success("🤖 Движок: Активен")
    else:
        st.error("🤖 Движок: Офлайн")
with col_r:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Обновить", use_container_width=True):
        st.rerun()

if not bot_online:
    st.warning("⚠️ Telegram Bot API недоступен. Проверьте, что сервис на порту 3000 запущен.")
    st.stop()

with st.expander("ℹ️ Как настроить TikTok для реальной публикации"):
    st.markdown("""
**TikTok работает через реальный Playwright + Chromium.** Чтобы публикации действительно
проходили, нужны cookies авторизованной сессии:

1. В браузере зайдите в TikTok и войдите в свой аккаунт.
2. Установите расширение **Cookie Editor** (Chrome / Firefox).
3. Откройте расширение на странице TikTok → нажмите **«Export» → «Export as JSON»**.
4. На странице **«📱 Аккаунты»** добавьте аккаунт TikTok с типом **🍪 Cookies**
   и вставьте скопированный JSON.
5. Готово — теперь любой запланированный пост автоматически опубликуется
   через 30 секунд после наступления времени.

**Instagram и YouTube** пока работают в режиме симуляции (статус «Опубликован»
выставляется, но реальной публикации не происходит). Это следующий шаг разработки.
""")

# ── Load data ────────────────────────────────────────────────────────────────
accounts_raw = get_accounts() or []
accounts = [a for a in accounts_raw if isinstance(a, dict)]
posts_raw = list_posts() or []
posts = [p for p in posts_raw if isinstance(p, dict)]

if not accounts:
    st.info("ℹ️ Сначала добавьте хотя бы один аккаунт на странице «📱 Аккаунты», "
            "чтобы планировать публикации.")
    st.stop()

# ── KPI ──────────────────────────────────────────────────────────────────────
total_posts = len(posts)
scheduled = sum(1 for p in posts if p["status"] == "scheduled")
publishing = sum(1 for p in posts if p["status"] == "publishing")
published = sum(1 for p in posts if p["status"] == "published")
failed = sum(1 for p in posts if p["status"] == "failed")

next_post = None
upcoming = sorted(
    [p for p in posts if p["status"] == "scheduled"],
    key=lambda p: p["scheduled_at"],
)
if upcoming:
    next_post = upcoming[0]

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("📝 Всего", total_posts)
k2.metric("⏳ Запланировано", scheduled)
k3.metric("📤 Публикуется", publishing)
k4.metric("✅ Опубликовано", published)
k5.metric("❌ Ошибок", failed)
if next_post:
    when = datetime.fromisoformat(next_post["scheduled_at"].replace("Z", "+00:00"))
    k6.metric("⏰ Ближайший", when.strftime("%d.%m %H:%M"))
else:
    k6.metric("⏰ Ближайший", "—")

st.divider()

# ── Tabs: создать / календарь / список ───────────────────────────────────────
tab_new, tab_cal, tab_list = st.tabs(["➕ Запланировать", "🗓 Календарь", "📋 Список"])

# ───────── TAB: NEW POST ─────────────────────────────────────────────────────
with tab_new:
    st.markdown("##### Новая публикация")

    col_left, col_right = st.columns([2, 1])
    with col_left:
        # Select accounts
        st.markdown("**1. Выберите аккаунты**")
        acc_options = {f"{PLATFORM_ICONS.get(a['platform'],'📱')} @{a['username']} ({PLATFORM_LABELS.get(a['platform'], a['platform'])})": a["id"]
                       for a in accounts}
        selected_labels = st.multiselect(
            "Аккаунты",
            list(acc_options.keys()),
            default=list(acc_options.keys())[:1] if acc_options else [],
            label_visibility="collapsed",
        )
        selected_ids = [acc_options[l] for l in selected_labels]

        # Media
        st.markdown("**2. Медиафайл**")
        media_file = st.file_uploader(
            "Видео или картинка",
            type=["mp4", "mov", "m4v", "webm", "jpg", "jpeg", "png", "webp", "gif"],
            label_visibility="collapsed",
        )

        # Caption
        st.markdown("**3. Текст публикации**")
        caption = st.text_area(
            "Описание",
            placeholder="Текст поста, упоминания (@user), эмодзи…",
            height=110,
            label_visibility="collapsed",
        )
        hashtags = st.text_input(
            "Хэштеги",
            placeholder="#маркетинг #smm #автоматизация",
        )

    with col_right:
        st.markdown("**4. Когда публиковать**")
        mode = st.radio(
            "Режим планирования",
            ["Одно время для всех", "С интервалом между аккаунтами"],
            label_visibility="collapsed",
        )

        col_d, col_t = st.columns(2)
        publish_date = col_d.date_input("Дата", value=datetime.now().date())
        publish_time = col_t.time_input("Время", value=(datetime.now() + timedelta(minutes=10)).time())

        interval_min = 0
        if mode == "С интервалом между аккаунтами":
            interval_min = st.number_input(
                "Интервал между аккаунтами (минут)", min_value=1, max_value=240, value=15,
            )
            st.caption(f"Первый аккаунт — в выбранное время, остальные — каждые {interval_min} мин позже.")

        st.markdown("**5. Дополнительно**")
        kind = st.selectbox("Тип контента", ["video", "reels", "image", "story"],
                            format_func=lambda x: {"video": "🎬 Видео", "reels": "🎞 Reels",
                                                   "image": "🖼 Картинка", "story": "📱 Story"}[x])

    st.markdown("---")
    submit_col, spacer = st.columns([1, 3])
    if submit_col.button("📅 Запланировать публикации", type="primary", use_container_width=True):
        if not selected_ids:
            st.error("❌ Выберите хотя бы один аккаунт")
        else:
            # Upload media if provided
            media_path = None
            if media_file is not None:
                with st.spinner("Загружаю медиафайл…"):
                    up_res = upload_media(media_file.getvalue(), media_file.name)
                if not up_res or "error" in up_res:
                    st.error(f"❌ Ошибка загрузки файла: {up_res}")
                    st.stop()
                media_path = up_res["media_path"]
                st.success(f"✔ Файл загружен: {media_file.name} ({up_res['size']//1024} КБ)")

            base_dt = datetime.combine(publish_date, publish_time)
            results = []
            with st.spinner(f"Планирую {len(selected_ids)} публикаци(й)…"):
                if mode == "Одно время для всех":
                    res = create_posts(
                        account_ids=selected_ids,
                        scheduled_at=base_dt.isoformat(),
                        caption=caption, hashtags=hashtags,
                        media_path=media_path, media_kind=kind,
                    )
                    if isinstance(res, list):
                        results.extend(res)
                    else:
                        st.error(f"❌ Ошибка: {res}")
                else:
                    for i, acc_id in enumerate(selected_ids):
                        when = base_dt + timedelta(minutes=i * interval_min)
                        res = create_posts(
                            account_ids=[acc_id],
                            scheduled_at=when.isoformat(),
                            caption=caption, hashtags=hashtags,
                            media_path=media_path, media_kind=kind,
                        )
                        if isinstance(res, list):
                            results.extend(res)

            if results:
                st.success(f"✅ Создано публикаций: {len(results)}. Перейдите во вкладку «Календарь» или «Список».")
                st.balloons()
            else:
                st.error("❌ Не удалось создать публикации. Проверьте что движок запущен.")

# ───────── TAB: CALENDAR ─────────────────────────────────────────────────────
with tab_cal:
    today = datetime.now().date()
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = today.year
        st.session_state.cal_month = today.month

    nav_l, nav_c, nav_r, nav_today = st.columns([1, 3, 1, 1])
    if nav_l.button("◀", use_container_width=True, key="cal_prev"):
        m = st.session_state.cal_month - 1
        y = st.session_state.cal_year
        if m < 1:
            m, y = 12, y - 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()
    if nav_r.button("▶", use_container_width=True, key="cal_next"):
        m = st.session_state.cal_month + 1
        y = st.session_state.cal_year
        if m > 12:
            m, y = 1, y + 1
        st.session_state.cal_month, st.session_state.cal_year = m, y
        st.rerun()
    if nav_today.button("🏠 Сегодня", use_container_width=True, key="cal_today"):
        st.session_state.cal_year, st.session_state.cal_month = today.year, today.month
        st.rerun()

    months_ru = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                 "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
    nav_c.markdown(f"<h3 style='text-align:center;margin:0;'>{months_ru[st.session_state.cal_month-1]} {st.session_state.cal_year}</h3>",
                   unsafe_allow_html=True)

    # Group posts by date
    posts_by_day = defaultdict(list)
    for p in posts:
        try:
            dt = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
            posts_by_day[dt.date()].append((dt, p))
        except Exception:
            pass

    # Render header
    head_cols = st.columns(7)
    for i, wd in enumerate(WEEKDAYS):
        head_cols[i].markdown(f"<div class='cp-header'>{wd}</div>", unsafe_allow_html=True)

    # Build grid
    year, month = st.session_state.cal_year, st.session_state.cal_month
    first_day = datetime(year, month, 1).date()
    first_weekday = first_day.weekday()  # 0 = Mon
    days_in_month = monthrange(year, month)[1]
    grid_start = first_day - timedelta(days=first_weekday)

    for week in range(6):
        cols = st.columns(7)
        for d in range(7):
            day = grid_start + timedelta(days=week * 7 + d)
            day_posts = sorted(posts_by_day.get(day, []), key=lambda x: x[0])
            other = day.month != month
            is_today = day == today
            cls = "cp-day"
            if other: cls += " cp-day-other"
            if is_today: cls += " cp-day-today"

            html = f"<div class='{cls}'><div class='cp-day-num'>{day.day}</div>"
            for dt, p in day_posts[:4]:
                pcls = f"cp-pill cp-pill-{p['platform']}"
                if p["status"] == "published": pcls += " cp-pill-published"
                if p["status"] == "failed":    pcls += " cp-pill-failed"
                icon = PLATFORM_ICONS.get(p["platform"], "📱")
                user = p.get("username") or f"#{p['account_id']}"
                html += f"<span class='{pcls}'>{dt.strftime('%H:%M')} {icon} @{user}</span>"
            if len(day_posts) > 4:
                html += f"<span class='cp-pill' style='background:#1e293b;'>+ ещё {len(day_posts)-4}</span>"
            html += "</div>"
            cols[d].markdown(html, unsafe_allow_html=True)

        # Stop if we've exhausted the month
        last_day_in_grid = grid_start + timedelta(days=week*7 + 6)
        if last_day_in_grid >= datetime(year, month, days_in_month).date() and week >= 3:
            if last_day_in_grid.month != month:
                break

# ───────── TAB: LIST ─────────────────────────────────────────────────────────
with tab_list:
    st.markdown("##### Все запланированные публикации")

    f1, f2, f3 = st.columns([1.5, 1.5, 1])
    status_options = {
        "Все": None,
        "⏳ Запланирован": "scheduled",
        "📤 Публикуется": "publishing",
        "✅ Опубликован": "published",
        "❌ Ошибка": "failed",
        "🚫 Отменён": "cancelled",
    }
    status_label = f1.selectbox("Статус", list(status_options.keys()))
    status_filter = status_options[status_label]

    plat_options = {"Все": None, "🎵 TikTok": "tiktok", "📸 Instagram": "instagram", "▶️ YouTube": "youtube"}
    plat_label = f2.selectbox("Платформа", list(plat_options.keys()))
    plat_filter = plat_options[plat_label]

    sort_order = f3.selectbox("Сортировка", ["По дате ↑", "По дате ↓"])

    filtered = posts[:]
    if status_filter:
        filtered = [p for p in filtered if p["status"] == status_filter]
    if plat_filter:
        filtered = [p for p in filtered if p["platform"] == plat_filter]
    filtered.sort(key=lambda p: p["scheduled_at"], reverse=(sort_order == "По дате ↓"))

    if not filtered:
        st.info("📭 Нет публикаций по выбранным фильтрам.")
    else:
        st.caption(f"Показано: {len(filtered)} из {len(posts)}")
        for p in filtered:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 3, 1.5, 1.5, 2])
                dt = datetime.fromisoformat(p["scheduled_at"].replace("Z", "+00:00"))
                icon = PLATFORM_ICONS.get(p["platform"], "📱")
                user = p.get("username") or f"#{p['account_id']}"
                c1.markdown(f"**{dt.strftime('%d.%m.%Y %H:%M')}**")
                c1.caption(f"{icon} @{user}")

                preview = (p.get("caption") or "—")[:90]
                c2.markdown(f"`{preview}`" if preview != "—" else "—")
                if p.get("hashtags"):
                    c2.caption(p["hashtags"][:80])

                kind_ru = {"video":"Видео","reels":"Reels","image":"Картинка","story":"Story"}.get(p["media_kind"], p["media_kind"])
                kind_lbl = {"video":"🎬","reels":"🎞","image":"🖼","story":"📱"}.get(p["media_kind"], "📄")
                c3.markdown(f"{kind_lbl} {kind_ru}")
                if p.get("media_path"):
                    c3.caption(f"📎 {os.path.basename(p['media_path'])[:14]}…")

                st_info = STATUS_LABELS.get(p["status"], ("❓", p["status"]))
                c4.markdown(f"<span class='status-badge status-{p['status']}'>{st_info[0]} {st_info[1]}</span>",
                            unsafe_allow_html=True)
                if p.get("error_message"):
                    c4.caption(f"⚠️ {p['error_message'][:60]}")

                with c5:
                    btn_run, btn_del = st.columns(2)
                    if p["status"] in ("scheduled", "failed"):
                        if btn_run.button("▶ Сейчас", key=f"run_{p['id']}", use_container_width=True,
                                         help="Опубликовать немедленно"):
                            res = run_post_now(p["id"])
                            if res and not (isinstance(res, dict) and "error" in res):
                                st.toast("Поставлено в очередь немедленной публикации", icon="🚀")
                                st.rerun()
                            else:
                                st.error(f"Ошибка: {res}")
                    else:
                        btn_run.markdown("&nbsp;")
                    if btn_del.button("🗑", key=f"del_post_{p['id']}", use_container_width=True,
                                      help="Удалить публикацию"):
                        res = delete_post(p["id"])
                        if res and (isinstance(res, dict) and res.get("success")):
                            st.toast("Публикация удалена", icon="🗑")
                            st.rerun()
                        else:
                            st.error(f"Ошибка удаления: {res}")
                st.markdown("<hr style='margin:8px 0; border-color:#1e293b;'>", unsafe_allow_html=True)
