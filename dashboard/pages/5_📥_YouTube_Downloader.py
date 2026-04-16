import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import subprocess
import json
import tempfile

st.set_page_config(page_title="YouTube Downloader", page_icon="📥", layout="wide")
st.title("📥 YouTube Downloader")
st.markdown("Скачивайте видео и аудио с YouTube и других платформ (yt-dlp)")

url = st.text_input("🔗 Вставьте ссылку на видео", placeholder="https://www.youtube.com/watch?v=...")

col1, col2, col3 = st.columns(3)

with col1:
    mode = st.radio("Тип", ["🎬 Видео", "🎵 Только аудио (MP3)"])
with col2:
    quality = st.selectbox(
        "Качество",
        ["best", "1080p", "720p", "480p", "360p", "worst"],
        format_func=lambda x: {"best": "Лучшее", "worst": "Наименьшее"}.get(x, x)
    )
with col3:
    output_dir = tempfile.mkdtemp()
    st.info(f"📁 Файл сохранится в:\n`{output_dir}`")

if url and st.button("ℹ️ Получить информацию о видео", use_container_width=True):
    with st.spinner("Получаю информацию..."):
        try:
            result = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-playlist", url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                info = json.loads(result.stdout)
                col_info, col_thumb = st.columns([2, 1])
                with col_info:
                    st.markdown(f"### {info.get('title', 'N/A')}")
                    st.markdown(f"**Канал:** {info.get('uploader', 'N/A')}")
                    duration = info.get('duration', 0)
                    st.markdown(f"**Длительность:** {duration // 60}:{duration % 60:02d}")
                    views = info.get('view_count', 0)
                    st.markdown(f"**Просмотры:** {views:,}" if views else "**Просмотры:** N/A")
                    st.markdown(f"**Дата:** {info.get('upload_date', 'N/A')}")
                with col_thumb:
                    thumb = info.get("thumbnail")
                    if thumb:
                        st.image(thumb, use_container_width=True)
            else:
                st.error(f"Ошибка: {result.stderr[:300]}")
        except FileNotFoundError:
            st.error("❌ yt-dlp не найден. Установите его: `pip install yt-dlp`")
        except subprocess.TimeoutExpired:
            st.error("⏰ Превышено время ожидания")
        except Exception as e:
            st.error(f"Ошибка: {e}")

st.divider()

if url and st.button("⬇️ Скачать", type="primary", use_container_width=True):
    with st.spinner("Скачиваю... это может занять несколько минут"):
        try:
            if mode == "🎵 Только аудио (MP3)":
                cmd = [
                    "yt-dlp", "-x", "--audio-format", "mp3",
                    "--audio-quality", "0",
                    "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
                    "--no-playlist", url,
                ]
            else:
                fmt = "bestvideo+bestaudio" if quality == "best" else f"bestvideo[height<={quality[:-1]}]+bestaudio"
                cmd = [
                    "yt-dlp", "-f", fmt,
                    "--merge-output-format", "mp4",
                    "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
                    "--no-playlist", url,
                ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                files = [f for f in os.listdir(output_dir) if not f.startswith(".")]
                if files:
                    st.success(f"✅ Файл скачан: **{files[0]}**")
                    filepath = os.path.join(output_dir, files[0])
                    with open(filepath, "rb") as f:
                        mime = "audio/mp3" if mode == "🎵 Только аудио (MP3)" else "video/mp4"
                        st.download_button(
                            f"⬇️ Скачать {files[0]}",
                            f.read(), files[0], mime,
                            use_container_width=True,
                        )
                else:
                    st.warning("Файл загружен, но не найден в папке")
            else:
                st.error(f"Ошибка yt-dlp:\n```\n{result.stderr[:500]}\n```")
        except FileNotFoundError:
            st.error("❌ yt-dlp не найден.")
        except subprocess.TimeoutExpired:
            st.error("⏰ Слишком долго. Попробуйте более короткое видео.")
        except Exception as e:
            st.error(f"Ошибка: {e}")
