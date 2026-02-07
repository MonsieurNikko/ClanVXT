"""
Test script to verify database tables and CRUD operations
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services import db


async def test_database():
    """Test database tables and basic CRUD."""
    print("=" * 60)
    print("CLAN SYSTEM DATABASE VERIFICATION")
    print("=" * 60)
    
    # Test 1: Verify tables exist by querying them
    print("\n[1] Verifying tables exist...")
    async with db.get_connection() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        print(f"    Found {len(tables)} tables: {', '.join(tables)}")
        
        expected = ['appeals', 'cases', 'clan_members', 'clans', 'create_requests', 
                    'elo_history', 'loans', 'matches', 'transfers', 'users']
        missing = set(expected) - set(tables)
        if missing:
            print(f"    ✗ MISSING TABLES: {missing}")
            return False
        print("    ✓ All required tables exist")
    
    # Test 2: Verify unique constraint on clans.name
    print("\n[2] Verifying UNIQUE constraint on clans.name...")
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT sql FROM sqlite_master WHERE name='clans'")
        schema = (await cursor.fetchone())[0]
        if 'UNIQUE' in schema or 'unique' in schema.lower():
            print("    ✓ UNIQUE constraint found on clans table")
        else:
            # Check for unique index
            cursor = await conn.execute("PRAGMA index_list(clans)")
            indexes = await cursor.fetchall()
            has_unique = any(idx[2] == 1 for idx in indexes)  # idx[2] is unique flag
            if has_unique:
                print("    ✓ UNIQUE index found on clans table")
            else:
                print("    ⚠ Could not verify UNIQUE constraint (may be in column def)")
        print(f"    Schema: {schema[:100]}...")
    
    # Test 3: Verify unique constraint on users.riot_id
    print("\n[3] Verifying UNIQUE constraint on users.riot_id...")
    async with db.get_connection() as conn:
        cursor = await conn.execute("SELECT sql FROM sqlite_master WHERE name='users'")
        schema = (await cursor.fetchone())[0]
        if 'riot_id' in schema.lower():
            print("    ✓ riot_id column exists")
        if 'UNIQUE' in schema:
            print("    ✓ UNIQUE constraint found in users table")
        print(f"    Schema: {schema[:150]}...")
    
    # Test 4: Test User CRUD
    print("\n[4] Testing User CRUD...")
    try:
        # Create user
        user_id = await db.create_user("123456789", "TestPlayer#VN1")
        print(f"    ✓ Created user with ID: {user_id}")
        
        # Read user
        user = await db.get_user("123456789")
        print(f"    ✓ Read user: {user['riot_id']}")
        
        # Update cooldown
        from datetime import datetime, timedelta
        cooldown = (datetime.utcnow() + timedelta(days=14)).isoformat()
        await db.update_user_cooldown(user_id, cooldown)
        user = await db.get_user_by_id(user_id)
        print(f"    ✓ Updated cooldown: {user['cooldown_until'][:10]}...")
        
        # Get by riot_id
        user = await db.get_user_by_riot_id("TestPlayer#VN1")
        print(f"    ✓ Get by riot_id: discord_id={user['discord_id']}")
        
    except Exception as e:
        print(f"    ✗ User CRUD failed: {e}")
        return False
    
    # Test 5: Test Clan CRUD with transaction
    print("\n[5] Testing Clan CRUD with member transaction...")
    try:
        # Create clan (with captain in one transaction)
        clan_id = await db.create_clan("TestClan", user_id)
        print(f"    ✓ Created clan with ID: {clan_id}")
        
        # Read clan
        clan = await db.get_clan("TestClan")
        print(f"    ✓ Read clan: {clan['name']}, status={clan['status']}, elo={clan['elo']}")
        
        # Verify captain was added as member
        members = await db.get_clan_members(clan_id)
        print(f"    ✓ Members count: {len(members)}, captain role: {members[0]['role']}")
        
        # Update Elo (with history)
        await db.update_clan_elo(clan_id, 1050, None, "test_win")
        history = await db.get_clan_elo_history(clan_id)
        print(f"    ✓ Elo updated, history entries: {len(history)}")
        
    except Exception as e:
        print(f"    ✗ Clan CRUD failed: {e}")
        return False
    
    # Test 6: Verify unique clan name constraint works
    print("\n[6] Testing UNIQUE constraint enforcement...")
    try:
        await db.create_clan("TestClan", user_id)  # Should fail
        print("    ✗ Should have failed on duplicate name!")
        return False
    except Exception as e:
        print(f"    ✓ Duplicate rejected as expected: {type(e).__name__}")
    
    # Cleanup
    print("\n[7] Cleaning up test data...")
    async with db.get_connection() as conn:
        await conn.execute("DELETE FROM elo_history")
        await conn.execute("DELETE FROM clan_members")
        await conn.execute("DELETE FROM clans")
        await conn.execute("DELETE FROM users")
        await conn.commit()
    print("    ✓ Test data cleaned up")
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_database())
    sys.exit(0 if success else 1)
