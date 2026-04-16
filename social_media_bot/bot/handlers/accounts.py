import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.accounts_kb import (
    accounts_delete_list_kb,
    accounts_menu_kb,
    auth_type_kb,
    back_to_accounts_kb,
    confirm_delete_kb,
    platform_choice_kb,
)
from bot.states.add_account import AddAccountFSM
from core.accounts.manager import AccountManager
from db.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = Router(name="accounts")


@router.callback_query(lambda c: c.data == "menu:accounts")
async def cb_accounts_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📱 <b>Управление аккаунтами</b>\n\nВыберите действие:",
        reply_markup=accounts_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Add account flow ──────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:add")
async def cb_add_account_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddAccountFSM.choose_platform)
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\nШаг 1/4: Выберите платформу:",
        reply_markup=platform_choice_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AddAccountFSM.choose_platform, lambda c: c.data.startswith("platform:"))
async def cb_choose_platform(callback: CallbackQuery, state: FSMContext) -> None:
    platform = callback.data.split(":")[1]
    await state.update_data(platform=platform)
    await state.set_state(AddAccountFSM.choose_auth_type)

    platform_labels = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}
    label = platform_labels.get(platform, platform)

    await callback.message.edit_text(
        f"➕ <b>Добавление аккаунта</b>\n\n"
        f"Платформа: <b>{label}</b>\n\n"
        f"Шаг 2/4: Выберите способ авторизации:",
        reply_markup=auth_type_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AddAccountFSM.choose_auth_type, lambda c: c.data.startswith("auth:"))
async def cb_choose_auth_type(callback: CallbackQuery, state: FSMContext) -> None:
    auth_type = callback.data.split(":")[1]
    await state.update_data(auth_type=auth_type)
    await state.set_state(AddAccountFSM.enter_username)

    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\n"
        "Шаг 3/4: Введите <b>имя пользователя</b> (username без @):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddAccountFSM.enter_username)
async def fsm_enter_username(message: Message, state: FSMContext) -> None:
    username = message.text.strip().lstrip("@") if message.text else ""
    if not username:
        await message.answer("❗ Имя пользователя не может быть пустым. Попробуйте снова:")
        return

    await state.update_data(username=username)
    data = await state.get_data()
    auth_type = data.get("auth_type", "cookies")

    if auth_type == "cookies":
        await state.set_state(AddAccountFSM.enter_session_data)
        await message.answer(
            "➕ <b>Добавление аккаунта</b>\n\n"
            "Шаг 4/4: Вставьте <b>cookies в формате JSON</b>.\n\n"
            "Пример:\n<code>{\"sessionid\": \"abc123\", \"ds_user_id\": \"12345\"}</code>\n\n"
            "Если cookies нет, отправьте: <code>{}</code>",
            parse_mode="HTML",
        )
    else:
        # API auth — skip cookies step and save immediately
        await _save_account(message, state, session_data=None)


@router.message(AddAccountFSM.enter_session_data)
async def fsm_enter_session_data(message: Message, state: FSMContext) -> None:
    raw_data = message.text.strip() if message.text else ""
    await _save_account(message, state, session_data=raw_data if raw_data else None)


async def _save_account(
    message: Message, state: FSMContext, session_data: str | None
) -> None:
    data = await state.get_data()
    platform = data.get("platform", "")
    username = data.get("username", "")
    auth_type = data.get("auth_type", "cookies")

    try:
        async with AsyncSessionLocal() as db:
            account = await AccountManager.add_account(
                db=db,
                platform=platform,
                username=username,
                auth_type=auth_type,
                raw_session_data=session_data,
            )

        await state.clear()
        await message.answer(
            f"✅ <b>Аккаунт успешно добавлен!</b>\n\n"
            f"ID: <code>{account.id}</code>\n"
            f"Платформа: <b>{platform.capitalize()}</b>\n"
            f"Username: @{username}\n"
            f"Тип авторизации: {auth_type}",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
        logger.info("Account added: id=%s platform=%s username=%s", account.id, platform, username)

    except ValueError as exc:
        await message.answer(
            f"❌ <b>Ошибка валидации:</b> {exc}\n\nПопробуйте снова или отправьте корректный JSON.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.exception("Failed to save account: %s", exc)
        await message.answer(
            "❌ Произошла ошибка при сохранении. Попробуйте позже.",
            reply_markup=back_to_accounts_kb(),
        )
        await state.clear()


# ── List accounts ─────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:list")
async def cb_list_accounts(callback: CallbackQuery) -> None:
    async with AsyncSessionLocal() as db:
        accounts = await AccountManager.list_accounts(db)

    text = AccountManager.format_accounts_list(accounts)
    await callback.message.edit_text(
        text,
        reply_markup=back_to_accounts_kb(),
        parse_mode="HTML",
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
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "❌ <b>Удаление аккаунта</b>\n\nВыберите аккаунт для удаления:",
        reply_markup=accounts_delete_list_kb(accounts),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("delete:"))
async def cb_delete_confirm(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as db:
        from db.crud import get_account_by_id
        account = await get_account_by_id(db, account_id)

    if not account:
        await callback.message.edit_text(
            "❗ Аккаунт не найден.",
            reply_markup=back_to_accounts_kb(),
        )
        await callback.answer()
        return

    platform_labels = {"tiktok": "TikTok", "instagram": "Instagram", "youtube": "YouTube"}
    label = platform_labels.get(account.platform, account.platform)

    await callback.message.edit_text(
        f"❌ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить аккаунт?\n\n"
        f"Платформа: <b>{label}</b>\n"
        f"Username: @{account.username}",
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
            f"✅ Аккаунт <code>{account_id}</code> успешно удалён.",
            reply_markup=back_to_accounts_kb(),
            parse_mode="HTML",
        )
        logger.info("Account deleted: id=%s", account_id)
    else:
        await callback.message.edit_text(
            "❗ Аккаунт не найден или уже был удалён.",
            reply_markup=back_to_accounts_kb(),
        )
    await callback.answer()


# ── Cancel any FSM ────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "accounts:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "📱 <b>Управление аккаунтами</b>\n\nВыберите действие:",
        reply_markup=accounts_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer("Отменено")
