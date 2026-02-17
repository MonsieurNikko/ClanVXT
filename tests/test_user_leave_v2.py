import asyncio
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import db

async def setup_test_db():
    """Reset DB for testing."""
    await db.init_db()
    async with db.get_connection() as conn:
        # Disable foreign keys temporarily for a clean wipe
        await conn.execute("PRAGMA foreign_keys = OFF")
        tables = [
            "loans", "transfers", "matches", "elo_history", "clan_members", 
            "clan_flags", "clans", "create_requests", "invite_requests", 
            "lfg_posts", "cases", "appeals", "system_bans", "cooldowns", "users"
        ]
        for table in tables:
            await conn.execute(f"DELETE FROM {table}")
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.commit()

async def test_member_leaves():
    print("\n--- Test: Member only leaves ---")
    u_admin = await db.create_user("admin999", "Admin#999")
    u_mem = await db.create_user("member1", "Member#1")
    c1 = await db.create_clan("ClanA", u_admin) # Valid captain
    await db.add_member(u_mem, c1, "member")
    
    res = await db.cleanup_user_on_leave("member1")
    print(f"Result: {res}")
    
    assert res["success"]
    assert "Deleted user from database" in res["actions"]
    
    # Check DB
    user = await db.get_user("member1")
    assert user is None
    members = await db.get_clan_members(c1)
    assert not any(m["user_id"] == u_mem for m in members)
    print("✅ Member only leaves: Passed")

async def test_captain_leaves_with_vice():
    print("\n--- Test: Captain leaves with Vice ---")
    u_cap = await db.create_user("cap1", "Cap#1")
    u_vice = await db.create_user("vice1", "Vice#1")
    clan_id = await db.create_clan("ClanV", u_cap)
    await db.add_member(u_vice, clan_id, "vice")
    
    res = await db.cleanup_user_on_leave("cap1")
    print(f"Result: {res}")
    
    assert res["success"]
    assert any("Promoted user" in a for a in res["actions"])
    
    # Check DB
    clan = await db.get_clan_by_id(clan_id)
    assert clan["captain_id"] == u_vice
    members = await db.get_clan_members(clan_id)
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[u_vice] == "captain"
    user_cap = await db.get_user("cap1")
    assert user_cap is None
    print("✅ Captain leaves with Vice: Passed")

async def test_captain_leaves_no_vice():
    print("\n--- Test: Captain leaves NO Vice (Should Anonymize) ---")
    u_cap_id = "cap2"
    u_cap = await db.create_user(u_cap_id, "Cap#2")
    u_mem = await db.create_user("mem2", "Mem#2")
    clan_id = await db.create_clan("ClanNV", u_cap)
    await db.add_member(u_mem, clan_id, "member")
    
    res = await db.cleanup_user_on_leave(u_cap_id)
    print(f"Result: {res}")
    
    assert res["success"]
    assert any("Anonymized user due to Captaincy" in a for a in res["actions"])
    
    # Check DB
    clan = await db.get_clan_by_id(clan_id)
    assert clan["status"] == "inactive"
    user = await db.get_user(f"LEAVER_{u_cap_id}")
    assert user is not None
    assert user["is_banned"] == 1
    print("✅ Captain leaves NO Vice (Anonymized): Passed")

async def test_user_with_history_anonymized():
    print("\n--- Test: User with match history anonymized ---")
    u_admin = await db.create_user("admin999b", "Admin#999b")
    u_hist = await db.create_user("hist1", "Hist#1")
    c1 = await db.create_clan("ClanH", u_admin)
    
    # Create a match where this user is creator
    async with db.get_connection() as conn:
        await conn.execute(
            "INSERT INTO matches (clan_a_id, clan_b_id, creator_user_id, status) VALUES (?, ?, ?, 'created')",
            (c1, c1, u_hist)
        )
        await conn.commit()
    
    res = await db.cleanup_user_on_leave("hist1")
    print(f"Result: {res}")
    
    assert res["success"]
    assert "Anonymized user due to Match History" in res["actions"]
    
    # Check DB
    user = await db.get_user("LEAVER_hist1")
    assert user is not None
    assert user["is_banned"] == 1
    assert "DeletedUser#" in user["riot_id"]
    print("✅ User with match history: Passed")

async def main():
    await setup_test_db()
    try:
        await test_member_leaves()
        await setup_test_db()
        await test_captain_leaves_with_vice()
        await setup_test_db()
        await test_captain_leaves_no_vice()
        await setup_test_db()
        await test_user_with_history_anonymized()
        print("\n🎉 ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
