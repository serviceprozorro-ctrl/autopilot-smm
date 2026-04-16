"""Media Downloader — powered by yt-dlp (1000+ sites)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import subprocess
import json
import tempfile
import threading
import time
from pathlib import Path

st.set_page_config(
    page_title="Media Downloader — AutoPilot",
    page_icon="📥",
    layout="wide",
)

YT_DLP = sys.executable.replace("python3.11", "yt-dlp") if "python" in sys.executable else "yt-dlp"
PYTHON = sys.executable

# Try to find yt-dlp in pythonlibs or PATH
_PYTHONLIBS = "/home/runner/workspace/.pythonlibs/lib/python3.11/site-packages"
_YTDLP_CMD = [PYTHON, "-m", "yt_dlp"]


def run_ytdlp(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = _PYTHONLIBS
    return subprocess.run(
        [PYTHON, "-m", "yt_dlp"] + args,
        capture_output=True, text=True, timeout=timeout, env=env,
    )


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.md-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    border: 1px solid #4f46e5;
    border-radius: 18px;
    padding: 22px 30px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 18px;
}
.md-title { font-size: 26px; font-weight: 800; color: #e2e8f0; }
.md-sub   { font-size: 13px; color: #94a3b8; margin-top: 4px; }
.site-badge {
    display: inline-block;
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 12px;
    color: #94a3b8;
    margin: 2px;
}
.info-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 18px 22px;
    margin: 12px 0;
}
.progress-box {
    background: #0a0f1e;
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 14px 18px;
    font-family: monospace;
    font-size: 12px;
    color: #38bdf8;
    max-height: 200px;
    overflow-y: auto;
}
.dl-item {
    background: #0f172a;
    border-left: 4px solid #22c55e;
    border-radius: 0 8px 8px 0;
    padding: 10px 16px;
    margin: 6px 0;
}
.fmt-chip {
    display: inline-block;
    background: #312e81;
    color: #a5b4fc;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    font-weight: 600;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="md-header">
  <div style="font-size:48px;">📥</div>
  <div>
    <div class="md-title">Media Downloader</div>
    <div class="md-sub">
      Powered by yt-dlp · 1000+ поддерживаемых сайтов ·
      YouTube · TikTok · Instagram · Twitter · SoundCloud · Twitch · Vimeo · и другие
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Supported sites badges ────────────────────────────────────────────────────
sites = ["YouTube", "TikTok", "Instagram", "Twitter/X", "SoundCloud", "Twitch",
         "Vimeo", "Facebook", "Dailymotion", "Reddit", "Bilibili", "NicoVideo",
         "Rumble", "Odysee", "VK", "OK.ru", "Coub", "+ 1000 других"]
st.markdown(" ".join(f'<span class="site-badge">{s}</span>' for s in sites), unsafe_allow_html=True)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_single, tab_batch, tab_playlist, tab_history = st.tabs([
    "🔗 Одна ссылка", "📋 Пакетная загрузка", "🎞 Плейлист / Канал", "🕓 История"
])

# ── Session state ─────────────────────────────────────────────────────────────
if "dl_history" not in st.session_state:
    st.session_state.dl_history = []
if "dl_files" not in st.session_state:
    st.session_state.dl_files = {}   # filename -> bytes


def _save_to_history(url: str, title: str, filename: str, size_mb: float, mode: str):
    st.session_state.dl_history.insert(0, {
        "url": url, "title": title, "filename": filename,
        "size_mb": round(size_mb, 1), "mode": mode,
        "ts": time.strftime("%H:%M:%S"),
    })
    st.session_state.dl_history = st.session_state.dl_history[:30]


def _build_cmd(url: str, mode: str, fmt: str, quality: str,
               subs: bool, thumb: bool, embed_meta: bool,
               out_dir: str, no_playlist: bool = True) -> list[str]:
    cmd = []
    if no_playlist:
        cmd += ["--no-playlist"]

    if mode == "audio":
        af = fmt.lower()
        cmd += ["-x", "--audio-format", af, "--audio-quality", "0"]
    else:
        vf = fmt.lower()
        if quality == "best":
            sel = "bestvideo+bestaudio/best"
        elif quality == "worst":
            sel = "worstvideo+worstaudio/worst"
        else:
            h = quality.replace("p", "")
            sel = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
        cmd += ["-f", sel, "--merge-output-format", vf]

    if subs:
        cmd += ["--write-auto-subs", "--sub-langs", "ru,en", "--embed-subs"]
    if thumb:
        cmd += ["--embed-thumbnail"]
    if embed_meta:
        cmd += ["--embed-metadata", "--add-metadata"]

    cmd += ["-o", os.path.join(out_dir, "%(title).80s.%(ext)s")]
    cmd.append(url)
    return cmd


def _get_info(url: str) -> dict | None:
    try:
        r = run_ytdlp(["--dump-json", "--no-playlist", url], timeout=30)
        if r.returncode == 0:
            return json.loads(r.stdout.split("\n")[0])
    except Exception:
        pass
    return None


def _format_duration(secs: int) -> str:
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _download_and_serve(url: str, cmd: list[str], out_dir: str,
                        mode_label: str, spinner_text: str):
    with st.spinner(spinner_text):
        try:
            r = run_ytdlp(cmd, timeout=600)
        except subprocess.TimeoutExpired:
            st.error("⏰ Превышено время ожидания (10 мин)")
            return

    if r.returncode != 0:
        st.error("❌ Ошибка загрузки")
        st.code(r.stderr[-800:], language="text")
        return

    files = sorted(
        [f for f in Path(out_dir).iterdir() if f.is_file()],
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not files:
        st.warning("⚠️ Файл не найден после загрузки")
        return

    for fpath in files:
        size_mb = fpath.stat().st_size / 1024 / 1024
        data = fpath.read_bytes()
        ext = fpath.suffix.lower()
        mime_map = {
            ".mp4": "video/mp4", ".mkv": "video/x-matroska",
            ".webm": "video/webm", ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4", ".flac": "audio/flac",
            ".ogg": "audio/ogg", ".wav": "audio/wav",
            ".opus": "audio/opus",
        }
        mime = mime_map.get(ext, "application/octet-stream")

        st.success(f"✅ **{fpath.name}** ({size_mb:.1f} MB)")
        st.download_button(
            f"⬇️ Скачать {fpath.name}",
            data, fpath.name, mime,
            use_container_width=True, type="primary",
            key=f"dl_{fpath.name}_{int(time.time())}",
        )

        _save_to_history(url, fpath.stem, fpath.name, size_mb, mode_label)

    if r.stdout:
        with st.expander("📋 Лог загрузки"):
            st.code(r.stdout[-1500:], language="text")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Single URL
# ═══════════════════════════════════════════════════════════════════════════════
with tab_single:
    url_single = st.text_input(
        "🔗 Ссылка на видео / трек",
        placeholder="https://www.youtube.com/watch?v=…  или  https://www.tiktok.com/@…",
        key="url_single",
    )

    # Options row
    col_mode, col_vfmt, col_afmt, col_qual = st.columns([1.2, 1, 1, 1])
    with col_mode:
        mode = st.radio("Тип", ["🎬 Видео", "🎵 Аудио"], horizontal=True, key="mode_s")
    with col_vfmt:
        video_fmt = st.selectbox("Формат видео", ["MP4", "MKV", "WEBM"], key="vfmt_s")
    with col_afmt:
        audio_fmt = st.selectbox("Формат аудио", ["MP3", "M4A", "FLAC", "OGG", "WAV", "OPUS"], key="afmt_s")
    with col_qual:
        quality = st.selectbox("Качество", ["best", "2160p", "1440p", "1080p", "720p", "480p", "360p", "worst"],
                               format_func=lambda x: {"best": "Наилучшее", "worst": "Наименьшее"}.get(x, x), key="qual_s")

    col_o1, col_o2, col_o3 = st.columns(3)
    with col_o1:
        subs = st.checkbox("💬 Субтитры (ru/en)", key="subs_s")
    with col_o2:
        thumb = st.checkbox("🖼 Встроить обложку", key="thumb_s", value=True)
    with col_o3:
        meta = st.checkbox("🏷 Метаданные", key="meta_s", value=True)

    c_info, c_dl = st.columns(2)
    info_btn = c_info.button("ℹ️ Предпросмотр", use_container_width=True, key="info_s")
    dl_btn   = c_dl.button("⬇️ Скачать", use_container_width=True, type="primary", key="dl_s")

    if url_single and info_btn:
        with st.spinner("Получаю информацию…"):
            info = _get_info(url_single)

        if info:
            col_meta, col_thumb = st.columns([3, 1])
            with col_meta:
                st.markdown(f"### {info.get('title','—')}")
                cols_i = st.columns(4)
                dur = info.get("duration", 0)
                cols_i[0].metric("⏱ Длительность", _format_duration(dur) if dur else "—")
                vc = info.get("view_count", 0)
                cols_i[1].metric("👁 Просмотры", f"{vc:,}" if vc else "—")
                cols_i[2].metric("📅 Дата", info.get("upload_date","—"))
                cols_i[3].metric("🌐 Сайт", info.get("extractor","—"))
                st.markdown(f"**Канал:** {info.get('uploader','—')}")

                # formats
                fmts = info.get("formats", [])
                if fmts:
                    video_fmts = [f for f in fmts if f.get("vcodec","none") not in ("none",None) and f.get("height")]
                    audio_fmts = [f for f in fmts if f.get("acodec","none") not in ("none",None) and f.get("vcodec","none") == "none"]
                    heights = sorted({f["height"] for f in video_fmts if f.get("height")}, reverse=True)
                    if heights:
                        st.markdown("**Доступные качества:** " + " ".join(f'<span class="fmt-chip">{h}p</span>' for h in heights[:8]), unsafe_allow_html=True)

                desc = info.get("description","")
                if desc:
                    with st.expander("📝 Описание"):
                        st.text(desc[:1000])
            with col_thumb:
                t = info.get("thumbnail")
                if t:
                    st.image(t, use_container_width=True, caption="Обложка")
        else:
            st.error("Не удалось получить информацию. Проверьте ссылку.")

    if url_single and dl_btn:
        out_dir = tempfile.mkdtemp()
        is_audio = "Аудио" in mode
        fmt = audio_fmt if is_audio else video_fmt
        cmd = _build_cmd(
            url_single,
            "audio" if is_audio else "video",
            fmt, quality, subs, thumb, meta,
            out_dir, no_playlist=True,
        )
        _download_and_serve(
            url_single, cmd, out_dir,
            f"{'🎵' if is_audio else '🎬'} {fmt}",
            f"Скачиваю {'аудио' if is_audio else 'видео'}… это может занять несколько минут",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Batch
# ═══════════════════════════════════════════════════════════════════════════════
with tab_batch:
    st.markdown("Введите ссылки — **по одной на строку**. Поддерживаются разные сайты одновременно.")

    urls_raw = st.text_area(
        "Ссылки",
        height=140,
        placeholder="https://www.youtube.com/watch?v=AAA\nhttps://www.tiktok.com/@user/video/123\nhttps://soundcloud.com/…",
        key="batch_urls",
    )

    col_bm, col_bvf, col_baf, col_bq = st.columns([1.2, 1, 1, 1])
    with col_bm:
        b_mode = st.radio("Тип", ["🎬 Видео", "🎵 Аудио"], horizontal=True, key="mode_b")
    with col_bvf:
        b_vfmt = st.selectbox("Формат видео", ["MP4", "MKV", "WEBM"], key="vfmt_b")
    with col_baf:
        b_afmt = st.selectbox("Формат аудио", ["MP3", "M4A", "FLAC", "OGG", "WAV"], key="afmt_b")
    with col_bq:
        b_qual = st.selectbox("Качество", ["best", "1080p", "720p", "480p", "360p", "worst"],
                              format_func=lambda x: {"best": "Наилучшее", "worst": "Наименьшее"}.get(x, x), key="qual_b")

    col_bo1, col_bo2 = st.columns(2)
    b_thumb = col_bo1.checkbox("🖼 Встроить обложку", key="thumb_b", value=True)
    b_meta  = col_bo2.checkbox("🏷 Метаданные", key="meta_b", value=True)

    if st.button("⬇️ Скачать всё", use_container_width=True, type="primary", key="batch_dl"):
        urls = [u.strip() for u in urls_raw.splitlines() if u.strip() and u.startswith("http")]
        if not urls:
            st.warning("Введите хотя бы одну корректную ссылку (должна начинаться с http)")
        else:
            is_audio = "Аудио" in b_mode
            fmt = b_afmt if is_audio else b_vfmt
            total = len(urls)
            progress_bar = st.progress(0, text=f"Загружаю 0/{total}…")
            results_placeholder = st.container()

            for i, url in enumerate(urls):
                progress_bar.progress((i) / total, text=f"Загружаю {i+1}/{total}: {url[:60]}…")
                out_dir = tempfile.mkdtemp()
                cmd = _build_cmd(url, "audio" if is_audio else "video", fmt, b_qual,
                                 False, b_thumb, b_meta, out_dir, no_playlist=True)
                with results_placeholder:
                    st.markdown(f"**[{i+1}/{total}]** `{url[:70]}`")
                    _download_and_serve(url, cmd, out_dir, f"{'🎵' if is_audio else '🎬'} {fmt}",
                                        f"Скачиваю {i+1}/{total}…")

            progress_bar.progress(1.0, text=f"✅ Готово! {total} файлов загружено")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Playlist / Channel
# ═══════════════════════════════════════════════════════════════════════════════
with tab_playlist:
    st.markdown("Скачать **весь плейлист**, **канал** или **выбранный диапазон** видео.")

    url_pl = st.text_input(
        "🔗 Ссылка на плейлист / канал",
        placeholder="https://www.youtube.com/playlist?list=…",
        key="url_pl",
    )

    col_pl1, col_pl2, col_pl3 = st.columns(3)
    with col_pl1:
        pl_mode = st.radio("Тип", ["🎬 Видео", "🎵 Аудио"], horizontal=True, key="mode_pl")
    with col_pl2:
        pl_vfmt = st.selectbox("Формат", ["MP4", "MKV"] if "Видео" in "🎬 Видео" else ["MP3","M4A"], key="vfmt_pl")
    with col_pl3:
        pl_qual = st.selectbox("Качество", ["720p", "1080p", "480p", "360p", "best"],
                               format_func=lambda x: {"best": "Наилучшее"}.get(x, x), key="qual_pl")

    col_r1, col_r2 = st.columns(2)
    pl_start = col_r1.number_input("Начать с видео №", min_value=1, value=1, step=1, key="pl_start")
    pl_end   = col_r2.number_input("Закончить на видео №", min_value=1, value=10, step=1, key="pl_end")

    pl_thumb = st.checkbox("🖼 Встроить обложку", key="thumb_pl", value=True)

    if url_pl and st.button("🔍 Получить список видео", key="pl_info"):
        with st.spinner("Сканирую плейлист…"):
            try:
                r = run_ytdlp([
                    "--flat-playlist", "--dump-json",
                    "--playlist-start", str(pl_start),
                    "--playlist-end", str(pl_end),
                    url_pl
                ], timeout=60)
                if r.returncode == 0:
                    items = [json.loads(line) for line in r.stdout.strip().splitlines() if line.strip()]
                    st.success(f"🎞 Найдено видео в диапазоне: **{len(items)}**")
                    for j, it in enumerate(items, 1):
                        dur = it.get("duration", 0)
                        dur_str = _format_duration(int(dur)) if dur else "—"
                        st.markdown(f"**{j}.** {it.get('title','—')} · `{dur_str}`")
                else:
                    st.error("Не удалось получить список:\n" + r.stderr[:400])
            except Exception as e:
                st.error(f"Ошибка: {e}")

    if url_pl and st.button("⬇️ Скачать плейлист", type="primary", key="pl_dl", use_container_width=True):
        is_audio = "Аудио" in pl_mode
        fmt = "MP3" if is_audio else pl_vfmt
        out_dir = tempfile.mkdtemp()

        cmd = []
        if is_audio:
            cmd += ["-x", "--audio-format", fmt.lower(), "--audio-quality", "0"]
        else:
            h = pl_qual.replace("p","")
            sel = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]" if pl_qual != "best" else "bestvideo+bestaudio/best"
            cmd += ["-f", sel, "--merge-output-format", fmt.lower()]

        if pl_thumb:
            cmd += ["--embed-thumbnail"]

        cmd += [
            "--playlist-start", str(pl_start),
            "--playlist-end",   str(pl_end),
            "--embed-metadata",
            "-o", os.path.join(out_dir, "%(playlist_index)s - %(title).60s.%(ext)s"),
            url_pl,
        ]

        with st.spinner(f"Скачиваю видео {pl_start}–{pl_end} из плейлиста…"):
            try:
                r = run_ytdlp(cmd, timeout=1800)
            except subprocess.TimeoutExpired:
                st.error("⏰ Превышено время (30 мин)")
                r = None

        if r and r.returncode == 0:
            files = sorted(Path(out_dir).glob("*"), key=lambda p: p.name)
            st.success(f"✅ Скачано файлов: {len(files)}")
            for fpath in files:
                size_mb = fpath.stat().st_size / 1024 / 1024
                data = fpath.read_bytes()
                ext = fpath.suffix.lower()
                mime_map = {".mp4":"video/mp4",".mkv":"video/x-matroska",
                            ".mp3":"audio/mpeg",".m4a":"audio/mp4",".flac":"audio/flac"}
                mime = mime_map.get(ext, "application/octet-stream")
                col_f, col_b = st.columns([3, 1])
                col_f.markdown(f"📄 **{fpath.name}** ({size_mb:.1f} MB)")
                col_b.download_button("⬇️", data, fpath.name, mime, key=f"pl_{fpath.name}")
                _save_to_history(url_pl, fpath.stem, fpath.name, size_mb, f"Playlist {'🎵' if is_audio else '🎬'}")
        elif r:
            st.error("Ошибка:\n" + r.stderr[-600:])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — History
# ═══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown("### 🕓 История загрузок (текущая сессия)")
    if not st.session_state.dl_history:
        st.info("Пока нет загрузок в этой сессии. Скачайте что-нибудь!")
    else:
        if st.button("🗑 Очистить историю", key="clear_hist"):
            st.session_state.dl_history = []
            st.rerun()

        for item in st.session_state.dl_history:
            col_h, col_m, col_s, col_t = st.columns([4, 1, 1, 1])
            col_h.markdown(f'<div class="dl-item">📄 <b>{item["filename"]}</b><br><small style="color:#94a3b8;">{item["url"][:60]}…</small></div>', unsafe_allow_html=True)
            col_m.metric("Размер", f"{item['size_mb']} MB")
            col_s.metric("Тип", item["mode"])
            col_t.metric("Время", item["ts"])

st.divider()
st.caption("Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) · Поддерживает 1000+ сайтов · github.com/mhogomchungu/media-downloader")
