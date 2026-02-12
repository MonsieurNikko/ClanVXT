import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import db, cooldowns

async def migrate():
    print("🚀 Starting Cooldown Migration...")
    
    async with db.get_connection() as conn:
        # 1. Get all users with legacy cooldowns
        cursor = await conn.execute(
            "SELECT id, discord_id, cooldown_until FROM users WHERE cooldown_until IS NOT NULL"
        )
        rows = await cursor.fetchall()
        
        if not rows:
            print("✅ No legacy cooldowns found to migrate.")
            return

        migrated_count = 0
        now = datetime.now(timezone.utc)
        
        for row in rows:
            user_id = row["id"]
            until_str = row["cooldown_until"]
            
            try:
                # Standardize timestamp
                if until_str.endswith('Z'):
                    until_str = until_str.replace('Z', '+00:00')
                
                until_dt = datetime.fromisoformat(until_str)
                if until_dt.tzinfo is None:
                    until_dt = until_dt.replace(tzinfo=timezone.utc)
                
                # Only migrate if still in the future
                if until_dt > now:
                    print(f"📦 Migrating cooldown for user {user_id}: {until_str}")
                    
                    # Insert into cooldowns table (UPSERT logic via ON CONFLICT in set_cooldown isn't direct here, 
                    # but we can use the db helper or raw SQL)
                    await conn.execute(
                        """INSERT INTO cooldowns (target_type, target_id, kind, until, reason)
                           VALUES ('user', ?, ?, ?, ?)
                           ON CONFLICT(target_type, target_id, kind) 
                           DO UPDATE SET until = excluded.until, updated_at = datetime('now')""",
                        (user_id, cooldowns.KIND_JOIN_LEAVE, until_dt.isoformat(), "Migrated from legacy system")
                    )
                    migrated_count += 1
                else:
                    print(f"🗑️ Skipping expired cooldown for user {user_id}")

            except Exception as e:
                print(f"❌ Error migrating user {user_id}: {e}")
                continue
        
        # 2. Clear all legacy columns (optional, but good for "Fusing")
        # For safety, let's just clear the ones we migrated or were expired
        await conn.execute("UPDATE users SET cooldown_until = NULL")
        await conn.commit()
        
        print(f"🎉 Successfully migrated {migrated_count} cooldowns.")

if __name__ == "__main__":
    asyncio.run(migrate())
