"""
Loan Service
Handles the logic for activating and ending loans, including member movement and Discord role updates.
"""

import discord
from services import db, cooldowns
import main as bot_main

async def activate_loan(loan_id: int, guild: discord.Guild):
    """
    Activate a loan: update DB status, move member between clans, and update Discord roles.
    """
    # 1. Get loan details
    loan = await db.get_loan(loan_id)
    if not loan:
        print(f"Loan {loan_id} not found for activation.")
        return
    
    member_id = loan["member_user_id"]
    lending_clan_id = loan["lending_clan_id"]
    borrowing_clan_id = loan["borrowing_clan_id"]
    
    # 2. Update DB status (sets status='active', start_at, end_at)
    await db.activate_loan(loan_id)
    
    # 3. Move member in DB
    # Remove from lending clan and add to borrowing clan
    await db.remove_member(member_id, lending_clan_id)
    await db.add_member(member_id, borrowing_clan_id, "member")
    
    # 4. Update Discord Roles
    try:
        member_user = await db.get_user_by_id(member_id)
        if member_user:
            discord_member = guild.get_member(int(member_user["discord_id"]))
            if discord_member:
                lending_clan = await db.get_clan_by_id(lending_clan_id)
                borrowing_clan = await db.get_clan_by_id(borrowing_clan_id)
                
                # Remove lending clan role
                if lending_clan and lending_clan.get("discord_role_id"):
                    role = guild.get_role(int(lending_clan["discord_role_id"]))
                    if role:
                        await discord_member.remove_roles(role, reason=f"Loan {loan_id} activated")
                
                # Add borrowing clan role
                if borrowing_clan and borrowing_clan.get("discord_role_id"):
                    role = guild.get_role(int(borrowing_clan["discord_role_id"]))
                    if role:
                        await discord_member.add_roles(role, reason=f"Loan {loan_id} activated")
    except Exception as e:
        print(f"Error updating roles for loan activation (Loan {loan_id}): {e}")

async def end_loan(loan_id: int, guild: discord.Guild):
    """
    End a loan: update DB status, move member back, apply cooldowns, and update Discord roles.
    """
    # 1. Get loan details
    loan = await db.get_loan(loan_id)
    if not loan:
        print(f"Loan {loan_id} not found for ending.")
        return
    
    if loan["status"] != "active":
        print(f"Loan {loan_id} is not active (status: {loan['status']}).")
        return
    
    member_id = loan["member_user_id"]
    lending_clan_id = loan["lending_clan_id"]
    borrowing_clan_id = loan["borrowing_clan_id"]
    
    # 2. Update DB status (sets status='ended')
    await db.end_loan(loan_id)
    
    # 3. Move member back in DB
    # Remove from borrowing clan and add back to lending clan
    await db.remove_member(member_id, borrowing_clan_id)
    await db.add_member(member_id, lending_clan_id, "member")
    
    # 4. Apply cooldowns (14 days for lending clan, borrowing clan, and member)
    await cooldowns.apply_loan_cooldowns(lending_clan_id, borrowing_clan_id, member_id)
    
    # 5. Update Discord Roles
    try:
        member_user = await db.get_user_by_id(member_id)
        if member_user:
            discord_member = guild.get_member(int(member_user["discord_id"]))
            if discord_member:
                lending_clan = await db.get_clan_by_id(lending_clan_id)
                borrowing_clan = await db.get_clan_by_id(borrowing_clan_id)
                
                # Remove borrowing clan role
                if borrowing_clan and borrowing_clan.get("discord_role_id"):
                    role = guild.get_role(int(borrowing_clan["discord_role_id"]))
                    if role:
                        await discord_member.remove_roles(role, reason=f"Loan {loan_id} ended")
                
                # Add lending clan role back
                if lending_clan and lending_clan.get("discord_role_id"):
                    role = guild.get_role(int(lending_clan["discord_role_id"]))
                    if role:
                        await discord_member.add_roles(role, reason=f"Loan {loan_id} ended")
    except Exception as e:
        print(f"Error updating roles for loan end (Loan {loan_id}): {e}")
