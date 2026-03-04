"""
Arena Dashboard - Interactive Info Panel
Provides a read-only channel with buttons to view clan system info.
Auto-sends dashboard to #arena channel on bot startup.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from services import db, bot_utils, cooldowns, permissions
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
        active_players = [m for m in members if (m.get("valorant_rank_score") or 0) > 0]
        
        embed = discord.Embed(
            title=f"🏰 {clan['name']}",
            color=discord.Color.dark_gold()
        )
        embed.add_field(name="📊 Elo", value=f"`{clan.get('elo', 1000)}`", inline=True)
        embed.add_field(name="👥 Thành viên", value=f"`{len(active_players)} Tuyển thủ / {len(members)} Tổng`", inline=True)
        embed.add_field(name="📅 Trạng thái", value=f"`{clan.get('status', 'active')}`", inline=True)
        
        # Full member list with roles & rank
        member_lines = []
        for m in members:
            role_emoji = "👑" if m["role"] == "captain" else ("⚔️" if m["role"] == "vice" else "👤")
            discord_member = interaction.guild.get_member(int(m["discord_id"])) if interaction.guild else None
            display_name = discord_member.display_name if discord_member else m["riot_id"]
            role_text = "Captain" if m["role"] == "captain" else ("Vice Captain" if m["role"] == "vice" else "Member")
            rank_display = m.get("valorant_rank") or "❓ Chưa khai"
            member_lines.append(f"{role_emoji} **{display_name}** — {role_text} | 🎖️ {rank_display}")
        
        embed.add_field(
            name="📋 Danh sách thành viên",
            value="\n".join(member_lines) if member_lines else "Không có thành viên",
            inline=False
        )
        
        if clan.get("description"):
            embed.add_field(name="📝 Mô tả", value=clan["description"], inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# =============================================================================
# CHALLENGE SELECT VIEW (Format Selection + Opponent)
# =============================================================================

class ChallengeSelectView(discord.ui.View):
    """Dropdown to select an opponent clan and match format."""
    
    def __init__(self, user_clan: dict, opponent_clans: list, user: discord.User, channel_id: int):
        super().__init__(timeout=60)
        self.user_clan = user_clan
        self.opponent_clans = opponent_clans
        self.user = user
        self.channel_id = channel_id
        self.selected_clan_id = None
        self.selected_format = "BO1"  # Default

        # 1. Opponent Select
        options = []
        for clan in opponent_clans:
            label = f"{clan['name']} ({clan['elo']} Elo)"
            if len(label) > 100:
                label = label[:97] + "..."
            options.append(discord.SelectOption(label=label, value=str(clan["id"])))
        
        if len(options) > 25:
            options = options[:25]
            
        select = discord.ui.Select(
            placeholder="Chọn đối thủ...",
            min_values=1, max_values=1,
            options=options, row=0
        )
        select.callback = self.select_callback
        self.add_item(select)

        # 2. Format Select
        format_select = discord.ui.Select(
            placeholder="Chọn thể thức BO1/BO3/BO5...",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Best of 1 (BO1)", value="BO1", description="Ban maps until 1 remains", default=True),
                discord.SelectOption(label="Best of 3 (BO3)", value="BO3", description="Ban 2, Pick 2, Decider"),
                discord.SelectOption(label="Best of 5 (BO5)", value="BO5", description="Ban 2, Pick 4, Decider"),
            ],
            row=1
        )
        format_select.callback = self.format_callback
        self.add_item(format_select)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_clan_id = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def format_callback(self, interaction: discord.Interaction):
        self.selected_format = interaction.data["values"][0]
        await interaction.response.defer()

    @discord.ui.button(label="Gửi Thách Đấu", style=discord.ButtonStyle.green, row=2)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Check Global Lock
        is_locked, reason = await db.is_matchmaking_locked()
        if is_locked:
            return await interaction.response.send_message(
                f"🚫 **Hệ thống thi đấu đang tạm khóa.**\nLý do: {reason}",
                ephemeral=True
            )

        if not self.selected_clan_id:
            return await interaction.response.send_message("❌ Vui lòng chọn clan đối thủ.", ephemeral=True)
            
        target_clan = next((c for c in self.opponent_clans if c["id"] == self.selected_clan_id), None)
        if not target_clan:
            return await interaction.response.send_message("❌ Clan không hợp lệ.", ephemeral=True)

        # Check: only 1 active match per clan
        if await db.has_active_match(self.user_clan["id"]):
            return await interaction.response.send_message(
                "❌ Clan của bạn hiện đang có một trận đấu chưa hoàn thành. Vui lòng hoàn thành trận đấu hiện tại trước khi gửi thách đấu mới.",
                ephemeral=True
            )
        if await db.has_active_match(target_clan["id"]):
            return await interaction.response.send_message(
                f"❌ **{target_clan['name']}** hiện đang có một trận đấu chưa hoàn thành. Không thể gửi thách đấu.",
                ephemeral=True
            )
        
        # --- Balance System: Rank Enforcement (Feature 6) ---
        if await db.is_balance_feature_enabled("rank_enforcement"):
            undeclared_a = await db.get_undeclared_members(self.user_clan["id"])
            if undeclared_a:
                names = ", ".join(f"<@{m['discord_id']}>" for m in undeclared_a[:5])
                return await interaction.response.send_message(
                    f"❌ Clan của bạn có **{len(undeclared_a)}** thành viên chưa khai rank: {names}\n"
                    f"Dùng `/clan update_rank` để gửi yêu cầu khai rank.",
                    ephemeral=True
                )
            undeclared_b = await db.get_undeclared_members(target_clan["id"])
            if undeclared_b:
                return await interaction.response.send_message(
                    f"❌ Clan **{target_clan['name']}** có **{len(undeclared_b)}** thành viên chưa khai rank. Không thể thách đấu.",
                    ephemeral=True
                )
             
        # Create challenge embed
        embed = discord.Embed(
            title=f"⚔️ LỜI THÁCH ĐẤU: {self.selected_format}",
            description=(
                f"**{self.user_clan['name']}** muốn thách đấu **{target_clan['name']}**!\n\n"
                f"Thể thức: **{self.selected_format}**\n"
                f"Người gửi: {interaction.user.mention} (Captain)\n\n"
                f"⚠️ Lưu ý: Sau khi chấp nhận, hai bên sẽ tiến hành **Ban/Pick Map** ngay lập tức."
            ),
            color=discord.Color.red()
        )
        
        # Send to target clan's channel
        if target_clan.get("discord_channel_id"):
            try:
                target_channel = interaction.guild.get_channel(int(target_clan["discord_channel_id"]))
                if target_channel:
                    view = ChallengeAcceptView(
                        challenger_clan=self.user_clan,
                        opponent_clan=target_clan,
                        creator_id=str(interaction.user.id),
                        arena_channel_id=interaction.channel_id,
                    )
                    await target_channel.send(
                        content=f"🔔 Có lời thách đấu từ **{self.user_clan['name']}**!",
                        embed=embed, view=view
                    )
                    await interaction.response.send_message(
                        f"✅ Đã gửi lời thách đấu **{self.selected_format}** đến {target_clan['name']}.",
                        ephemeral=True
                    )
                    print(f"[ARENA] Challenge sent: {self.user_clan['name']} -> {target_clan['name']} ({self.selected_format})")
                else:
                    await interaction.response.send_message("❌ Không tìm thấy kênh riêng của clan đối thủ.", ephemeral=True)
            except Exception as e:
                print(f"[ARENA] Error sending challenge: {e}")
                await interaction.response.send_message(f"❌ Lỗi gửi thách đấu: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Clan đối thủ chưa thiết lập kênh riêng.", ephemeral=True)




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


class UserInfoSelectView(discord.ui.View):
    """View with user picker to select a member and view info."""

    def __init__(self):
        super().__init__(timeout=120)
        self.select = discord.ui.UserSelect(
            placeholder="Chọn hoặc gõ tên để xem thông tin...",
            min_values=1,
            max_values=1
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        member = self.select.values[0]

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
# CHALLENGE SELECT VIEW
# =============================================================================

class ChallengeAcceptView(discord.ui.View):
    """Persistent view sent to opponent clan channel: Accept or Decline a challenge."""

    def __init__(self, challenger_clan: Dict[str, Any], opponent_clan: Dict[str, Any],
                 creator_id: str, arena_channel_id: int):
        super().__init__(timeout=None)  # Persistent across restarts
        self.challenger_clan = challenger_clan
        self.opponent_clan = opponent_clan
        self.creator_id = creator_id
        self.arena_channel_id = arena_channel_id

        chal_id = challenger_clan["id"]
        opp_id = opponent_clan["id"]

        accept_btn = discord.ui.Button(
            label="✅ Chấp nhận",
            style=discord.ButtonStyle.success,
            custom_id=f"challenge_accept:{chal_id}:{opp_id}:{creator_id}:{arena_channel_id}",
        )
        accept_btn.callback = self._callback_noop
        self.add_item(accept_btn)

        decline_btn = discord.ui.Button(
            label="❌ Từ chối",
            style=discord.ButtonStyle.danger,
            custom_id=f"challenge_decline:{chal_id}:{opp_id}:{creator_id}",
        )
        decline_btn.callback = self._callback_noop
        self.add_item(decline_btn)

    async def _callback_noop(self, interaction: discord.Interaction):
        pass # Managed by on_interaction handler to prevent double-acknowledgment

    async def _accept(self, interaction: discord.Interaction):
        # Must be member of opponent clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.response.send_message("❌ Bạn chưa có trong hệ thống.", ephemeral=True)
            return
        membership = await db.get_user_clan(user["id"])
        if not membership or membership["id"] != self.opponent_clan["id"]:
            await interaction.response.send_message("❌ Chỉ thành viên clan được thách mới có thể chấp nhận.", ephemeral=True)
            return

        await interaction.response.defer()

        # Re-fetch clans to ensure still active
        challenger = await db.get_clan_by_id(self.challenger_clan["id"])
        opponent = await db.get_clan_by_id(self.opponent_clan["id"])
        if not challenger or challenger["status"] != "active":
            await interaction.followup.send("❌ Clan thách đấu không còn active.")
            return
        if not opponent or opponent["status"] != "active":
            await interaction.followup.send("❌ Clan của bạn không còn active.")
            return

        # --- Balance System: Rank Enforcement (Feature 6) ---
        if await db.is_balance_feature_enabled("rank_enforcement"):
            undeclared_chal = await db.get_undeclared_members(challenger["id"])
            if undeclared_chal:
                names = ", ".join(f"<@{m['discord_id']}>" for m in undeclared_chal[:5])
                await interaction.followup.send(
                    f"❌ Clan **{challenger['name']}** có **{len(undeclared_chal)}** thành viên chưa khai rank: {names}"
                )
                return
            undeclared_opp = await db.get_undeclared_members(opponent["id"])
            if undeclared_opp:
                names = ", ".join(f"<@{m['discord_id']}>" for m in undeclared_opp[:5])
                await interaction.followup.send(
                    f"❌ Clan của bạn có **{len(undeclared_opp)}** thành viên chưa khai rank: {names}\n"
                    f"Dùng `/clan update_rank` để gửi yêu cầu khai rank."
                )
                return

        # === CHALLENGE UPGRADE: redirect to ban/pick flow ===
        from cogs.challenge import start_challenge_flow
        await start_challenge_flow(
            interaction=interaction,
            challenger=challenger,
            opponent=opponent,
            creator_id=self.creator_id,
            arena_channel_id=self.arena_channel_id,
        )

    async def _decline(self, interaction: discord.Interaction):
        # Must be member of opponent clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.response.send_message("❌ Bạn chưa có trong hệ thống.", ephemeral=True)
            return
        membership = await db.get_user_clan(user["id"])
        if not membership or membership["id"] != self.opponent_clan["id"]:
            await interaction.response.send_message("❌ Chỉ thành viên clan được thách mới có thể từ chối.", ephemeral=True)
            return

        declined_embed = discord.Embed(
            title="⚔️ Thách Đấu Đã Bị Từ Chối",
            description=(
                f"**{self.challenger_clan['name']}** vs **{self.opponent_clan['name']}**\n\n"
                f"❌ Từ chối bởi {interaction.user.mention}"
            ),
            color=discord.Color.dark_grey(),
        )
        await interaction.response.edit_message(embed=declined_embed, view=None)

        # Notify challenger clan channel
        challenger = await db.get_clan_by_id(self.challenger_clan["id"])
        if challenger and challenger.get("discord_channel_id"):
            try:
                chal_channel = interaction.client.get_channel(int(challenger["discord_channel_id"]))
                if chal_channel:
                    await chal_channel.send(
                        f"❌ Clan **{self.opponent_clan['name']}** đã **từ chối** lời thách đấu."
                    )
            except Exception as e:
                print(f"[ARENA] Error notifying challenger clan: {e}")

        await bot_utils.log_event(
            "CHALLENGE_DECLINED",
            f"{self.opponent_clan['name']} từ chối thách đấu từ {self.challenger_clan['name']} "
            f"(bởi {interaction.user.mention})",
        )




# =============================================================================
# LFG / FREE AGENT VIEWS & MODALS
# =============================================================================

class LFGContactView(discord.ui.View):
    """View with buttons on the LFG announcement message."""
    
    def __init__(self, post_id: int):
        super().__init__(timeout=None)  # Persistent
        self.post_id = post_id
    
    @discord.ui.button(
        label="Liên hệ (Captain/Vice)",
        style=discord.ButtonStyle.primary,
        emoji="✉️",
        custom_id="lfg:contact_captain" # Note: format might need to include post_id if not using persistent base
    )
    async def contact_captain(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Allow Captain/Vice to contact the Free Agent."""
        # This will be handled in on_interaction for persistence if we don't pass post_id in custom_id
        pass

    @discord.ui.button(
        label="Lập team (Free Agent)",
        style=discord.ButtonStyle.secondary,
        emoji="🤝",
        custom_id="lfg:connect_solo"
    )
    async def connect_solo(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Allow other free agents to connect."""
        pass


class LFGModal(discord.ui.Modal, title="🤝 Đăng Ký Tìm Clan (Free Agent)"):
    """Modal to collect Free Agent information."""
    
    riot_id = discord.ui.TextInput(
        label="Riot ID",
        placeholder="Name#TAG (Ví dụ: TenCuaBan#VXT)...",
        min_length=3,
        max_length=32,
        required=True
    )
    
    rank = discord.ui.TextInput(
        label="Rank Valorant",
        placeholder="Ví dụ: Ascendant 3, Immortal 1...",
        min_length=1,
        max_length=20,
        required=True
    )
    
    role = discord.ui.TextInput(
        label="Role chính",
        placeholder="Ví dụ: Duelist, Sentinel, Flex...",
        min_length=1,
        max_length=20,
        required=True
    )
    
    tracker_link = discord.ui.TextInput(
        label="Link Tracker (Tùy chọn)",
        placeholder="Link tracker.gg của bạn (nếu có)...",
        required=False
    )
    
    note = discord.ui.TextInput(
        label="Ghi chú thêm",
        style=discord.TextStyle.paragraph,
        placeholder="Mô tả bản thân hoặc mong muốn tìm clan...",
        max_length=200,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user_db = await db.get_user(str(interaction.user.id))
        if not user_db:
            # Create user if not exists
            await db.create_user(str(interaction.user.id), interaction.user.name)
            user_db = await db.get_user(str(interaction.user.id))

        # Save to DB
        post_id = await db.create_lfg_post(
            user_id=user_db["id"],
            riot_id=self.riot_id.value,
            rank=self.rank.value,
            role=self.role.value,
            tracker_link=self.tracker_link.value or "",
            note=self.note.value or ""
        )

        # Post to chat-arena
        channel_name = config.CHANNEL_CHAT_ARENA
        channel = discord.utils.get(interaction.guild.channels, name=channel_name)
        
        if not channel:
            await interaction.followup.send(f"❌ Không tìm thấy kênh `#{channel_name}` để đăng tin.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔍 Free Agent Đang Tìm Clan!",
            description=f"{interaction.user.mention} đang tìm kiếm một bến đỗ mới.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🆔 Riot ID", value=f"`{self.riot_id.value}`", inline=True)
        embed.add_field(name="🏆 Rank", value=f"`{self.rank.value}`", inline=True)
        embed.add_field(name="⚔️ Role", value=f"`{self.role.value}`", inline=True)
        
        if self.tracker_link.value:
            embed.add_field(name="📊 Tracker", value=f"[Xem Profile]({self.tracker_link.value})", inline=True)
        
        if self.note.value:
            embed.add_field(name="📝 Ghi chú", value=self.note.value, inline=False)
            
        embed.set_footer(text=f"Post ID: {post_id} • Bấm nút bên dưới để liên hệ!")

        # Dynamic View with Post ID in custom_ids for persistence tracking
        view = discord.ui.View(timeout=None)
        
        btn_contact = discord.ui.Button(
            label="Liên hệ (Captain/Vice)", 
            style=discord.ButtonStyle.primary, 
            emoji="✉️",
            custom_id=f"lfg:contact:{post_id}"
        )
        btn_solo = discord.ui.Button(
            label="Lập team (Solo)", 
            style=discord.ButtonStyle.secondary, 
            emoji="🤝",
            custom_id=f"lfg:solo:{post_id}"
        )
        
        view.add_item(btn_contact)
        view.add_item(btn_solo)

        await channel.send(embed=embed, view=view)
        
        await interaction.followup.send("✅ Đã đăng tin tìm clan tại kênh chat arena!", ephemeral=True)
        
        # Enhanced Logging
        log_msg = f"👤 **{interaction.user.name}** ({interaction.user.mention}) đã đăng tin tìm clan:\n• **Riot ID**: `{self.riot_id.value}`\n• **Rank**: `{self.rank.value}`\n• **Role**: `{self.role.value}`"
        await bot_utils.log_event("LFG_POST_CREATED", log_msg)
        print(f"[ARENA] LFG Post created by {interaction.user.name} (Riot: {self.riot_id.value}, Rank: {self.rank.value})")


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
                # Balance System: show avg rank
                avg_rank = await db.get_clan_avg_rank(clan["id"])
                from services.elo import RANK_SCORE_TO_NAME
                rank_label = RANK_SCORE_TO_NAME.get(round(avg_rank), "N/A") if avg_rank > 0 else "N/A"
                leaderboard_lines.append(
                    f"{medal} **{clan['name']}** — `{clan.get('elo', 1000)}` Elo | 🎯 {rank_label}"
                )
            
            embed.description = "\n".join(leaderboard_lines)
            embed.set_footer(text="🎯 = Avg Rank của clan | Cập nhật theo thời gian thực")
            
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
            # Get 10 most recent matches (excluding cancelled by default in db.py)
            matches = await db.get_recent_matches(limit=10, include_cancelled=False)
            print(f"[ARENA] Found {len(matches)} recent matches")
            
            if not matches:
                await interaction.followup.send("📭 Chưa có trận đấu nào được ghi nhận.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="⚔️ Lịch Sử Trận Đấu Gần Đây",
                color=discord.Color.red(),
                description="*Ghi chú: 10 trận đấu chính thức mới nhất.*"
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
                    "dispute": "⚠️",
                    "resolved": "⚖️",
                    "voided": "🚫",
                    "created": "🆕"
                }.get(match["status"], "❓")
                
                # Date & Time (formatted)
                # SQLite datetime strings usually look like '2026-02-12 10:39:15' or ISO '2026-02-12T10:39:15'
                raw_date = match.get("created_at", "")
                if raw_date:
                    try:
                        # Simple cleanup for display
                        display_date = raw_date.replace("T", " ")[:16] # YYYY-MM-DD HH:MM
                    except:
                        display_date = raw_date[:10]
                else:
                    display_date = "N/A"
                
                # Build line based on match state
                winner_id = match.get("winner_clan_id") or match.get("reported_winner_clan_id") or match.get("resolved_winner_clan_id")
                
                if winner_id and match["status"] in ("confirmed", "resolved", "reported"):
                    winner_name = clan_a_name if winner_id == match["clan_a_id"] else clan_b_name
                    loser_name = clan_b_name if winner_id == match["clan_a_id"] else clan_a_name
                    
                    # Score info
                    score_text = ""
                    if match.get("score_a") is not None and match.get("score_b") is not None:
                        score_text = f" `{match['score_a']}-{match['score_b']}`"
                    
                    # Elo change info
                    elo_text = ""
                    if match.get("elo_applied"):
                        delta_a = match.get("final_delta_a", 0)
                        delta_b = match.get("final_delta_b", 0)
                        w_delta = abs(delta_a if winner_id == match["clan_a_id"] else delta_b)
                        l_delta = abs(delta_b if winner_id == match["clan_a_id"] else delta_a)
                        elo_text = f" (`+{w_delta}` / `-{l_delta}`)"
                    
                    prefix = "✅ " if match["status"] == "confirmed" else status_emoji
                    line = f"{prefix}**{winner_name}** thắng **{loser_name}**{score_text}{elo_text}"
                    if match["status"] == "reported":
                        line += " — *đang chờ xác nhận*"
                elif match["status"] == "voided":
                    line = f"{status_emoji} ~~{clan_a_name} vs {clan_b_name}~~ — *Trận đấu vô hiệu*"
                else:
                    status_text = {
                        "created": "đang chờ kết quả",
                        "reported": "chờ xác nhận",
                        "dispute": "tranh chấp — chờ Mod",
                    }.get(match["status"], match["status"])
                    line = f"{status_emoji} **{clan_a_name}** vs **{clan_b_name}** — *{status_text}*"

                
                line += f"\n└ 🕒 `{display_date}`"
                match_lines.append(line)
            
            embed.description = "\n\n".join(match_lines)
            embed.set_footer(text="10 trận gần nhất • Elo: (thắng/thua)")
            
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
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Không tìm thấy guild để tra cứu.",
                ephemeral=True
            )
            return

        view = UserInfoSelectView()
        await interaction.response.send_message(
            "🔎 Chọn hoặc gõ tên để xem thông tin người dùng:",
            view=view,
            ephemeral=True
        )
    
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
        label="Tìm Clan",
        style=discord.ButtonStyle.success,
        emoji="🤝",
        custom_id="arena:find_clan",
        row=1
    )
    async def find_clan_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open LFG modal for solo players."""
        print(f"[ARENA] User {interaction.user} clicked: Find Clan")
        
        # Check if user already in a clan
        user_clan = await permissions.get_user_clan_by_discord_id(str(interaction.user.id))
        if user_clan:
            print(f"[ARENA] REJECTED: User {interaction.user.name} already in clan {user_clan['name']}")
            await interaction.response.send_message(
                f"❌ Bạn đã ở trong clan **{user_clan['name']}** rồi. Hãy rời clan trước khi tìm clan mới.",
                ephemeral=True
            )
            return

        # Show modal
        await interaction.response.send_modal(LFGModal())
    
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
        
        # New Section: Try-Out
        embed.add_field(
            name="🛡️ Chế độ Thử Việc (Try-Out)",
            value=(
                "• Dành cho thành viên mới (Recruit) thời hạn **24h**\n"
                "• Được tham gia thi đấu ngay lập tức\n"
                "• Nếu bị kick/tự rời trong 24h: **KHÔNG BỊ COOLDOWN**\n"
                "• Sau 24h không được Promote → **Tự động Kick**"
            ),
            inline=False
        )
        
        # Section 4: Cooldown & Rời Clan
        embed.add_field(
            name="⏳ Cooldown",
            value=(
                "• Rời clan/bị kick → chờ **03 ngày** mới vào clan khác\n"
                "• Captain rời clan → phải **chuyển Captain** trước\n"
                "• Clan < 5 người → **tạm khóa** tính năng thi đấu"
            ),
            inline=False
        )
        
        # Section 5: Trận đấu & Elo
        embed.add_field(
            name="⚔️ Trận Đấu & Elo",
            value=(
                "• Elo **thay đổi** dựa trên chênh lệch sức mạnh (K=32)\n"
                "• **10 trận đầu** = placement: Elo thay đổi nhanh hơn (K=40)\n"
                "• **Ban/Pick Map**: BO1/BO3 theo chuẩn giải đấu\n"
                "• **Giới hạn**: Mỗi clan chỉ được 1 trận chưa hoàn thành (Active)"
            ),
            inline=False
        )
        
        # Section 6: Cho mượn (Loan)
        embed.add_field(
            name="🤝 Cho Mượn Thành Viên",
            value=(
                "• Tối đa **2 người** cho mượn/mỗi clan\n"
                "• Cần **3 bên đồng ý**: 2 Captain + người được mượn\n"
                "• Thời hạn tối đa **7 ngày**\n"
                "• Cooldown **03 ngày** sau khi kết thúc"
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
                "• Cooldown **03 ngày** không rời clan mới"
            ),
            inline=True
        )
        
        # Section 8: Quy định thi đấu online
        embed.add_field(
            name="🎮 Quy Định Khi Thi Đấu Clan (Online)",
            value=(
                "• Tất cả trận đấu clan bắt buộc phải thi đấu trong voice channel của server chính\n"
                "• Thành viên tham gia trận phải có mặt đầy đủ trong voice để Mod có thể kiểm soát\n"
                "• Không được tự ý sang server riêng để thi đấu\n"
                "• Không được thay người ngoài danh sách đăng ký mà không báo trước\n"
                "• Mỗi team chỉ được tối đa **1 người nước ngoài (tây)** trong đội hình\n"
                "• Không được lách luật bằng cách thay người giữa trận\n"
                "• Vi phạm giới hạn đội hình/thay người trái phép sẽ bị xử lý nghiêm"
            ),
            inline=False
        )

        # Section: Balance System
        embed.add_field(
            name="⚖️ Hệ Thống Cân Bằng (Balance)",
            value=(
                "• **Khai báo Rank**: Mọi thành viên phải khai Rank Valorant khi vào clan\n"
                "• **Bắt buộc khai báo**: Clan muốn thi đấu → tất cả phải đã khai Rank\n"
                "• **Giới hạn tuyển quân**: Tối đa tuyển quân mỗi tuần (chống lách luật)\n"
                "• **Giới hạn Rank cao**: Tối đa thành viên Immortal 2+ trong mỗi clan\n"
                "• **Elo Decay**: Clan trên ngưỡng không thi đấu lâu sẽ bị giảm Elo\n"
                "• **Thưởng hoạt động**: Clan thi đấu đều đặn nhận bonus Elo\n"
                "• **Underdog Bonus**: Clan yếu hơn thắng sẽ được thưởng thêm\n"
                "• **Chống farm**: Win rate quá cao sẽ bị giảm Elo nhận được"
            ),
            inline=False
        )

        # Section 9: Khung xử phạt
        embed.add_field(
            name="🚨 Khung Xử Phạt Vi Phạm",
            value=(
                "**Lần 1:** Reset Elo clan về mức thấp nhất: **100 Elo**\n"
                "**Lần 2:** Xóa clan khỏi hệ thống. Thành viên không được tạo/tham gia clan khác\n"
                "**Lần 3:** **Ban** khỏi server"
            ),
            inline=False
        )

        # Section 10: Vi phạm khác
        embed.add_field(
            name="🚫 Các Vi Phạm Khác",
            value=(
                "• Dùng nhiều acc/smurf → **ban hệ thống**\n"
                "• Gian lận Elo/dàn xếp → **ban vĩnh viễn**\n"
                "• Tên clan tục tĩu/kỳ thị → **reject**\n"
                "• Mọi quyết định cuối thuộc về **Mod**"
            ),
            inline=False
        )

        # Section 11: Mục đích
        embed.add_field(
            name="📌 Mục Đích",
            value="Đảm bảo minh bạch, công bằng và hạn chế rủi ro thay người không hợp lệ. Mod có quyền xác minh và đưa ra quyết định cuối cùng.",
            inline=False
        )
        
        embed.set_footer(text="💡 Liên hệ Mod nếu có thắc mắc! | VXT Clan System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"[ARENA] Sent rules to {interaction.user}")

    @discord.ui.button(
        label="Donate", 
        style=discord.ButtonStyle.secondary,
        emoji="☕",
        custom_id="arena:donate",
        row=1
    )
    async def donate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show donation info."""
        print(f"[ARENA] User {interaction.user} clicked: Donate")
        
        embed = discord.Embed(
            title="☕ Ủng Hộ Đội Ngũ Phát Triển",
            description=config.DONATE_DESCRIPTION,
            color=discord.Color.gold()
        )
        
        if config.DONATE_IMAGE_URL:
            embed.set_image(url=config.DONATE_IMAGE_URL)
        
        embed.set_footer(text="Cảm ơn tấm lòng của bạn! ❤️ - Server không thu phí, tiền donate là tự nguyện.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @discord.ui.button(
        label="Thách Đấu",
        style=discord.ButtonStyle.danger,
        emoji="⚔️",
        custom_id="arena:challenge",
        row=2,
    )
    async def challenge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open clan challenge flow: pick opponent clan → create match."""
        print(f"[ARENA] User {interaction.user} clicked: Challenge")

        # 1. Must have Verified role
        user_role_names = [role.name for role in interaction.user.roles]
        if config.ROLE_VERIFIED not in user_role_names:
            await interaction.response.send_message(
                f"❌ Bạn cần role **{config.ROLE_VERIFIED}** để thách đấu.",
                ephemeral=True,
            )
            return

        # 2. Must be in a clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.response.send_message(
                "❌ Bạn chưa có trong hệ thống. Hãy tham gia clan trước!",
                ephemeral=True,
            )
            return

        user_clan = await db.get_user_clan(user["id"])
        if not user_clan:
            await interaction.response.send_message(
                "❌ Bạn không thuộc clan nào. Hãy tham gia clan trước!",
                ephemeral=True,
            )
            return

        # 3. Clan must be active
        if user_clan.get("status") != "active":
            await interaction.response.send_message(
                f"❌ Clan của bạn đang ở trạng thái **{user_clan.get('status')}**, không thể thách đấu.",
                ephemeral=True,
            )
            return

        # 4. Quick cooldown check (display early instead of after select)
        is_cd, cd_until = await cooldowns.check_cooldown("clan", user_clan["id"], "match_create")
        if is_cd:
            try:
                # Standardize format (FUSED & ROBUST)
                until_str = cd_until.replace('Z', '+00:00')
                if ' ' in until_str and 'T' not in until_str:
                    until_str = until_str.replace(' ', 'T')
                
                until_dt = datetime.fromisoformat(until_str)
                if until_dt.tzinfo is None:
                    until_dt = until_dt.replace(tzinfo=timezone.utc)
                
                now_dt = datetime.now(timezone.utc)
                diff = until_dt - now_dt
                secs = max(0, int(diff.total_seconds()))
                
                if secs == 0:
                    time_str = "vài giây"
                else:
                    mins, s = divmod(secs, 60)
                    time_str = f"{mins} phút {s} giây" if mins else f"{s} giây"
            except Exception as e:
                print(f"[DEBUG] Arena cooldown parse error: {e}")
                time_str = "một lát"
            await interaction.response.send_message(
                f"⏳ Clan của bạn vừa tạo match. Vui lòng chờ **{time_str}**.",
                ephemeral=True,
            )
            return

        # 5. Get opponent clan list
        all_clans = await db.get_all_active_clans()
        opponents = [c for c in all_clans if c["id"] != user_clan["id"]]

        if not opponents:
            await interaction.response.send_message(
                "📭 Không có clan nào khác để thách đấu.",
                ephemeral=True,
            )
            return

        # 6. Show dropdown
        view = ChallengeSelectView(user_clan, all_clans, interaction.user, interaction.channel_id)
        await interaction.response.send_message(
            f"⚔️ **{user_clan['name']}** — Chọn clan đối thủ:",
            view=view,
            ephemeral=True,
        )
        print(f"[ARENA] Opened challenge select for {interaction.user}")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_arena_embed() -> discord.Embed:
    """Create the main Arena Dashboard embed."""
    embed = discord.Embed(
        title="🏟️ ARENA - Trung Tâm Thông Tin",
        description=(
            "Chào mừng đến với Arena!\n\n"
            "Bấm vào các nút bên dưới để xem thông tin về hệ thống Clan:\n\n"
            "🏰 Danh sách Clan — Xem tất cả các clan đang hoạt động\n"
            "🏆 Bảng xếp hạng — Top clan theo điểm Elo\n"
            "⚔️ Lịch sử Match — Các trận đấu gần đây\n"
            "👤 Thông tin của tôi — Xem thông tin clan của bạn\n"
            "🔎 Tra cứu người khác — Chọn hoặc gõ tên để xem thông tin\n\n"
            "➕ Tạo Clan — Tạo clan mới và mời đồng đội\n"
            "🤝 Tìm Clan — Tìm clan hoặc tuyển thêm thành viên\n"
            "📜 Luật Lệ — Xem quy định hệ thống Clan\n"
            "🏷️ Đổi Tên Clan — Captain đổi tên clan mình\n\n"
            "⚔️ Thách Đấu — Chọn clan đối thủ và tạo match ngay!"
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
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle persistent challenge accept/decline buttons after bot restart."""
        if interaction.type != discord.InteractionType.component:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not (custom_id.startswith("challenge_") or custom_id.startswith("lfg:")):
            return
        if interaction.response.is_done():
            return

        # challenge_accept:{chal_id}:{opp_id}:{creator_id}:{arena_channel_id}
        if custom_id.startswith("challenge_accept:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                chal_id, opp_id, creator_id, arena_ch_id = int(parts[1]), int(parts[2]), parts[3], int(parts[4])
                challenger = await db.get_clan_by_id(chal_id)
                opponent = await db.get_clan_by_id(opp_id)
                if challenger and opponent:
                    view = ChallengeAcceptView(challenger, opponent, creator_id, arena_ch_id)
                    await view._accept(interaction)
                    return

        # challenge_decline:{chal_id}:{opp_id}:{creator_id}
        if custom_id.startswith("challenge_decline:"):
            parts = custom_id.split(":")
            if len(parts) == 4:
                chal_id, opp_id, creator_id = int(parts[1]), int(parts[2]), parts[3]
                challenger = await db.get_clan_by_id(chal_id)
                opponent = await db.get_clan_by_id(opp_id)
                if challenger and opponent:
                    view = ChallengeAcceptView(challenger, opponent, creator_id, 0)
                    await view._decline(interaction)
                    return

        # ---------------------------------------------------------------------
        # LFG / FIND CLAN HANDLING
        # ---------------------------------------------------------------------
        if custom_id.startswith("lfg:"):
            # Format: lfg:contact:POST_ID or lfg:solo:POST_ID
            parts = custom_id.split(":")
            if len(parts) < 3: return
            
            action = parts[1]
            try:
                post_id = int(parts[2])
            except ValueError:
                return
            
            # Get post data
            post = await db.get_lfg_post_by_id(post_id)
            if not post or post["status"] != "active":
                await interaction.on_error(ValueError("Post not found or inactive")) # trigger error if needed
                await interaction.response.send_message("❌ Tin này không còn tồn tại hoặc đã bị đóng.", ephemeral=True)
                return
            
            # Get Free Agent user
            fa_user = await db.get_user_by_id(post["user_id"])
            if not fa_user:
                await interaction.response.send_message("❌ Không tìm thấy thông tin người đăng tin.", ephemeral=True)
                return

            # FA's discord ID
            fa_discord_id = int(fa_user["discord_id"])
            if fa_discord_id == interaction.user.id:
                await interaction.response.send_message("❌ Bạn không thể tự liên hệ với chính mình!", ephemeral=True)
                return

            
            if action == "contact":
                # Check clicker is Captain/Vice of a clan
                clicker_clan = await permissions.get_user_clan_by_discord_id(str(interaction.user.id))
                if not clicker_clan or clicker_clan["member_role"] not in ["captain", "vice"]:
                    await interaction.response.send_message("❌ Chỉ Captain hoặc Vice Captain của một clan mới có thể bấm nút này.", ephemeral=True)
                    return
                
                # Send DM to Free Agent
                try:
                    fa_discord_user = await interaction.client.fetch_user(fa_discord_id)
                    dm_embed = discord.Embed(
                        title="🏰 Clan Đang Quan Tâm Đến Bạn!",
                        description=(
                            f"Clan **{clicker_clan['name']}** muốn liên hệ với bạn về tin tìm clan.\n\n"
                            f"👤 Người liên hệ: {interaction.user.mention} ({clicker_clan['member_role'].capitalize()})\n"
                            f"💬 Vui lòng check tin nhắn chờ hoặc chủ động nhắn tin cho họ!"
                        ),
                        color=discord.Color.green()
                    )
                    await fa_discord_user.send(embed=dm_embed)
                    
                    # Send DM to Captain with FA info
                    captain_embed = discord.Embed(
                        title="✅ Đã gửi thông báo liên hệ",
                        description=f"Hệ thống đã gửi thông báo đến **{fa_discord_user.name}**. Bạn có thể nhắn tin cho họ ngay bây giờ.",
                        color=discord.Color.blue()
                    )
                    captain_embed.add_field(name="👤 User", value=f"{fa_discord_user.mention}", inline=True)
                    captain_embed.add_field(name="🆔 Riot ID", value=f"`{post['riot_id']}`", inline=True)
                    await interaction.user.send(embed=captain_embed)
                    
                    await interaction.response.send_message("✅ Đã gửi thông báo cho cả hai bên qua DM!", ephemeral=True)
                    
                    # Enhanced Logging
                    log_msg = f"🏰 Clan **{clicker_clan['name']}** ({interaction.user.mention}) đã liên hệ với Free Agent **{fa_discord_user.name}** ({fa_discord_user.mention})"
                    await bot_utils.log_event("LFG_CONTACTED", log_msg)
                    print(f"[ARENA] LFG Contact: {interaction.user.name} (Clan: {clicker_clan['name']}) contacted {fa_discord_user.name}")
                except Exception as e:
                    await interaction.response.send_message(f"❌ Không thể gửi DM: {e}", ephemeral=True)

            elif action == "solo":
                # Check clicker is NOT in a clan
                clicker_clan = await permissions.get_user_clan_by_discord_id(str(interaction.user.id))
                if clicker_clan:
                    await interaction.response.send_message("❌ Bạn đã có clan rồi. Chỉ những Free Agent khác mới có thể kết nối lập team.", ephemeral=True)
                    return
                
                if str(interaction.user.id) == fa_user["discord_id"]:
                    await interaction.response.send_message("❌ Bạn không thể tự lập team với chính mình.", ephemeral=True)
                    return

                # Connect two solo players
                try:
                    fa_discord_user = await interaction.client.fetch_user(fa_discord_id)
                    
                    # Inform both
                    msg = (
                        f"🤝 **Kết nối thành công!**\n"
                        f"Hai bạn đều đang tìm clan và có thể muốn lập team cùng nhau:\n"
                        f"• {interaction.user.mention} (Riot: `{interaction.user.name}`)\n"
                        f"• {fa_discord_user.mention} (Riot: `{post['riot_id']}`)\n\n"
                        f"Hãy nhắn tin cho nhau để bắt đầu hành trình mới!"
                    )
                    
                    await fa_discord_user.send(msg)
                    await interaction.user.send(msg)
                    
                    await interaction.response.send_message("✅ Tuyệt vời! Đã gửi thông báo kết nối cho cả hai qua DM.", ephemeral=True)
                    
                    # Enhanced Logging
                    log_msg = f"🤝 **{interaction.user.name}** ({interaction.user.mention}) đã kết nối với **{fa_discord_user.name}** ({fa_discord_user.mention}) để lập team solo."
                    await bot_utils.log_event("LFG_SOLO_CONNECT", log_msg)
                    print(f"[ARENA] LFG Solo Connect: {interaction.user.name} and {fa_discord_user.name} connected")
                except Exception as e:
                    await interaction.response.send_message(f"❌ Không thể gửi DM: {e}", ephemeral=True)
    
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
