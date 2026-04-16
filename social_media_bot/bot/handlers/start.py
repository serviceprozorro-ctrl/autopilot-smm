import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import main_menu_kb

logger = logging.getLogger(__name__)

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать в Social Media Bot!</b>\n\n"
        "Управляйте аккаунтами TikTok, Instagram и YouTube из одного места.\n\n"
        "Выберите раздел:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    logger.info("User %s started the bot", message.from_user.id if message.from_user else "unknown")


@router.callback_query(lambda c: c.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:stats")
async def cb_stats(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        "Раздел статистики находится в разработке.\n"
        "Здесь будет отображаться:\n"
        "• Количество аккаунтов по платформам\n"
        "• Количество запланированных публикаций\n"
        "• Активность за последние 7 дней",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:autopost")
async def cb_autopost(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🚀 <b>Автопостинг</b>\n\n"
        "Функция автопостинга находится в разработке.\n"
        "Скоро здесь появится возможность:\n"
        "• Загружать контент с других платформ\n"
        "• Настраивать расписание публикаций\n"
        "• Массовое переопубликование контента",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()
