from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, User
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ChatPermissions
from keyboards import get_main_menu, get_back_menu
from database import add_violation, get_warn_count, clear_warns, get_history
import re

router = Router()

# --- Тексты для ЛС ---
TEXT_SETUP = "1. Добавь бота в группу.\n2. Сделай его админом с правами на бан/удаление.\n3. Готово!"
TEXT_ROLES = "Админ может всё. Модератор может мутить и варнить."
TEXT_COMMANDS = "/warn, /ban, /mute, /unban, /unmute, /info"

# --- Вспомогательные функции ---

async def is_admin(message: Message) -> bool:
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def parse_time(args: list) -> tuple[int, list]:
    """Парсит время из аргументов (например, 1h, 30m). Возвращает секунды и остаток аргументов."""
    if not args:
        return 0, args # 0 = бессрочно или дефолт
    
    time_str = args[0]
    duration = 0
    
    if time_str.endswith('d'):
        duration = int(time_str[:-1]) * 86400
    elif time_str.endswith('h'):
        duration = int(time_str[:-1]) * 3600
    elif time_str.endswith('m'):
        duration = int(time_str[:-1]) * 60
        
    if duration > 0:
        return duration, args[1:]
    return 0, args

async def get_target_user(message: Message) -> User | None:
    """Ищет целевого пользователя: сначала в реплае, потом по @username в тексте"""
    # 1. Проверка реплая
    if message.reply_to_message:
        return message.reply_to_message.from_user
    
    # 2. Поиск @username в тексте сообщения
    # Ищем паттерн @слово
    match = re.search(r"@(\w+)", message.text)
    if match:
        username = match.group(1)
        try:
            # Пытаемся получить чат-мембер по юзернейму
            # Это работает, если юзер есть в чате
            chat_member = await message.bot.get_chat_member(message.chat.id, f"@{username}")
            return chat_member.user
        except:
            return None
            
    return None

# --- ЛС Меню ---
@router.message(Command("start"))
async def cmd_start(message: Message):
    if message.chat.type == 'private':
        await message.answer("👋 Привет! Я бот-модератор.", reply_markup=get_main_menu())

@router.callback_query(F.data == "start")
async def cb_start(callback: CallbackQuery):
    await callback.message.edit_text("👋 Меню:", reply_markup=get_main_menu())
    await callback.answer()

@router.callback_query(F.data == "guide_setup")
async def cb_setup(callback: CallbackQuery):
    await callback.message.edit_text(TEXT_SETUP, reply_markup=get_back_menu())
    await callback.answer()

@router.callback_query(F.data == "guide_roles")
async def cb_roles(callback: CallbackQuery):
    await callback.message.edit_text(TEXT_ROLES, reply_markup=get_back_menu())
    await callback.answer()

@router.callback_query(F.data == "guide_commands")
async def cb_commands(callback: CallbackQuery):
    await callback.message.edit_text(TEXT_COMMANDS, reply_markup=get_back_menu())
    await callback.answer()

# --- КОМАНДЫ МОДЕРАЦИИ ---

@router.message(Command("warn"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_warn(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя. Ответьте на сообщение или укажите @username.")
    if target.is_bot: return
    
    args = message.text.split()[1:]
    duration, rest_args = parse_time(args)
    reason = " ".join(rest_args) if rest_args else "Нарушение правил"
    
    await add_violation(message.chat.id, target.id, 'warn', reason, message.from_user.id)
    count = await get_warn_count(message.chat.id, target.id)
    
    if count >= 3:
        try:
            await message.chat.ban(target.id)
            await message.chat.unban(target.id) # Кик
            await clear_warns(message.chat.id, target.id)
            await message.answer(f"⛔️ {target.get_mention_html()} кикнут (3 варна).", parse_mode="HTML")
        except TelegramBadRequest:
            await message.answer("Не удалось кикнуть (возможно, он админ).")
    else:
        await message.answer(f"⚠️ {target.get_mention_html()} получил варн ({count}/3).\nПричина: {reason}", parse_mode="HTML")

@router.message(Command("unwarn"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unwarn(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя.")
        
    await clear_warns(message.chat.id, target.id)
    await message.answer(f"✅ Варны с {target.get_mention_html()} сняты.", parse_mode="HTML")

@router.message(Command("mute"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_mute(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя.")
    
    args = message.text.split()[1:]
    duration, rest_args = parse_time(args)
    if duration == 0: duration = 3600 # Дефолт 1 час, если время не указано
    reason = " ".join(rest_args) if rest_args else "Нарушение правил"
    
    try:
        until = message.date.timestamp() + duration
        perms = ChatPermissions(can_send_messages=False)
        
        await message.chat.restrict(
            user_id=target.id, 
            permissions=perms, 
            until_date=until
        )
        await message.answer(f"🔇 {target.get_mention_html()} замьючен на {duration//60} мин.\nПричина: {reason}", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("unmute"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unmute(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя.")
    
    try:
        perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        await message.chat.restrict(
            user_id=target.id, 
            permissions=perms
        )
        await message.answer(f"🔊 {target.get_mention_html()} размьючен.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("ban"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_ban(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя.")
    
    args = message.text.split()[1:]
    duration, rest_args = parse_time(args)
    reason = " ".join(rest_args) if rest_args else "Нарушение правил"
    
    try:
        if duration > 0:
            until = message.date.timestamp() + duration
            await message.chat.ban(target.id, until_date=until)
            time_text = f" на {duration//86400} дн." if duration >= 86400 else f" на {duration//3600} ч."
        else:
            await message.chat.ban(target.id)
            time_text = " навсегда"
            
        await message.answer(f"🔨 {target.get_mention_html()} забанен{time_text}.\nПричина: {reason}", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("unban"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unban(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Не удалось найти пользователя.")
    
    try:
        await message.chat.unban(target.id)
        await message.answer(f"🔓 {target.get_mention_html()} разбанен.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("info"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_info(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        target = message.from_user # Если не указан юзер, показываем инфо о себе
        
    warns = await get_warn_count(message.chat.id, target.id)
    await message.answer(f"ℹ️ {target.get_mention_html()}\nID: <code>{target.id}</code>\nВарнов: {warns}", parse_mode="HTML")

@router.message(Command("history"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_history(message: Message):
    if not await is_admin(message): return
    
    target = await get_target_user(message)
    if not target:
        return await message.answer("❌ Укажите пользователя через @username или ответ на сообщение.")
        
    history = await get_history(message.chat.id, target.id)
    
    if not history:
        text = f"📜 У {target.get_mention_html()} нет истории нарушений."
    else:
        text = f"📜 История {target.get_mention_html()}:\n"
        for h_type, reason, ts in history:
            text += f"- {h_type.upper()}: {reason}\n"
    await message.answer(text, parse_mode="HTML")