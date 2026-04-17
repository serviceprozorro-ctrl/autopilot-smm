"""Аналитика по аккаунтам: подписчики, посты, охваты, рост."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime
import pandas as pd
import streamlit as st

from utils.api_client import (
    analytics_overview, analytics_account, create_analytics_snapshot,
    get_accounts,
)

st.set_page_config(page_title="Аналитика", page_icon="📊", layout="wide")
st.title("📊 Аналитика аккаунтов")
st.caption("Снимки статистики по подписчикам, постам и вовлечённости. "
           "Делай регулярные снимки — увидишь рост во времени.")

overview = analytics_overview()
if not overview:
    st.error("Не удалось получить данные. Проверь, что бот работает.")
    st.stop()

# ── Topline ─────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("👥 Всего подписчиков", overview.get("total_followers", 0))
c2.metric("📱 Аккаунтов", overview.get("total_accounts", 0))
accs = overview.get("accounts", [])
avg_er = (sum(a.get("engagement_rate", 0) for a in accs) / len(accs)) if accs else 0
c3.metric("💬 Средний ER", f"{avg_er:.2f}%")

st.divider()

# ── Таблица аккаунтов ───────────────────────────────────────────────────────
if accs:
    df = pd.DataFrame(accs)
    df["last_update"] = df["last_update"].apply(
        lambda x: datetime.fromisoformat(x).strftime("%d.%m %H:%M") if x else "нет данных"
    )
    df = df.rename(columns={
        "platform": "Платформа", "username": "Логин",
        "followers": "Подписчики", "posts_count": "Постов",
        "engagement_rate": "ER, %", "last_update": "Обновлено",
    })
    st.dataframe(df[["Платформа", "Логин", "Подписчики", "Постов", "ER, %", "Обновлено"]],
                 use_container_width=True, hide_index=True)
else:
    st.info("Нет аккаунтов. Добавь хотя бы один в «📱 Аккаунты».")

st.divider()

# ── Снимок статистики ───────────────────────────────────────────────────────
st.subheader("📸 Внести снимок статистики")
st.caption("Платформы не дают публичный API без ключей — пока вводишь данные руками "
           "или через Mini App. Снимки накапливаются → строим графики.")

accounts = get_accounts() or []
if accounts:
    with st.form("snapshot_form"):
        c1, c2 = st.columns([2, 3])
        acc_options = [f"#{a['id']} {a['platform']} @{a['username']}" for a in accounts]
        chosen = c1.selectbox("Аккаунт", acc_options)
        chosen_id = accounts[acc_options.index(chosen)]["id"]

        cf1, cf2, cf3 = c2.columns(3)
        followers = cf1.number_input("Подписчики", 0, 100_000_000, 0, step=100)
        following = cf2.number_input("Подписки", 0, 100_000, 0, step=10)
        posts_n = cf3.number_input("Постов", 0, 1_000_000, 0)

        cf4, cf5, cf6 = c2.columns(3)
        likes_total = cf4.number_input("Всего лайков", 0, 1_000_000_000, 0, step=1000)
        avg_views = cf5.number_input("Средние просмотры", 0, 100_000_000, 0, step=100)
        er = cf6.number_input("ER, %", 0.0, 100.0, 0.0, step=0.1)

        if st.form_submit_button("💾 Сохранить снимок", type="primary"):
            res = create_analytics_snapshot(
                chosen_id, followers=followers, following=following,
                posts_count=posts_n, likes_total=likes_total,
                avg_views=avg_views, engagement_rate=er,
            )
            if res and "id" in res:
                st.success(f"Снимок #{res['id']} сохранён")
                st.rerun()
            else:
                st.error(f"Ошибка: {res}")

# ── История по конкретному аккаунту ────────────────────────────────────────
st.divider()
st.subheader("📈 История роста")

if accounts:
    acc_options = [f"#{a['id']} {a['platform']} @{a['username']}" for a in accounts]
    pick = st.selectbox("Выбери аккаунт", acc_options, key="history_pick")
    pick_id = accounts[acc_options.index(pick)]["id"]
    detail = analytics_account(pick_id)

    if detail and detail.get("history"):
        c1, c2, c3 = st.columns(3)
        latest = detail.get("latest") or {}
        c1.metric("👥 Подписчики", latest.get("followers", 0),
                  delta=detail.get("growth_followers_7d", 0), delta_color="normal",
                  help="Δ за 7 дней")
        c2.metric("📈 Рост за 30 дн", detail.get("growth_followers_30d", 0))
        c3.metric("Снимков всего", len(detail["history"]))

        hist = pd.DataFrame(detail["history"])
        hist["captured_at"] = pd.to_datetime(hist["captured_at"])
        hist = hist.sort_values("captured_at")
        hist = hist.set_index("captured_at")
        st.line_chart(hist[["followers", "posts_count"]])
        st.area_chart(hist[["engagement_rate"]])
    else:
        st.info("Для этого аккаунта ещё нет снимков. Добавь хотя бы один выше.")
