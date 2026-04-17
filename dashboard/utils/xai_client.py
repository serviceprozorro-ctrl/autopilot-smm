"""xAI Grok image-generation client.

Использует REST API xAI: POST /v1/images/generations с моделью grok-2-image.
Возвращает PNG-байты или URL. Если ключа нет — кидает RuntimeError.
"""
import base64
import logging
import os
from pathlib import Path
from typing import List

import requests

logger = logging.getLogger(__name__)

XAI_BASE = "https://api.x.ai/v1"
TIMEOUT = 90


def is_available() -> bool:
    return bool(os.environ.get("XAI_API_KEY"))


def _headers() -> dict:
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY не задан — добавьте секрет, чтобы включить Grok-генерацию")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def generate_image(prompt: str, output_path: Path, n: int = 1,
                   model: str = "grok-2-image") -> List[Path]:
    """Создаёт изображение по текстовому промпту, сохраняет в `output_path` (или _0,_1...).

    xAI отдаёт либо `b64_json`, либо `url`. Поддерживаем оба варианта.
    """
    body = {"model": model, "prompt": prompt, "n": max(1, min(n, 4))}
    r = requests.post(f"{XAI_BASE}/images/generations", json=body,
                      headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"xAI {r.status_code}: {r.text[:300]}")
    data = r.json().get("data") or []
    out_paths: List[Path] = []
    for i, item in enumerate(data):
        if n == 1:
            target = output_path
        else:
            target = output_path.with_name(f"{output_path.stem}_{i}{output_path.suffix}")
        if item.get("b64_json"):
            target.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            img = requests.get(item["url"], timeout=TIMEOUT)
            img.raise_for_status()
            target.write_bytes(img.content)
        else:
            continue
        out_paths.append(target)
    if not out_paths:
        raise RuntimeError("xAI вернул пустой ответ")
    return out_paths


def generate_variations(reference_description: str, base_prompt_addons: List[str],
                        output_dir: Path, prefix: str = "var") -> List[Path]:
    """Генерит вариации образа по описанию + список модификаторов (поза, фон, свет)."""
    output_dir.mkdir(exist_ok=True, parents=True)
    paths: List[Path] = []
    for i, addon in enumerate(base_prompt_addons):
        prompt = (
            f"Photorealistic portrait. Subject: {reference_description}. "
            f"Variation: {addon}. High detail, professional lighting, 9:16 vertical."
        )
        target = output_dir / f"{prefix}_{i:02d}.png"
        try:
            generate_image(prompt, target, n=1)
            paths.append(target)
        except Exception as e:
            logger.warning("Не удалось сгенерировать вариацию %s: %s", i, e)
    return paths
