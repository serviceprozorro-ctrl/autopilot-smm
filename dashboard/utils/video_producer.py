"""Продакшн-пайплайн для коротких видео.

Этапы:
  1) Идея → сценарий (Claude) с длительностями каждой сцены (6/10/20/30 с)
  2) Сценарий → раскадровка
  3) Раскадровка → картинки (Grok / xAI; fallback — плейсхолдеры)
  4) Текст → озвучка (OpenAI TTS)
  5) Whisper → субтитры с тайм-кодами
  6) ffmpeg → склейка с разной длительностью на сцену + аудио + хардсаб
"""
import json
import logging
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import List, Optional

from anthropic import Anthropic
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

from utils import xai_client

logger = logging.getLogger(__name__)

PRODUCTION_DIR = Path(__file__).resolve().parents[1] / "production_output"
PRODUCTION_DIR.mkdir(exist_ok=True)

ALLOWED_SCENE_DURATIONS = [6, 10, 20, 30]


def _anthropic() -> Anthropic:
    return Anthropic(
        base_url=os.environ["AI_INTEGRATIONS_ANTHROPIC_BASE_URL"],
        api_key=os.environ["AI_INTEGRATIONS_ANTHROPIC_API_KEY"],
    )


def _openai() -> OpenAI:
    return OpenAI(
        base_url=os.environ["AI_INTEGRATIONS_OPENAI_BASE_URL"],
        api_key=os.environ["AI_INTEGRATIONS_OPENAI_API_KEY"],
    )


# ── Разбиение длительности видео на сцены 6/10/20/30 ─────────────────────────

def split_duration_into_scenes(total_sec: int) -> List[int]:
    """Разбивает общую длительность на сегменты из ALLOWED_SCENE_DURATIONS.

    Алгоритм: жадно берём максимально возможный сегмент, остатком < 6 склеиваем
    с предыдущей сценой, чтобы не было слишком коротких фрагментов.
    """
    total_sec = max(6, int(total_sec))
    chunks: List[int] = []
    remaining = total_sec
    while remaining >= 6:
        candidates = [d for d in ALLOWED_SCENE_DURATIONS if d <= remaining]
        chunks.append(max(candidates))
        remaining -= chunks[-1]
    if remaining > 0 and chunks:
        chunks[-1] += remaining
    return chunks


# ── 1. Сценарий ──────────────────────────────────────────────────────────────

def generate_script(idea: str, duration_sec: int = 30, style: str = "энергичный",
                    platform: str = "tiktok",
                    portfolio_description: Optional[str] = None) -> dict:
    """Возвращает {title, hook, scenes:[{narration, visual, duration_sec}], cta, hashtags}."""
    client = _anthropic()
    scene_plan = split_duration_into_scenes(duration_sec)
    scenes_hint = ", ".join(str(s) for s in scene_plan)

    portfolio_block = ""
    if portfolio_description:
        portfolio_block = (
            f"\nГерой кадра / визуальный образ: {portfolio_description}\n"
            "Используй этот образ в каждом visual-описании сцены.\n"
        )

    prompt = f"""Создай сценарий для короткого видео на {platform.upper()}.

Идея: {idea}
Общая длительность: {duration_sec} секунд
Раскадровка по сценам (секунды): {scenes_hint}
Стиль: {style}
Язык озвучки: русский
{portfolio_block}
Верни СТРОГО JSON:
{{
  "title": "название",
  "hook": "цепляющая первая фраза (5-7 слов)",
  "scenes": [
    {{"narration": "текст озвучки на русском (плотность речи под длительность)",
      "visual": "детальное описание кадра на английском для AI-генератора",
      "duration_sec": <число из плана>}}
  ],
  "cta": "призыв к действию",
  "hashtags": "#тег1 #тег2"
}}

Сцен ровно {len(scene_plan)} штук — для длинных сцен (20-30 с) делай больше речи и
несколько действий внутри одного кадра. Только JSON, без markdown.
"""
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    data = json.loads(text)

    # Нормализуем длительности — на случай галлюцинаций модели
    scenes = data.get("scenes") or []
    for i, sc in enumerate(scenes):
        if i < len(scene_plan):
            sc["duration_sec"] = scene_plan[i]
        else:
            sc["duration_sec"] = sc.get("duration_sec") or 6
    data["scenes"] = scenes
    return data


# ── 2. Картинки сцен ────────────────────────────────────────────────────────

