import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import requests
import concurrent.futures
from urllib.parse import urlparse
import time

st.set_page_config(page_title="Проверка ссылок", page_icon="🔗", layout="wide")
st.title("🔗 Проверка ссылок")
st.markdown("Проверьте статус ссылок: живые, мёртвые, редиректы")

EXAMPLE_URLS = """https://google.com
https://github.com
https://python.org
https://this-url-does-not-exist-404.com
https://httpstat.us/301
https://httpstat.us/403
https://httpstat.us/500
https://youtube.com"""

urls_input = st.text_area(
    "Введите URL (по одному на строку)",
    value=EXAMPLE_URLS,
    height=200,
    placeholder="https://example.com\nhttps://another.com",
)

col1, col2, col3 = st.columns(3)
timeout = col1.slider("Таймаут (сек)", 1, 30, 8)
max_workers = col2.slider("Параллельность", 1, 20, 5)
follow_redirects = col3.checkbox("Следовать редиректам", value=True)

def check_url(url: str, timeout: int, follow: bool) -> dict:
    url = url.strip()
    if not url or not url.startswith(("http://", "https://")):
        return {"url": url, "status": None, "code": "INVALID", "time_ms": 0, "final_url": url}

    start = time.time()
    try:
        resp = requests.head(
            url, timeout=timeout, allow_redirects=follow,
            headers={"User-Agent": "Mozilla/5.0 LinkChecker/1.0"},
        )
        # Some servers don't support HEAD, fallback to GET
        if resp.status_code == 405:
            resp = requests.get(
                url, timeout=timeout, allow_redirects=follow,
                headers={"User-Agent": "Mozilla/5.0 LinkChecker/1.0"},
                stream=True,
            )
        elapsed = int((time.time() - start) * 1000)
        final_url = resp.url if follow else url
        return {
            "url": url,
            "status": "✅ Живая" if resp.status_code < 400 else ("🔄 Редирект" if 300 <= resp.status_code < 400 else "❌ Ошибка"),
            "code": resp.status_code,
            "time_ms": elapsed,
            "final_url": final_url,
        }
    except requests.exceptions.Timeout:
        return {"url": url, "status": "⏰ Таймаут", "code": "TIMEOUT", "time_ms": timeout * 1000, "final_url": url}
    except requests.exceptions.ConnectionError:
        return {"url": url, "status": "💀 Мёртвая", "code": "CONN_ERR", "time_ms": int((time.time()-start)*1000), "final_url": url}
    except Exception as e:
        return {"url": url, "status": "❓ Ошибка", "code": str(e)[:30], "time_ms": 0, "final_url": url}


if st.button("🔍 Проверить ссылки", type="primary", use_container_width=True):
    urls = [u.strip() for u in urls_input.strip().splitlines() if u.strip()]
    if not urls:
        st.warning("Введите хотя бы один URL")
    else:
        st.markdown(f"Проверяю **{len(urls)}** ссылок...")
        progress = st.progress(0)
        results_placeholder = st.empty()
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(check_url, url, timeout, follow_redirects): url for url in urls}
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                results.append(future.result())
                progress.progress((i + 1) / len(urls))

        progress.empty()

        # Summary
        ok = sum(1 for r in results if "✅" in str(r["status"]))
        dead = sum(1 for r in results if "💀" in str(r["status"]) or "❌" in str(r["status"]))
        timeout_c = sum(1 for r in results if "⏰" in str(r["status"]))
        redirect = sum(1 for r in results if "🔄" in str(r["status"]))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Живые", ok)
        c2.metric("💀 Мёртвые", dead)
        c3.metric("🔄 Редиректы", redirect)
        c4.metric("⏰ Таймаут", timeout_c)

        # Сначала мёртвые
        results.sort(key=lambda x: 0 if "💀" in str(x["status"]) or "❌" in str(x["status"]) else 1)

        table_data = [{
            "Статус": r["status"],
            "Код": r["code"],
            "URL": r["url"],
            "Время (мс)": r["time_ms"],
            "Итоговый URL": r["final_url"] if r["final_url"] != r["url"] else "",
        } for r in results]

        st.dataframe(table_data, use_container_width=True, hide_index=True)
