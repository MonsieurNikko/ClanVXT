import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from services import db, permissions, cooldowns

async def setup_test_data():
    """Setup test clans and users."""
    # Drop tables to ensure fresh schema
    async with db.get_connection() as conn:
        await conn.execute("DROP TABLE IF EXISTS loans")
        await conn.execute("DROP TABLE IF EXISTS transfers")
        await conn.execute("DROP TABLE IF EXISTS cooldowns")
        await conn.execute("DROP TABLE IF EXISTS clan_members")
        await conn.execute("DROP TABLE IF EXISTS create_requests")
        await conn.execute("DROP TABLE IF EXISTS matches")
        await conn.execute("DROP TABLE IF EXISTS elo_history")
        await conn.execute("DROP TABLE IF EXISTS cases")
        await conn.execute("DROP TABLE IF EXISTS appeals")
        await conn.execute("DROP TABLE IF EXISTS clans")
        await conn.execute("DROP TABLE IF EXISTS users")
        await conn.commit()

    await db.init_db()
    
    # Clean up (redundant but safe)
    async with db.get_connection() as conn:
        await conn.execute("DELETE FROM clans")
        await conn.execute("DELETE FROM users")
        await conn.execute("DELETE FROM clan_members")
        await conn.execute("DELETE FROM loans")
        await conn.execute("DELETE FROM transfers")
        await conn.execute("DELETE FROM cooldowns")
        await conn.commit()

    # Create Users
    u1 = await db.create_user("1001", "CaptSource#1")
    u2 = await db.create_user("1002", "CaptDest#1")
    u3 = await db.create_user("1003", "Member#1")
    u4 = await db.create_user("1004", "Member#2")
    u5 = await db.create_user("1005", "Member#3")
    u6 = await db.create_user("1006", "Member#4")
    u7 = await db.create_user("1007", "Member#5") # Source needs 5+1(capt) = 6 to allow transfer leaving 5? Or 5 is enough?
    # Rule: "Clan nguồn phải đảm bảo còn tối thiểu 5 thành viên sau khi chuyển đi"
    # So if clan has 5, transfer fails (remains 4). If 6, transfer ok (remains 5).
    
    # Create Clans
    c1 = await db.create_clan("SourceClan", u1)
    c2 = await db.create_clan("DestClan", u2)
    
    # Add members to SourceClan (Total 6: Capt + 5 members)
    await db.add_member(u3, c1, "member")
    await db.add_member(u4, c1, "member")
    await db.add_member(u5, c1, "member")
    await db.add_member(u6, c1, "member")
    await db.add_member(u7, c1, "member")
    
    await db.update_clan_status(c1, "active")
    await db.update_clan_status(c2, "active")
    
    return c1, c2, u1, u2, u3, u7

async def test_loan_flow(c1, c2, u3):
    print("\n--- Testing Loan Flow ---")
    
    # 1. Check Permission
    allowed, err = await permissions.can_request_loan(u3, c1)
    print(f"Can request loan: {allowed} (Err: {err})")
    assert allowed
    
    # 2. Create Loan
    loan_id = await db.create_loan(c1, c2, u3, u3, 7)
    print(f"Loan created: ID {loan_id}")
    
    # 3. Simulate Acceptance
    await db.update_loan_acceptance(loan_id, lending=True, borrowing=True, member=True)
    
    # 4. Activate
    await db.activate_loan(loan_id)
    loan = await db.get_loan(loan_id)
    print(f"Loan Status: {loan['status']}")
    assert loan['status'] == 'active'
    
    # 5. Check Active Loan Checks
    allowed, err = await permissions.can_request_loan(u3, c1)
    print(f"Can request another loan (should fail): {allowed} (Err: {err})")
    assert not allowed
    
    # 6. End Loan
    await db.end_loan(loan_id)
    await cooldowns.apply_loan_cooldowns(c1, c2, u3)
    print("Loan ended and cooldowns applied.")
    
    # 7. Check Cooldowns
    is_cd, until = await cooldowns.check_loan_cooldown("user", u3)
    print(f"User Cooldown: {is_cd} (Until: {until})")
    assert is_cd

async def test_transfer_flow(c1, c2, u7):
    print("\n--- Testing Transfer Flow ---")
    
    # 1. Check Permission (Source has 6 members, removing 1 leaves 5 -> OK)
    allowed, err = await permissions.can_request_transfer(u7, c1, c2)
    print(f"Can request transfer: {allowed} (Err: {err})")
    assert allowed
    
    # 2. Create Transfer
    transfer_id = await db.create_transfer(c1, c2, u7, u7)
    print(f"Transfer created: ID {transfer_id}")
    
    # 3. Simulate Acceptance
    await db.update_transfer_acceptance(transfer_id, source=True, dest=True, member=True)
    
    # 4. Complete
    await db.complete_transfer(transfer_id)
    # Move member manually as cog does
    await db.remove_member(u7, c1)
    await db.add_member(u7, c2, "member")
    
    await cooldowns.apply_transfer_sickness(u7)
    await cooldowns.apply_member_join_cooldown(u7, "Transfer")
    
    print("Transfer completed.")
    
    # 5. Check Sickness
    is_cd, until = await cooldowns.check_cooldown("user", u7, cooldowns.KIND_TRANSFER_SICKNESS)
    print(f"Transfer Sickness: {is_cd} (Until: {until})")
    assert is_cd

async def main():
    try:
        c1, c2, u1, u2, u3, u7 = await setup_test_data()
        await test_loan_flow(c1, c2, u3)
        await test_transfer_flow(c1, c2, u7)
        print("\n✅ All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
