from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить бота в группу", callback_data="guide_setup")
    builder.button(text="🛡️ Команды модерации", callback_data="guide_commands")
    builder.button(text="👮 Уровни доступа", callback_data="guide_roles")
    builder.adjust(1)
    return builder.as_markup()

def get_back_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В главное меню", callback_data="start")
    builder.adjust(1)
    return builder.as_markup()