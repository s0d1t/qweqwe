import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from config import BOT_TOKEN
from handlers import router
from database import db_start

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="📖 Меню помощи"),
        BotCommand(command="warn", description="⚠️ Выдать предупреждение"),
        BotCommand(command="unwarn", description="✅ Снять предупреждение"),
        BotCommand(command="mute", description="🔇 Замутить пользователя"),
        BotCommand(command="unmute", description="🔊 Размутить пользователя"),
        BotCommand(command="ban", description="🔨 Забанить пользователя"),
        BotCommand(command="unban", description="🔓 Разбанить пользователя"),
        BotCommand(command="info", description="ℹ️ Информация о пользователе"),
        BotCommand(command="history", description="📜 История нарушений"),
    ]
    await bot.set_my_commands(commands)

async def main():
    await db_start()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(router)
    await set_commands(bot)
    
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())