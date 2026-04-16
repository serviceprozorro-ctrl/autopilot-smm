import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.graph_objects as go
import psutil
import platform
from datetime import datetime
from utils.api_client import get_stats, get_accounts, is_bot_online

st.set_page_config(
    page_title="AutoPilot — SMM Control Panel",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 AutoPilot")
    st.markdown("**SMM Control Panel**")
    st.divider()
    bot_status = is_bot_online()
    if bot_status:
        st.success("🤖 Telegram Bot: Online")
    else:
        st.error("🤖 Telegram Bot: Offline")
    st.caption(f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    st.divider()
    st.page_link("pages/0_⚙️_Settings.py", label="⚙️ Настройки бота")
    st.divider()
    st.markdown("### 🛠 Инструменты")
    st.page_link("pages/1_📱_Accounts.py", label="📱 Аккаунты")
    st.page_link("pages/2_🖼_Background_Remover.py", label="🖼 Убрать фон")
    st.page_link("pages/3_🧾_QR_Generator.py", label="🧾 QR-код")
    st.page_link("pages/4_💻_Fake_Data.py", label="💻 Fake Data")
    st.page_link("pages/5_📥_YouTube_Downloader.py", label="📥 YouTube DL")
    st.page_link("pages/6_📊_Resource_Monitor.py", label="📊 Мониторинг")
    st.page_link("pages/7_🔍_Code_Analyzer.py", label="🔍 Анализ кода")
    st.page_link("pages/8_🔗_Link_Checker.py", label="🔗 Link Checker")
    st.page_link("pages/9_📷_Image_Editor.py", label="📷 Редактор фото")
    st.page_link("pages/10_📝_Article_Summarizer.py", label="📝 Суммаризатор")
    st.page_link("pages/11_🗞_News_Reader.py", label="🗞 Новости")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🚀 AutoPilot — SMM Control Panel")
st.markdown("Панель управления мульти-аккаунтами и инструменты автоматизации в одном месте")
st.divider()

# ── Account stats from bot API ────────────────────────────────────────────────
stats = get_stats() if bot_status else None
accounts = get_accounts() if bot_status else []

col1, col2, col3, col4, col5 = st.columns(5)

total = stats.get("total_accounts", 0) if stats else 0
active = stats.get("by_status", {}).get("active", 0) if stats else 0
banned = stats.get("by_status", {}).get("banned", 0) if stats else 0
tiktok = stats.get("by_platform", {}).get("tiktok", 0) if stats else 0
instagram = stats.get("by_platform", {}).get("instagram", 0) if stats else 0

with col1:
    st.metric("📱 Всего аккаунтов", total)
with col2:
    st.metric("✅ Активных", active)
with col3:
    st.metric("🚫 Забаненных", banned)
with col4:
    st.metric("🎵 TikTok", tiktok)
with col5:
    st.metric("📸 Instagram", instagram)

st.divider()

# ── Charts ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📊 По платформам")
    if stats and total > 0:
        by_platform = stats.get("by_platform", {})
        labels = ["TikTok", "Instagram", "YouTube"]
        values = [
            by_platform.get("tiktok", 0),
            by_platform.get("instagram", 0),
            by_platform.get("youtube", 0),
        ]
        fig = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=0.4,
            marker_colors=["#EE1D52", "#C13584", "#FF0000"],
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#E2E8F0", margin=dict(t=20, b=20, l=20, r=20), height=280,
            showlegend=True, legend=dict(font=dict(color="#E2E8F0")),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Нет данных. Добавьте аккаунты через раздел 📱 Аккаунты.")

with col_right:
    st.subheader("🖥 Ресурсы системы")
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    for label, value, color in [
        ("CPU", cpu, "#7C3AED"),
        ("RAM", ram.percent, "#2563EB"),
        ("Диск", disk.percent, "#059669"),
    ]:
        st.markdown(f"**{label}** — {value:.1f}%")
        st.progress(int(value) / 100)

    st.caption(f"Python {platform.python_version()} · {platform.system()} {platform.machine()}")

st.divider()

# ── Recent accounts table ─────────────────────────────────────────────────────
st.subheader("📋 Последние аккаунты")
if accounts:
    platform_icons = {"tiktok": "🎵", "instagram": "📸", "youtube": "▶️"}
    status_icons = {"active": "✅", "banned": "🚫", "inactive": "⏸", "pending": "⏳"}
    auth_icons = {"cookies": "🍪", "login_password": "🔐", "qr_code": "📱", "api": "🔑"}

    rows = []
    for acc in accounts[:10]:
        rows.append({
            "Платформа": platform_icons.get(acc.get("platform",""), "📱") + " " + acc.get("platform","").capitalize(),
            "Username": "@" + acc.get("username", ""),
            "Авторизация": auth_icons.get(acc.get("auth_type",""), "❓") + " " + acc.get("auth_type",""),
            "Статус": status_icons.get(acc.get("status",""), "❓") + " " + acc.get("status",""),
            "Сессия": "✔" if acc.get("has_session") else "✘",
            "ID": acc.get("id"),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)
elif bot_status:
    st.info("Аккаунты не добавлены. Используйте раздел 📱 Аккаунты или Telegram-бота.")
else:
    st.warning("⚠️ Social Media Bot недоступен. Убедитесь, что он запущен.")

st.divider()

# ── Tools grid ────────────────────────────────────────────────────────────────
st.subheader("🛠 Инструменты AutoPilot")
tools = [
    ("🖼", "Background Remover", "Убирает фон с фото за секунду", "pages/2_🖼_Background_Remover.py"),
    ("🧾", "QR Generator", "QR-коды для ссылок, текста, WiFi", "pages/3_🧾_QR_Generator.py"),
    ("💻", "Fake Data", "Реалистичные тестовые данные", "pages/4_💻_Fake_Data.py"),
    ("📥", "YouTube DL", "Скачать видео/аудио с YouTube", "pages/5_📥_YouTube_Downloader.py"),
    ("📊", "Resource Monitor", "Мониторинг CPU, RAM, диска", "pages/6_📊_Resource_Monitor.py"),
    ("🔍", "Code Analyzer", "Анализ кода через Pylint/Pyflakes", "pages/7_🔍_Code_Analyzer.py"),
    ("🔗", "Link Checker", "Проверка живых ссылок", "pages/8_🔗_Link_Checker.py"),
    ("📷", "Image Editor", "Кроп, blur, resize, эффекты", "pages/9_📷_Image_Editor.py"),
    ("📝", "Summarizer", "Краткое изложение статей", "pages/10_📝_Article_Summarizer.py"),
    ("🗞", "News Reader", "Актуальные новости из RSS", "pages/11_🗞_News_Reader.py"),
]

cols = st.columns(5)
for i, (emoji, name, desc, page) in enumerate(tools):
    with cols[i % 5]:
        st.markdown(f"### {emoji} {name}")
        st.caption(desc)
        st.page_link(page, label=f"Открыть →")
        st.divider()
