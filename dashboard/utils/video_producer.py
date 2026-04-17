"""Продакшн-пайплайн для коротких видео.

Этапы:
  1) Идея → сценарий (Claude)
  2) Сценарий → раскадровка (список сцен с описаниями)
  3) Раскадровка → картинки (генератор через subprocess к JS-сэндбоксу не нужен —
     используем прямой HTTP к media-генератору. Здесь fallback: цветные плейсхолдеры
     с текстом, если генератор недоступен)
  4) Текст → озвучка (OpenAI TTS через прокси)
  5) Whisper → субтитры с тайм-кодами
  6) ffmpeg → склейка картинок + аудио + хардсаб

Каждая стадия возвращает данные для следующей; вызываем по отдельности из UI.
"""
import json
import logging
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

PRODUCTION_DIR = Path(__file__).resolve().parents[1] / "production_output"
PRODUCTION_DIR.mkdir(exist_ok=True)


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


# ── 1. Сценарий ──────────────────────────────────────────────────────────────

def generate_script(idea: str, duration_sec: int = 30, style: str = "энергичный",
                    platform: str = "tiktok") -> dict:
    """Возвращает {title, hook, scenes:[{narration, visual}], cta, hashtags}."""
    client = _anthropic()
    prompt = f"""Создай сценарий для короткого видео на {platform.upper()}.

Идея: {idea}
Длительность: {duration_sec} секунд
Стиль: {style}
Язык: русский

Верни СТРОГО JSON со схемой:
{{
  "title": "название видео",
  "hook": "цепляющая первая фраза (5-7 слов)",
  "scenes": [
    {{"narration": "текст озвучки сцены", "visual": "детальное описание картинки сцены на английском для AI-генератора"}}
  ],
  "cta": "призыв к действию в конце",
  "hashtags": "#тег1 #тег2 #тег3"
}}

Сцен должно быть {max(3, duration_sec // 6)}–{max(4, duration_sec // 4)} штук, чтобы каждая длилась 4-7 секунд.
Озвучка коротких фраз — 8-15 слов на сцену. Только JSON, без markdown.
"""
    resp = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    return json.loads(text)


# ── 2. Картинки сцен ────────────────────────────────────────────────────────

def _placeholder_image(text: str, output: Path, idx: int):
    """Если генератор недоступен — рисуем цветной плейсхолдер с подписью."""
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
    draw.text((60, 1800), f"Сцена {idx + 1}", fill=(255, 255, 255, 200), font=font)
    img.save(output)


def generate_scene_images(scenes: list[dict], session_dir: Path) -> list[Path]:
    """Пытаемся сгенерировать через media-generation; иначе плейсхолдеры."""
    out_paths = []
    for i, sc in enumerate(scenes):
        out = session_dir / f"scene_{i:02d}.png"
        # Пока без AI-генератора (требует JS-сэндбокс из агента) — плейсхолдер.
        # Пользователь может позже заменить картинки руками или включить
        # реальный генератор картинок в этой функции.
        _placeholder_image(sc.get("visual") or sc.get("narration", ""), out, i)
        out_paths.append(out)
    return out_paths


# ── 3. Озвучка ──────────────────────────────────────────────────────────────

def synthesize_voiceover(text: str, output: Path, voice: str = "alloy") -> Path:
    """OpenAI TTS — выбираем голос и генерим mp3."""
    client = _openai()
    resp = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        response_format="mp3",
    )
    output.write_bytes(resp.read())
    return output


# ── 4. Субтитры ─────────────────────────────────────────────────────────────

def transcribe_to_srt(audio_path: Path, srt_path: Path) -> Path:
    """Whisper выдаёт сегменты с тайм-кодами — собираем SRT."""
    client = _openai()
    with open(audio_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            language="ru",
        )
    segments = resp.segments or []
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _fmt_srt_time(seg.start)
        end = _fmt_srt_time(seg.end)
        text = seg.text.strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path


def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ── 5. Сборка видео через ffmpeg ────────────────────────────────────────────

def assemble_video(images: list[Path], audio: Path, srt: Optional[Path],
                   output: Path, total_duration: float) -> Path:
    """Каждая картинка показывается равную долю общей длительности.
    Накладываем аудио и субтитры (хардсаб)."""
    n = len(images)
    per_img = max(1.0, total_duration / n)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for img in images:
            f.write(f"file '{img}'\n")
            f.write(f"duration {per_img}\n")
        f.write(f"file '{images[-1]}'\n")  # последняя картинка повторяется (concat quirk)
        concat_list = f.name

    # 1) Видеотрек из картинок
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

    # 2) Накладываем аудио + (опционально) субтитры
    out_filter = []
    if srt and srt.exists():
        # Экранируем путь для filtergraph
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
