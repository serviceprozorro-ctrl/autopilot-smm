"""Полный пайплайн продакшна: идея → сценарий → картинки → озвучка → субтитры → видео."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import time
from pathlib import Path

import streamlit as st

from utils import video_producer as vp
from utils.api_client import upload_media

st.set_page_config(page_title="Продакшн", page_icon="🎬", layout="wide")
st.title("🎬 Продакшн — Создание видео под ключ")
st.caption("Идея → AI-сценарий → раскадровка → озвучка → субтитры → готовый MP4. "
           "Можно сразу запланировать в контент-плане.")

# ── State ───────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("prod_script", None)
ss.setdefault("prod_session_dir", None)
ss.setdefault("prod_images", [])
ss.setdefault("prod_audio", None)
ss.setdefault("prod_srt", None)
ss.setdefault("prod_video", None)


def reset():
    for k in ["prod_script", "prod_session_dir", "prod_images",
              "prod_audio", "prod_srt", "prod_video"]:
        ss[k] = None if k != "prod_images" else []


with st.sidebar:
    st.markdown("### 🎬 Сессия")
    if st.button("🗑 Начать заново", use_container_width=True):
        reset()
        st.rerun()
    st.divider()
    st.markdown("**Этапы:**")
    st.caption(f"1️⃣ Сценарий {'✅' if ss.prod_script else '⏳'}")
    st.caption(f"2️⃣ Картинки {'✅' if ss.prod_images else '⏳'}")
    st.caption(f"3️⃣ Озвучка {'✅' if ss.prod_audio else '⏳'}")
    st.caption(f"4️⃣ Субтитры {'✅' if ss.prod_srt else '⏳'}")
    st.caption(f"5️⃣ Видео {'✅' if ss.prod_video else '⏳'}")

# ── Step 1: Сценарий ────────────────────────────────────────────────────────
st.subheader("1️⃣ Сценарий")
with st.form("script_form"):
    c1, c2, c3 = st.columns([3, 1, 1])
    idea = c1.text_input("Идея видео", placeholder="Например: 5 лайфхаков для утренней рутины")
    duration = c2.number_input("Длительность, сек", 10, 120, 30, step=5)
    platform = c3.selectbox("Платформа", ["tiktok", "instagram", "youtube"])

    c4, c5 = st.columns([2, 1])
    style = c4.selectbox("Стиль подачи",
                         ["энергичный", "спокойный", "обучающий", "юмористический",
                          "вдохновляющий", "продающий"])
    submit = c5.form_submit_button("✨ Сгенерировать сценарий", type="primary",
                                    use_container_width=True)

if submit and idea:
    with st.spinner("Claude пишет сценарий…"):
        try:
            ss.prod_script = vp.generate_script(idea, duration, style, platform)
            session_id = str(int(time.time()))
            ss.prod_session_dir = vp.PRODUCTION_DIR / session_id
            ss.prod_session_dir.mkdir(exist_ok=True)
            (ss.prod_session_dir / "script.json").write_text(
                json.dumps(ss.prod_script, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success("Сценарий готов!")
        except Exception as e:
            st.error(f"Ошибка генерации сценария: {e}")

if ss.prod_script:
    sc = ss.prod_script
    with st.expander("📜 Готовый сценарий", expanded=True):
        st.markdown(f"**📌 Название:** {sc.get('title', '—')}")
        st.markdown(f"**🎣 Хук:** _{sc.get('hook', '—')}_")
        st.markdown(f"**🎬 Сцен:** {len(sc.get('scenes', []))}")
        for i, scene in enumerate(sc.get("scenes", []), 1):
            st.markdown(f"**Сцена {i}** — 🎤 {scene['narration']}")
            st.caption(f"🎨 Визуал: {scene['visual']}")
        st.markdown(f"**📣 CTA:** {sc.get('cta', '—')}")
        st.markdown(f"**🏷 Хэштеги:** `{sc.get('hashtags', '')}`")

st.divider()

# ── Step 2: Картинки ────────────────────────────────────────────────────────
st.subheader("2️⃣ Картинки сцен")
if ss.prod_script:
    if st.button("🖼 Сгенерировать картинки сцен", disabled=bool(ss.prod_images)):
        with st.spinner("Генерирую картинки…"):
            try:
                ss.prod_images = vp.generate_scene_images(
                    ss.prod_script["scenes"], ss.prod_session_dir)
                st.success(f"Готово: {len(ss.prod_images)} картинок")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    if ss.prod_images:
        st.info("ℹ️ Базовые плейсхолдеры. Можешь заменить любую картинку вручную ниже.")
        cols = st.columns(min(4, len(ss.prod_images)))
        for i, img_path in enumerate(ss.prod_images):
            with cols[i % len(cols)]:
                st.image(str(img_path), caption=f"Сцена {i+1}", use_container_width=True)
                replace = st.file_uploader(f"Заменить #{i+1}", type=["png", "jpg", "jpeg"],
                                           key=f"replace_{i}", label_visibility="collapsed")
                if replace:
                    img_path.write_bytes(replace.read())
                    st.rerun()
else:
    st.info("Сначала сгенерируй сценарий")

st.divider()

# ── Step 3: Озвучка ─────────────────────────────────────────────────────────
st.subheader("3️⃣ Озвучка")
if ss.prod_script and ss.prod_images:
    voice = st.selectbox("Голос диктора",
                         ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                         index=4, help="nova — женский, onyx — мужской глубокий")
    if st.button("🎙 Озвучить сценарий", disabled=bool(ss.prod_audio)):
        with st.spinner("OpenAI TTS озвучивает…"):
            try:
                full_text = " ".join(
                    [ss.prod_script.get("hook", "")] +
                    [s["narration"] for s in ss.prod_script["scenes"]] +
                    [ss.prod_script.get("cta", "")]
                ).strip()
                audio_path = ss.prod_session_dir / "voiceover.mp3"
                ss.prod_audio = vp.synthesize_voiceover(full_text, audio_path, voice)
                st.success("Готово!")
            except Exception as e:
                st.error(f"Ошибка озвучки: {e}")

    if ss.prod_audio and Path(ss.prod_audio).exists():
        st.audio(str(ss.prod_audio))
else:
    st.info("Сначала сгенерируй картинки")

st.divider()

# ── Step 4: Субтитры ────────────────────────────────────────────────────────
st.subheader("4️⃣ Субтитры")
if ss.prod_audio:
    if st.button("📝 Сгенерировать субтитры (Whisper)", disabled=bool(ss.prod_srt)):
        with st.spinner("Whisper транскрибирует…"):
            try:
                srt_path = ss.prod_session_dir / "subtitles.srt"
                ss.prod_srt = vp.transcribe_to_srt(Path(ss.prod_audio), srt_path)
                st.success("Готово!")
            except Exception as e:
                st.error(f"Ошибка субтитров: {e}")

    if ss.prod_srt and Path(ss.prod_srt).exists():
        with st.expander("📄 SRT-файл"):
            st.code(Path(ss.prod_srt).read_text(encoding="utf-8"), language="text")
else:
    st.info("Сначала озвучь сценарий")

st.divider()

# ── Step 5: Сборка видео ────────────────────────────────────────────────────
st.subheader("5️⃣ Сборка видео")
if ss.prod_audio and ss.prod_images:
    burn_subs = st.checkbox("Вшить субтитры в видео", value=bool(ss.prod_srt))
    if st.button("🎞 Собрать MP4", type="primary", disabled=bool(ss.prod_video)):
        with st.spinner("ffmpeg монтирует видео…"):
            try:
                duration = vp.get_audio_duration(Path(ss.prod_audio))
                video_path = ss.prod_session_dir / "final.mp4"
                ss.prod_video = vp.assemble_video(
                    images=ss.prod_images,
                    audio=Path(ss.prod_audio),
                    srt=Path(ss.prod_srt) if burn_subs and ss.prod_srt else None,
                    output=video_path,
                    total_duration=duration,
                )
                st.success(f"Видео готово ({duration:.1f} сек)")
            except Exception as e:
                st.error(f"Ошибка сборки: {e}")

    if ss.prod_video and Path(ss.prod_video).exists():
        st.video(str(ss.prod_video))

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Скачать MP4",
                data=Path(ss.prod_video).read_bytes(),
                file_name="autopilot_video.mp4",
                mime="video/mp4",
                use_container_width=True,
            )
        with c2:
            if st.button("📤 Отправить в контент-план", use_container_width=True):
                with st.spinner("Загружаю в бот…"):
                    res = upload_media(Path(ss.prod_video).read_bytes(), "autopilot_video.mp4")
                    if res and res.get("path"):
                        st.success(f"Загружено: `{res['path']}`")
                        st.info("Теперь зайди в «📅 Контент-план» и выбери этот файл.")
                    else:
                        st.error("Не удалось загрузить файл")
else:
    st.info("Нужны картинки и озвучка")
