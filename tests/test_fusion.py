import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import db, cooldowns

async def test_lazy_migration():
    print("🧪 Testing Lazy Migration...")
    
    # 1. Setup legacy cooldown
    user_id = 999
    legacy_until = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    
    async with db.get_connection() as conn:
        # Ensure user exists (ignoring constraints for simple test if needed, but better to do it right)
        await conn.execute("INSERT OR IGNORE INTO users (id, discord_id, riot_id) VALUES (?, '999', 'Test#1')", (user_id,))
        await conn.execute("UPDATE users SET cooldown_until = ? WHERE id = ?", (legacy_until, user_id))
        await conn.commit()
    
    print(f"✅ Set legacy cooldown for user {user_id}: {legacy_until}")
    
    # 2. Verify check_member_join_cooldown performs migration
    is_cd, until = await cooldowns.check_member_join_cooldown(user_id)
    print(f"🔍 check_member_join_cooldown result: is_cd={is_cd}, until={until}")
    
    assert is_cd == True
    
    # 3. Verify it's now in the new table
    new_cd = await db.get_cooldown("user", user_id, "join_leave")
    print(f"📊 New table entry: {new_cd}")
    assert new_cd is not None
    assert new_cd["reason"] == "Lazy migration from legacy column"
    
    # 4. Verify legacy column is cleared
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT cooldown_until FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        print(f"🧹 Legacy column value: {row['cooldown_until']}")
        assert row["cooldown_until"] is None
        
    print("✅ Lazy Migration Test Passed!")

async def test_admin_clear_sync():
    print("\n🧪 Testing Admin Clear Sync...")
    user_id = 999
    
    # 1. Set cooldown via service
    await cooldowns.apply_member_join_cooldown(user_id, "Test Admin Clear")
    
    # 2. Clear via db wrapper (which is what admin clear calls)
    await db.update_user_cooldown(user_id, None)
    
    # 3. Verify both systems clear
    is_cd, _ = await cooldowns.check_member_join_cooldown(user_id)
    assert is_cd == False
    
    new_cd = await db.get_cooldown("user", user_id, "join_leave")
    assert new_cd is None
    
    print("✅ Admin Clear Sync Test Passed!")

async def main():
    try:
        await test_lazy_migration()
        await test_admin_clear_sync()
        print("\n✨ ALL FUSION TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
