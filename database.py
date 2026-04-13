import aiosqlite
import asyncio

DB_NAME = "mod_bot.db"

async def db_start():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица нарушений
        await db.execute("""CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            type TEXT,
            reason TEXT,
            moderator_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )""")
        await db.commit()

async def add_violation(chat_id: int, user_id: int, v_type: str, reason: str, mod_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO violations (chat_id, user_id, type, reason, moderator_id) VALUES (?, ?, ?, ?, ?)",
                         (chat_id, user_id, v_type, reason, mod_id))
        await db.commit()

async def get_warn_count(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM violations WHERE chat_id = ? AND user_id = ? AND type = 'warn'", (chat_id, user_id))
        result = await cursor.fetchone()
        return result[0] if result else 0

async def clear_warns(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM violations WHERE chat_id = ? AND user_id = ? AND type = 'warn'", (chat_id, user_id))
        await db.commit()

async def get_history(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT type, reason, timestamp FROM violations WHERE chat_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 5", (chat_id, user_id))
        return await cursor.fetchall()