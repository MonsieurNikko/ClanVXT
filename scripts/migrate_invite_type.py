import aiosqlite
import asyncio
import os
from pathlib import Path

DB_PATH = Path("data/clan.db")

async def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Migrating database at {DB_PATH} (Step 2)...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Add invite_type column to invite_requests
        try:
            await db.execute("ALTER TABLE invite_requests ADD COLUMN invite_type TEXT DEFAULT 'full'")
            print("Added invite_type column to invite_requests.")
        except Exception as e:
            print(f"Skipped adding invite_type (might exist): {e}")

        await db.commit()
    
    print("Migration Step 2 complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
