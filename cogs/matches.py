"""
Match Commands Cog
Implements match creation, reporting, confirmation, and dispute workflow
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from typing import Optional

import config
from services import db
from services import permissions
from services import elo
from services import elo
from services import bot_utils


# =============================================================================
# ERROR MESSAGES
# =============================================================================

ERRORS = {
    "NOT_IN_CLAN": "Bạn không thuộc clan nào. Hãy gia nhập clan trước.",
    "CLAN_NOT_FOUND": "Không tìm thấy clan.",
    "SAME_CLAN": "Không thể tạo match với chính clan của bạn!",
    "NOT_MATCH_CREATOR": "Chỉ người tạo match mới có thể thực hiện hành động này.",
    "NOT_OPPONENT_CLAN": "Bạn không còn thuộc clan này.",
    "MATCH_NOT_FOUND": "Không tìm thấy match.",
    "MATCH_ALREADY_PROCESSED": "Match đã được xử lý.",
    "CANNOT_CANCEL": "Không thể hủy match sau khi đã báo cáo kết quả.",
    "NOT_MOD": "Bạn cần role '{role}' để sử dụng lệnh này.",
    "MATCH_NOT_DISPUTED": "Match không ở trạng thái tranh chấp.",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_match_embed(match: dict, status_text: str, color: discord.Color) -> discord.Embed:
    """Create a standard match embed."""
    embed = discord.Embed(
        title=f"⚔️ Match #{match['id']}",
        description=f"**{match['clan_a_name']}** vs **{match['clan_b_name']}**",
        color=color
    )
    embed.add_field(name="Trạng thái", value=status_text, inline=True)
    embed.add_field(
        name="Elo", 
        value=f"{match['clan_a_name']}: {match['clan_a_elo']} | {match['clan_b_name']}: {match['clan_b_elo']}", 
        inline=False
    )
    if match.get("note"):
        embed.add_field(name="Ghi chú", value=match["note"], inline=False)
    embed.set_footer(text=f"Tạo lúc: {match['created_at'][:19]}")
    return embed


async def check_mod(interaction: discord.Interaction) -> bool:
    """Check if user has mod role."""
    user_role_names = [role.name for role in interaction.user.roles]
    if config.ROLE_MOD in user_role_names:
        return True
    await interaction.response.send_message(
        ERRORS["NOT_MOD"].format(role=config.ROLE_MOD),
        ephemeral=True
    )
    return False


# =============================================================================
# UI COMPONENTS: Match Creation View
# =============================================================================

class MatchCreatedView(discord.ui.View):
    """View shown after match is created: Report A Win, Report B Win, Cancel."""
    
    def __init__(self, match_id: int, creator_id: str, clan_a_id: int, clan_b_id: int, 
                 clan_a_name: str, clan_b_name: str):
        super().__init__(timeout=None)  # Persistent view
        self.match_id = match_id
        self.creator_id = creator_id
        self.clan_a_id = clan_a_id
        self.clan_b_id = clan_b_id
        self.clan_a_name = clan_a_name
        self.clan_b_name = clan_b_name
        
        # Create buttons with custom IDs for persistence
        self.add_item(ReportWinButton(match_id, clan_a_id, clan_a_name, creator_id, style=discord.ButtonStyle.primary))
        self.add_item(ReportWinButton(match_id, clan_b_id, clan_b_name, creator_id, style=discord.ButtonStyle.primary))
        self.add_item(CancelMatchButton(match_id, creator_id))


class ReportWinButton(discord.ui.Button):
    """Button to report a clan as winner."""
    
    def __init__(self, match_id: int, winner_clan_id: int, clan_name: str, creator_id: str, 
                 style: discord.ButtonStyle):
        # Include creator_id in custom_id for persistence after restart
        super().__init__(
            label=f"{clan_name} Thắng",
            style=style,
            custom_id=f"match_report:{match_id}:{winner_clan_id}:{creator_id}"
        )
        self.match_id = match_id
        self.winner_clan_id = winner_clan_id
        self.clan_name = clan_name
        self.creator_id = creator_id
    
    async def callback(self, interaction: discord.Interaction):
        # Only match creator can report
        if str(interaction.user.id) != self.creator_id:
            await interaction.response.send_message(ERRORS["NOT_MATCH_CREATOR"], ephemeral=True)
            return
        
        # Try to report (atomic check for status = 'created')
        success = await db.report_match_v2(self.match_id, self.winner_clan_id)
        
        if not success:
            await interaction.response.send_message(ERRORS["MATCH_ALREADY_PROCESSED"], ephemeral=True)
            return
        
        # Get updated match data
        match = await db.get_match_with_clans(self.match_id)
        
        # Determine opponent clan for Confirm/Dispute
        if self.winner_clan_id == match["clan_a_id"]:
            opponent_clan_id = match["clan_b_id"]
            opponent_name = match["clan_b_name"]
            winner_name = match["clan_a_name"]
        else:
            opponent_clan_id = match["clan_a_id"]
            opponent_name = match["clan_a_name"]
            winner_name = match["clan_b_name"]
        
        # Update embed
        embed = create_match_embed(
            match,
            f"📝 Đã báo cáo: **{winner_name}** thắng\nChờ {opponent_name} xác nhận...",
            discord.Color.yellow()
        )
        
        # New view with Confirm/Dispute buttons
        view = MatchReportedView(self.match_id, opponent_clan_id, self.winner_clan_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        await bot_utils.log_event(
            "MATCH_REPORTED",
            f"Match #{self.match_id}: {interaction.user.mention} báo cáo {winner_name} thắng"
        )


class CancelMatchButton(discord.ui.Button):
    """Button to cancel a match (creator only, before reporting)."""
    
    def __init__(self, match_id: int, creator_id: str):
        # Include creator_id in custom_id for persistence after restart
        super().__init__(
            label="Hủy Match",
            style=discord.ButtonStyle.danger,
            custom_id=f"match_cancel:{match_id}:{creator_id}"
        )
        self.match_id = match_id
        self.creator_id = creator_id
    
    async def callback(self, interaction: discord.Interaction):
        # Only match creator can cancel
        if str(interaction.user.id) != self.creator_id:
            await interaction.response.send_message(ERRORS["NOT_MATCH_CREATOR"], ephemeral=True)
            return
        
        # Try to cancel (atomic check for status = 'created')
        success = await db.cancel_match(self.match_id)
        
        if not success:
            await interaction.response.send_message(ERRORS["CANNOT_CANCEL"], ephemeral=True)
            return
        
        # Update message
        embed = discord.Embed(
            title=f"⚔️ Match #{self.match_id}",
            description="❌ **Match đã bị hủy**",
            color=discord.Color.dark_grey()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        await bot_utils.log_event(
            "MATCH_CANCELLED",
            f"Match #{self.match_id} bị hủy bởi {interaction.user.mention}"
        )


# =============================================================================
# UI COMPONENTS: Match Reported View
# =============================================================================

class MatchReportedView(discord.ui.View):
    """View shown after result is reported: Confirm, Dispute."""
    
    def __init__(self, match_id: int, opponent_clan_id: int, reported_winner_id: int):
        super().__init__(timeout=None)
        self.match_id = match_id
        self.opponent_clan_id = opponent_clan_id
        self.reported_winner_id = reported_winner_id
        
        self.add_item(ConfirmButton(match_id, opponent_clan_id, reported_winner_id))
        self.add_item(DisputeButton(match_id, opponent_clan_id))


class ConfirmButton(discord.ui.Button):
    """Button to confirm match result."""
    
    def __init__(self, match_id: int, opponent_clan_id: int, winner_clan_id: int):
        # Include opponent_clan_id and winner_clan_id for persistence after restart
        super().__init__(
            label="✅ Xác nhận",
            style=discord.ButtonStyle.success,
            custom_id=f"match_confirm:{match_id}:{opponent_clan_id}:{winner_clan_id}"
        )
        self.match_id = match_id
        self.opponent_clan_id = opponent_clan_id
        self.winner_clan_id = winner_clan_id
    
    async def callback(self, interaction: discord.Interaction):
        # Check user is still in opponent clan
        is_member = await permissions.is_user_in_clan(str(interaction.user.id), self.opponent_clan_id)
        if not is_member:
            await interaction.response.send_message(ERRORS["NOT_OPPONENT_CLAN"], ephemeral=True)
            return
        
        # Get user internal ID
        user_id = await permissions.get_user_internal_id(str(interaction.user.id))
        if not user_id:
            await interaction.response.send_message("Bạn chưa đăng ký trong hệ thống.", ephemeral=True)
            return
        
        # Try to confirm (atomic check for status = 'reported')
        success = await db.confirm_match_v2(self.match_id, user_id)
        
        if not success:
            await interaction.response.send_message(ERRORS["MATCH_ALREADY_PROCESSED"], ephemeral=True)
            return
        
        # Apply Elo
        elo_result = await elo.apply_match_result(self.match_id, self.winner_clan_id)
        
        # Get updated match data
        match = await db.get_match_with_clans(self.match_id)
        
        # Build result message
        if elo_result["success"]:
            winner_name = elo_result["clan_a_name"] if self.winner_clan_id == match["clan_a_id"] else elo_result["clan_b_name"]
            
            delta_a = elo_result["final_delta_a"]
            delta_b = elo_result["final_delta_b"]
            delta_a_str = f"+{delta_a}" if delta_a >= 0 else str(delta_a)
            delta_b_str = f"+{delta_b}" if delta_b >= 0 else str(delta_b)
            
            status_text = (
                f"✅ **Đã xác nhận!** {winner_name} thắng\n\n"
                f"**Elo thay đổi:**\n"
                f"• {elo_result['clan_a_name']}: {elo_result['elo_a_old']} → {elo_result['elo_a_new']} ({delta_a_str})\n"
                f"• {elo_result['clan_b_name']}: {elo_result['elo_b_old']} → {elo_result['elo_b_new']} ({delta_b_str})\n\n"
                f"📊 Multiplier: {elo_result['multiplier']}x (match {elo_result['match_count_24h']}/ngày)"
            )
            color = discord.Color.green()
        else:
            if elo_result["reason"] == "CLANS_INACTIVE":
                inactive = ", ".join(elo_result["inactive_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n⚠️ **Clan không active:** {inactive}\n\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_FROZEN":
                frozen = ", ".join(elo_result["frozen_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n🥶 **Clan bị đóng băng:** {frozen}\n\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_BANNED":
                banned = ", ".join(elo_result["banned_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n🚫 **Clan bị cấm hệ thống:** {banned}\n\n❌ Elo không được áp dụng."
            else:
                status_text = f"✅ **Đã xác nhận!**\n\n⚠️ Không thể áp dụng Elo: {elo_result['reason']}"
            color = discord.Color.orange()
        
        embed = create_match_embed(match, status_text, color)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        await bot_utils.log_event(
            "MATCH_CONFIRMED",
            f"Match #{self.match_id} xác nhận bởi {interaction.user.mention}. Elo applied: {elo_result['success']}"
        )


class DisputeButton(discord.ui.Button):
    """Button to dispute match result."""
    
    def __init__(self, match_id: int, opponent_clan_id: int):
        # Include opponent_clan_id for persistence after restart
        super().__init__(
            label="❌ Tranh chấp",
            style=discord.ButtonStyle.danger,
            custom_id=f"match_dispute:{match_id}:{opponent_clan_id}"
        )
        self.match_id = match_id
        self.opponent_clan_id = opponent_clan_id
    
    async def callback(self, interaction: discord.Interaction):
        # Check user is still in opponent clan
        is_member = await permissions.is_user_in_clan(str(interaction.user.id), self.opponent_clan_id)
        if not is_member:
            await interaction.response.send_message(ERRORS["NOT_OPPONENT_CLAN"], ephemeral=True)
            return
        
        # Show modal for reason
        modal = DisputeReasonModal(self.match_id, self.opponent_clan_id)
        await interaction.response.send_modal(modal)


class DisputeReasonModal(discord.ui.Modal, title="Lý do tranh chấp"):
    """Modal to input dispute reason."""
    
    reason = discord.ui.TextInput(
        label="Lý do",
        placeholder="Mô tả lý do bạn tranh chấp kết quả này...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True
    )
    
    def __init__(self, match_id: int, opponent_clan_id: int):
        super().__init__()
        self.match_id = match_id
        self.opponent_clan_id = opponent_clan_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get user internal ID
        user_id = await permissions.get_user_internal_id(str(interaction.user.id))
        if not user_id:
            await interaction.response.send_message("Bạn chưa đăng ký trong hệ thống.", ephemeral=True)
            return
        
        # Try to dispute (atomic check for status = 'reported')
        success = await db.dispute_match(self.match_id, user_id, self.reason.value)
        
        if not success:
            await interaction.response.send_message(ERRORS["MATCH_ALREADY_PROCESSED"], ephemeral=True)
            return
        
        # Get match data
        match = await db.get_match_with_clans(self.match_id)
        
        # Update embed
        embed = create_match_embed(
            match,
            f"⚠️ **TRANH CHẤP!**\n\nLý do: {self.reason.value}\n\nChờ Mod xử lý...",
            discord.Color.red()
        )
        
        # Update original message
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Ping mod-log
        log_channel = bot_utils.get_log_channel()
        if log_channel:
            mod_role = bot_utils.get_mod_role()
            ping = mod_role.mention if mod_role else ""
            await log_channel.send(
                f"{ping}\n"
                f"🚨 **TRANH CHẤP MATCH #{self.match_id}**\n"
                f"• {match['clan_a_name']} vs {match['clan_b_name']}\n"
                f"• Người tranh chấp: {interaction.user.mention}\n"
                f"• Lý do: {self.reason.value}\n\n"
                f"Sử dụng `/admin match resolve {self.match_id} <winner_clan> <reason>` để xử lý."
            )
        
        # [P2 Fix] Notify creator via DM
        try:
            if match.get("creator_discord_id"):
                creator = interaction.client.get_user(int(match["creator_discord_id"]))
                if not creator:
                    creator = await interaction.client.fetch_user(int(match["creator_discord_id"]))
                if creator:
                    await creator.send(
                        f"🚨 **Match #{self.match_id} bị tranh chấp!**\n"
                        f"Clan đối thủ **{match['clan_b_name']}** đã tranh chấp kết quả bạn báo cáo.\n"
                        f"Lý do: {self.reason.value}\n"
                        f"Vui lòng chờ Moderator kiểm tra và xử lý."
                    )
        except Exception:
            pass
        
        await bot_utils.log_event(
            "MATCH_DISPUTED",
            f"Match #{self.match_id} tranh chấp bởi {interaction.user.mention}. Lý do: {self.reason.value}"
        )


# =============================================================================
# COG DEFINITION
# =============================================================================

class MatchesCog(commands.Cog):
    """Cog containing match-related commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle persistent button interactions for matches."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if custom_id:
            print(f"[DEBUG] Interaction by {interaction.user.id}: {custom_id}")
        
        # Check if already handled
        if interaction.response.is_done():
            return
        
        # Format: match_report:{match_id}:{winner_clan_id}:{creator_id}
        if custom_id.startswith("match_report:"):
            parts = custom_id.split(":")
            if len(parts) == 4:
                match_id = int(parts[1])
                winner_clan_id = int(parts[2])
                creator_id = parts[3]
                await self.handle_match_report(interaction, match_id, winner_clan_id, creator_id)
                return
        
        # Format: match_cancel:{match_id}:{creator_id}
        if custom_id.startswith("match_cancel:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                match_id = int(parts[1])
                creator_id = parts[2]
                await self.handle_match_cancel(interaction, match_id, creator_id)
                return
        
        # Format: match_confirm:{match_id}:{opponent_clan_id}:{winner_clan_id}
        if custom_id.startswith("match_confirm:"):
            parts = custom_id.split(":")
            if len(parts) == 4:
                match_id = int(parts[1])
                opponent_clan_id = int(parts[2])
                winner_clan_id = int(parts[3])
                await self.handle_match_confirm(interaction, match_id, opponent_clan_id, winner_clan_id)
                return
        
        # Format: match_dispute:{match_id}:{opponent_clan_id}
        if custom_id.startswith("match_dispute:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                match_id = int(parts[1])
                opponent_clan_id = int(parts[2])
                await self.handle_match_dispute(interaction, match_id, opponent_clan_id)
                return

    async def handle_match_report(self, interaction: discord.Interaction, match_id: int, winner_clan_id: int, creator_id: str):
        # Only match creator can report
        if str(interaction.user.id) != creator_id:
            await interaction.response.send_message(ERRORS["NOT_MATCH_CREATOR"], ephemeral=True)
            return
        
        # Try to report (atomic check for status = 'created')
        success = await db.report_match_v2(match_id, winner_clan_id)
        
        if not success:
            # If failed, check if it was because it's already reported (might be double click or race)
            # We fail silently or standard error
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(ERRORS["MATCH_ALREADY_PROCESSED"], ephemeral=True)
            except Exception: pass
            return
        
        # Get updated match data
        match = await db.get_match_with_clans(match_id)
        
        # Determine opponent clan for Confirm/Dispute
        if winner_clan_id == match["clan_a_id"]:
            opponent_clan_id = match["clan_b_id"]
            opponent_name = match["clan_b_name"]
            winner_name = match["clan_a_name"]
        else:
            opponent_clan_id = match["clan_a_id"]
            opponent_name = match["clan_a_name"]
            winner_name = match["clan_b_name"]
        
        # Update embed
        embed = create_match_embed(
            match,
            f"📝 Đã báo cáo: **{winner_name}** thắng\nChờ {opponent_name} xác nhận...",
            discord.Color.yellow()
        )
        
        # New view with Confirm/Dispute buttons
        view = MatchReportedView(match_id, opponent_clan_id, winner_clan_id)
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        await bot_utils.log_event(
            "MATCH_REPORTED",
            f"Match #{match_id}: {interaction.user.mention} báo cáo {winner_name} thắng"
        )

    async def handle_match_cancel(self, interaction: discord.Interaction, match_id: int, creator_id: str):
        # Only match creator can cancel
        if str(interaction.user.id) != creator_id:
            await interaction.response.send_message(ERRORS["NOT_MATCH_CREATOR"], ephemeral=True)
            return
        
        # Try to cancel
        success = await db.cancel_match(match_id)
        
        if not success:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(ERRORS["CANNOT_CANCEL"], ephemeral=True)
            except Exception: pass
            return
        
        # Update message
        embed = discord.Embed(
            title=f"⚔️ Match #{match_id}",
            description="❌ **Match đã bị hủy**",
            color=discord.Color.dark_grey()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        await bot_utils.log_event(
            "MATCH_CANCELLED",
            f"Match #{match_id} bị hủy bởi {interaction.user.mention}"
        )

    async def handle_match_confirm(self, interaction: discord.Interaction, match_id: int, opponent_clan_id: int, winner_clan_id: int):
        # Check user is still in opponent clan
        is_member = await permissions.is_user_in_clan(str(interaction.user.id), opponent_clan_id)
        if not is_member:
            await interaction.response.send_message(ERRORS["NOT_OPPONENT_CLAN"], ephemeral=True)
            return
        
        # Get user internal ID
        user_id = await permissions.get_user_internal_id(str(interaction.user.id))
        if not user_id:
            await interaction.response.send_message("Bạn chưa đăng ký trong hệ thống.", ephemeral=True)
            return
        
        # Try to confirm
        success = await db.confirm_match_v2(match_id, user_id)
        
        if not success:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(ERRORS["MATCH_ALREADY_PROCESSED"], ephemeral=True)
            except Exception: pass
            return
        
        # Apply Elo
        elo_result = await elo.apply_match_result(match_id, winner_clan_id)
        
        # Get updated match data
        match = await db.get_match_with_clans(match_id)
        
        # Build result message
        if elo_result["success"]:
            winner_name = elo_result["clan_a_name"] if winner_clan_id == match["clan_a_id"] else elo_result["clan_b_name"]
            
            delta_a = elo_result["final_delta_a"]
            delta_b = elo_result["final_delta_b"]
            delta_a_str = f"+{delta_a}" if delta_a >= 0 else str(delta_a)
            delta_b_str = f"+{delta_b}" if delta_b >= 0 else str(delta_b)
            
            status_text = (
                f"✅ **Đã xác nhận!** {winner_name} thắng\n\n"
                f"**Elo thay đổi:**\n"
                f"• {elo_result['clan_a_name']}: {elo_result['elo_a_old']} → {elo_result['elo_a_new']} ({delta_a_str})\n"
                f"• {elo_result['clan_b_name']}: {elo_result['elo_b_old']} → {elo_result['elo_b_new']} ({delta_b_str})\n\n"
                f"📊 Multiplier: {elo_result['multiplier']}x (match {elo_result['match_count_24h']}/ngày)"
            )
            color = discord.Color.green()
        else:
            if elo_result["reason"] == "CLANS_INACTIVE":
                inactive = ", ".join(elo_result["inactive_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n⚠️ **Clan không active:** {inactive}\n\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_FROZEN":
                frozen = ", ".join(elo_result["frozen_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n🥶 **Clan bị đóng băng:** {frozen}\n\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_BANNED":
                banned = ", ".join(elo_result["banned_clans"])
                status_text = f"✅ **Đã xác nhận!**\n\n🚫 **Clan bị cấm hệ thống:** {banned}\n\n❌ Elo không được áp dụng."
            else:
                status_text = f"✅ **Đã xác nhận!**\n\n⚠️ Không thể áp dụng Elo: {elo_result['reason']}"
            color = discord.Color.orange()
        
        embed = create_match_embed(match, status_text, color)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        await bot_utils.log_event(
            "MATCH_CONFIRMED",
            f"Match #{match_id} xác nhận bởi {interaction.user.mention}. Elo applied: {elo_result['success']}"
        )

    async def handle_match_dispute(self, interaction: discord.Interaction, match_id: int, opponent_clan_id: int):
        # Check user is still in opponent clan
        is_member = await permissions.is_user_in_clan(str(interaction.user.id), opponent_clan_id)
        if not is_member:
            await interaction.response.send_message(ERRORS["NOT_OPPONENT_CLAN"], ephemeral=True)
            return
        
        # Show modal for reason
        modal = DisputeReasonModal(match_id, opponent_clan_id)
        await interaction.response.send_modal(modal)
    
    # =========================================================================
    # MATCH COMMANDS
    # =========================================================================
    
    match_group = app_commands.Group(name="match", description="Match commands")
    
    @match_group.command(name="create", description="Tạo match mới với clan khác")
    @app_commands.describe(
        opponent_clan="Tên clan đối thủ",
        note="Ghi chú (tùy chọn)"
    )
    async def match_create(self, interaction: discord.Interaction, opponent_clan: str, note: Optional[str] = None):
        """Create a new match against another clan."""
        await interaction.response.defer()
        
        # Check user is in a clan
        user_clan = await permissions.get_user_clan_by_discord_id(str(interaction.user.id))
        if not user_clan:
            await interaction.followup.send(ERRORS["NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Get opponent clan
        opponent = await db.get_clan(opponent_clan)
        if not opponent:
            await interaction.followup.send(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        # Can't match against self
        if opponent["id"] == user_clan["id"]:
            await interaction.followup.send(ERRORS["SAME_CLAN"], ephemeral=True)
            return
            
        # [P3 Fix] Rate limit - Match creation cooldown (5 minutes)
        is_cd, until = await cooldowns.check_cooldown("clan", user_clan["id"], "match_create")
        if is_cd:
            # Format time for display
            try:
                from datetime import datetime
                until_dt = datetime.fromisoformat(until)
                now_dt = datetime.now(timezone.utc)
                diff = until_dt - now_dt
                seconds = int(diff.total_seconds())
                minutes = seconds // 60
                secs = seconds % 60
                time_str = f"{minutes} phút {secs} giây"
            except Exception:
                time_str = until
                
            await interaction.followup.send(
                f"❌ **Rate Limit!** Clan của bạn vừa tạo match. Vui lòng chờ **{time_str}** để tạo match tiếp theo.", 
                ephemeral=True
            )
            return

        # [P1 Fix] Check both clans are active
        if user_clan["status"] != "active":
            await interaction.followup.send(f"Clan của bạn đang ở trạng thái **{user_clan['status']}** và không thể tạo match.", ephemeral=True)
            return
            
        if opponent["status"] != "active":
            await interaction.followup.send(f"Clan đối thủ **{opponent['name']}** đang ở trạng thái **{opponent['status']}** và không thể thi đấu.", ephemeral=True)
            return
            
        # Check if match already exists (optional but good)
        # ... skipped for now since create_match_v2 exists ...
            
        # Get user internal ID
        user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        
        # Create match in DB
        match_id = await db.create_match_v2(
            clan_a_id=user_clan["id"],
            clan_b_id=opponent["id"],
            creator_user_id=user["id"],
            note=note
        )
        
        # Get full match data
        match = await db.get_match_with_clans(match_id)
        
        # Create embed
        embed = create_match_embed(
            match,
            "🆕 **Đang chờ kết quả...**\n\nNgười tạo match hãy báo cáo kết quả.",
            discord.Color.blue()
        )
        
        # Create view with buttons
        view = MatchCreatedView(
            match_id=match_id,
            creator_id=str(interaction.user.id),
            clan_a_id=user_clan["id"],
            clan_b_id=opponent["id"],
            clan_a_name=user_clan["name"],
            clan_b_name=opponent["name"]
        )
        
        # Send message
        msg = await interaction.followup.send(embed=embed, view=view)
        
        # [P1 Fix] Notify opponent clan channel
        if opponent.get("channel_id"):
            try:
                opp_channel = self.bot.get_channel(int(opponent["channel_id"]))
                if opp_channel:
                    opp_role_mention = f"<@&{opponent['role_id']}>" if opponent.get('role_id') else "@everyone"
                    await opp_channel.send(
                        f"⚔️ {opp_role_mention}, clan **{user_clan['name']}** vừa thách đấu clan bạn!\n"
                        f"Theo dõi kết quả tại: {interaction.channel.mention}"
                    )
            except Exception as e:
                print(f"Error notifying opponent clan: {e}")

        # Store message ID for persistence
        await db.update_match_message_ids(match_id, str(msg.id), str(interaction.channel_id))
        
        await bot_utils.log_event(
            "MATCH_CREATED",
            f"Match #{match_id}: {user_clan['name']} vs {opponent['name']} (tạo bởi {interaction.user.mention})"
        )
        
        # [P3 Fix] Apply rate limit (5 minutes)
        await db.set_cooldown_minutes("clan", user_clan["id"], "match_create", 5, "Match created")
    
    # =========================================================================
    # ADMIN COMMANDS
    # =========================================================================
    
    matchadmin_group = app_commands.Group(name="matchadmin", description="Match admin commands")
    matchadmin_match = app_commands.Group(name="match", description="Match admin", parent=matchadmin_group)
    
    @matchadmin_match.command(name="resolve", description="Xử lý match tranh chấp (Mod only)")
    @app_commands.describe(
        match_id="ID của match",
        winner_clan="Tên clan thắng",
        reason="Lý do quyết định"
    )
    async def admin_match_resolve(self, interaction: discord.Interaction, match_id: int, 
                                   winner_clan: str, reason: str):
        """Resolve a disputed match."""
        if not await check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get match
        match = await db.get_match_with_clans(match_id)
        if not match:
            await interaction.followup.send(ERRORS["MATCH_NOT_FOUND"], ephemeral=True)
            return
        
        if match["status"] != "dispute":
            await interaction.followup.send(ERRORS["MATCH_NOT_DISPUTED"], ephemeral=True)
            return
        
        # Find winner clan ID
        winner = await db.get_clan(winner_clan)
        if not winner:
            await interaction.followup.send(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        if winner["id"] not in [match["clan_a_id"], match["clan_b_id"]]:
            await interaction.followup.send("Clan này không tham gia match!", ephemeral=True)
            return
        
        # Get mod user ID
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        
        # Resolve match
        success = await db.resolve_match(match_id, mod_user["id"], winner["id"], reason)
        
        if not success:
            await interaction.followup.send("Không thể xử lý match. Trạng thái đã thay đổi.", ephemeral=True)
            return
        
        # Apply Elo
        elo_result = await elo.apply_match_result(match_id, winner["id"])
        
        # Get updated match
        match = await db.get_match_with_clans(match_id)
        
        # Build result message
        if elo_result["success"]:
            delta_a = elo_result["final_delta_a"]
            delta_b = elo_result["final_delta_b"]
            delta_a_str = f"+{delta_a}" if delta_a >= 0 else str(delta_a)
            delta_b_str = f"+{delta_b}" if delta_b >= 0 else str(delta_b)
            
            elo_msg = (
                f"**Elo thay đổi:**\n"
                f"• {elo_result['clan_a_name']}: {elo_result['elo_a_old']} → {elo_result['elo_a_new']} ({delta_a_str})\n"
                f"• {elo_result['clan_b_name']}: {elo_result['elo_b_old']} → {elo_result['elo_b_new']} ({delta_b_str})"
            )
        else:
            if elo_result["reason"] == "CLANS_INACTIVE":
                inactive = ", ".join(elo_result["inactive_clans"])
                elo_msg = f"⚠️ **Clan không active:** {inactive}\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_FROZEN":
                frozen = ", ".join(elo_result["frozen_clans"])
                elo_msg = f"🥶 **Clan bị đóng băng:** {frozen}\n❌ Elo không được áp dụng."
            elif elo_result["reason"] == "CLANS_BANNED":
                banned = ", ".join(elo_result["banned_clans"])
                elo_msg = f"🚫 **Clan bị cấm hệ thống:** {banned}\n❌ Elo không được áp dụng."
            else:
                elo_msg = f"⚠️ Elo không áp dụng: {elo_result['reason']}"
        
        await interaction.followup.send(
            f"✅ Đã xử lý Match #{match_id}\n"
            f"**Người thắng:** {winner['name']}\n"
            f"**Lý do:** {reason}\n\n"
            f"{elo_msg}",
            ephemeral=True
        )
        
        # Try to update original message
        try:
            if match.get("channel_id") and match.get("message_id"):
                channel = self.bot.get_channel(int(match["channel_id"]))
                if channel:
                    message = await channel.fetch_message(int(match["message_id"]))
                    
                    embed = create_match_embed(
                        match,
                        f"⚖️ **ĐÃ XỬ LÝ BỞI MOD**\n\n"
                        f"Người thắng: **{winner['name']}**\n"
                        f"Lý do: {reason}\n\n"
                        f"{elo_msg}",
                        discord.Color.purple()
                    )
                    await message.edit(embed=embed, view=None)
        except Exception as e:
            print(f"Could not update original message: {e}")
        
        await bot_utils.log_event(
            "MATCH_RESOLVED",
            f"Match #{match_id} xử lý bởi {interaction.user.mention}. "
            f"Người thắng: {winner['name']}. Lý do: {reason}. Elo applied: {elo_result['success']}"
        )


# =============================================================================
# COG SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(MatchesCog(bot))
