"""
Arena Dashboard - Interactive Info Panel
Provides a read-only channel with buttons to view clan system info.
Auto-sends dashboard to #arena channel on bot startup.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Dict, Any, Optional

from services import db, bot_utils
import config


# =============================================================================
# ARENA VIEW (Persistent Buttons)
# =============================================================================

class ArenaView(discord.ui.View):
    """Persistent view with buttons to show clan system information."""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent - no timeout
        print("[ARENA] ArenaView initialized")
    
    @discord.ui.button(
        label="Danh sách Clan", 
        style=discord.ButtonStyle.primary, 
        emoji="🏰",
        custom_id="arena:clan_list"
    )
    async def clan_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all active clans."""
        print(f"[ARENA] User {interaction.user} clicked: Clan List")
        await interaction.response.defer(ephemeral=True)
        
        try:
            clans = await db.get_all_active_clans()
            print(f"[ARENA] Found {len(clans)} active clans")
            
            if not clans:
                await interaction.followup.send("📭 Chưa có clan nào hoạt động.", ephemeral=True)
                return
            
            # Build embed
            embed = discord.Embed(
                title="🏰 Danh Sách Clan Hoạt Động",
                color=discord.Color.blue(),
                description=f"Tổng số: **{len(clans)}** clan"
            )
            
            # Sort by Elo descending
            clans_sorted = sorted(clans, key=lambda c: c.get("elo", 1000), reverse=True)
            
            clan_lines = []
            for i, clan in enumerate(clans_sorted[:15], 1):  # Limit to 15
                member_count = await db.count_clan_members(clan["id"])
                clan_lines.append(
                    f"**{i}.** {clan['name']} | Elo: `{clan.get('elo', 1000)}` | 👥 {member_count}"
                )
            
            embed.add_field(
                name="Top 15 Clan theo Elo",
                value="\n".join(clan_lines) if clan_lines else "Không có dữ liệu",
                inline=False
            )
            
            if len(clans) > 15:
                embed.set_footer(text=f"...và {len(clans) - 15} clan khác")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[ARENA] Sent clan list to {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR in clan_list_button: {e}")
            await interaction.followup.send("❌ Đã xảy ra lỗi khi tải danh sách clan.", ephemeral=True)
    
    @discord.ui.button(
        label="Bảng xếp hạng", 
        style=discord.ButtonStyle.success, 
        emoji="🏆",
        custom_id="arena:leaderboard"
    )
    async def leaderboard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show Elo leaderboard."""
        print(f"[ARENA] User {interaction.user} clicked: Leaderboard")
        await interaction.response.defer(ephemeral=True)
        
        try:
            clans = await db.get_all_active_clans()
            print(f"[ARENA] Leaderboard: {len(clans)} clans")
            
            if not clans:
                await interaction.followup.send("📭 Chưa có clan nào để xếp hạng.", ephemeral=True)
                return
            
            # Sort by Elo
            clans_sorted = sorted(clans, key=lambda c: c.get("elo", 1000), reverse=True)
            
            embed = discord.Embed(
                title="🏆 Bảng Xếp Hạng Elo",
                color=discord.Color.gold()
            )
            
            # Top 10 with medals
            medals = ["🥇", "🥈", "🥉"] + [""] * 7
            leaderboard_lines = []
            
            for i, clan in enumerate(clans_sorted[:10], 0):
                medal = medals[i] if i < 3 else f"**{i+1}.**"
                leaderboard_lines.append(
                    f"{medal} **{clan['name']}** — `{clan.get('elo', 1000)}` Elo"
                )
            
            embed.description = "\n".join(leaderboard_lines)
            embed.set_footer(text="Cập nhật theo thời gian thực")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[ARENA] Sent leaderboard to {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR in leaderboard_button: {e}")
            await interaction.followup.send("❌ Đã xảy ra lỗi khi tải bảng xếp hạng.", ephemeral=True)
    
    @discord.ui.button(
        label="Lịch sử Match", 
        style=discord.ButtonStyle.secondary, 
        emoji="⚔️",
        custom_id="arena:match_history"
    )
    async def match_history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show recent matches."""
        print(f"[ARENA] User {interaction.user} clicked: Match History")
        await interaction.response.defer(ephemeral=True)
        
        try:
            matches = await db.get_recent_matches(limit=10)
            print(f"[ARENA] Found {len(matches)} recent matches")
            
            if not matches:
                await interaction.followup.send("📭 Chưa có trận đấu nào được ghi nhận.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="⚔️ Lịch Sử Trận Đấu Gần Đây",
                color=discord.Color.red()
            )
            
            match_lines = []
            for match in matches:
                # Get clan names
                clan_a = await db.get_clan_by_id(match["clan_a_id"])
                clan_b = await db.get_clan_by_id(match["clan_b_id"])
                
                clan_a_name = clan_a["name"] if clan_a else "Unknown"
                clan_b_name = clan_b["name"] if clan_b else "Unknown"
                
                status_emoji = {
                    "confirmed": "✅",
                    "reported": "⏳",
                    "disputed": "⚠️",
                    "resolved": "🔒",
                    "cancelled": "❌",
                    "voided": "🚫"
                }.get(match["status"], "❓")
                
                # Winner info
                winner_text = ""
                if match.get("winner_clan_id"):
                    winner = await db.get_clan_by_id(match["winner_clan_id"])
                    winner_text = f" 🏆 {winner['name']}" if winner else ""
                
                match_lines.append(
                    f"{status_emoji} **{clan_a_name}** vs **{clan_b_name}**{winner_text}"
                )
            
            embed.description = "\n".join(match_lines)
            embed.set_footer(text="10 trận gần nhất")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[ARENA] Sent match history to {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR in match_history_button: {e}")
            await interaction.followup.send("❌ Đã xảy ra lỗi khi tải lịch sử trận đấu.", ephemeral=True)
    
    @discord.ui.button(
        label="Thông tin của tôi", 
        style=discord.ButtonStyle.secondary, 
        emoji="👤",
        custom_id="arena:my_info"
    )
    async def my_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show user's clan info."""
        print(f"[ARENA] User {interaction.user} clicked: My Info")
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get user from database
            user = await db.get_user(str(interaction.user.id))
            
            if not user:
                await interaction.followup.send(
                    "📭 Bạn chưa có trong hệ thống. Hãy tham gia hoặc tạo một clan!",
                    ephemeral=True
                )
                return
            
            # Get user's clan
            membership = await db.get_user_clan(user["id"])
            
            embed = discord.Embed(
                title=f"👤 Thông Tin Của {interaction.user.display_name}",
                color=discord.Color.purple()
            )
            
            embed.add_field(name="Discord ID", value=f"`{interaction.user.id}`", inline=True)
            
            if user.get("riot_id"):
                embed.add_field(name="Riot ID", value=f"`{user['riot_id']}`", inline=True)
            
            if membership:
                # get_user_clan returns clan info directly with member_role field
                embed.add_field(name="Clan", value=f"**{membership['name']}**", inline=True)
                embed.add_field(name="Vai trò", value=membership["member_role"].capitalize(), inline=True)
                embed.add_field(name="Elo Clan", value=f"`{membership.get('elo', 1000)}`", inline=True)
            else:
                embed.add_field(name="Clan", value="Chưa tham gia clan nào", inline=False)
            
            # Cooldown info - always show status
            cooldowns = await db.get_all_user_cooldowns(user["id"])
            if cooldowns:
                cooldown_lines = []
                for cd in cooldowns:
                    kind_display = {
                        "join_leave": "🚪 Tham gia Clan",
                        "loan": "🤝 Cho mượn",
                        "transfer": "🔄 Chuyển nhượng"
                    }.get(cd["kind"], cd["kind"])
                    cooldown_lines.append(f"{kind_display}: đến `{cd['until'][:10]}`")
                embed.add_field(
                    name="⏰ Cooldown",
                    value="\n".join(cooldown_lines),
                    inline=False
                )
            else:
                embed.add_field(name="⏰ Cooldown", value="✅ Không có", inline=False)
            
            # Ban status - always show
            ban_info = await db.is_user_banned(user["id"])
            if ban_info:
                embed.add_field(
                    name="🚫 Ban Status",
                    value=f"❌ Bị ban — Lý do: {ban_info.get('reason', 'N/A')}",
                    inline=False
                )
                embed.color = discord.Color.red()
            else:
                embed.add_field(name="🚫 Ban Status", value="✅ Không bị ban", inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[ARENA] Sent user info to {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR in my_info_button: {e}")
            await interaction.followup.send("❌ Đã xảy ra lỗi khi tải thông tin.", ephemeral=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_arena_embed() -> discord.Embed:
    """Create the main Arena Dashboard embed."""
    embed = discord.Embed(
        title="🏟️ ARENA - Trung Tâm Thông Tin",
        description=(
            "Chào mừng đến với **Arena**!\n\n"
            "Bấm vào các nút bên dưới để xem thông tin về hệ thống Clan:\n\n"
            "🏰 **Danh sách Clan** — Xem tất cả các clan đang hoạt động\n"
            "🏆 **Bảng xếp hạng** — Top clan theo điểm Elo\n"
            "⚔️ **Lịch sử Match** — Các trận đấu gần đây\n"
            "👤 **Thông tin của tôi** — Xem thông tin clan của bạn"
        ),
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="VXT Clan System • Bấm nút để xem thông tin")
    return embed


# =============================================================================
# ARENA COG
# =============================================================================

class ArenaCog(commands.Cog):
    """Cog for Arena Dashboard functionality."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.arena_channel: Optional[discord.TextChannel] = None
        self.arena_message_id: Optional[int] = None
        print("[ARENA] ArenaCog initialized")
    
    async def cog_load(self):
        """Register persistent view when cog loads."""
        self.bot.add_view(ArenaView())
        print("[ARENA] Registered ArenaView as persistent view")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Find #arena channel and send/update dashboard on bot startup."""
        print("[ARENA] on_ready triggered - searching for arena channel...")
        
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            print(f"[ARENA] ERROR: Could not find guild {config.GUILD_ID}")
            return
        
        # Find #arena channel
        arena_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_ARENA)
        
        if not arena_channel:
            print(f"[ARENA] WARNING: Channel '{config.CHANNEL_ARENA}' not found. Skipping auto-setup.")
            return
        
        self.arena_channel = arena_channel
        print(f"[ARENA] Found arena channel: #{arena_channel.name} (ID: {arena_channel.id})")
        
        # Check if there's already a dashboard message from the bot
        existing_message = None
        try:
            async for message in arena_channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    # Check if it's our Arena embed
                    if message.embeds[0].title and "ARENA" in message.embeds[0].title:
                        existing_message = message
                        print(f"[ARENA] Found existing dashboard message: {message.id}")
                        break
        except Exception as e:
            print(f"[ARENA] ERROR reading channel history: {e}")
        
        if existing_message:
            # Update existing message with fresh view (in case bot restarted)
            try:
                await existing_message.edit(embed=create_arena_embed(), view=ArenaView())
                self.arena_message_id = existing_message.id
                print(f"[ARENA] Updated existing dashboard message: {existing_message.id}")
            except Exception as e:
                print(f"[ARENA] ERROR updating message: {e}")
        else:
            # Send new dashboard
            try:
                new_message = await arena_channel.send(embed=create_arena_embed(), view=ArenaView())
                self.arena_message_id = new_message.id
                print(f"[ARENA] Sent new dashboard message: {new_message.id}")
                await bot_utils.log_event("ARENA_AUTO_SETUP", f"Arena Dashboard auto-created in #{arena_channel.name}")
            except Exception as e:
                print(f"[ARENA] ERROR sending dashboard: {e}")
    
    @app_commands.command(name="arena_refresh", description="Làm mới Arena Dashboard (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def arena_refresh(self, interaction: discord.Interaction):
        """Manually refresh the Arena Dashboard."""
        print(f"[ARENA] /arena_refresh called by {interaction.user}")
        
        # Try to find arena channel if not already set
        if not self.arena_channel:
            print("[ARENA] arena_channel not set, searching now...")
            guild = self.bot.get_guild(config.GUILD_ID)
            if guild:
                self.arena_channel = discord.utils.get(guild.text_channels, name=config.CHANNEL_ARENA)
                if self.arena_channel:
                    print(f"[ARENA] Found arena channel: #{self.arena_channel.name}")
        
        if not self.arena_channel:
            await interaction.response.send_message(
                f"❌ Không tìm thấy kênh `#{config.CHANNEL_ARENA}`. Hãy tạo kênh này trước.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Delete old messages from bot in arena channel
        deleted_count = 0
        try:
            async for message in self.arena_channel.history(limit=50):
                if message.author == self.bot.user:
                    await message.delete()
                    deleted_count += 1
        except Exception as e:
            print(f"[ARENA] ERROR deleting old messages: {e}")
        
        print(f"[ARENA] Deleted {deleted_count} old messages")
        
        # Send fresh dashboard
        try:
            new_message = await self.arena_channel.send(embed=create_arena_embed(), view=ArenaView())
            self.arena_message_id = new_message.id
            
            await interaction.followup.send(
                f"✅ Arena Dashboard đã được làm mới trong #{self.arena_channel.name}!",
                ephemeral=True
            )
            print(f"[ARENA] Dashboard refreshed: {new_message.id}")
            await bot_utils.log_event("ARENA_REFRESH", f"Arena Dashboard refreshed by {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR refreshing dashboard: {e}")
            await interaction.followup.send(f"❌ Lỗi: {e}", ephemeral=True)


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    """Load the Arena cog."""
    await bot.add_cog(ArenaCog(bot))
    print("[ARENA] Cog loaded successfully")
