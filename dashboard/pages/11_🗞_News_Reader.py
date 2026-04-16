import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import feedparser
from datetime import datetime
import html
import re

st.set_page_config(page_title="News Reader", page_icon="🗞", layout="wide")
st.title("🗞 News Reader")
st.markdown("Читайте актуальные новости из RSS-лент прямо в панели")

FEEDS = {
    "🇷🇺 RBC": "https://rss.rbctv.ru/rbc_top/index.rss",
    "🇷🇺 Lenta.ru": "https://lenta.ru/rss",
    "🇷🇺 Habr (Tech)": "https://habr.com/ru/rss/articles/?fl=ru",
    "🇺🇸 BBC World": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "🇺🇸 Hacker News": "https://news.ycombinator.com/rss",
    "🇺🇸 TechCrunch": "https://techcrunch.com/feed/",
    "🌍 Reuters": "https://feeds.reuters.com/reuters/topNews",
    "💰 CoinDesk (Crypto)": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "📱 The Verge": "https://www.theverge.com/rss/index.xml",
}

col_left, col_right = st.columns([1, 3])

with col_left:
    st.subheader("📡 Источники")
    selected_feeds = st.multiselect(
        "Выберите ленты",
        list(FEEDS.keys()),
        default=["🇷🇺 Habr (Tech)", "🇺🇸 Hacker News"],
    )

    custom_url = st.text_input("➕ Добавить свой RSS", placeholder="https://example.com/feed.xml")
    if custom_url:
        FEEDS["🔗 Свой"] = custom_url
        if "🔗 Свой" not in selected_feeds:
            selected_feeds.append("🔗 Свой")

    count = st.slider("Новостей из каждой ленты", 5, 50, 15)
    search_query = st.text_input("🔍 Поиск по заголовкам", placeholder="python, AI, crypto...")

    refresh = st.button("🔄 Загрузить новости", type="primary", use_container_width=True)

def clean_html(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def parse_date(entry) -> str:
    for attr in ["published_parsed", "updated_parsed"]:
        if hasattr(entry, attr) and getattr(entry, attr):
            try:
                return datetime(*getattr(entry, attr)[:6]).strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass
    return ""

with col_right:
    if refresh or ("news_items" not in st.session_state and selected_feeds):
        all_items = []
        progress = st.progress(0)

        for i, feed_name in enumerate(selected_feeds):
            url = FEEDS.get(feed_name, "")
            if not url:
                continue
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:count]:
                    title = clean_html(entry.get("title", "Без заголовка"))
                    summary = clean_html(entry.get("summary", entry.get("description", "")))
                    link = entry.get("link", "")
                    date = parse_date(entry)
                    all_items.append({
                        "source": feed_name,
                        "title": title,
                        "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                        "link": link,
                        "date": date,
                    })
            except Exception as e:
                st.warning(f"Не удалось загрузить {feed_name}: {e}")
            progress.progress((i + 1) / len(selected_feeds))

        progress.empty()

        if search_query:
            q = search_query.lower()
            all_items = [item for item in all_items if q in item["title"].lower() or q in item["summary"].lower()]

        st.session_state["news_items"] = all_items

    items = st.session_state.get("news_items", [])

    if not items:
        st.info("Выберите ленты и нажмите «Загрузить новости»")
    else:
        st.markdown(f"**{len(items)} новостей**" + (f' по запросу «{search_query}»' if search_query else ""))
        st.divider()

        for item in items:
            col_badge, col_content = st.columns([1, 5])
            with col_badge:
                st.caption(item["source"])
                if item["date"]:
                    st.caption(item["date"])
            with col_content:
                if item["link"]:
                    st.markdown(f"### [{item['title']}]({item['link']})")
                else:
                    st.markdown(f"### {item['title']}")
                if item["summary"]:
                    st.markdown(item["summary"])
            st.divider()
