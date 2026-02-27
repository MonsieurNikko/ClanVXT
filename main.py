"""
Clan System Discord Bot
Main entry point - startup, cog loading, command sync
"""

import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

import config
from services import db, loan_service, bot_utils

# =============================================================================
# BOT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # Required for member select & DMs
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =============================================================================
# STARTUP VALIDATION
# =============================================================================

@bot.event
async def on_ready():
    """Validate configuration and sync commands on startup."""
    # Note: We use bot_utils instead of globals now
    
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("-" * 50)
    
    # Get the target guild
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        print(f"ERROR: Could not find guild with ID {config.GUILD_ID}")
        print("Make sure GUILD_ID is correct and bot is in the server.")
        await bot.close()
        return
    
    print(f"Target guild: {guild.name}")
    
    # ==========================================================================
    # VALIDATE ROLES (Must exist, DO NOT CREATE)
    # ==========================================================================
    
    verified_role = discord.utils.get(guild.roles, name=config.ROLE_VERIFIED)
    if not verified_role:
        print(f"ERROR: Required role '{config.ROLE_VERIFIED}' not found!")
        print("This role must exist on the server. DO NOT CREATE it manually here.")
        await bot.close()
        return
    bot_utils.set_verified_role(verified_role)
    print(f"✓ Found verified role: {verified_role.name}")
    
    mod_role = discord.utils.get(guild.roles, name=config.ROLE_MOD)
    if not mod_role:
        print(f"ERROR: Required role '{config.ROLE_MOD}' not found!")
        print("This role must exist on the server. DO NOT CREATE it manually here.")
        await bot.close()
        return
    bot_utils.set_mod_role(mod_role)
    print(f"✓ Found mod role: {mod_role.name}")
    
    player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
    if not player_role:
        print(f"ERROR: Required role '{config.ROLE_PLAYER}' not found!")
        print("This role must exist on the server. DO NOT CREATE it manually here.")
        await bot.close()
        return
    bot_utils.set_player_role(player_role)
    print(f"✓ Found player role: {player_role.name}")
    
    # ==========================================================================
    # VALIDATE/CREATE CHANNELS
    # ==========================================================================
    
    # Log channel
    log_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_MOD_LOG)
    if not log_channel:
        print(f"WARNING: Log channel '{config.CHANNEL_MOD_LOG}' not found. Creating...")
        try:
            log_channel = await guild.create_text_channel(
                config.CHANNEL_MOD_LOG,
                reason="Clan System: Auto-created log channel"
            )
            print(f"✓ Created log channel: #{log_channel.name}")
        except discord.Forbidden:
            print("ERROR: Missing permission to create channels!")
            await bot.close()
            return
    else:
        print(f"✓ Found log channel: #{log_channel.name}")
    bot_utils.set_log_channel(log_channel)
    
    # Clans category
    clans_category = discord.utils.get(guild.categories, name=config.CATEGORY_CLANS)
    if not clans_category:
        print(f"WARNING: Category '{config.CATEGORY_CLANS}' not found. Creating...")
        try:
            clans_category = await guild.create_category(
                config.CATEGORY_CLANS,
                reason="Clan System: Auto-created clans category"
            )
            print(f"✓ Created category: {clans_category.name}")
        except discord.Forbidden:
            print("ERROR: Missing permission to create categories!")
            await bot.close()
            return
    else:
        print(f"✓ Found category: {clans_category.name}")
    bot_utils.set_clans_category(clans_category)
    
    # Update-bot channel (optional, don't create if not found)
    update_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_UPDATE_BOT)
    if update_channel:
        bot_utils.set_update_channel(update_channel)
        print(f"✓ Found update channel: #{update_channel.name}")
    else:
        print(f"⚠ Update channel '{config.CHANNEL_UPDATE_BOT}' not found. Updates will not be posted.")

    # Chat channel (optional)
    chat_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_CHAT_ARENA)
    if chat_channel:
        bot_utils.set_chat_channel(chat_channel)
        print(f"✓ Found chat arena channel: #{chat_channel.name}")
    else:
        print(f"⚠ Chat channel '{config.CHANNEL_CHAT_ARENA}' not found. Loan announcements will not be posted.")

    
    # ==========================================================================
    # LOAD COGS & SYNC COMMANDS
    # ==========================================================================
    
    # Initialize database
    await db.init_db()
    print("✓ Database initialized")
    
    # Load cogs
    await bot.load_extension("cogs.clan")
    print("✓ Loaded cog: cogs.clan")
    
    await bot.load_extension("cogs.matches")
    print("✓ Loaded cog: cogs.matches")
    
    await bot.load_extension("cogs.loans")
    print("✓ Loaded cog: cogs.loans")
    
    await bot.load_extension("cogs.transfers")
    print("✓ Loaded cog: cogs.transfers")
    
    await bot.load_extension("cogs.admin")
    print("✓ Loaded cog: cogs.admin")
    
    await bot.load_extension("cogs.moderation")
    print("✓ Loaded cog: cogs.moderation")
    
    await bot.load_extension("cogs.arena")
    print("✓ Loaded cog: cogs.arena")
    
    await bot.load_extension("cogs.highlights")  # New Feature
    print("✓ Loaded cog: cogs.highlights")
    
    await bot.load_extension("cogs.challenge")
    print("✓ Loaded cog: cogs.challenge")
    
    # Sync commands to the specific guild (instant)
    guild_obj = discord.Object(id=config.GUILD_ID)
    bot.tree.copy_global_to(guild=guild_obj)
    synced = await bot.tree.sync(guild=guild_obj)
    print(f"✓ Synced {len(synced)} commands to guild")
    
    # Start background tasks
    expire_requests_task.start()
    check_loans_task.start()
    check_transfers_task.start()
    check_cooldowns_task.start()
    weekly_balance_task.start()
    print("✓ Started background tasks")
    
    print("-" * 50)
    print("Bot is ready!")
    
    await bot_utils.log_event("BOT_STARTED", f"Clan System bot started. Commands synced: {len(synced)}")


