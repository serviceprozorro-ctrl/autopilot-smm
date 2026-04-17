"""Реальная публикация в TikTok через Playwright + Chromium.

Аккаунт авторизуется через cookies, экспортированные из браузера
(плагины «Cookie Editor», «EditThisCookie» — формат JSON).

Минимально нужны cookies: sessionid, sessionid_ss, sid_tt, ssid_ucp_v1,
tt-target-idc, msToken (часть из них опциональны).
"""
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Пути к Nix-Chromium и кэшу профилей
CHROMIUM_BIN = shutil.which("chromium") or "/usr/bin/chromium"
PROFILES_DIR = Path(__file__).resolve().parents[2] / "browser_profiles"
PROFILES_DIR.mkdir(exist_ok=True)


def _normalize_cookies(raw: str) -> list[dict]:
    """Поддерживаем три формата cookies:
    1) JSON-массив объектов из Cookie Editor: [{name, value, domain, path, ...}, ...]
    2) JSON-объект {name: value}
    3) Строка вида 'a=b; c=d' (Cookie header)
    """
    raw = raw.strip()
    if not raw:
        return []

    cookies: list[dict] = []

    # Попытка 1 — JSON
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            for c in data:
                if not isinstance(c, dict) or "name" not in c or "value" not in c:
                    continue
                cookie = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain") or ".tiktok.com",
                    "path": c.get("path") or "/",
                }
                if c.get("expirationDate"):
                    cookie["expires"] = float(c["expirationDate"])
                if "secure" in c:
                    cookie["secure"] = bool(c["secure"])
                if "httpOnly" in c:
                    cookie["httpOnly"] = bool(c["httpOnly"])
                if c.get("sameSite") in ("Strict", "Lax", "None"):
                    cookie["sameSite"] = c["sameSite"]
                cookies.append(cookie)
            return cookies
        if isinstance(data, dict):
            for k, v in data.items():
                cookies.append({"name": k, "value": str(v), "domain": ".tiktok.com", "path": "/"})
            return cookies
    except Exception:
        pass

    # Попытка 2 — Cookie header
    for piece in raw.split(";"):
        piece = piece.strip()
        if "=" in piece:
            k, v = piece.split("=", 1)
            cookies.append({"name": k.strip(), "value": v.strip(),
                            "domain": ".tiktok.com", "path": "/"})
    return cookies


async def publish_to_tiktok(
    account_id: int,
    username: str,
    cookies_raw: Optional[str],
    media_path: Optional[str],
    caption: Optional[str],
    hashtags: Optional[str],
) -> dict:
    """Возвращает dict {success, external_id, error}."""
    if not cookies_raw:
        return {"success": False, "error": "Нет cookies для авторизации в TikTok"}
    if not media_path or not os.path.exists(media_path):
        return {"success": False, "error": f"Медиафайл не найден: {media_path}"}

    cookies = _normalize_cookies(cookies_raw)
    if not cookies:
        return {"success": False, "error": "Не удалось разобрать cookies (ожидается JSON или Cookie header)"}

    full_caption = (caption or "").strip()
    if hashtags:
        full_caption = (full_caption + "\n" + hashtags.strip()).strip()

    try:
        from playwright.async_api import async_playwright
    except Exception as e:
        return {"success": False, "error": f"Playwright не установлен: {e}"}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_BIN,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )

        # Ставим cookies до открытия страницы
        try:
            await context.add_cookies(cookies)
        except Exception as e:
            await browser.close()
            return {"success": False, "error": f"Не удалось установить cookies: {e}"}

        page = await context.new_page()

        try:
            logger.info("[TikTok] Открываю страницу загрузки для @%s", username)
            await page.goto("https://www.tiktok.com/upload?lang=en", timeout=45000,
                            wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Проверяем что мы вошли (если нас перекинуло на /login — cookies невалидны)
            if "/login" in page.url:
                await browser.close()
                return {"success": False,
                        "error": "Cookies невалидны — TikTok перенаправил на /login. Перезаполните cookies."}

            # Иногда страница загрузки внутри iframe — попробуем найти input по двум сценариям
            # 1) Прямой input[type=file]
            file_input = None
            try:
                file_input = await page.wait_for_selector(
                    'input[type="file"]', timeout=15000, state="attached"
                )
            except Exception:
                pass

            # 2) Внутри iframe
            if file_input is None:
                for frame in page.frames:
                    try:
                        fi = await frame.wait_for_selector('input[type="file"]', timeout=3000, state="attached")
                        if fi:
                            file_input = fi
                            break
                    except Exception:
                        continue

            if file_input is None:
                # Сохраним скрин для диагностики
                err_path = PROFILES_DIR / f"err_{account_id}.png"
                try:
                    await page.screenshot(path=str(err_path))
                except Exception:
                    pass
                await browser.close()
                return {"success": False,
                        "error": f"Не нашёл поле загрузки видео на странице TikTok. Скрин: {err_path}"}

            logger.info("[TikTok] Загружаю файл: %s", media_path)
            await file_input.set_input_files(media_path)

            # Ждём пока видео загрузится — индикатор каждый раз чуть разный.
            # Подождём появления поля описания.
            await asyncio.sleep(8)

            # Заполняем описание
            if full_caption:
                # Поле описания — contenteditable div с data-contents
                caption_target = None
                for sel in ['div[contenteditable="true"]',
                            '[data-contents="true"]',
                            'div.notranslate[contenteditable]']:
                    try:
                        caption_target = await page.wait_for_selector(sel, timeout=5000)
                        if caption_target:
                            break
                    except Exception:
                        continue

                if caption_target:
                    try:
                        await caption_target.click()
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Delete")
                        await page.keyboard.type(full_caption, delay=20)
                        logger.info("[TikTok] Описание заполнено (%d символов)", len(full_caption))
                    except Exception as e:
                        logger.warning("[TikTok] Не получилось ввести описание: %s", e)

            # Ждём окончания обработки видео — кнопка Post становится активной
            await asyncio.sleep(15)

            # Ищем кнопку Post / Опубликовать
            post_btn = None
            for sel in ['button[data-e2e="post_video_button"]',
                        'button:has-text("Post")',
                        'button:has-text("Опубликовать")']:
                try:
                    post_btn = await page.wait_for_selector(sel, timeout=8000)
                    if post_btn:
                        break
                except Exception:
                    continue

            if not post_btn:
                err_path = PROFILES_DIR / f"err_post_{account_id}.png"
                try:
                    await page.screenshot(path=str(err_path))
                except Exception:
                    pass
                await browser.close()
                return {"success": False,
                        "error": f"Не нашёл кнопку «Post». Возможно видео ещё обрабатывается. Скрин: {err_path}"}

            await post_btn.click()
            logger.info("[TikTok] Кнопка «Post» нажата, жду подтверждения…")

            # Ждём редирект или сообщение об успехе
            try:
                await page.wait_for_url("**/upload/post-success**", timeout=60000)
                external_id = "uploaded"
            except Exception:
                # Альтернатива — текст «Your video is being uploaded» или редирект на профиль
                await asyncio.sleep(5)
                if "tiktok.com" in page.url and "upload" not in page.url:
                    external_id = page.url.split("/")[-1] or "uploaded"
                else:
                    external_id = "queued"

            await browser.close()
            return {"success": True, "external_id": external_id, "error": None}

        except Exception as e:
            logger.exception("[TikTok] Ошибка публикации: %s", e)
            try:
                await browser.close()
            except Exception:
                pass
            return {"success": False, "error": f"Ошибка Playwright: {e}"}
