import asyncio
import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.keyboards.accounts_kb import (
    accounts_delete_list_kb,
    accounts_menu_kb,
    auth_type_kb,
    back_to_accounts_kb,
    confirm_delete_kb,
    platform_choice_kb,
    qr_confirm_kb,
)
from bot.states.add_account import AddAccountFSM
from core.accounts.manager import AccountManager, PLATFORM_LABELS
from core.accounts.tiktok_auth import (
    QR_POLL_INTERVAL,
    QR_TIMEOUT,
    check_qr_status,
    generate_qr_token,
    verify_login_password,
)
from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = Router(name="accounts")


# ── Accounts menu ─────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:accounts")
async def cb_accounts_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📱 <b>Управление аккаунтами</b>\n\nВыберите действие:",
        reply_markup=accounts_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Step 1: Choose platform ───────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:add")
async def cb_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.choose_platform)
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\nШаг 1 — Выберите платформу:",
        reply_markup=platform_choice_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Step 2: Choose auth type ──────────────────────────────────────────────────

@router.callback_query(AddAccountFSM.choose_platform, lambda c: c.data.startswith("platform:"))
async def cb_choose_platform(callback: CallbackQuery, state: FSMContext) -> None:
    platform = callback.data.split(":")[1]
    await state.update_data(platform=platform)
    await state.set_state(AddAccountFSM.choose_auth_type)

    label = PLATFORM_LABELS.get(platform, platform.capitalize())
    await callback.message.edit_text(
        f"➕ <b>Добавление аккаунта</b>\n\n"
        f"Платформа: <b>{label}</b>\n\n"
        f"Шаг 2 — Выберите способ авторизации:",
        reply_markup=auth_type_kb(platform),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Step 3a: QR-code flow ─────────────────────────────────────────────────────

@router.callback_query(AddAccountFSM.choose_auth_type, lambda c: c.data == "auth:qr_code")
async def cb_auth_qr(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.qr_awaiting_scan)
    data = await state.get_data()
    platform = data.get("platform", "tiktok")

    await callback.message.edit_text(
        "📱 <b>QR-код авторизация</b>\n\n⏳ Генерирую QR-код...",
        parse_mode="HTML",
    )
    await callback.answer()

    qr_session = await generate_qr_token()

    if qr_session:
        await state.update_data(qr_token=qr_session.token, qr_url=qr_session.qr_url)
        instructions = (
            "📱 <b>QR-код для входа в TikTok</b>\n\n"
            f"Токен: <code>{qr_session.token[:20]}...</code>\n\n"
            "<b>Инструкция:</b>\n"
            "1️⃣ Откройте приложение <b>TikTok</b> на телефоне\n"
            "2️⃣ Нажмите на иконку <b>профиля</b> (нижний правый угол)\n"
            "3️⃣ Нажмите <b>⋮</b> (три точки) → <b>QR-код</b>\n"
            "4️⃣ Отсканируйте QR-код на экране\n"
            "5️⃣ Подтвердите вход в приложении\n\n"
            f"🔗 Ссылка для входа:\n<code>{qr_session.qr_url}</code>\n\n"
            "⏱ QR-код действителен <b>2 минуты</b>"
        )
    else:
        # Fallback: show manual instructions without live QR
        await state.update_data(qr_token="manual", qr_url="")
        instructions = (
            "📱 <b>QR-код авторизация TikTok</b>\n\n"
            "⚠️ Не удалось получить QR от TikTok (возможны ограничения).\n\n"
            "<b>Альтернативный способ — через браузер:</b>\n"
            "1️⃣ Откройте <a href='https://www.tiktok.com/login/'>tiktok.com/login</a>\n"
            "2️⃣ Выберите <b>«Войти по QR-коду»</b>\n"
            "3️⃣ Отсканируйте QR приложением TikTok\n"
            "4️⃣ После входа скопируйте cookies через DevTools\n\n"
            "После входа нажмите кнопку ниже:"
        )

    await callback.message.edit_text(
        instructions,
        reply_markup=qr_confirm_kb(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(AddAccountFSM.qr_awaiting_scan, lambda c: c.data == "qr:scanned")
async def cb_qr_scanned(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    qr_token = data.get("qr_token", "")
    platform = data.get("platform", "tiktok")

    if qr_token == "manual":
        # Manual fallback — ask user to provide username
        await state.set_state(AddAccountFSM.qr_enter_username)
        await callback.message.edit_text(
            "✅ Отлично! Введите ваш TikTok <b>username</b> (без @):",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "⏳ <b>Проверяю статус QR-кода...</b>\n\nПожалуйста, подождите.",
        parse_mode="HTML",
    )
    await callback.answer()

    # Poll QR status
    start = asyncio.get_event_loop().time()
    confirmed = False
    cookies = {}

    while (asyncio.get_event_loop().time() - start) < QR_TIMEOUT:
        result = await check_qr_status(qr_token)
        status = result.get("status")

        if status == "confirmed":
            cookies = result.get("cookies", {})
            confirmed = True
            break
        elif status == "scanned":
            await callback.message.edit_text(
                "📱 QR отсканирован! Ожидаю подтверждения в приложении...",
                parse_mode="HTML",
            )
        elif status == "expired":
            await callback.message.edit_text(
                "⏰ <b>QR-код истёк.</b>\n\nНачните сначала.",
                reply_markup=back_to_accounts_kb(),
                parse_mode="HTML",
            )
            await state.clear()
            return
        await asyncio.sleep(QR_POLL_INTERVAL)

    if confirmed and cookies:
        # Save account with real session
        async with AsyncSessionLocal() as db:
            account = await AccountManager.add_account_cookies(
                db=db,
                platform=platform,
                username=cookies.get("tt_target_user", "tiktok_user"),
                raw_cookies=str(cookies),
            )
        await state.clear()
        await callback.message.edit_text(
            f"✅ <b>Аккаунт добавлен через QR!</b>\n\n"
            f"ID: <code>{account.id}</code>\n"
            f"Платформа: TikTok\n"
            f"Сессия: сохранена ✔",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
    else:
        # QR not confirmed — ask username for manual entry
        await state.set_state(AddAccountFSM.qr_enter_username)
        await callback.message.edit_text(
            "⚠️ Не удалось автоматически получить сессию.\n\n"
            "Введите ваш TikTok <b>username</b> (без @) чтобы сохранить аккаунт без сессии:",
            parse_mode="HTML",
        )


@router.message(AddAccountFSM.qr_enter_username)
async def fsm_qr_username(message: Message, state: FSMContext) -> None:
    username = message.text.strip().lstrip("@") if message.text else ""
    if not username:
        await message.answer("❗ Введите корректный username:")
        return

    data = await state.get_data()
    platform = data.get("platform", "tiktok")

    async with AsyncSessionLocal() as db:
        account = await AccountManager.add_account_qr_pending(
            db=db, platform=platform, username=username, qr_token="manual"
        )
    await state.clear()
    await message.answer(
        f"✅ <b>Аккаунт сохранён</b>\n\n"
        f"ID: <code>{account.id}</code>\n"
        f"Username: @{username}\n"
        f"Статус: ⏳ Ожидает сессию\n\n"
        f"💡 Для полного доступа добавьте cookies через раздел «Аккаунты».",
        reply_markup=back_to_accounts_kb(),
        parse_mode="HTML",
    )


# ── Step 3b: Login + Password flow ────────────────────────────────────────────

@router.callback_query(AddAccountFSM.choose_auth_type, lambda c: c.data == "auth:login_password")
async def cb_auth_login_password(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.enter_username)
    data = await state.get_data()
    label = PLATFORM_LABELS.get(data.get("platform", ""), "платформа")

    await callback.message.edit_text(
        f"🔐 <b>Авторизация по логину и паролю</b>\n"
        f"Платформа: <b>{label}</b>\n\n"
        f"Шаг 3 — Введите <b>username</b> (логин / email / номер телефона):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddAccountFSM.enter_username)
async def fsm_enter_username(message: Message, state: FSMContext) -> None:
    username = message.text.strip() if message.text else ""
    if not username:
        await message.answer("❗ Username не может быть пустым. Попробуйте снова:")
        return
    await state.update_data(username=username)
    await state.set_state(AddAccountFSM.enter_password)
    await message.answer(
        "🔑 Шаг 4 — Введите <b>пароль</b>:\n\n"
        "⚠️ <i>Сообщение с паролем будет автоматически удалено для безопасности.</i>",
        parse_mode="HTML",
    )


@router.message(AddAccountFSM.enter_password)
async def fsm_enter_password(message: Message, state: FSMContext) -> None:
    password = message.text if message.text else ""

    # Delete user's password message immediately
    try:
        await message.delete()
    except Exception:
        pass

    if not password or len(password) < 4:
        await message.answer("❗ Пароль слишком короткий. Введите снова:")
        return

    data = await state.get_data()
    platform = data.get("platform", "")
    username = data.get("username", "")

    # Verify/store credentials
    result = await verify_login_password(username, password, platform)

    if result["status"] == "error":
        await message.answer(
            f"❌ Ошибка: {result['message']}\n\nПопробуйте снова:",
        )
        return

    try:
        async with AsyncSessionLocal() as db:
            account = await AccountManager.add_account_login_password(
                db=db,
                platform=platform,
                username=username,
                password=password,
            )
        await state.clear()
        label = PLATFORM_LABELS.get(platform, platform.capitalize())
        await message.answer(
            f"✅ <b>Аккаунт добавлен!</b>\n\n"
            f"ID: <code>{account.id}</code>\n"
            f"Платформа: <b>{label}</b>\n"
            f"Username: @{username}\n"
            f"Авторизация: 🔐 Логин + Пароль\n"
            f"Пароль: сохранён в зашифрованном виде 🔒\n\n"
            f"ℹ️ {result['message']}",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
        logger.info("Login+password account added: id=%s platform=%s", account.id, platform)
    except Exception as exc:
        logger.exception("Failed to save login+password account: %s", exc)
        await message.answer(
            "❌ Ошибка при сохранении. Попробуйте позже.",
            reply_markup=back_to_accounts_kb(),
        )
        await state.clear()


# ── Step 3c: Cookies flow ─────────────────────────────────────────────────────

@router.callback_query(AddAccountFSM.choose_auth_type, lambda c: c.data == "auth:cookies")
async def cb_auth_cookies(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.enter_username_cookies)
    await callback.message.edit_text(
        "🍪 <b>Авторизация через Cookies</b>\n\n"
        "Шаг 3 — Введите <b>username</b> (без @):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddAccountFSM.enter_username_cookies)
async def fsm_enter_username_cookies(message: Message, state: FSMContext) -> None:
    username = message.text.strip().lstrip("@") if message.text else ""
    if not username:
        await message.answer("❗ Username не может быть пустым:")
        return
    await state.update_data(username=username)
    await state.set_state(AddAccountFSM.enter_session_data)
    await message.answer(
        "🍪 Шаг 4 — Вставьте <b>cookies в формате JSON</b>.\n\n"
        "Как получить cookies:\n"
        "• Браузер → DevTools (F12) → Application → Cookies\n"
        "• Или используйте расширение «Cookie-Editor»\n\n"
        "Пример:\n"
        "<code>{\"sessionid\": \"abc123\", \"csrftoken\": \"xyz\", \"ds_user_id\": \"12345\"}</code>\n\n"
        "Нет cookies? Отправьте <code>{}</code> и добавьте позже.",
        parse_mode="HTML",
    )


@router.message(AddAccountFSM.enter_session_data)
async def fsm_enter_session_data(message: Message, state: FSMContext) -> None:
    raw = message.text.strip() if message.text else "{}"
    data = await state.get_data()

    try:
        async with AsyncSessionLocal() as db:
            account = await AccountManager.add_account_cookies(
                db=db,
                platform=data.get("platform", ""),
                username=data.get("username", ""),
                raw_cookies=raw,
            )
        await state.clear()
        label = PLATFORM_LABELS.get(data.get("platform", ""), "")
        await message.answer(
            f"✅ <b>Аккаунт добавлен!</b>\n\n"
            f"ID: <code>{account.id}</code>\n"
            f"Платформа: <b>{label}</b>\n"
            f"Username: @{account.username}\n"
            f"Сессия: {'сохранена ✔' if account.session_data else 'не добавлена ✘'}",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
    except ValueError as exc:
        await message.answer(
            f"❌ <b>Ошибка:</b> {exc}\n\n"
            "Убедитесь что вставили корректный JSON. Попробуйте снова или отправьте <code>{}</code>:",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Failed to save cookies account: %s", exc)
        await message.answer("❌ Ошибка при сохранении.", reply_markup=back_to_accounts_kb())
        await state.clear()


# ── Step 3d: API key flow ─────────────────────────────────────────────────────

@router.callback_query(AddAccountFSM.choose_auth_type, lambda c: c.data == "auth:api")
async def cb_auth_api(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.enter_username_api)
    await callback.message.edit_text(
        "🔑 <b>API авторизация</b>\n\n"
        "Шаг 3 — Введите <b>username</b> (без @):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddAccountFSM.enter_username_api)
async def fsm_enter_username_api(message: Message, state: FSMContext) -> None:
    username = message.text.strip().lstrip("@") if message.text else ""
    if not username:
        await message.answer("❗ Username не может быть пустым:")
        return
    await state.update_data(username=username)
    await state.set_state(AddAccountFSM.enter_api_key)
    await message.answer(
        "🔑 Шаг 4 — Введите <b>API ключ</b> или OAuth токен доступа:",
        parse_mode="HTML",
    )


@router.message(AddAccountFSM.enter_api_key)
async def fsm_enter_api_key(message: Message, state: FSMContext) -> None:
    api_key = message.text.strip() if message.text else ""

    # Delete message with API key for security
    try:
        await message.delete()
    except Exception:
        pass

    if not api_key:
        await message.answer("❗ API ключ не может быть пустым:")
        return

    data = await state.get_data()

    try:
        async with AsyncSessionLocal() as db:
            account = await AccountManager.add_account_api(
                db=db,
                platform=data.get("platform", ""),
                username=data.get("username", ""),
                api_key=api_key,
            )
        await state.clear()
        label = PLATFORM_LABELS.get(data.get("platform", ""), "")
        await message.answer(
            f"✅ <b>Аккаунт добавлен!</b>\n\n"
            f"ID: <code>{account.id}</code>\n"
            f"Платформа: <b>{label}</b>\n"
            f"Username: @{account.username}\n"
            f"API ключ: сохранён 🔒",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Failed to save API account: %s", exc)
        await message.answer("❌ Ошибка при сохранении.", reply_markup=back_to_accounts_kb())
        await state.clear()


# ── List accounts ─────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:list")
async def cb_list_accounts(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as db:
        accounts = await AccountManager.list_accounts(db)
    text = AccountManager.format_accounts_list(accounts)
    await callback.message.edit_text(
        text, reply_markup=back_to_accounts_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ── Delete account flow ───────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:delete_prompt")
async def cb_delete_prompt(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as db:
        accounts = await AccountManager.list_accounts(db)

    if not accounts:
        await callback.message.edit_text(
            "📭 Нет аккаунтов для удаления.",
            reply_markup=back_to_accounts_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "❌ <b>Удаление аккаунта</b>\n\nВыберите аккаунт:",
        reply_markup=accounts_delete_list_kb(accounts),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("delete:"))
async def cb_delete_select(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as db:
        from db.crud import get_account_by_id
        account = await get_account_by_id(db, account_id)

    if not account:
        await callback.message.edit_text("❗ Аккаунт не найден.", reply_markup=back_to_accounts_kb())
        await callback.answer()
        return

    label = PLATFORM_LABELS.get(account.platform, account.platform)
    from core.accounts.manager import AUTH_LABELS
    auth_label = AUTH_LABELS.get(account.auth_type, account.auth_type)

    await callback.message.edit_text(
        f"❌ <b>Подтвердите удаление</b>\n\n"
        f"Платформа: <b>{label}</b>\n"
        f"Username: @{account.username}\n"
        f"Авторизация: {auth_label}",
        reply_markup=confirm_delete_kb(account_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("confirm_delete:"))
async def cb_confirm_delete(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as db:
        deleted = await AccountManager.remove_account(db, account_id)

    if deleted:
        await callback.message.edit_text(
            f"✅ Аккаунт <code>{account_id}</code> удалён.",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
        logger.info("Account deleted: id=%s", account_id)
    else:
        await callback.message.edit_text(
            "❗ Аккаунт не найден или уже удалён.",
            reply_markup=back_to_accounts_kb(),
        )
    await callback.answer()


# ── Cancel FSM ────────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📱 <b>Управление аккаунтами</b>\n\nВыберите действие:",
        reply_markup=accounts_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer("Отменено")
