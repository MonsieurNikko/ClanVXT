"""
Loan Service
Handles the logic for activating and ending loans, including member movement and Discord role updates.
"""

import discord
from services import db, cooldowns
from services import bot_utils

async def activate_loan(loan_id: int, guild: discord.Guild) -> bool:
    """
    Activate a loan: update DB status, move member between clans, and update Discord roles.
    Returns True if successful.
    """
    # 1. Get loan details
    loan = await db.get_loan(loan_id)
    if not loan:
        return False
        
    lending_clan_id = loan["lending_clan_id"]
    borrowing_clan_id = loan["borrowing_clan_id"]
    member_id = loan["member_user_id"]

    # 2. Check source clan member count one last time
    import config
    count = await db.count_clan_members(lending_clan_id)
    if count <= config.MIN_MEMBERS_ACTIVE:
        return False

    # 3. Update DB status and check success (atomic)
    if not await db.activate_loan(loan_id):
        return False
    
    # 3. Move member in DB (atomic)
    await db.move_member(member_id, lending_clan_id, borrowing_clan_id, "member")
    
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
    
    # 5. Public Announcement in chat-arena
    chat_channel = bot_utils.get_chat_channel()
    if chat_channel:
        try:
            lending_clan = await db.get_clan_by_id(lending_clan_id)
            borrowing_clan = await db.get_clan_by_id(borrowing_clan_id)
            member_user = await db.get_user_by_id(member_id)
            
            embed = discord.Embed(
                title="🤝 Thông Báo Loan Thành Viên",
                description=f"Một hợp đồng mượn quân đã được ký kết!",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="👤 Thành viên", value=f"<@{member_user['discord_id']}>", inline=False)
            embed.add_field(name="📤 Từ Clan", value=lending_clan['name'], inline=True)
            embed.add_field(name="📥 Đến Clan", value=borrowing_clan['name'], inline=True)
            embed.add_field(name="⏰ Thời hạn", value=f"{loan['duration_days']} ngày", inline=True)
            
            await chat_channel.send(embed=embed)
        except Exception as e:
            print(f"Error posting public loan announcement in chat-arena: {e}")
            
    return True

async def end_all_clan_loans(clan_id: int, guild: discord.Guild):
    """
    Called when a clan is disbanded. Ends all active loans where this clan is involved.
    """
    active_loans = await db.get_all_active_loans_for_clan(clan_id)
    if not active_loans:
        return
        
    for loan in active_loans:
        try:
            loan_id = loan["id"]
            member_id = loan["member_user_id"]
            lending_id = loan["lending_clan_id"]
            borrowing_id = loan["borrowing_clan_id"]
            
            # 1. Update status
            await db.end_loan(loan_id)
            
            # 2. Movement logic
            if clan_id == borrowing_id:
                # Borrowing clan is disbanding, return member to lending clan
                await db.move_member(member_id, borrowing_id, lending_id, "member")
                # Update Roles
                await _update_roles_for_end(guild, member_id, lending_id, borrowing_id, loan_id)
            else:
                # Lending clan is disbanding, member becomes free agent
                await db.remove_member(member_id, borrowing_id)
                # Remove borrowing role
                await _remove_borrowing_role(guild, member_id, borrowing_id, loan_id)
                
            await bot_utils.log_event("LOAN_FORCE_ENDED", f"Loan {loan_id} ended early because clan {clan_id} disbanded.")
            
        except Exception as e:
            print(f"Error ending loan {loan['id']} during disband: {e}")

async def _update_roles_for_end(guild: discord.Guild, member_id: int, lending_id: int, borrowing_id: int, loan_id: int):
    # Abstracted role update logic from end_loan
    try:
        member_user = await db.get_user_by_id(member_id)
        if not member_user: return
        discord_member = guild.get_member(int(member_user["discord_id"]))
        if not discord_member: return
        
        lending_clan = await db.get_clan_by_id(lending_id)
        borrowing_clan = await db.get_clan_by_id(borrowing_id)
        
        if borrowing_clan and borrowing_clan.get("discord_role_id"):
            role = guild.get_role(int(borrowing_clan["discord_role_id"]))
            if role: await discord_member.remove_roles(role, reason=f"Loan {loan_id} ended (disband)")
            
        if lending_clan and lending_clan.get("discord_role_id"):
            role = guild.get_role(int(lending_clan["discord_role_id"]))
            if role: await discord_member.add_roles(role, reason=f"Loan {loan_id} ended (disband)")
    except Exception: pass

async def _remove_borrowing_role(guild: discord.Guild, member_id: int, borrowing_id: int, loan_id: int):
    try:
        member_user = await db.get_user_by_id(member_id)
        if not member_user: return
        discord_member = guild.get_member(int(member_user["discord_id"]))
        if not discord_member: return
        
        borrowing_clan = await db.get_clan_by_id(borrowing_id)
        if borrowing_clan and borrowing_clan.get("discord_role_id"):
            role = guild.get_role(int(borrowing_clan["discord_role_id"]))
            if role: await discord_member.remove_roles(role, reason=f"Loan {loan_id} ended (lender disbanded)")
    except Exception: pass

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
    
    # 3. Move member back in DB (atomic)
    await db.move_member(member_id, borrowing_clan_id, lending_clan_id, "member")
    
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
