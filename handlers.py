from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from keyboards import get_main_menu, get_back_menu
from database import add_violation, get_warn_count, clear_warns, get_history

router = Router()

# --- Тексты для ЛС ---
TEXT_SETUP = "1. Добавь бота в группу.\n2. Сделай его админом с правами на бан/удаление.\n3. Готово!"
TEXT_ROLES = "Админ может всё. Модератор может мутить и варнить."
TEXT_COMMANDS = "/warn, /ban, /mute, /unban, /unmute, /info"

# --- Проверка прав ---
async def is_admin(message: Message) -> bool:
    try:
        member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
        return member.status in ['creator', 'administrator']
    except:
        return False

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
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    if target.is_bot: return
    
    reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Нарушение"
    
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
        await message.answer(f"⚠️ {target.get_mention_html()} варн ({count}/3). Причина: {reason}", parse_mode="HTML")

@router.message(Command("unwarn"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unwarn(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    await clear_warns(message.chat.id, target.id)
    await message.answer(f"✅ Варны с {target.get_mention_html()} сняты.", parse_mode="HTML")

@router.message(Command("mute"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_mute(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    args = message.text.split()[1:]
    duration = 3600 # 1 час
    if args and args[0].endswith('h'): duration = int(args[0][:-1]) * 3600
    elif args and args[0].endswith('m'): duration = int(args[0][:-1]) * 60
    
    try:
        until = message.date.timestamp() + duration
        await message.chat.restrict(target.id, permissions=message.chat.permissions, until_date=until)
        await message.answer(f"🔇 {target.get_mention_html()} мут на {duration//60} мин.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("unmute"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unmute(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    try:
        await message.chat.restrict(target.id, permissions=message.chat.permissions)
        await message.answer(f"🔊 {target.get_mention_html()} размьючен.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("ban"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_ban(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Нарушение"
    
    try:
        await message.chat.ban(target.id)
        await message.answer(f"🔨 {target.get_mention_html()} забанен. Причина: {reason}", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("unban"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_unban(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение забаненного юзера.")
    
    target = message.reply_to_message.from_user
    try:
        await message.chat.unban(target.id)
        await message.answer(f"🔓 {target.get_mention_html()} разбанен.", parse_mode="HTML")
    except TelegramBadRequest as e:
        await message.answer(f"Ошибка: {e}")

@router.message(Command("info"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_info(message: Message):
    if not await is_admin(message): return
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warns = await get_warn_count(message.chat.id, target.id)
    await message.answer(f"ℹ️ {target.get_mention_html()}\nВарнов: {warns}", parse_mode="HTML")

@router.message(Command("history"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_history(message: Message):
    if not await is_admin(message): return
    if not message.reply_to_message: return await message.answer("Ответьте на сообщение.")
    
    target = message.reply_to_message.from_user
    history = await get_history(message.chat.id, target.id)
    
    if not history:
        text = f"📜 У {target.get_mention_html()} нет истории."
    else:
        text = f"📜 История {target.get_mention_html()}:\n"
        for h_type, reason, ts in history:
            text += f"- {h_type}: {reason}\n"
    await message.answer(text, parse_mode="HTML")