
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "clan.db"

async def migrate():
    print(f"Connecting to database at {DB_PATH}...")
    async with aiosqlite.connect(DB_PATH) as conn:
        # Check if columns already exist
        cursor = await conn.execute("PRAGMA table_info(matches)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "score_a" not in columns:
            print("Adding 'score_a' column to 'matches' table...")
            await conn.execute("ALTER TABLE matches ADD COLUMN score_a INTEGER DEFAULT NULL")
        else:
            print("'score_a' already exists.")

        if "score_b" not in columns:
            print("Adding 'score_b' column to 'matches' table...")
            await conn.execute("ALTER TABLE matches ADD COLUMN score_b INTEGER DEFAULT NULL")
        else:
            print("'score_b' already exists.")

        await conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())
