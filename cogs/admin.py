"""
Admin Cog
Implements moderation commands including cooldown management, case handling,
system bans, clan freeze, and Elo operations.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
import json

import config
from services import db, cooldowns, moderation, permissions
import main as bot_main


class AdminCog(commands.Cog):
    """Cog for Admin/Mod commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    admin_group = app_commands.Group(name="admin", description="Admin management commands")
    cooldown_group = app_commands.Group(name="cooldown", description="Manage cooldowns", parent=admin_group)
    case_group = app_commands.Group(name="case", description="Manage cases", parent=admin_group)
    ban_group = app_commands.Group(name="ban", description="System ban management", parent=admin_group)
    freeze_group = app_commands.Group(name="freeze", description="Clan freeze management", parent=admin_group)
    
    async def check_mod(self, interaction: discord.Interaction) -> bool:
        """Check if user has mod role."""
        user_role_names = [role.name for role in interaction.user.roles]
        if config.ROLE_MOD in user_role_names:
            return True
        await interaction.response.send_message(f"You need the '{config.ROLE_MOD}' role to use this command.", ephemeral=True)
        return False

    # =========================================================================
    # COOLDOWN COMMANDS (existing)
    # =========================================================================

    @cooldown_group.command(name="view", description="View active cooldowns for a target")
    @app_commands.describe(
        target_type="User or Clan",
        user="Target user (if type is User)",
        clan_name="Target clan name (if type is Clan)"
    )
    async def cooldown_view(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], user: Optional[discord.User] = None, clan_name: Optional[str] = None):
        """View active cooldowns."""
        if not await self.check_mod(interaction):
            return
            
        target_id = 0
        target_name = ""
        
        if target_type == "user":
            if not user:
                return await interaction.response.send_message("Please specify a user.", ephemeral=True)
            db_user = await db.get_user(str(user.id))
            if not db_user:
                return await interaction.response.send_message("User not registered.", ephemeral=True)
            target_id = db_user["id"]
            target_name = user.display_name
        else:
            if not clan_name:
                return await interaction.response.send_message("Please specify a clan name.", ephemeral=True)
            clan = await db.get_clan_any_status(clan_name)
            if not clan:
                return await interaction.response.send_message("Clan not found.", ephemeral=True)
            target_id = clan["id"]
            target_name = clan["name"]
            
        # Check all known kinds
        kinds = [cooldowns.KIND_JOIN_LEAVE, cooldowns.KIND_LOAN, cooldowns.KIND_TRANSFER_SICKNESS]
        active_cooldowns = []
        
        for kind in kinds:
            is_cd, until = await cooldowns.check_cooldown(target_type, target_id, kind)
            if is_cd:
                active_cooldowns.append(f"• **{kind}**: Until {until}")
                
        if not active_cooldowns:
            await interaction.response.send_message(f"✅ No active cooldowns for **{target_name}** ({target_type}).", ephemeral=True)
        else:
            await interaction.response.send_message(f"⏳ **Active Cooldowns for {target_name}**:\n" + "\n".join(active_cooldowns), ephemeral=True)

    @cooldown_group.command(name="set", description="Set or overwrite a cooldown")
    @app_commands.describe(
        target_type="User or Clan",
        kind="Type of cooldown",
        duration_days="Duration in days (0-365)",
        reason="Reason for cooldown",
        user="Target user (if type is User)",
        clan_name="Target clan name (if type is Clan)"
    )
    async def cooldown_set(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], kind: Literal["join_leave", "loan", "transfer_sickness"], duration_days: int, reason: str, user: Optional[discord.User] = None, clan_name: Optional[str] = None):
        """Set a cooldown."""
        if not await self.check_mod(interaction):
            return
            
        if not (0 <= duration_days <= 365):
            return await interaction.response.send_message("Duration must be between 0 and 365 days.", ephemeral=True)

        target_id = 0
        target_name = ""
        
        if target_type == "user":
            if not user:
                return await interaction.response.send_message("Please specify a user.", ephemeral=True)
            db_user = await db.get_user(str(user.id))
            if not db_user:
                return await interaction.response.send_message("User not registered.", ephemeral=True)
            target_id = db_user["id"]
            target_name = user.display_name
        else:
            if not clan_name:
                return await interaction.response.send_message("Please specify a clan name.", ephemeral=True)
            clan = await db.get_clan_any_status(clan_name)
            if not clan:
                return await interaction.response.send_message("Clan not found.", ephemeral=True)
            target_id = clan["id"]
            target_name = clan["name"]
            
        await cooldowns.apply_cooldown(target_type, target_id, kind, duration_days, reason)
        
        await interaction.response.send_message(f"✅ Set **{kind}** cooldown for **{target_name}** for {duration_days} days.\nReason: {reason}")
        
        await bot_main.log_event(
            "ADMIN_COOLDOWN_SET",
            f"Admin {interaction.user.mention} set {kind} cooldown for {target_name} ({target_type}) for {duration_days} days. Reason: {reason}"
        )

    @cooldown_group.command(name="clear", description="Clear cooldowns")
    @app_commands.describe(
        target_type="User or Clan",
        kind="Specific kind to clear (optional, clears all if empty)",
        user="Target user (if type is User)",
        clan_name="Target clan name (if type is Clan)"
    )
    async def cooldown_clear(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], kind: Optional[Literal["join_leave", "loan", "transfer_sickness"]] = None, user: Optional[discord.User] = None, clan_name: Optional[str] = None):
        """Clear cooldowns."""
        if not await self.check_mod(interaction):
            return
            
        target_id = 0
        target_name = ""
        
        if target_type == "user":
            if not user:
                return await interaction.response.send_message("Please specify a user.", ephemeral=True)
            db_user = await db.get_user(str(user.id))
            if not db_user:
                return await interaction.response.send_message("User not registered.", ephemeral=True)
            target_id = db_user["id"]
            target_name = user.display_name
        else:
            if not clan_name:
                return await interaction.response.send_message("Please specify a clan name.", ephemeral=True)
            clan = await db.get_clan_any_status(clan_name)
            if not clan:
                return await interaction.response.send_message("Clan not found.", ephemeral=True)
            target_id = clan["id"]
            target_name = clan["name"]
            
        await cooldowns.clear_cooldown(target_type, target_id, kind)
        
        msg = f"✅ Cleared **{kind if kind else 'ALL'}** cooldowns for **{target_name}**."
        await interaction.response.send_message(msg)
        
        await bot_main.log_event(
            "ADMIN_COOLDOWN_CLEAR",
            f"Admin {interaction.user.mention} cleared {kind if kind else 'ALL'} cooldowns for {target_name} ({target_type})."
        )

    # =========================================================================
    # CASE MANAGEMENT COMMANDS
    # =========================================================================

    @case_group.command(name="list", description="List cases with optional filters")
    @app_commands.describe(
        status="Filter by status",
        target_type="Filter by target type"
    )
    async def case_list(self, interaction: discord.Interaction, status: Optional[Literal["open", "investigating", "needs_info", "resolved", "appealed", "closed"]] = None, target_type: Optional[Literal["user", "clan", "match", "other"]] = None):
        """List cases."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        cases = await db.get_cases_filtered(status=status, target_type=target_type, limit=20)
        
        if not cases:
            await interaction.followup.send("Không có case nào phù hợp.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📋 Danh Sách Cases",
            color=discord.Color.blue()
        )
        
        lines = []
        for case in cases[:15]:
            status_emoji = {"open": "🔵", "investigating": "🔍", "needs_info": "❓", "resolved": "✅", "appealed": "📝", "closed": "⬛"}.get(case["status"], "❔")
            lines.append(f"`#{case['id']}` {status_emoji} **{case['target_type']}** - {case['status']} ({case['created_at'][:10]})")
        
        embed.description = "\n".join(lines)
        if len(cases) > 15:
            embed.set_footer(text=f"Hiển thị 15/{len(cases)} cases")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @case_group.command(name="view", description="View case details")
    @app_commands.describe(case_id="Case ID to view")
    async def case_view(self, interaction: discord.Interaction, case_id: int):
        """View detailed case info (mod version - full details)."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        case = await db.get_case(case_id)
        if not case:
            await interaction.followup.send(f"Case #{case_id} không tồn tại.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"📋 Case #{case_id}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Loại", value=case["target_type"], inline=True)
        embed.add_field(name="Target ID", value=str(case["target_id"]), inline=True)
        embed.add_field(name="Trạng thái", value=case["status"], inline=True)
        embed.add_field(name="Lý do báo cáo", value=case["reason"][:500], inline=False)
        
        if case.get("proof"):
            embed.add_field(name="Bằng chứng", value=case["proof"][:500], inline=False)
        
        if case.get("verdict"):
            embed.add_field(name="Kết luận", value=case["verdict"], inline=True)
        if case.get("verdict_reason"):
            embed.add_field(name="Lý do kết luận", value=case["verdict_reason"][:200], inline=False)
        if case.get("punishment"):
            embed.add_field(name="Hình phạt", value=case["punishment"], inline=True)
        
        embed.add_field(name="Ngày tạo", value=case["created_at"][:19], inline=True)
        if case.get("resolved_at"):
            embed.add_field(name="Ngày xử lý", value=case["resolved_at"][:19], inline=True)
        
        # Get actions for this case
        actions = await db.get_case_actions(case_id)
        if actions:
            action_lines = []
            for a in actions[-5:]:  # Last 5 actions
                action_lines.append(f"• `{a['action_type']}` - {a['performed_at'][:10]}")
            embed.add_field(name="Lịch sử hành động", value="\n".join(action_lines), inline=False)
        
        # Check for appeal
        appeal = await db.get_appeal_by_case(case_id)
        if appeal:
            embed.add_field(name="Kháng cáo", value=f"Appeal #{appeal['id']} - {appeal['status']}", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @case_group.command(name="action", description="Perform moderation action on a case")
    @app_commands.describe(
        case_id="Case ID",
        action_type="Type of action to perform",
        reason="Reason for the action",
        target_id="Target ID for the action (match_id, clan_name, or user mention)"
    )
    async def case_action(
        self, 
        interaction: discord.Interaction, 
        case_id: int,
        action_type: Literal["warning", "freeze_clan", "unfreeze_clan", "rollback_match", "reset_elo", "void_match", "dissolve_clan", "system_ban_user", "system_ban_clan", "system_unban_user", "system_unban_clan"],
        reason: str,
        target_id: Optional[str] = None
    ):
        """Perform a moderation action attached to a case."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        case = await db.get_case(case_id)
        if not case:
            await interaction.followup.send(f"Case #{case_id} không tồn tại.", ephemeral=True)
            return
        
        if case["status"] == "closed":
            await interaction.followup.send("Case đã đóng, không thể thực hiện hành động mới.", ephemeral=True)
            return
        
        # Get mod user
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        guild = interaction.guild
        
        result_msg = ""
        target_info = target_id or "N/A"
        
        try:
            if action_type == "warning":
                result_msg = f"⚠️ Đã ghi nhận cảnh cáo.\nLý do: {reason}"
                
            elif action_type == "freeze_clan":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                await moderation.freeze_clan(clan["id"], reason, mod_user["id"])
                result_msg = f"🥶 Đã đóng băng clan **{clan['name']}**.\nLý do: {reason}"
                target_info = clan["name"]
                
            elif action_type == "unfreeze_clan":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                unfrozen = await moderation.unfreeze_clan(clan["id"])
                if unfrozen:
                    result_msg = f"🔥 Đã bỏ đóng băng clan **{clan['name']}**."
                else:
                    result_msg = f"Clan **{clan['name']}** không bị đóng băng."
                target_info = clan["name"]
                
            elif action_type == "rollback_match":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định match ID.", ephemeral=True)
                    return
                try:
                    match_id = int(target_id)
                except ValueError:
                    await interaction.followup.send("Match ID phải là số.", ephemeral=True)
                    return
                rollback_result = await moderation.rollback_match_elo(match_id, mod_user["id"])
                if rollback_result["success"]:
                    details = rollback_result["rollback_details"]
                    changes = "\n".join([f"• {d['clan_name']}: {d['before']} → {d['after']} ({d['reverted_change']:+d})" for d in details])
                    result_msg = f"🔄 Đã rollback Elo cho Match #{match_id}:\n{changes}"
                else:
                    result_msg = f"❌ Không thể rollback: {rollback_result['reason']}"
                target_info = f"Match #{match_id}"
                
            elif action_type == "reset_elo":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                reset_result = await moderation.reset_clan_elo(clan["id"], mod_user["id"], 1000)
                if reset_result["success"]:
                    result_msg = f"🔄 Đã reset Elo clan **{clan['name']}**: {reset_result['old_elo']} → 1000"
                else:
                    result_msg = f"❌ Lỗi: {reset_result['reason']}"
                target_info = clan["name"]
                
            elif action_type == "void_match":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định match ID.", ephemeral=True)
                    return
                try:
                    match_id = int(target_id)
                except ValueError:
                    await interaction.followup.send("Match ID phải là số.", ephemeral=True)
                    return
                void_result = await moderation.void_match_result(match_id)
                if void_result["success"]:
                    result_msg = f"❌ Đã void Match #{match_id}."
                else:
                    result_msg = f"❌ Không thể void: {void_result['reason']}"
                target_info = f"Match #{match_id}"
                
            elif action_type == "dissolve_clan":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                dissolve_result = await moderation.dissolve_clan(clan["id"], mod_user["id"], guild)
                if dissolve_result["success"]:
                    result_msg = f"💀 Đã giải tán clan **{clan['name']}**.\n• {dissolve_result['members_count']} thành viên\n• Role removed: {dissolve_result['role_removed']}\n• Channel archived: {dissolve_result['channel_archived']}"
                else:
                    result_msg = f"❌ Lỗi: {dissolve_result['reason']}"
                target_info = clan["name"]
                
            elif action_type == "system_ban_user":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định user (mention hoặc Discord ID).", ephemeral=True)
                    return
                user_discord_id = target_id.strip("<@!>")
                target_user = await db.get_user(user_discord_id)
                if not target_user:
                    await interaction.followup.send("User chưa đăng ký trong hệ thống.", ephemeral=True)
                    return
                await moderation.ban_user_system(target_user["id"], reason, mod_user["id"])
                result_msg = f"🚫 Đã cấm hệ thống user ID {user_discord_id}.\nLý do: {reason}"
                target_info = f"User {user_discord_id}"
                
            elif action_type == "system_ban_clan":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                await moderation.ban_clan_system(clan["id"], reason, mod_user["id"])
                result_msg = f"🚫 Đã cấm hệ thống clan **{clan['name']}**.\nLý do: {reason}"
                target_info = clan["name"]
                
            elif action_type == "system_unban_user":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định user (mention hoặc Discord ID).", ephemeral=True)
                    return
                user_discord_id = target_id.strip("<@!>")
                target_user = await db.get_user(user_discord_id)
                if not target_user:
                    await interaction.followup.send("User chưa đăng ký trong hệ thống.", ephemeral=True)
                    return
                unbanned = await moderation.unban_user_system(target_user["id"])
                if unbanned:
                    result_msg = f"✅ Đã gỡ cấm hệ thống cho user ID {user_discord_id}."
                else:
                    result_msg = f"User không bị cấm hệ thống."
                target_info = f"User {user_discord_id}"
                
            elif action_type == "system_unban_clan":
                if not target_id:
                    await interaction.followup.send("Cần chỉ định tên clan.", ephemeral=True)
                    return
                clan = await db.get_clan_any_status(target_id)
                if not clan:
                    await interaction.followup.send("Clan không tồn tại.", ephemeral=True)
                    return
                unbanned = await moderation.unban_clan_system(clan["id"])
                if unbanned:
                    result_msg = f"✅ Đã gỡ cấm hệ thống cho clan **{clan['name']}**."
                else:
                    result_msg = f"Clan không bị cấm hệ thống."
                target_info = clan["name"]
            
            # Log the action
            payload = {"action_type": action_type, "reason": reason, "target_id": target_id}
            await db.add_case_action(case_id, action_type, mod_user["id"], target_info, json.dumps(payload))
            
            await interaction.followup.send(result_msg, ephemeral=True)
            
            await bot_main.log_event(
                "CASE_ACTION",
                f"Case #{case_id}: {interaction.user.mention} performed **{action_type}** on {target_info}. Reason: {reason}"
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi: {str(e)}", ephemeral=True)

    @case_group.command(name="close", description="Close a case")
    @app_commands.describe(
        case_id="Case ID",
        decision="Final decision/note"
    )
    async def case_close(self, interaction: discord.Interaction, case_id: int, decision: Optional[str] = None):
        """Close a case."""
        if not await self.check_mod(interaction):
            return
        
        case = await db.get_case(case_id)
        if not case:
            await interaction.response.send_message(f"Case #{case_id} không tồn tại.", ephemeral=True)
            return
        
        if case["status"] == "closed":
            await interaction.response.send_message(f"Case #{case_id} đã đóng.", ephemeral=True)
            return
        
        await db.close_case(case_id)
        
        await interaction.response.send_message(f"✅ Đã đóng Case #{case_id}.")
        
        await bot_main.log_event(
            "CASE_CLOSED",
            f"Case #{case_id} closed by {interaction.user.mention}. Decision: {decision or 'N/A'}"
        )

    # =========================================================================
    # DIRECT BAN COMMANDS (without case)
    # =========================================================================

    @ban_group.command(name="user", description="System ban a user")
    @app_commands.describe(
        user="User to ban",
        reason="Reason for ban"
    )
    async def ban_user(self, interaction: discord.Interaction, user: discord.User, reason: str):
        """Ban a user from the clan system."""
        if not await self.check_mod(interaction):
            return
        
        db_user = await db.get_user(str(user.id))
        if not db_user:
            await interaction.response.send_message("User chưa đăng ký.", ephemeral=True)
            return
        
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        await moderation.ban_user_system(db_user["id"], reason, mod_user["id"])
        
        await interaction.response.send_message(f"🚫 Đã cấm hệ thống **{user.display_name}**.\nLý do: {reason}")
        
        await bot_main.log_event(
            "SYSTEM_BAN",
            f"User {user.mention} banned by {interaction.user.mention}. Reason: {reason}"
        )

    @ban_group.command(name="clan", description="System ban a clan")
    @app_commands.describe(
        clan_name="Clan name to ban",
        reason="Reason for ban"
    )
    async def ban_clan(self, interaction: discord.Interaction, clan_name: str, reason: str):
        """Ban a clan from the clan system."""
        if not await self.check_mod(interaction):
            return
        
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message("Clan không tồn tại.", ephemeral=True)
            return
        
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        await moderation.ban_clan_system(clan["id"], reason, mod_user["id"])
        
        await interaction.response.send_message(f"🚫 Đã cấm hệ thống clan **{clan['name']}**.\nLý do: {reason}")
        
        await bot_main.log_event(
            "SYSTEM_BAN",
            f"Clan {clan['name']} banned by {interaction.user.mention}. Reason: {reason}"
        )

    @admin_group.command(name="unban", description="Remove system ban")
    @app_commands.describe(
        target_type="User or Clan",
        user="User to unban",
        clan_name="Clan name to unban"
    )
    async def unban(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], user: Optional[discord.User] = None, clan_name: Optional[str] = None):
        """Remove system ban from user or clan."""
        if not await self.check_mod(interaction):
            return
        
        if target_type == "user":
            if not user:
                await interaction.response.send_message("Cần chỉ định user.", ephemeral=True)
                return
            db_user = await db.get_user(str(user.id))
            if not db_user:
                await interaction.response.send_message("User chưa đăng ký.", ephemeral=True)
                return
            removed = await moderation.unban_user_system(db_user["id"])
            if removed:
                await interaction.response.send_message(f"✅ Đã gỡ cấm hệ thống cho **{user.display_name}**.")
                await bot_main.log_event("SYSTEM_UNBAN", f"User {user.mention} unbanned by {interaction.user.mention}.")
            else:
                await interaction.response.send_message(f"User không bị cấm hệ thống.", ephemeral=True)
        else:
            if not clan_name:
                await interaction.response.send_message("Cần chỉ định tên clan.", ephemeral=True)
                return
            clan = await db.get_clan_any_status(clan_name)
            if not clan:
                await interaction.response.send_message("Clan không tồn tại.", ephemeral=True)
                return
            removed = await moderation.unban_clan_system(clan["id"])
            if removed:
                await interaction.response.send_message(f"✅ Đã gỡ cấm hệ thống cho clan **{clan['name']}**.")
                await bot_main.log_event("SYSTEM_UNBAN", f"Clan {clan['name']} unbanned by {interaction.user.mention}.")
            else:
                await interaction.response.send_message(f"Clan không bị cấm hệ thống.", ephemeral=True)

    # =========================================================================
    # FREEZE COMMANDS
    # =========================================================================

    @freeze_group.command(name="clan", description="Freeze a clan (no Elo applied)")
    @app_commands.describe(
        clan_name="Clan name to freeze",
        reason="Reason for freezing"
    )
    async def freeze_clan_cmd(self, interaction: discord.Interaction, clan_name: str, reason: str):
        """Freeze a clan - they can play but Elo won't be applied."""
        if not await self.check_mod(interaction):
            return
        
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message("Clan không tồn tại.", ephemeral=True)
            return
        
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        await moderation.freeze_clan(clan["id"], reason, mod_user["id"])
        
        await interaction.response.send_message(f"🥶 Đã đóng băng clan **{clan['name']}**.\nElo sẽ không được áp dụng cho các trận đấu.\nLý do: {reason}")
        
        await bot_main.log_event(
            "CLAN_FROZEN",
            f"Clan {clan['name']} frozen by {interaction.user.mention}. Reason: {reason}"
        )

    @admin_group.command(name="unfreeze", description="Unfreeze a clan")
    @app_commands.describe(clan_name="Clan name to unfreeze")
    async def unfreeze_clan_cmd(self, interaction: discord.Interaction, clan_name: str):
        """Unfreeze a clan."""
        if not await self.check_mod(interaction):
            return
        
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message("Clan không tồn tại.", ephemeral=True)
            return
        
        unfrozen = await moderation.unfreeze_clan(clan["id"])
        if unfrozen:
            await interaction.response.send_message(f"🔥 Đã bỏ đóng băng clan **{clan['name']}**.")
            await bot_main.log_event("CLAN_UNFROZEN", f"Clan {clan['name']} unfrozen by {interaction.user.mention}.")
        else:
            await interaction.response.send_message(f"Clan **{clan['name']}** không bị đóng băng.", ephemeral=True)


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

