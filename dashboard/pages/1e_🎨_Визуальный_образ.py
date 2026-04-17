"""Визуальная идентичность: загрузка эталонного фото, анализ Claude,
генерация вариаций через Grok (xAI), хранение в портфолио."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import base64
import json
import time
from pathlib import Path

import streamlit as st
from anthropic import Anthropic

from utils import xai_client
from utils.api_client import (
    list_portfolio, upload_portfolio, create_portfolio_item,
    delete_portfolio, get_accounts,
)

st.set_page_config(page_title="Визуальный образ", page_icon="🎨", layout="wide")
st.title("🎨 Визуальный образ — портфолио для контента")
st.caption("Загрузи эталонное фото → AI-анализ → набор вариаций (поза, фон, свет). "
           "Используй образ при генерации сценариев в «🎬 Продакшн».")

PORTFOLIO_VAR_DIR = Path(__file__).resolve().parents[1] / "production_output" / "portfolio_variations"
PORTFOLIO_VAR_DIR.mkdir(parents=True, exist_ok=True)


def _anthropic() -> Anthropic:
    return Anthropic(
        base_url=os.environ["AI_INTEGRATIONS_ANTHROPIC_BASE_URL"],
        api_key=os.environ["AI_INTEGRATIONS_ANTHROPIC_API_KEY"],
    )


def analyze_reference(image_bytes: bytes, mime: str) -> dict:
    """Claude Vision: описание персонажа + рекомендации по съёмкам."""
    b64 = base64.standard_b64encode(image_bytes).decode()
    client = _anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {
                "type": "base64", "media_type": mime, "data": b64,
            }},
            {"type": "text", "text": (
                "Проанализируй фото для социального контента. Верни СТРОГО JSON:\n"
                "{\n"
                "  \"description\": \"короткое описание героя на английском (для генератора)\",\n"
                "  \"style_tags\": [\"5-8 тегов на русском: стиль, цвет, настроение\"],\n"
                "  \"strengths\": [\"что хорошо смотрится в кадре\"],\n"
                "  \"recommendations\": [\"3-5 идей вариаций: позы, локации, свет\"],\n"
                "  \"quality_score\": <0-10 — насколько фото подходит как эталон>\n"
                "}\nТолько JSON, без markdown."
            )},
        ]}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    return json.loads(text)


# ── State ───────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("portfolio_analysis", None)
ss.setdefault("portfolio_uploaded_id", None)

if not xai_client.is_available():
    st.warning("⚠️ XAI_API_KEY не задан — генерация вариаций недоступна. "
               "Можно загружать и анализировать эталонные фото.")

tab_upload, tab_gallery = st.tabs(["📤 Загрузить и проанализировать", "🖼 Моё портфолио"])

# ── Upload tab ──────────────────────────────────────────────────────────────
with tab_upload:
    st.subheader("Шаг 1 — Загрузка эталонного фото")

    accounts = get_accounts() or []
    acc_options = ["— общий —"] + [
        f"#{a['id']} {a['platform']} @{a['username']}" for a in accounts
    ]
    c1, c2 = st.columns([2, 1])
    title = c1.text_input("Название образа", value="Основной образ")
    acc_choice = c2.selectbox("К аккаунту", acc_options)
    account_id = None
    if acc_choice != "— общий —":
        account_id = accounts[acc_options.index(acc_choice) - 1]["id"]

    photo = st.file_uploader("Эталонное фото", type=["png", "jpg", "jpeg", "webp"])

    if photo and st.button("🧠 Проанализировать и сохранить", type="primary"):
        with st.spinner("Claude изучает кадр…"):
            try:
                mime = f"image/{photo.type.split('/')[-1]}" if photo.type else "image/jpeg"
                analysis = analyze_reference(photo.getvalue(), mime)
                ss.portfolio_analysis = analysis
                up = upload_portfolio(
                    photo.getvalue(), photo.name,
                    title=title, account_id=account_id,
                    description=analysis.get("description", ""),
                    style_tags=", ".join(analysis.get("style_tags", [])),
                )
                ss.portfolio_uploaded_id = up.get("id") if up else None
                st.success("Готово — образ в портфолио")
            except Exception as e:
                st.error(f"Ошибка анализа: {e}")

    if ss.portfolio_analysis:
        a = ss.portfolio_analysis
        st.divider()
        st.subheader("📋 Анализ образа")
        c1, c2 = st.columns(2)
        c1.metric("Качество как эталона", f"{a.get('quality_score', 0)}/10")
        c2.write("**Сильные стороны:**")
        for s in a.get("strengths", []):
            c2.markdown(f"- {s}")
        st.write("**Описание:** " + a.get("description", "—"))
        st.write("**Теги:** " + ", ".join(a.get("style_tags", [])))
        st.write("**Рекомендации:**")
        for r in a.get("recommendations", []):
            st.markdown(f"- {r}")

        st.divider()
        st.subheader("Шаг 2 — Сгенерировать вариации (Grok)")
        n = st.slider("Сколько вариаций", 2, 6, 4)
        if st.button("✨ Сгенерировать", disabled=not xai_client.is_available()):
            with st.spinner(f"Grok рисует {n} вариаций…"):
                try:
                    addons = (a.get("recommendations") or [])[:n]
                    while len(addons) < n:
                        addons.append("alternative pose, different lighting")
                    sub_dir = PORTFOLIO_VAR_DIR / str(int(time.time()))
                    paths = xai_client.generate_variations(
                        a.get("description", "subject"),
                        addons[:n], sub_dir, prefix="var",
                    )
                    if not paths:
                        st.error("Grok не вернул картинки")
                    for i, p in enumerate(paths):
                        create_portfolio_item(
                            image_path=str(p),
                            title=f"{title} · вариация {i+1}",
                            account_id=account_id,
                            source="grok",
                            description=f"{a.get('description','')} | {addons[i]}",
                            style_tags=a.get("style_tags", []),
                            parent_id=ss.portfolio_uploaded_id,
                        )
                    st.success(f"Готово: {len(paths)} вариаций в портфолио")
                except Exception as e:
                    st.error(f"Ошибка: {e}")

# ── Gallery tab ─────────────────────────────────────────────────────────────
with tab_gallery:
    items = list_portfolio() or []
    if not items:
        st.info("Портфолио пусто — загрузи первое фото на вкладке слева.")
    else:
        st.caption(f"Всего образов: {len(items)}")
        cols = st.columns(4)
        for i, it in enumerate(items):
            with cols[i % 4]:
                if Path(it["image_path"]).exists():
                    st.image(it["image_path"], use_container_width=True)
                else:
                    st.warning(f"Файл потерян: {it['image_path']}")
                st.markdown(f"**{it['title']}**")
                st.caption(f"#{it['id']} · {it['source']}")
                if it.get("style_tags"):
                    st.caption("🏷 " + ", ".join(it["style_tags"][:5]))
                if st.button("🗑", key=f"del_p_{it['id']}", help="Удалить"):
                    delete_portfolio(it["id"])
                    st.rerun()