def _placeholder_image(text: str, output: Path, idx: int):
    colors = [(124, 58, 237), (37, 99, 235), (5, 150, 105), (220, 38, 38),
              (245, 158, 11), (236, 72, 153), (14, 165, 233)]
    bg = colors[idx % len(colors)]
    img = Image.new("RGB", (1080, 1920), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/nix/store/*/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
    except Exception:
        font = ImageFont.load_default()
    wrapped = textwrap.fill(text[:200], width=18)
    draw.multiline_text((60, 600), wrapped, fill=(255, 255, 255), font=font, spacing=12)
    draw.text((60, 1800), f"Сцена {idx + 1}", fill=(255, 255, 255), font=font)
    img.save(output)


def generate_scene_images(scenes: list[dict], session_dir: Path,
                          use_grok: bool = True) -> list[Path]:
    """Картинки сцен через xAI Grok; fallback — плейсхолдеры."""
    out_paths = []
    grok_ok = use_grok and xai_client.is_available()
    for i, sc in enumerate(scenes):
        out = session_dir / f"scene_{i:02d}.png"
        visual = sc.get("visual") or sc.get("narration", "")
        if grok_ok:
            try:
                xai_client.generate_image(
                    f"{visual}. Vertical 9:16 composition, cinematic, ultra-detailed.",
                    out, n=1,
                )
                out_paths.append(out)
                continue
            except Exception as e:
                logger.warning("Grok-image сбой на сцене %s: %s — плейсхолдер", i, e)
        _placeholder_image(visual, out, i)
        out_paths.append(out)
    return out_paths


# ── 3. Озвучка ──────────────────────────────────────────────────────────────

def synthesize_voiceover(text: str, output: Path, voice: str = "alloy") -> Path:
    client = _openai()
    resp = client.audio.speech.create(
        model="gpt-4o-mini-tts", voice=voice, input=text, response_format="mp3",
    )
    output.write_bytes(resp.read())
    return output


# ── 4. Субтитры ─────────────────────────────────────────────────────────────

def transcribe_to_srt(audio_path: Path, srt_path: Path) -> Path:
    client = _openai()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="whisper-1", file=f, response_format="verbose_json", language="ru",
        )
    segments = resp.segments or []
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(
            f"{i}\n{_fmt_srt_time(seg.start)} --> {_fmt_srt_time(seg.end)}\n{seg.text.strip()}\n"
        )
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path


def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── 5. Сборка ───────────────────────────────────────────────────────────────

def assemble_video(images: list[Path], audio: Path, srt: Optional[Path],
                   output: Path,
                   scene_durations: Optional[list[int]] = None,
                   total_duration: Optional[float] = None) -> Path:
    """Каждая сцена — со своей длительностью (или равные доли total_duration)."""
    n = len(images)
    if scene_durations and len(scene_durations) == n:
        durations = [max(1.0, float(d)) for d in scene_durations]
    else:
        per = max(1.0, (total_duration or 30.0) / n)
        durations = [per] * n

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for img, dur in zip(images, durations):
            f.write(f"file '{img}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{images[-1]}'\n")
        concat_list = f.name

    tmp_video = output.with_suffix(".tmp.mp4")
    cmd_video = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-vsync", "vfr", "-pix_fmt", "yuv420p",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=cover,crop=1080:1920,fps=30",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        str(tmp_video),
    ]
    _run(cmd_video)
    os.unlink(concat_list)

    out_filter = []
    if srt and srt.exists():
        srt_escaped = str(srt).replace(":", "\\:").replace("'", "\\'")
        out_filter = [
            "-vf",
            f"subtitles='{srt_escaped}':force_style='Fontsize=22,PrimaryColour=&HFFFFFF&,"
            f"OutlineColour=&H000000&,BorderStyle=3,Outline=2,Alignment=2,MarginV=120'",
        ]

    cmd_mux = [
        "ffmpeg", "-y", "-i", str(tmp_video), "-i", str(audio),
        *out_filter,
        "-c:v", "libx264" if out_filter else "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        str(output),
    ]
    _run(cmd_mux)
    if tmp_video.exists():
        tmp_video.unlink()
    return output


def _run(cmd: list[str]):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("ffmpeg failed: %s", proc.stderr[-2000:])
        raise RuntimeError(f"ffmpeg ошибка: {proc.stderr[-500:]}")


def get_audio_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except Exception:
        return 30.0
