"""
Clan System Discord Bot
Main entry point - startup, cog loading, command sync
"""

import asyncio
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

import config
from services import db, loan_service

# =============================================================================
# BOT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # Required for member select & DMs
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Cache for validated Discord objects
_log_channel: discord.TextChannel | None = None
_clans_category: discord.CategoryChannel | None = None
_verified_role: discord.Role | None = None
_mod_role: discord.Role | None = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_log_channel() -> discord.TextChannel | None:
    """Get the cached mod-log channel."""
    return _log_channel


def get_clans_category() -> discord.CategoryChannel | None:
    """Get the cached CLANS category."""
    return _clans_category


def get_verified_role() -> discord.Role | None:
    """Get the cached Verified role."""
    return _verified_role


def get_mod_role() -> discord.Role | None:
    """Get the cached Mod role."""
    return _mod_role


async def log_event(event_type: str, details: str) -> None:
    """Log an event to the mod-log channel."""
    channel = get_log_channel()
    if channel:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        await channel.send(f"`[{timestamp}]` **[{event_type}]** {details}")


# =============================================================================
# STARTUP VALIDATION
# =============================================================================

@bot.event
async def on_ready():
    """Validate configuration and sync commands on startup."""
    global _log_channel, _clans_category, _verified_role, _mod_role
    
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
    
    _verified_role = discord.utils.get(guild.roles, name=config.ROLE_VERIFIED)
    if not _verified_role:
        print(f"ERROR: Required role '{config.ROLE_VERIFIED}' not found!")
        print("This role must exist on the server. DO NOT CREATE it manually here.")
        await bot.close()
        return
    print(f"✓ Found verified role: {_verified_role.name}")
    
    _mod_role = discord.utils.get(guild.roles, name=config.ROLE_MOD)
    if not _mod_role:
        print(f"ERROR: Required role '{config.ROLE_MOD}' not found!")
        print("This role must exist on the server. DO NOT CREATE it manually here.")
        await bot.close()
        return
    print(f"✓ Found mod role: {_mod_role.name}")
    
    # ==========================================================================
    # VALIDATE/CREATE CHANNELS
    # ==========================================================================
    
    # Log channel
    _log_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_MOD_LOG)
    if not _log_channel:
        print(f"WARNING: Log channel '{config.CHANNEL_MOD_LOG}' not found. Creating...")
        try:
            _log_channel = await guild.create_text_channel(
                config.CHANNEL_MOD_LOG,
                reason="Clan System: Auto-created log channel"
            )
            print(f"✓ Created log channel: #{_log_channel.name}")
        except discord.Forbidden:
            print("ERROR: Missing permission to create channels!")
            await bot.close()
            return
    else:
        print(f"✓ Found log channel: #{_log_channel.name}")
    
    # Clans category
    _clans_category = discord.utils.get(guild.categories, name=config.CATEGORY_CLANS)
    if not _clans_category:
        print(f"WARNING: Category '{config.CATEGORY_CLANS}' not found. Creating...")
        try:
            _clans_category = await guild.create_category(
                config.CATEGORY_CLANS,
                reason="Clan System: Auto-created clans category"
            )
            print(f"✓ Created category: {_clans_category.name}")
        except discord.Forbidden:
            print("ERROR: Missing permission to create categories!")
            await bot.close()
            return
    else:
        print(f"✓ Found category: {_clans_category.name}")
    
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
    
    # Sync commands to the specific guild (instant)
    guild_obj = discord.Object(id=config.GUILD_ID)
    bot.tree.copy_global_to(guild=guild_obj)
    synced = await bot.tree.sync(guild=guild_obj)
    print(f"✓ Synced {len(synced)} commands to guild")
    
    # Start background tasks
    # Start background tasks
    expire_requests_task.start()
    check_loans_task.start()
    check_transfers_task.start()
    print("✓ Started background tasks")
    
    print("-" * 50)
    print("Bot is ready!")
    
    await log_event("BOT_STARTED", f"Clan System bot started. Commands synced: {len(synced)}")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Handle persistent button interactions (for clan accept/decline after bot restart)."""
    if interaction.type != discord.InteractionType.component:
        return
    
    custom_id = interaction.data.get("custom_id", "")
    
    # Handle clan accept buttons
    if custom_id.startswith("clan_accept:"):
        parts = custom_id.split(":")
        if len(parts) == 3:
            clan_id = int(parts[1])
            user_id = int(parts[2])
            await handle_clan_accept(interaction, clan_id, user_id)
            return
    
    # Handle clan decline buttons
    if custom_id.startswith("clan_decline:"):
        parts = custom_id.split(":")
        if len(parts) == 3:
            clan_id = int(parts[1])
            user_id = int(parts[2])
            await handle_clan_decline(interaction, clan_id, user_id)
            return


async def handle_clan_accept(interaction: discord.Interaction, clan_id: int, user_id: int):
    """Handle clan accept button click."""
    # Check if request still exists and is pending
    request = await db.get_user_pending_request(user_id)
    if not request or request["clan_id"] != clan_id:
        await interaction.response.edit_message(
            content="This invitation has expired or been cancelled.",
            view=None
        )
        return
    
    # Get clan name for messages
    clan = await db.get_clan_by_id(clan_id)
    clan_name = clan["name"] if clan else "Unknown"
    
    # Accept the request
    await db.accept_create_request(clan_id, user_id)
    
    # Add user to clan_members
    await db.add_member(user_id, clan_id, "member")
    
    # Check if all 4 accepted
    all_accepted = await db.check_all_accepted(clan_id)
    
    await interaction.response.edit_message(
        content=f"✅ You have **accepted** the invitation to join **{clan_name}**!",
        view=None
    )
    
    if all_accepted:
        # Update clan status to pending_approval
        await db.update_clan_status(clan_id, "pending_approval")
        
        # Notify captain via DM
        try:
            # Get captain's discord_id from clan_members
            members = await db.get_clan_members(clan_id)
            captain_member = next((m for m in members if m["role"] == "captain"), None)
            if captain_member:
                captain_discord_id = captain_member["discord_id"]
                captain_user = interaction.client.get_user(int(captain_discord_id))
                if not captain_user:
                    captain_user = await interaction.client.fetch_user(int(captain_discord_id))
                if captain_user:
                    await captain_user.send(
                        f"🎉 **Great news!**\n\n"
                        f"All 4 invited members have **accepted** your clan **{clan_name}**!\n\n"
                        f"Your clan is now **pending mod approval**. A moderator will review and approve it soon."
                    )
        except Exception as e:
            print(f"Failed to DM captain: {e}")
        
        # Alert mod-log
        await log_event(
            "CLAN_PENDING_APPROVAL",
            f"Clan '{clan_name}' - All 4 invited members accepted. Awaiting mod approval. (ID: {clan_id})"
        )


async def handle_clan_decline(interaction: discord.Interaction, clan_id: int, user_id: int):
    """Handle clan decline button click."""
    # Check if request still exists
    request = await db.get_user_pending_request(user_id)
    if not request or request["clan_id"] != clan_id:
        await interaction.response.edit_message(
            content="This invitation has expired or been cancelled.",
            view=None
        )
        return
    
    # Get clan name for messages
    clan = await db.get_clan_by_id(clan_id)
    clan_name = clan["name"] if clan else "Unknown"
    
    # Decline the request
    await db.decline_create_request(clan_id, user_id)
    
    # Delete the entire clan creation
    async with db.get_connection() as conn:
        await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
        await conn.commit()
    
    await interaction.response.edit_message(
        content=f"❌ You have **declined** the invitation to join **{clan_name}**.\n"
                f"The clan creation has been cancelled.",
        view=None
    )
    
    await log_event(
        "CLAN_CANCELLED",
        f"Clan '{clan_name}' creation cancelled - {interaction.user.mention} declined invitation"
    )




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
            
            # Hard delete the clan and its requests
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
            
            await log_event("CLAN_EXPIRED", f"Clan '{clan_name}' creation expired (48h timeout) and deleted")
        
        await conn.commit()


@tasks.loop(minutes=10)
async def check_loans_task():
    """Check for expired requests and end active loans."""
    async with db.get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        
        # 1. Expire pending requests (48h)
        # We need to calculate expiration based on created_at since we didn't store expires_at explicitly in loans table
        # Wait, schema says created_at. Let's assume 48h from created_at.
        expiry_threshold = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        
        cursor = await conn.execute(
            "SELECT id FROM loans WHERE status = 'requested' AND created_at < ?",
            (expiry_threshold,)
        )
        expired_loans = await cursor.fetchall()
        
        for row in expired_loans:
            loan_id = row[0]
            await conn.execute("UPDATE loans SET status = 'expired', updated_at = ? WHERE id = ?", (now, loan_id))
            await log_event("LOAN_EXPIRED", f"Loan request {loan_id} expired (48h timeout)")
            
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
            await log_event("LOAN_ENDED", f"Loan {loan_id} ended automatically. Cooldowns applied.")
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
            await log_event("TRANSFER_EXPIRED", f"Transfer request {transfer_id} expired (48h timeout)")
            
        await conn.commit()


@expire_requests_task.before_loop
async def before_expire_task():
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