@bot.event
async def on_member_remove(member):
    """Event triggered when a member leaves the Discord server."""
    print(f"User {member} (ID: {member.id}) left the server. Starting cleanup...")
    try:
        results = await db.cleanup_user_on_leave(str(member.id))
        if results.get("success"):
            actions_str = ", ".join(results["actions"])
            log_msg = f"User cleanup for {member} ({member.id}): {actions_str}"
            print(f"✓ {log_msg}")
            await bot_utils.log_event("USER_LEAVE_CLEANUP", log_msg)
        else:
            reason = results.get("reason", "unknown")
            if reason != "user_not_found":
                print(f"⚠ Cleanup failed for {member}: {reason}")
    except Exception as e:
        print(f"❌ Error during cleanup for {member}: {e}")


# =============================================================================
# BACKGROUND TASKS
# =============================================================================

@tasks.loop(minutes=10)
async def expire_requests_task():
    """Check for expired create requests and cancel them."""
    async with db.get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        
        # Find expired pending requests
        cursor = await conn.execute(
            """SELECT DISTINCT cr.clan_id, c.name 
               FROM create_requests cr
               JOIN clans c ON cr.clan_id = c.id
               WHERE cr.status = 'pending' 
               AND cr.expires_at < ?
               AND c.status = 'waiting_accept'""",
            (now,)
        )
        expired_clans = await cursor.fetchall()
        
        for row in expired_clans:
            clan_id = row[0]
            clan_name = row[1]
            
            # Safe hard delete the clan and all its relates
            await db.hard_delete_clan(clan_id)
            
            await bot_utils.log_event("CLAN_EXPIRED", f"Clan '{clan_name}' creation expired (48h timeout) and deleted")
        
        # No need for conn.commit() here as hard_delete_clan handles it


@tasks.loop(minutes=10)
async def check_loans_task():
    """Check for expired requests and end active loans."""
    async with db.get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        
        # 1. Expire pending requests (48h)
        expiry_threshold = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        
        cursor = await conn.execute(
            "SELECT id FROM loans WHERE status = 'requested' AND created_at < ?",
            (expiry_threshold,)
        )
        expired_loans = await cursor.fetchall()
        
        for row in expired_loans:
            loan_id = row[0]
            await conn.execute("UPDATE loans SET status = 'expired', updated_at = ? WHERE id = ?", (now, loan_id))
            await bot_utils.log_event("LOAN_EXPIRED", f"Loan request {loan_id} expired (48h timeout)")
            
        # 2. End active loans
        cursor = await conn.execute(
            "SELECT id FROM loans WHERE status = 'active' AND end_at < ?",
            (now,)
        )
        ending_loans = await cursor.fetchall()
        
        await conn.commit()
        
    # Process ending loans outside the transaction to use helper
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for row in ending_loans:
        loan_id = row[0]
        try:
            await loan_service.end_loan(loan_id, guild)
            await bot_utils.log_event("LOAN_ENDED", f"Loan {loan_id} ended automatically. Cooldowns applied.")
        except Exception as e:
            print(f"Error ending loan {loan_id}: {e}")


@tasks.loop(minutes=10)
async def check_transfers_task():
    """Check for expired transfer requests."""
    async with db.get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        expiry_threshold = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        
        cursor = await conn.execute(
            "SELECT id FROM transfers WHERE status = 'requested' AND created_at < ?",
            (expiry_threshold,)
        )
        expired_transfers = await cursor.fetchall()
        
        for row in expired_transfers:
            transfer_id = row[0]
            await conn.execute("UPDATE transfers SET status = 'expired', updated_at = ? WHERE id = ?", (now, transfer_id))
            await bot_utils.log_event("TRANSFER_EXPIRED", f"Transfer request {transfer_id} expired (48h timeout)")
            
        await conn.commit()


