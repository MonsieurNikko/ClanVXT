import aiosqlite
import asyncio
import os
from pathlib import Path

# Get DB path from config or environment, similar to main bot
# Assuming default path for this script
DB_PATH = Path("data/clan.db")

async def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Migrating database at {DB_PATH}...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Add join_type column
        try:
            await db.execute("ALTER TABLE clan_members ADD COLUMN join_type TEXT DEFAULT 'full'")
            print("Added join_type column.")
        except Exception as e:
            print(f"Skipped adding join_type (might exist): {e}")

        # 2. Add tryout_expires_at column
        try:
            await db.execute("ALTER TABLE clan_members ADD COLUMN tryout_expires_at TEXT DEFAULT NULL")
            print("Added tryout_expires_at column.")
        except Exception as e:
            print(f"Skipped adding tryout_expires_at (might exist): {e}")
            
        await db.commit()
    
    print("Migration complete.")

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    asyncio.run(migrate())
