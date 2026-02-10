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
# CLAN DETAIL SELECT VIEW
# =============================================================================

class ClanDetailSelectView(discord.ui.View):
    """View with dropdown to select a clan and view full member details."""
    
    def __init__(self, clans: List[Dict[str, Any]]):
        super().__init__(timeout=120)  # 2 min timeout
        self.clans = {str(c["id"]): c for c in clans}
        
        # Build select options
        options = [
            discord.SelectOption(
                label=clan["name"][:25],  # Discord limit
                value=str(clan["id"]),
                description=f"Elo: {clan.get('elo', 1000)}",
                emoji="🏰"
            )
            for clan in clans[:25]
        ]
        
        select = discord.ui.Select(
            placeholder="🔍 Chọn clan để xem chi tiết...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.on_select
        self.add_item(select)
    
    async def on_select(self, interaction: discord.Interaction):
        """Handle clan selection."""
        clan_id = int(interaction.data["values"][0])
        clan = await db.get_clan_by_id(clan_id)
        
        if not clan:
            await interaction.response.send_message("❌ Không tìm thấy clan.", ephemeral=True)
            return
        
        # Get full member list
        members = await db.get_clan_members(clan_id)
        
        embed = discord.Embed(
            title=f"🏰 {clan['name']}",
            color=discord.Color.dark_gold()
        )
        embed.add_field(name="📊 Elo", value=f"`{clan.get('elo', 1000)}`", inline=True)
        embed.add_field(name="👥 Thành viên", value=f"`{len(members)}`", inline=True)
        embed.add_field(name="📅 Trạng thái", value=f"`{clan.get('status', 'active')}`", inline=True)
        
        # Full member list with roles
        member_lines = []
        for m in members:
            role_emoji = "👑" if m["role"] == "captain" else ("⚔️" if m["role"] == "vice" else "👤")
            discord_member = interaction.guild.get_member(int(m["discord_id"])) if interaction.guild else None
            display_name = discord_member.display_name if discord_member else m["riot_id"]
            role_text = "Captain" if m["role"] == "captain" else ("Vice Captain" if m["role"] == "vice" else "Member")
            member_lines.append(f"{role_emoji} **{display_name}** — {role_text}")
        
        embed.add_field(
            name="📋 Danh sách thành viên",
            value="\n".join(member_lines) if member_lines else "Không có thành viên",
            inline=False
        )
        
        if clan.get("description"):
            embed.add_field(name="📝 Mô tả", value=clan["description"], inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ClanRenameModal(discord.ui.Modal, title="🏷️ Đổi Tên Clan"):
    """Modal for captains to rename their clan."""
    
    new_name = discord.ui.TextInput(
        label="Tên Clan Mới",
        placeholder="Nhập tên clan mới (3-32 ký tự)...",
        min_length=3,
        max_length=32,
        required=True
    )
    
    def __init__(self, clan: Dict[str, Any]):
        super().__init__()
        self.clan = clan
        self.new_name.default = clan["name"]
        
    async def on_submit(self, interaction: discord.Interaction):
        """Handle new name submission."""
        new_name = self.new_name.value.strip()
        clan_id = self.clan["id"]
        old_name = self.clan["name"]
        
        # 1. Validate name
        import re
        if not re.match(r"^[a-zA-Z0-9\sÀ-ỹ]+$", new_name):
            await interaction.response.send_message(
                "❌ Tên clan chỉ được chứa chữ cái, số và khoảng trắng.", 
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        
        # 2. Update Database
        success = await db.update_clan_name(clan_id, new_name)
        if not success:
            await interaction.followup.send(
                f"❌ Tên clan **{new_name}** đã tồn tại hoặc không hợp lệ.",
                ephemeral=True
            )
            return
            
        # 3. Rename Discord Role
        role_updated = False
        if self.clan.get("discord_role_id"):
            try:
                role = interaction.guild.get_role(int(self.clan["discord_role_id"]))
                if role:
                    await role.edit(name=new_name, reason=f"Clan Rename: {old_name} -> {new_name}")
                    role_updated = True
            except Exception as e:
                print(f"[ARENA] Failed to rename role for clan {clan_id}: {e}")
                
        # 4. Rename Discord Channel
        channel_updated = False
        if self.clan.get("discord_channel_id"):
            try:
                channel = interaction.guild.get_channel(int(self.clan["discord_channel_id"]))
                if channel:
                    new_channel_name = new_name.lower().replace(" ", "-")
                    await channel.edit(name=new_channel_name, reason=f"Clan Rename: {old_name} -> {new_name}")
                    channel_updated = True
            except Exception as e:
                print(f"[ARENA] Failed to rename channel for clan {clan_id}: {e}")
                
        # 5. Log and Notify
        await bot_utils.log_event(
            "CLAN_RENAMED",
            f"Captain {interaction.user.mention} renamed clan: **{old_name}** ➡️ **{new_name}**"
        )
        
        msg = f"✅ Đã đổi tên clan thành **{new_name}** thành công!\n"
        if role_updated: msg += "- Đã đổi tên Role Discord 🎭\n"
        if channel_updated: msg += "- Đã đổi tên Kênh Discord 💬\n"
        
        await interaction.followup.send(msg, ephemeral=True)
        print(f"[ARENA] Clan {old_name} (ID: {clan_id}) renamed to {new_name} by {interaction.user}")


def _extract_user_id(raw: str) -> Optional[int]:
    raw = raw.strip()
    if raw.startswith("<@") and raw.endswith(">"):
        raw = raw[2:-1]
        if raw.startswith("!"):
            raw = raw[1:]
    if raw.isdigit():
        return int(raw)
    return None


async def _build_user_info_embed(member: discord.Member, user: Dict[str, Any]) -> discord.Embed:
    membership = await db.get_user_clan(user["id"])

    embed = discord.Embed(
        title=f"👤 Thông Tin Của {member.display_name}",
        color=discord.Color.purple()
    )

    embed.add_field(name="Discord", value=f"{member.mention}\n`{member.id}`", inline=True)

    if user.get("riot_id"):
        embed.add_field(name="Riot ID", value=f"`{user['riot_id']}`", inline=True)

    if membership:
        embed.add_field(name="Clan", value=f"**{membership['name']}**", inline=True)
        embed.add_field(name="Vai trò", value=membership["member_role"].capitalize(), inline=True)
        embed.add_field(name="Elo Clan", value=f"`{membership.get('elo', 1000)}`", inline=True)
    else:
        embed.add_field(name="Clan", value="🎯 Lính đánh thuê tự do", inline=False)

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

    return embed


class UserInfoModal(discord.ui.Modal, title="🔎 Tra cứu người dùng"):
    """Modal for checking another user's info."""

    user_input = discord.ui.TextInput(
        label="Nhập ID hoặc mention",
        placeholder="Ví dụ: 123456789012345678 hoặc @User",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = _extract_user_id(self.user_input.value)
        if not user_id:
            await interaction.response.send_message(
                "❌ Vui lòng nhập ID hoặc mention hợp lệ.",
                ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Không tìm thấy guild để tra cứu.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(user_id)
        if not member:
            try:
                member = await interaction.guild.fetch_member(user_id)
            except Exception:
                member = None

        if not member:
            await interaction.response.send_message(
                "❌ Không tìm thấy người dùng trong server.",
                ephemeral=True
            )
            return

        user = await db.get_user(str(member.id))
        if not user:
            await interaction.response.send_message(
                "📭 Người dùng chưa có trong hệ thống clan.",
                ephemeral=True
            )
            return

        embed = await _build_user_info_embed(member, user)
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
        """Show all active clans with their members."""
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
            
            for i, clan in enumerate(clans_sorted[:10], 1):  # Limit to 10 clans
                members = await db.get_clan_members(clan["id"])
                member_count = len(members)
                
                # Build compact member list (inline, limited to first 4)
                member_parts = []
                captain = None
                others = []
                
                for m in members:
                    # Try to get Discord member for display name
                    discord_member = interaction.guild.get_member(int(m["discord_id"])) if interaction.guild else None
                    display_name = discord_member.display_name if discord_member else m["riot_id"]
                    
                    if m["role"] == "captain":
                        captain = f"👑 {display_name}"
                    else:
                        others.append(display_name)
                
                # Format: Captain + first 3 others inline
                if captain:
                    member_parts.append(captain)
                
                # Show max 3 other members
                for name in others[:3]:
                    member_parts.append(f"👤 {name}")
                
                # If more than 3 others, show +X
                remaining = len(others) - 3
                if remaining > 0:
                    member_parts.append(f"*...+{remaining} khác*")
                
                members_text = " • ".join(member_parts) if member_parts else "Không có thành viên"
                
                embed.add_field(
                    name=f"{i}. {clan['name']} | Elo: `{clan.get('elo', 1000)}` | 👥 {member_count}",
                    value=members_text,
                    inline=False
                )
            
            if len(clans) > 10:
                embed.set_footer(text=f"...và {len(clans) - 10} clan khác")
            
            # Add dropdown to select clan for detailed view
            view = ClanDetailSelectView(clans_sorted[:25])  # Discord limit 25 options
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            print(f"[ARENA] Sent clan list with members to {interaction.user}")
            
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
            
            embed = await _build_user_info_embed(interaction.user, user)
            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"[ARENA] Sent user info to {interaction.user}")
            
        except Exception as e:
            print(f"[ARENA] ERROR in my_info_button: {e}")
            await interaction.followup.send("❌ Đã xảy ra lỗi khi tải thông tin.", ephemeral=True)

    @discord.ui.button(
        label="Tra cứu người khác",
        style=discord.ButtonStyle.secondary,
        emoji="🔎",
        custom_id="arena:other_info"
    )
    async def other_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal to check another user's info."""
        print(f"[ARENA] User {interaction.user} clicked: Other User Info")
        await interaction.response.send_modal(UserInfoModal())
    
    @discord.ui.button(
        label="Tạo Clan", 
        style=discord.ButtonStyle.danger,
        emoji="➕",
        custom_id="arena:create_clan",
        row=1
    )
    async def create_clan_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the clan creation modal."""
        print(f"[ARENA] User {interaction.user} clicked: Create Clan")
        
        # Check verified role
        user_role_names = [role.name for role in interaction.user.roles]
        if config.ROLE_VERIFIED not in user_role_names:
            await interaction.response.send_message(
                f"❌ Bạn cần role **{config.ROLE_VERIFIED}** để tạo clan.",
                ephemeral=True
            )
            return
        
        # Check if user already in a clan
        user = await db.get_user(str(interaction.user.id))
        if user:
            existing_clan = await db.get_user_clan(user["id"])
            if existing_clan:
                await interaction.response.send_message(
                    f"❌ Bạn đã ở trong clan **{existing_clan['name']}** rồi. Hãy rời clan trước khi tạo clan mới.",
                    ephemeral=True
                )
                return
            
            # Check cooldown
            cooldowns_list = await db.get_all_user_cooldowns(user["id"])
            join_leave_cd = next((cd for cd in cooldowns_list if cd["kind"] == "join_leave"), None)
            if join_leave_cd:
                from datetime import datetime, timezone
                cd_until = datetime.fromisoformat(join_leave_cd["until"].replace("Z", "+00:00"))
                if cd_until > datetime.now(timezone.utc):
                    await interaction.response.send_message(
                        f"❌ Bạn đang trong thời gian chờ đến **{cd_until.strftime('%Y-%m-%d')}** trước khi có thể tạo/tham gia clan.",
                        ephemeral=True
                    )
                    return
        
        # Import and show the ClanCreateModal from clan.py
        from cogs.clan import ClanCreateModal
        await interaction.response.send_modal(ClanCreateModal())
        print(f"[ARENA] Opened ClanCreateModal for {interaction.user}")
    
    @discord.ui.button(
        label="Luật Lệ", 
        style=discord.ButtonStyle.secondary,
        emoji="📜",
        custom_id="arena:rules",
        row=1
    )
    async def rules_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show clan system rules."""
        print(f"[ARENA] User {interaction.user} clicked: Rules")
        
        embed = discord.Embed(
            title="📜 Luật Lệ Hệ Thống Clan",
            description="Tóm tắt các quy định quan trọng của hệ thống Clan VXT",
            color=discord.Color.dark_gold()
        )
        
        # Section 1: Tổng quan
        embed.add_field(
            name="🏰 Tổng Quan",
            value=(
                "• Mỗi người chỉ được **1 tài khoản** Discord\n"
                "• Mỗi người chỉ thuộc **1 clan** tại 1 thời điểm\n"
                "• **Elo** là điểm của **clan**, không có Elo cá nhân\n"
                "• Mọi clan mới phải qua **Mod duyệt**"
            ),
            inline=False
        )
        
        # Section 2: Tạo Clan
        embed.add_field(
            name="🆕 Tạo Clan",
            value=(
                "• Captain phải có role **Thiểu Năng Con**\n"
                "• Cần **5 người** ngay từ đầu (Captain + 4)\n"
                "• 4 người phải **Accept** qua DM trong **48h**\n"
                "• Tên clan **duy nhất**, không được nhái/giả mạo"
            ),
            inline=False
        )
        
        # Section 3: Quyền lợi Clan
        embed.add_field(
            name="🎁 Quyền Lợi Khi Có Clan",
            value=(
                "• **Role riêng** với tên và màu của clan\n"
                "• **Kênh chat riêng** chỉ clan và Mod xem được\n"
                "• Tham gia **thi đấu** và ghi nhận **Elo**\n"
                "• Cạnh tranh **BXH** và nhận **phần thưởng mùa**"
            ),
            inline=False
        )
        
        # Section 4: Cooldown & Rời Clan
        embed.add_field(
            name="⏳ Cooldown",
            value=(
                "• Rời clan/bị kick → chờ **14 ngày** mới vào clan khác\n"
                "• Captain rời clan → phải **chuyển Captain** trước\n"
                "• Clan < 5 người → **tạm khóa** tính năng thi đấu"
            ),
            inline=False
        )
        
        # Section 5: Trận đấu & Elo
        embed.add_field(
            name="⚔️ Trận Đấu & Elo",
            value=(
                "• Clan **thắng**: **+25 Elo** | **thua**: **-15 Elo**\n"
                "• **Elo khởi điểm**: 1000 | **10 trận đầu**: xếp hạng nhanh\n"
                "• Cùng 2 clan: tối đa **2 trận/24h** tính Elo\n"
                "• Tranh chấp → **Mod** quyết định"
            ),
            inline=False
        )
        
        # Section 6: Cho mượn (Loan)
        embed.add_field(
            name="🤝 Cho Mượn Thành Viên",
            value=(
                "• Tối đa **1 người** cho mượn/mỗi clan\n"
                "• Cần **3 bên đồng ý**: 2 Captain + người được mượn\n"
                "• Thời hạn tối đa **7 ngày**\n"
                "• Cooldown **14 ngày** sau khi kết thúc"
            ),
            inline=True
        )
        
        # Section 7: Chuyển nhượng (Transfer)
        embed.add_field(
            name="🔄 Chuyển Nhượng",
            value=(
                "• Cần **3 bên đồng ý** (giống Cho mượn)\n"
                "• Clan nguồn phải còn **≥5 người** sau chuyển\n"
                "• **Transfer Sickness**: cấm thi đấu **3 ngày**\n"
                "• Cooldown **14 ngày** không rời clan mới"
            ),
            inline=True
        )
        
        # Section 8: Vi phạm
        embed.add_field(
            name="🚫 Vi Phạm & Hình Phạt",
            value=(
                "• Dùng nhiều acc/smurf → **ban hệ thống**\n"
                "• Gian lận Elo/dàn xếp → **ban vĩnh viễn**\n"
                "• Tên clan tục tĩu/kỳ thị → **reject**\n"
                "• Mọi quyết định cuối thuộc về **Mod**"
            ),
            inline=False
        )
        
        embed.set_footer(text="💡 Liên hệ Mod nếu có thắc mắc! | VXT Clan System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"[ARENA] Sent rules to {interaction.user}")

    @discord.ui.button(
        label="Đổi Tên Clan", 
        style=discord.ButtonStyle.secondary,
        emoji="🏷️",
        custom_id="arena:rename_clan",
        row=1
    )
    async def rename_clan_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Allow captain to rename their clan."""
        print(f"[ARENA] User {interaction.user} clicked: Rename Clan")
        
        # 1. Get user and clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.response.send_message("❌ Bạn chưa có trong hệ thống.", ephemeral=True)
            return
            
        clan = await db.get_user_clan(user["id"])
        if not clan:
            await interaction.response.send_message("❌ Bạn không ở trong clan nào.", ephemeral=True)
            return
            
        # 2. Check if Captain
        if clan["member_role"] != "captain":
            await interaction.response.send_message("❌ Chỉ **Captain** mới có quyền đổi tên clan.", ephemeral=True)
            return
            
        # 3. Open Modal
        await interaction.response.send_modal(ClanRenameModal(clan))


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
            "👤 **Thông tin của tôi** — Xem thông tin clan của bạn\n\n"
            "🔎 **Tra cứu người khác** — Xem thông tin clan của một người bất kỳ\n\n"
            "➕ **Tạo Clan** — Tạo clan mới và mời đồng đội\n"
            "📜 **Luật Lệ** — Xem quy định hệ thống Clan\n"
            "🏷️ **Đổi Tên Clan** — Captain đổi tên clan mình"
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
    
    @app_commands.command(name="post_latest_update", description="Đăng thông báo cập nhật mới nhất lên #update-bot (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def post_latest_update(self, interaction: discord.Interaction):
        """Parse historyUpdate.md and post the latest Discord Update section."""
        print(f"[ARENA] /post_latest_update called by {interaction.user}")
        await interaction.response.defer(ephemeral=True)
        
        import re
        from pathlib import Path
        
        # Read historyUpdate.md
        history_path = Path(__file__).parent.parent / "historyUpdate.md"
        if not history_path.exists():
            await interaction.followup.send("❌ Không tìm thấy file historyUpdate.md", ephemeral=True)
            return
        
        try:
            content = history_path.read_text(encoding="utf-8")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi đọc file: {e}", ephemeral=True)
            return
        
        # Parse latest version and Discord Update section
        # Pattern: ## [version] - date ... #### 📢 Discord Update ... (until next #### or ---)
        version_pattern = r'## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})'
        discord_pattern = r'#### 📢 Discord Update\s*\n((?:>.*\n?)+)'
        
        version_match = re.search(version_pattern, content)
        if not version_match:
            await interaction.followup.send("❌ Không tìm thấy version trong historyUpdate.md", ephemeral=True)
            return
        
        version = version_match.group(1)
        date = version_match.group(2)
        
        # Find Discord Update section for this version (first occurrence after version header)
        version_start = version_match.start()
        discord_match = re.search(discord_pattern, content[version_start:])
        
        if not discord_match:
            await interaction.followup.send(
                f"❌ Không tìm thấy phần '#### 📢 Discord Update' cho version {version}",
                ephemeral=True
            )
            return
        
        # Extract and clean the Discord Update content
        raw_content = discord_match.group(1)
        # Remove leading > from each line
        lines = [line.lstrip("> ").strip() for line in raw_content.strip().split("\n")]
        discord_content = "\n".join(lines)
        
        # Post to update channel
        update_channel = bot_utils.get_update_channel()
        if not update_channel:
            await interaction.followup.send(
                f"❌ Chưa tìm thấy kênh #update-bot. Hãy đảm bảo kênh tồn tại và restart bot.",
                ephemeral=True
            )
            return
        
        # Create embed
        embed = discord.Embed(
            title="🎉 Cập Nhật Mới!",
            description=discord_content,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Phiên bản {version} • {date}")
        
        try:
            await update_channel.send(embed=embed)
            await interaction.followup.send(
                f"✅ Đã đăng thông báo cập nhật **v{version}** lên #{update_channel.name}!",
                ephemeral=True
            )
            print(f"[ARENA] Posted update v{version} to #{update_channel.name}")
            await bot_utils.log_event("UPDATE_POSTED", f"v{version} posted by {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi đăng: {e}", ephemeral=True)


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    """Load the Arena cog."""
    await bot.add_cog(ArenaCog(bot))
    print("[ARENA] Cog loaded successfully")