@tasks.loop(minutes=10)
async def check_cooldowns_task():
    """Check for expired cooldowns and notify users."""
    expired = await db.pop_expired_cooldowns()
    expired_users = await db.pop_expired_user_cooldowns()

    kind_labels = {
        "join_leave": "Tham gia Clan",
        "loan": "Cho mượn",
        "transfer_sickness": "Transfer Sickness",
        "transfer": "Chuyển nhượng",
        "match_create": "Tạo trận đấu"
    }

    notified = set()

    for cd in expired:
        if cd.get("target_type") != "user":
            continue
        db_user = await db.get_user_by_id(cd["target_id"])
        if not db_user:
            continue
        discord_id = int(db_user["discord_id"])
        key = (discord_id, cd.get("kind"))
        if key in notified:
            continue
        notified.add(key)

        label = kind_labels.get(cd.get("kind"), cd.get("kind", "Cooldown"))
        user_obj = bot.get_user(discord_id)
        if not user_obj:
            try:
                user_obj = await bot.fetch_user(discord_id)
            except Exception:
                user_obj = None
        if user_obj:
            try:
                await user_obj.send(f"✅ Cooldown **{label}** của bạn đã hết. Bạn có thể tiếp tục tham gia hoạt động clan.")
            except Exception:
                pass

    for row in expired_users:
        discord_id = int(row["discord_id"])
        key = (discord_id, "join_leave")
        if key in notified:
            continue
        notified.add(key)

        user_obj = bot.get_user(discord_id)
        if not user_obj:
            try:
                user_obj = await bot.fetch_user(discord_id)
            except Exception:
                user_obj = None
        if user_obj:
            try:
                await user_obj.send("✅ Cooldown **Tham gia Clan** của bạn đã hết. Bạn có thể gia nhập clan mới.")
            except Exception:
                pass


@tasks.loop(hours=24)
async def weekly_balance_task():
    """Balance System Weekly Task: Elo decay + activity bonus (runs daily, checks weekly gate)."""
    try:
        last_run = await db.get_system_setting("last_weekly_run")
        now = datetime.now(timezone.utc)
        
        if last_run:
            last_run_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
            if (now - last_run_dt).days < 7:
                return  # Not yet a week
        
        print("[BALANCE] Running weekly balance task...")
        
        # Feature 2: Elo Decay
        if await db.is_balance_feature_enabled("elo_decay"):
            decayed_clans = await db.get_clans_for_decay()
            for clan in decayed_clans:
                old_elo = clan["elo"]
                await db.apply_elo_decay(clan["id"], config.ELO_DECAY_AMOUNT)
                new_elo = max(config.ELO_FLOOR, old_elo - config.ELO_DECAY_AMOUNT)
                print(f"[BALANCE] Elo decay: {clan['name']} {old_elo} → {new_elo}")
            
            if decayed_clans:
                await bot_utils.log_event(
                    "BALANCE_ELO_DECAY",
                    f"Weekly Elo decay applied to {len(decayed_clans)} clans (-{config.ELO_DECAY_AMOUNT} each)"
                )
        
        # Feature 4: Activity Bonus
        if await db.is_balance_feature_enabled("activity_bonus"):
            all_clans = await db.get_all_active_clans()
            bonus_count = 0
            for clan in all_clans:
                # Optional: Check if clan is below the Elo threshold to receive bonus
                if clan["elo"] < config.ACTIVITY_BONUS_ELO_THRESHOLD:
                    activity = await db.get_clan_activity_count(clan["id"])
                    if activity >= config.ACTIVITY_BONUS_MIN_MATCHES:
                        bonus = config.ACTIVITY_BONUS_AMOUNT
                        async with db.get_connection() as conn:
                            await conn.execute(
                                "UPDATE clans SET elo = elo + ?, updated_at = datetime('now') WHERE id = ?",
                                (bonus, clan["id"])
                            )
                            await conn.execute(
                                """INSERT INTO elo_history (clan_id, old_elo, new_elo, change_amount, reason)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (clan["id"], clan["elo"], clan["elo"] + bonus, bonus, "activity_bonus")
                            )
                            await conn.commit()
                        bonus_count += 1
            
            if bonus_count > 0:
                await bot_utils.log_event(
                    "BALANCE_ACTIVITY_BONUS",
                    f"Weekly activity bonus (+{config.ACTIVITY_BONUS_AMOUNT}) applied to {bonus_count} clans"
                )
        
        # Update last run timestamp
        await db.set_system_setting("last_weekly_run", now.isoformat())
        print("[BALANCE] Weekly balance task completed.")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[BALANCE] Error in weekly task: {e}")


@expire_requests_task.before_loop
async def before_expire_task():
    """Wait until bot is ready before starting task."""
    await bot.wait_until_ready()

@check_loans_task.before_loop
async def before_check_loans():
    """Wait until bot is ready before starting task."""
    await bot.wait_until_ready()

@check_transfers_task.before_loop
async def before_check_transfers():
    """Wait until bot is ready before starting task."""
    await bot.wait_until_ready()


@check_cooldowns_task.before_loop
async def before_check_cooldowns():
    """Wait until bot is ready before starting task."""
    await bot.wait_until_ready()

@weekly_balance_task.before_loop
async def before_weekly_balance():
    """Wait until bot is ready before starting task."""
    await bot.wait_until_ready()



# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Clan System Bot - Starting...")
    print("=" * 50)
    bot.run(config.BOT_TOKEN)
