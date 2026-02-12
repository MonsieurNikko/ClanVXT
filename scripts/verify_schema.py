
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "clan.db"

async def check():
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("PRAGMA table_info(matches)")
        rows = await cursor.fetchall()
        print("Columns in 'matches' table:")
        for row in rows:
            print(f"- {row['name']} ({row['type']})")

if __name__ == "__main__":
    asyncio.run(check())
