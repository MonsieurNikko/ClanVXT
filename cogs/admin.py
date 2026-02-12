"""
Admin Cog
Implements moderation commands including cooldown management, case handling,
system bans, clan freeze, and Elo operations.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
import json

import config
from services import db, cooldowns, moderation, permissions
from services import bot_utils


class AdminCog(commands.Cog):
    """Cog for Admin/Mod commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    admin_group = app_commands.Group(name="admin", description="Admin management commands")
    cooldown_group = app_commands.Group(name="cooldown", description="Manage cooldowns", parent=admin_group)
    case_group = app_commands.Group(name="case", description="Manage cases", parent=admin_group)
    ban_group = app_commands.Group(name="ban", description="System ban management", parent=admin_group)
    freeze_group = app_commands.Group(name="freeze", description="Clan freeze management", parent=admin_group)
    clan_group = app_commands.Group(name="clan", description="Admin clan management", parent=admin_group)
    loan_admin_group = app_commands.Group(name="loan", description="Admin loan management", parent=admin_group)
    
    async def check_mod(self, interaction: discord.Interaction) -> bool:
        """Check if user has mod role."""
        user_role_names = [role.name for role in interaction.user.roles]
        if config.ROLE_MOD in user_role_names:
            return True
        await interaction.response.send_message(f"Bạn cần role '{config.ROLE_MOD}' để sử dụng lệnh này.", ephemeral=True)
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
                return await interaction.response.send_message("Người dùng chưa đăng ký.", ephemeral=True)
            target_id = db_user["id"]
            target_name = user.display_name
        else:
            if not clan_name:
                return await interaction.response.send_message("Please specify a clan name.", ephemeral=True)
            clan = await db.get_clan_any_status(clan_name)
            if not clan:
                return await interaction.response.send_message("Không tìm thấy clan.", ephemeral=True)
            target_id = clan["id"]
            target_name = clan["name"]
            
        # Check active cooldowns
        active_cooldowns = []
        
        if target_type == "user":
            user_cds = await db.get_all_user_cooldowns(target_id)
            for cd in user_cds:
                active_cooldowns.append(f"• **{cd['kind']}**: Đến {cd['until']}")
        else:
            # Clans don't have legacy columns
            for kind in [cooldowns.KIND_JOIN_LEAVE, cooldowns.KIND_LOAN]:
                is_cd, until = await cooldowns.check_cooldown("clan", target_id, kind)
                if is_cd:
                    active_cooldowns.append(f"• **{kind}**: Đến {until}")
                
        if not active_cooldowns:
            await interaction.response.send_message(f"✅ Không có cooldown nào đang hoạt động cho **{target_name}** ({target_type}).", ephemeral=True)
        else:
            await interaction.response.send_message(f"⏳ **Cooldown đang hoạt động cho {target_name}**:\n" + "\n".join(active_cooldowns), ephemeral=True)

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
            return await interaction.response.send_message("Thời hạn phải từ 0 đến 365 ngày.", ephemeral=True)

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

        if target_type == "user" and kind == cooldowns.KIND_JOIN_LEAVE:
            # We already applied to the new table with cooldowns.apply_cooldown above.
            # Just ensure the legacy column is cleared in the users table.
            print(f"[ADMIN] Setting join_leave cooldown for user {target_id}, clearing legacy column.")
            async with db.get_connection() as conn:
                await conn.execute("UPDATE users SET cooldown_until = NULL WHERE id = ?", (target_id,))
                await conn.commit()
        
        await interaction.response.send_message(f"✅ Đã đặt cooldown **{kind}** cho **{target_name}** trong {duration_days} ngày.\nLý do: {reason}")
        
        await bot_utils.log_event(
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

        if target_type == "user" and (kind is None or kind == cooldowns.KIND_JOIN_LEAVE):
            # Kind was cleared in the new table via cooldowns.clear_cooldown above.
            # Clear legacy column in users table.
            print(f"[ADMIN] Clearing cooldown for user {target_id}, clearing legacy column.")
            async with db.get_connection() as conn:
                await conn.execute("UPDATE users SET cooldown_until = NULL WHERE id = ?", (target_id,))
                await conn.commit()
        
        msg = f"✅ Đã xóa **{kind if kind else 'TẤT CẢ'}** cooldown cho **{target_name}**."
        await interaction.response.send_message(msg)

        if target_type == "user" and user:
            try:
                kind_text = kind if kind else "TẤT CẢ"
                await user.send(
                    f"✅ Cooldown **{kind_text}** của bạn đã được xóa. Bạn có thể tiếp tục tham gia hoạt động clan."
                )
            except Exception:
                pass
        
        await bot_utils.log_event(
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
        target_info = target_id or "Không có"
        
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
            
            await bot_utils.log_event(
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
        
        await bot_utils.log_event(
            "CASE_CLOSED",
            f"Case #{case_id} closed by {interaction.user.mention}. Decision: {decision or 'Không có'}"
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
        
        await bot_utils.log_event(
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
        
        await bot_utils.log_event(
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
                await bot_utils.log_event("SYSTEM_UNBAN", f"User {user.mention} unbanned by {interaction.user.mention}.")
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
                await bot_utils.log_event("SYSTEM_UNBAN", f"Clan {clan['name']} unbanned by {interaction.user.mention}.")
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
        
        await bot_utils.log_event(
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
            await bot_utils.log_event("CLAN_UNFROZEN", f"Clan {clan['name']} unfrozen by {interaction.user.mention}.")
        else:
            await interaction.response.send_message(f"Clan **{clan['name']}** không bị đóng băng.", ephemeral=True)

    # =========================================================================
    # CLAN ADMIN COMMANDS
    # =========================================================================

    @clan_group.command(name="set_elo", description="Đặt điểm Elo cho clan (Admin only)")
    @app_commands.describe(
        clan_name="Tên clan cần chỉnh điểm",
        new_elo="Điểm Elo mới",
        reason="Lý do điều chỉnh"
    )
    async def admin_set_elo(self, interaction: discord.Interaction, clan_name: str, new_elo: int, reason: str):
        """Manually set a clan's Elo score."""
        if not await self.check_mod(interaction):
            return
            
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message("❌ Clan không tồn tại.", ephemeral=True)
            return

        # Perform the update
        mod_user = await permissions.ensure_user_exists(str(interaction.user.id), interaction.user.name)
        await db.update_clan_elo(
            clan_id=clan["id"],
            new_elo=new_elo,
            match_id=None,
            reason=f"Admin Adjustment: {reason}",
            changed_by=mod_user["id"]
        )
        
        await interaction.response.send_message(
            f"✅ Đã cập nhật Elo cho clan **{clan['name']}**.\n"
            f"• Cũ: `{clan['elo']}`\n"
            f"• Mới: `{new_elo}`\n"
            f"• Lý do: {reason}"
        )
        
        await bot_utils.log_event(
            "CLAN_ELO_ADJUSTED",
            f"Clan {clan['name']} Elo set to {new_elo} by {interaction.user.mention}. Reason: {reason}"
        )
        print(f"[ADMIN] Elo adjusted for {clan['name']} to {new_elo} by {interaction.user}")

    # =========================================================================
    # DASHBOARD COMMAND
    # =========================================================================
    
    @admin_group.command(name="dashboard", description="View database overview with all clans, members, matches")
    async def admin_dashboard(self, interaction: discord.Interaction):
        """Show admin dashboard with database overview."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        view = DashboardView(self.bot)
        embed = await view.get_overview_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # =============================================================================
    # LOAN ADMIN COMMANDS
    # =============================================================================

    @loan_admin_group.command(name="fix_roles", description="Fix Discord roles for all active loans")
    async def admin_loan_fix_roles(self, interaction: discord.Interaction):
        """Scan all active loans and fix Discord roles for loaned members."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Chỉ sử dụng được trong server.", ephemeral=True)
            return
        
        # Get all active loans
        async with db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id, lending_clan_id, borrowing_clan_id, member_user_id FROM loans WHERE status = 'active'"
            )
            active_loans = [dict(row) for row in await cursor.fetchall()]
        
        if not active_loans:
            await interaction.followup.send("ℹ️ Không có loan nào đang hoạt động.", ephemeral=True)
            return
        
        fixed = 0
        errors = []
        
        for loan in active_loans:
            loan_id = loan["id"]
            try:
                member_user = await db.get_user_by_id(loan["member_user_id"])
                if not member_user:
                    errors.append(f"Loan {loan_id}: user not found")
                    continue
                
                discord_member = guild.get_member(int(member_user["discord_id"]))
                if not discord_member:
                    errors.append(f"Loan {loan_id}: <@{member_user['discord_id']}> not in server")
                    continue
                
                lending_clan = await db.get_clan_by_id(loan["lending_clan_id"])
                borrowing_clan = await db.get_clan_by_id(loan["borrowing_clan_id"])
                
                changed = False
                
                # Remove lending clan role (member is loaned away)
                if lending_clan and lending_clan.get("discord_role_id"):
                    role = guild.get_role(int(lending_clan["discord_role_id"]))
                    if role and role in discord_member.roles:
                        await discord_member.remove_roles(role, reason=f"Admin fix_roles: Loan {loan_id}")
                        changed = True
                
                # Add borrowing clan role (member should be in borrowing clan)
                if borrowing_clan and borrowing_clan.get("discord_role_id"):
                    role = guild.get_role(int(borrowing_clan["discord_role_id"]))
                    if role and role not in discord_member.roles:
                        await discord_member.add_roles(role, reason=f"Admin fix_roles: Loan {loan_id}")
                        changed = True
                
                if changed:
                    fixed += 1
                    
            except Exception as e:
                errors.append(f"Loan {loan_id}: {e}")
        
        # Result
        result = f"✅ Đã kiểm tra {len(active_loans)} loan, sửa role cho {fixed} member."
        if errors:
            result += f"\n⚠️ Lỗi ({len(errors)}):\n" + "\n".join(f"• {e}" for e in errors)
        
        await interaction.followup.send(result, ephemeral=True)
        
        await bot_utils.log_event(
            "ADMIN_LOAN_FIX_ROLES",
            f"{interaction.user.mention} ran fix_roles: {len(active_loans)} loans checked, {fixed} fixed."
        )


# =============================================================================
# DASHBOARD VIEW
# =============================================================================

class DashboardView(discord.ui.View):
    """Dashboard with tabs for admin overview."""
    
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.current_page = 0
        self.current_tab = "overview"
    
    async def get_overview_embed(self) -> discord.Embed:
        """Get overview/stats embed."""
        async with db.get_connection() as conn:
            # Count clans by status
            cursor = await conn.execute("SELECT status, COUNT(*) FROM clans GROUP BY status")
            clan_stats = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Count total users
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            # Count total matches by status
            cursor = await conn.execute("SELECT status, COUNT(*) FROM matches GROUP BY status")
            match_stats = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Active loans
            cursor = await conn.execute("SELECT COUNT(*) FROM loans WHERE status = 'active'")
            active_loans = (await cursor.fetchone())[0]
            
            # Pending transfers
            cursor = await conn.execute("SELECT COUNT(*) FROM transfers WHERE status = 'requested'")
            pending_transfers = (await cursor.fetchone())[0]
            
            # Pending invites
            cursor = await conn.execute("SELECT COUNT(*) FROM invite_requests WHERE status = 'pending'")
            pending_invites = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title="📊 Admin Dashboard - Overview",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Clan stats
        clan_text = f"🟢 Active: **{clan_stats.get('active', 0)}**\n"
        clan_text += f"🟡 Pending: **{clan_stats.get('pending_approval', 0)}**\n"
        clan_text += f"⏳ Waiting Accept: **{clan_stats.get('waiting_accept', 0)}**\n"
        clan_text += f"🔴 Inactive: **{clan_stats.get('inactive', 0)}**\n"
        clan_text += f"❄️ Frozen: **{clan_stats.get('frozen', 0)}**\n"
        clan_text += f"💀 Disbanded: **{clan_stats.get('disbanded', 0)}**"
        embed.add_field(name="🏰 Clans", value=clan_text, inline=True)
        
        # User stats
        user_text = f"👥 Total Users: **{total_users}**\n"
        user_text += f"📨 Pending Invites: **{pending_invites}**"
        embed.add_field(name="👤 Users", value=user_text, inline=True)
        
        # Match stats
        total_matches = sum(match_stats.values())
        match_text = f"📊 Total: **{total_matches}**\n"
        match_text += f"✅ Confirmed: **{match_stats.get('confirmed', 0)}**\n"
        match_text += f"⚠️ Disputed: **{match_stats.get('dispute', 0)}**\n"
        match_text += f"⏳ Created: **{match_stats.get('created', 0)}**"
        embed.add_field(name="⚔️ Matches", value=match_text, inline=True)
        
        # Operations
        ops_text = f"🔄 Active Loans: **{active_loans}**\n"
        ops_text += f"📦 Pending Transfers: **{pending_transfers}**"
        embed.add_field(name="📋 Operations", value=ops_text, inline=False)
        
        embed.set_footer(text="Use dropdown to view details")
        return embed
    
    async def get_clans_embed(self, page: int = 0) -> discord.Embed:
        """Get clans list embed with pagination."""
        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT c.id, c.name, c.status, c.elo, c.matches_played,
                       (SELECT COUNT(*) FROM clan_members WHERE clan_id = c.id) as member_count
                FROM clans c
                WHERE c.status NOT IN ('disbanded', 'cancelled', 'rejected')
                ORDER BY c.elo DESC
                LIMIT 10 OFFSET ?
            """, (page * 10,))
            clans = await cursor.fetchall()
            
            cursor = await conn.execute("SELECT COUNT(*) FROM clans WHERE status NOT IN ('disbanded', 'cancelled', 'rejected')")
            total = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title=f"🏰 All Clans (Page {page + 1}/{max(1, (total + 9) // 10)})",
            color=discord.Color.green()
        )
        
        if not clans:
            embed.description = "No clans found."
            return embed
        
        description = "```\n"
        description += f"{'Clan':<20} {'Elo':<6} {'M':<4} {'Status':<10}\n"
        description += "-" * 44 + "\n"
        for clan in clans:
            status_icon = {"active": "🟢", "inactive": "🔴", "frozen": "❄️", "pending_approval": "🟡", "waiting_accept": "⏳"}.get(clan[2], "❓")
            name = clan[1][:18] + ".." if len(clan[1]) > 20 else clan[1]
            description += f"{name:<20} {clan[3]:<6} {clan[5]:<4} {status_icon}{clan[2][:8]}\n"
        description += "```"
        embed.description = description
        embed.set_footer(text=f"M = Members | Total: {total} clans")
        
        self.total_pages = max(1, (total + 9) // 10)
        return embed
    
    async def get_members_embed(self, page: int = 0) -> discord.Embed:
        """Get members list with clan info."""
        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT u.discord_id, u.riot_id, u.is_banned, cm.role, c.name as clan_name,
                       (SELECT COUNT(*) FROM cooldowns cd
                        WHERE cd.target_type = 'user'
                          AND cd.target_id = u.id
                          AND cd.until > datetime('now')) as has_cooldown
                FROM users u
                LEFT JOIN clan_members cm ON u.id = cm.user_id
                LEFT JOIN clans c ON cm.clan_id = c.id AND c.status IN ('active', 'inactive', 'frozen')
                ORDER BY c.name, cm.role DESC
                LIMIT 15 OFFSET ?
            """, (page * 15,))
            members = await cursor.fetchall()
            
            cursor = await conn.execute("SELECT COUNT(*) FROM users")
            total = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title=f"👥 All Members (Page {page + 1}/{max(1, (total + 14) // 15)})",
            color=discord.Color.purple()
        )
        
        if not members:
            embed.description = "No members found."
            return embed
        
        lines = []
        for m in members:
            discord_id = m[0]
            riot_id = m[1] or "N/A"
            is_banned = m[2]
            role = m[3]
            clan_name = m[4]
            has_cooldown = m[5] > 0
            
            # Status indicators
            status = ""
            if is_banned:
                status += "🚫"
            if has_cooldown:
                status += "⏰"
            
            # Role icon
            role_icon = {"captain": "👑", "vice": "⚔️", "member": "👤"}.get(role, "")
            
            # Clan display
            clan_display = f"**{clan_name}**" if clan_name else "🎯 Tự do"
            
            # Riot ID (truncated if needed)
            riot_display = (riot_id[:15] + "..") if len(riot_id) > 17 else riot_id
            
            lines.append(f"{status} <@{discord_id}> — `{riot_display}` {role_icon} {clan_display}")
        
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Total: {total} users | 🚫=Banned ⏰=Cooldown")
        
        self.total_pages = max(1, (total + 14) // 15)
        return embed
    
    async def get_matches_embed(self, page: int = 0) -> discord.Embed:
        """Get recent matches."""
        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT m.id, ca.name, cb.name, m.status, m.created_at,
                       CASE WHEN m.reported_winner_clan_id = m.clan_a_id THEN 'A'
                            WHEN m.reported_winner_clan_id = m.clan_b_id THEN 'B'
                            ELSE '–' END as winner
                FROM matches m
                JOIN clans ca ON m.clan_a_id = ca.id
                JOIN clans cb ON m.clan_b_id = cb.id
                ORDER BY m.created_at DESC
                LIMIT 10 OFFSET ?
            """, (page * 10,))
            matches = await cursor.fetchall()
            
            cursor = await conn.execute("SELECT COUNT(*) FROM matches")
            total = (await cursor.fetchone())[0]
        
        embed = discord.Embed(
            title=f"⚔️ Recent Matches (Page {page + 1}/{max(1, (total + 9) // 10)})",
            color=discord.Color.orange()
        )
        
        if not matches:
            embed.description = "No matches found."
            return embed
        
        description = "```\n"
        description += f"{'ID':<5} {'Clan A vs B':<25} {'W':<3} {'Status':<10}\n"
        description += "-" * 45 + "\n"
        for m in matches:
            clan_a = m[1][:10] + ".." if len(m[1]) > 12 else m[1]
            clan_b = m[2][:10] + ".." if len(m[2]) > 12 else m[2]
            status_icon = {"confirmed": "✅", "dispute": "⚠️", "created": "⏳", "reported": "📝", "resolved": "✔️", "cancelled": "❌"}.get(m[3], "❓")
            description += f"{m[0]:<5} {clan_a} vs {clan_b:<10} {m[5]:<3} {status_icon}{m[3][:8]}\n"
        description += "```"
        embed.description = description
        embed.set_footer(text=f"W = Winner (A/B) | Total: {total} matches")
        
        self.total_pages = max(1, (total + 9) // 10)
        return embed
    
    @discord.ui.select(
        placeholder="Select tab...",
        options=[
            discord.SelectOption(label="Overview", value="overview", emoji="📊", description="System stats overview"),
            discord.SelectOption(label="Clans", value="clans", emoji="🏰", description="All clans with Elo"),
            discord.SelectOption(label="Members", value="members", emoji="👥", description="All registered members"),
            discord.SelectOption(label="Matches", value="matches", emoji="⚔️", description="Recent matches"),
        ]
    )
    async def tab_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle tab selection."""
        self.current_tab = select.values[0]
        self.current_page = 0
        
        if self.current_tab == "overview":
            embed = await self.get_overview_embed()
        elif self.current_tab == "clans":
            embed = await self.get_clans_embed()
        elif self.current_tab == "members":
            embed = await self.get_members_embed()
        elif self.current_tab == "matches":
            embed = await self.get_matches_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Previous page."""
        if self.current_page > 0:
            self.current_page -= 1
        
        if self.current_tab == "clans":
            embed = await self.get_clans_embed(self.current_page)
        elif self.current_tab == "members":
            embed = await self.get_members_embed(self.current_page)
        elif self.current_tab == "matches":
            embed = await self.get_matches_embed(self.current_page)
        else:
            embed = await self.get_overview_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Next page."""
        self.current_page += 1
        if hasattr(self, 'total_pages') and self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        
        if self.current_tab == "clans":
            embed = await self.get_clans_embed(self.current_page)
        elif self.current_tab == "members":
            embed = await self.get_members_embed(self.current_page)
        elif self.current_tab == "matches":
            embed = await self.get_matches_embed(self.current_page)
        else:
            embed = await self.get_overview_embed()
        
        await interaction.response.edit_message(embed=embed, view=self)


# =============================================================================
# SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

