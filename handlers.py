import asyncio # <--- ДОБАВЛЕНО
import re
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, User
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ChatPermissions
from keyboards import get_main_menu, get_back_menu
from database import add_violation, get_warn_count, clear_warns, get_history

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

def parse_time_from_text(text: str) -> int:
    """Ищет время в формате 1h, 30m, 2d в тексте и возвращает секунды"""
    match = re.search(r'(\d+)([hmd])', text)
    if not match:
        return 0
    
    val = int(match.group(1))
    unit = match.group(2)
    
    if unit == 'h': return val * 3600
    if unit == 'm': return val * 60
    if unit == 'd': return val * 86400
    return 0

def extract_reason(text: str, command: str) -> str:
    """Вырезает команду, время и @username, оставляет причину"""
    clean_text = text.replace(command, "").strip()
    clean_text = re.sub(r'\d+[hmd]\s*', '', clean_text).strip() # Удаляем время
    clean_text = re.sub(r'@\w+\s*', '', clean_text).strip()     # Удаляем @никнейм
    
    return clean_text if clean_text else "Нарушение правил"

async def get_user_by_username(message: Message, username: str) -> User | None:
    """Находит юзера по никнейму в чате"""
    try:
        for name in [f"@{username}", username]:
            try:
                chat_member = await message.bot.get_chat_member(message.chat.id, name)
                return chat_member.user
            except:
                continue
    except:
        pass
    return None

async def resolve_target_async(message: Message) -> User | None:
    """
    Главная логика получения цели:
    1. Если есть Reply -> берем оттуда.
    2. Если нет Reply -> ищем @username в тексте.
    """
    # 1. Приоритет: Reply
    if message.reply_to_message:
        return message.reply_to_message.from_user
        
    # 2. Поиск @username в тексте
    match = re.search(r"@(\w+)", message.text)
    if match:
        username = match.group(1)
        return await get_user_by_username(message, username)
        
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
    
    target = await resolve_target_async(message)
    
    if not target:
        return await message.answer(
            "❌ <b>Не указан пользователь.</b>\n"
            "Чтобы использовать команду из меню:\n"
            "1. Сначала ответьте (Reply) на сообщение нарушителя.\n"
            "2. Затем нажмите /warn в меню.", 
            parse_mode="HTML"
        )
    
    if target.is_bot:
        return await message.answer("❌ Ботов нельзя варнить.")

    reason = extract_reason(message.text, "/warn")
    
    await add_violation(message.chat.id, target.id, 'warn', reason, message.from_user.id)
    count = await get_warn_count(message.chat.id, target.id)
    
    if count >= 3:
        try:
            await message.chat.ban(target.id)
            await message.chat.unban(target.id) # Кик
            await clear_warns(message.chat.id, target.id)
            await message.answer(f"⛔️ {target.get_mention_html()} кикнут (3 варна).", parse_mode="HTML")
        except TelegramBadRequest as e:
            await message.answer(f"Не удалось кикнуть: {e}")
    else:
        await message.answer(f"⚠️ {target.get_mention_html()} получил варн ({count}/3).\nПричина: {reason}", parse_mode="HTML")

@router.message(Command("unwarn"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unwarn(message: Message):
    if not await is_admin(message): return
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы снять варны.")
        
    await clear_warns(message.chat.id, target.id)
    await message.answer(f"✅ Варны с {target.get_mention_html()} сняты.", parse_mode="HTML")

@router.message(Command("mute"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_mute(message: Message):
    if not await is_admin(message): return
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы замутить.")
    
    duration = parse_time_from_text(message.text)
    if duration == 0: duration = 3600 # Дефолт 1 час, если не указано время
    
    reason = extract_reason(message.text, "/mute")
    
    try:
        until = int(time.time()) + duration
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
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы размутить.")
    
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
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы забанить.")
    
    duration = parse_time_from_text(message.text)
    reason = extract_reason(message.text, "/ban")
    
    try:
        if duration > 0:
            until = int(time.time()) + duration
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
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение забаненного пользователя.")
    
    try:
        await message.chat.unban(target.id)
        await message.answer(f"🔓 {target.get_mention_html()} разбанен.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("info"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_info(message: Message):
    if not await is_admin(message): return
    
    target = await resolve_target_async(message)
    # Если цель не найдена (нет реплая и нет @), показываем инфо о себе
    if not target:
        target = message.from_user
        
    warns = await get_warn_count(message.chat.id, target.id)
    await message.answer(
        f"ℹ️ <b>Информация:</b>\n"
        f"Пользователь: {target.get_mention_html()}\n"
        f"ID: <code>{target.id}</code>\n"
        f"Варнов: {warns}", 
        parse_mode="HTML"
    )

@router.message(Command("history"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_history(message: Message):
    if not await is_admin(message): return
    
    target = await resolve_target_async(message)
    if not target:
        return await message.answer("❌ Ответьте на сообщение пользователя, чтобы посмотреть историю.")
        
    history = await get_history(message.chat.id, target.id)
    
    if not history:
        text = f"📜 У {target.get_mention_html()} нет истории нарушений."
    else:
        text = f"📜 <b>История</b> {target.get_mention_html()}:\n"
        for h_type, reason, ts in history:
            text += f"- {h_type.upper()}: {reason}\n"
    await message.answer(text, parse_mode="HTML")