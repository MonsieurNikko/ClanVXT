"""
Admin Cog
Implements moderation commands including cooldown management, case handling,
system bans, clan freeze, and Elo operations.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Literal, List
from datetime import datetime, timezone, timedelta
import json

import config
from services import db, cooldowns, moderation, permissions
from services import bot_utils, elo


class AnnounceModal(discord.ui.Modal, title="📢 Soạn Thông Báo"):
    """Modal for admin to write a multiline announcement."""

    ann_title = discord.ui.TextInput(
        label="Tiêu đề thông báo",
        placeholder="Ví dụ: 🚨 CẬP NHẬT LUẬT LỆ ARENA",
        max_length=200,
        required=True
    )
    body = discord.ui.TextInput(
        label="Nội dung thông báo",
        style=discord.TextStyle.paragraph,
        placeholder="Paste nội dung thông báo ở đây...",
        max_length=3900,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("❌ Chỉ dùng trong server.", ephemeral=True)

        chat_channel = bot_utils.get_chat_channel()
        if not chat_channel:
            return await interaction.followup.send("❌ Không tìm thấy kênh #chat-arena.", ephemeral=True)

        player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
        mention_text = player_role.mention if player_role else "@player"

        title_str = self.ann_title.value.strip()
        body_str = self.body.value.strip()

        # Build full text
        full_body = f"**{title_str}**\n\n{body_str}\n\n*📢 Thông báo bởi {interaction.user.display_name}*"

        # Split into ≤1900-char chunks at newline boundaries
        MAX = 1900
        chunks = []
        remaining = full_body
        while len(remaining) > MAX:
            split_at = remaining.rfind("\n", 0, MAX)
            if split_at == -1:
                split_at = MAX
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")
        chunks.append(remaining)

        try:
            await chat_channel.send(content=f"{mention_text}\n\n{chunks[0]}")
            for chunk in chunks[1:]:
                await chat_channel.send(content=chunk)

            await interaction.followup.send(
                f"✅ Đã gửi thông báo lên {chat_channel.mention}! ({len(chunks)} tin nhắn)",
                ephemeral=True
            )
            await bot_utils.log_event(
                "ADMIN_ANNOUNCE",
                f"{interaction.user.mention} posted announcement: **{title_str}**"
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi gửi thông báo: {e}", ephemeral=True)


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
    role_group = app_commands.Group(name="role", description="Admin role management", parent=admin_group)
    matchmaking_group = app_commands.Group(name="matchmaking", description="Manage matchmaking settings", parent=admin_group)
    
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
            for kind in [cooldowns.KIND_JOIN_LEAVE, cooldowns.KIND_LOAN, cooldowns.KIND_MATCH_CREATE]:
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
    async def cooldown_set(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], kind: Literal["join_leave", "loan", "transfer_sickness", "match_create"], duration_days: int, reason: str, user: Optional[discord.User] = None, clan_name: Optional[str] = None):
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
        print(f"[ADMIN] COOLDOWN_SET: {target_name} ({target_type}) | {kind} | {duration_days} days by {interaction.user.name}. Reason: {reason}")

    @cooldown_group.command(name="clear", description="Clear cooldowns")
    @app_commands.describe(
        target_type="User or Clan",
        kind="Specific kind to clear (optional, clears all if empty)",
        user="Target user (if type is User)",
        clan_name="Target clan name (if type is Clan)"
    )
    async def cooldown_clear(self, interaction: discord.Interaction, target_type: Literal["user", "clan"], kind: Optional[Literal["join_leave", "loan", "transfer_sickness", "match_create"]] = None, user: Optional[discord.User] = None, clan_name: Optional[str] = None):
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
        print(f"[ADMIN] COOLDOWN_CLEAR: {target_name} ({target_type}) | {kind if kind else 'ALL'} by {interaction.user.name}")

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
            
            log_detail = f"Case #{case_id}: {interaction.user.mention} thực hiện **{action_type}** trên {target_info}.\nLý do: {reason}"
            await bot_utils.log_event("CASE_ACTION", log_detail)
            print(f"[MOD] CASE_ACTION: {log_detail}")
            
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
            f"Clan **{clan['name']}** được điều chỉnh Elo bởi {interaction.user.mention}.\n"
            f"• Thay đổi: `{clan['elo']}` → `{new_elo}`\n"
            f"• Lý do: {reason}"
        )
        print(f"[ADMIN] CLAN_ELO_ADJUSTED: {clan['name']} ({clan['elo']} -> {new_elo}) by {interaction.user}. Reason: {reason}")
    @clan_group.command(name="set_member", description="Force move/add a member to a clan (Admin test/fix)")
    @app_commands.describe(
        user="Member cần điều chỉnh clan",
        clan_name="Clan đích",
        role="Role nội bộ sau khi vào clan đích",
        reason="Lý do chỉnh tay (audit log)"
    )
    async def admin_set_member_clan(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        clan_name: str,
        role: Literal["member", "vice", "captain"] = "member",
        reason: str = "Admin manual test/fix",
    ):
        """Force set a user's clan membership for testing/maintenance (DB-backed)."""
        if not await self.check_mod(interaction):
            return

        target_clan = await db.get_clan_any_status(clan_name)
        if not target_clan:
            await interaction.response.send_message("❌ Clan đích không tồn tại.", ephemeral=True)
            return

        db_user = await db.get_user(str(user.id))
        if not db_user:
            await db.create_user(str(user.id), user.display_name)
            db_user = await db.get_user(str(user.id))

        if not db_user:
            await interaction.response.send_message("❌ Không thể tạo/tải user trong DB.", ephemeral=True)
            return

        current_clan = await db.get_user_clan(db_user["id"])
        old_clan_name = current_clan["name"] if current_clan else "None"
        old_role = current_clan["member_role"] if current_clan else "none"

        try:
            # If user is captain of another clan and moving away, auto-handover captain to another member.
            if current_clan and current_clan["id"] != target_clan["id"] and current_clan["member_role"] == "captain":
                async with db.get_connection() as conn:
                    cursor = await conn.execute(
                        """SELECT user_id, role FROM clan_members
                           WHERE clan_id = ? AND user_id != ?
                           ORDER BY CASE role WHEN 'vice' THEN 0 ELSE 1 END, user_id ASC
                           LIMIT 1""",
                        (current_clan["id"], db_user["id"]),
                    )
                    replacement = await cursor.fetchone()
                    if not replacement:
                        await interaction.response.send_message(
                            "❌ Không thể chuyển clan cho Captain khi clan hiện tại không có người thay thế.",
                            ephemeral=True,
                        )
                        return

                    await conn.execute(
                        "UPDATE clan_members SET role = 'captain' WHERE clan_id = ? AND user_id = ?",
                        (current_clan["id"], replacement["user_id"]),
                    )
                    await conn.execute(
                        "UPDATE clans SET captain_id = ?, updated_at = datetime('now') WHERE id = ?",
                        (replacement["user_id"], current_clan["id"]),
                    )
                    await conn.commit()

            # Membership move/add
            if current_clan and current_clan["id"] != target_clan["id"]:
                await db.move_member(db_user["id"], current_clan["id"], target_clan["id"], "member")
            elif not current_clan:
                await db.add_member(db_user["id"], target_clan["id"], "member")

            # Apply final role in target clan (handles captain safety + clans.captain_id sync)
            role_result = await db.admin_set_member_role(target_clan["id"], db_user["id"], role)
            if not role_result.get("success"):
                await interaction.response.send_message(
                    f"❌ Đã chuyển member nhưng set role thất bại: {role_result.get('reason')}",
                    ephemeral=True,
                )
                return

            # Sync Discord roles best-effort
            guild = interaction.guild or self.bot.get_guild(config.GUILD_ID)
            role_sync_note = ""
            if guild:
                discord_member = guild.get_member(user.id)
                if discord_member:
                    if current_clan and current_clan.get("discord_role_id") and current_clan["id"] != target_clan["id"]:
                        old_discord_role = guild.get_role(int(current_clan["discord_role_id"]))
                        if old_discord_role and old_discord_role in discord_member.roles:
                            await discord_member.remove_roles(old_discord_role, reason=f"Admin set_member: {reason}")

                    if target_clan.get("discord_role_id"):
                        new_discord_role = guild.get_role(int(target_clan["discord_role_id"]))
                        if new_discord_role and new_discord_role not in discord_member.roles:
                            await discord_member.add_roles(new_discord_role, reason=f"Admin set_member: {reason}")
                    
                    # Also ensure 'player' role is assigned
                    player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
                    if player_role and player_role not in discord_member.roles:
                        await discord_member.add_roles(player_role, reason=f"Admin set_member: {reason}")
                else:
                    role_sync_note = "\n⚠️ User không có trong guild, chỉ cập nhật DB."
            else:
                role_sync_note = "\n⚠️ Không lấy được guild, chỉ cập nhật DB."

            await interaction.response.send_message(
                f"✅ Đã điều chỉnh clan cho {user.mention}.\n"
                f"• Clan: **{old_clan_name}** → **{target_clan['name']}**\n"
                f"• Role: `{old_role}` → `{role_result.get('new_role')}`\n"
                f"• Lý do: {reason}"
                f"{role_sync_note}"
            )

            await bot_utils.log_event(
                "ADMIN_SET_MEMBER_CLAN",
                f"{interaction.user.mention} moved {user.mention} from '{old_clan_name}' to '{target_clan['name']}' and set role to {role_result.get('new_role')}. Reason: {reason}"
            )
            print(f"[ADMIN] SET_MEMBER_CLAN: {user.name} moved {old_clan_name} -> {target_clan['name']} | Role: {role_result.get('new_role')} by {interaction.user.name}. Reason: {reason}")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi khi điều chỉnh clan: {e}", ephemeral=True)

    @clan_group.command(name="sync_player_role", description="Gán role 'player' cho tất cả thành viên của mọi clan")
    async def admin_sync_player_role(self, interaction: discord.Interaction):
        """Sync 'player' role to all members of active/inactive clans."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("❌ Chỉ sử dụng được trong server.", ephemeral=True)
            
        player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
        if not player_role:
            return await interaction.followup.send(f"❌ Không tìm thấy role **{config.ROLE_PLAYER}**.", ephemeral=True)
            
        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT DISTINCT u.discord_id FROM users u
                JOIN clan_members cm ON u.id = cm.user_id
                JOIN clans c ON cm.clan_id = c.id
                WHERE c.status IN ('active', 'inactive', 'frozen')
            """)
            members_to_sync = await cursor.fetchall()
            
        fixed = 0
        failed = 0
        for row in members_to_sync:
            try:
                member = guild.get_member(int(row[0]))
                if member and player_role not in member.roles:
                    await member.add_roles(player_role, reason="Admin sync_player_role")
                    fixed += 1
                elif not member:
                    failed += 1
            except Exception:
                failed += 1
                
        await interaction.followup.send(f"✅ Đã đồng bộ role **{config.ROLE_PLAYER}**:\n• Đã gán: {fixed}\n• Thất bại/Không tìm thấy: {failed}", ephemeral=True)
        await bot_utils.log_event("ADMIN_SYNC_PLAYER_ROLE", f"{interaction.user.mention} synced role: {fixed} assigned.")

    @role_group.command(name="grant", description="Grant clan management role to a member (DB update)")
    @app_commands.describe(
        user="Member to grant role",
        role="Role to grant (vice/captain)",
        reason="Reason for the role grant"
    )
    async def admin_role_grant(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: Literal["vice", "captain"],
        reason: str,
    ):
        """Grant elevated internal clan role via admin override (writes to DB)."""
        if not await self.check_mod(interaction):
            return

        db_user = await db.get_user(str(user.id))
        if not db_user:
            await interaction.response.send_message("❌ User chưa đăng ký trong hệ thống DB.", ephemeral=True)
            return

        clan_data = await db.get_user_clan(db_user["id"])
        if not clan_data:
            await interaction.response.send_message("❌ User hiện không thuộc clan nào.", ephemeral=True)
            return

        result = await db.admin_set_member_role(clan_data["id"], db_user["id"], role)
        if not result.get("success"):
            reason_code = result.get("reason")
            if reason_code == "captain_demote_forbidden":
                msg = "❌ Không thể hạ Captain trực tiếp. Hãy chỉ định Captain mới trước."
            elif reason_code == "target_not_in_clan":
                msg = "❌ User không còn trong clan tại thời điểm cập nhật."
            else:
                msg = f"❌ Không thể cập nhật role. ({reason_code})"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        old_role = result.get("old_role")
        new_role = result.get("new_role")
        changed = result.get("changed", False)
        state_text = "(không đổi)" if not changed else ""

        await interaction.response.send_message(
            f"✅ Đã cấp role nội bộ cho {user.mention} trong clan **{clan_data['name']}**.\n"
            f"• Role: `{old_role}` → `{new_role}` {state_text}\n"
            f"• Lý do: {reason}"
        )

        await bot_utils.log_event(
            "ADMIN_ROLE_GRANT",
            f"{interaction.user.mention} set role for {user.mention} in clan '{clan_data['name']}': {old_role} -> {new_role}. Reason: {reason}"
        )
        print(f"[ADMIN] ROLE_GRANT: {user.name} granted {role} in {clan_data['name']} by {interaction.user.name}. Reason: {reason}")

    @role_group.command(name="remove", description="Remove elevated role (set user back to member) (DB update)")
    @app_commands.describe(
        user="Member to remove elevated role from",
        reason="Reason for removing the elevated role"
    )
    async def admin_role_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ):
        """Remove elevated role by forcing role to member via admin override (writes to DB)."""
        if not await self.check_mod(interaction):
            return

        db_user = await db.get_user(str(user.id))
        if not db_user:
            await interaction.response.send_message("❌ User chưa đăng ký trong hệ thống DB.", ephemeral=True)
            return

        clan_data = await db.get_user_clan(db_user["id"])
        if not clan_data:
            await interaction.response.send_message("❌ User hiện không thuộc clan nào.", ephemeral=True)
            return

        if clan_data["member_role"] == "captain":
            await interaction.response.send_message(
                "❌ Không thể xóa role của Captain trực tiếp. Hãy dùng `/admin role grant` để chỉ định Captain mới trước.",
                ephemeral=True,
            )
            return

        result = await db.admin_set_member_role(clan_data["id"], db_user["id"], "member")
        if not result.get("success"):
            reason_code = result.get("reason")
            await interaction.response.send_message(f"❌ Không thể cập nhật role. ({reason_code})", ephemeral=True)
            return

        old_role = result.get("old_role")
        new_role = result.get("new_role")
        changed = result.get("changed", False)
        state_text = "(không đổi)" if not changed else ""

        await interaction.response.send_message(
            f"✅ Đã xóa role nâng cao của {user.mention} trong clan **{clan_data['name']}**.\n"
            f"• Role: `{old_role}` → `{new_role}` {state_text}\n"
            f"• Lý do: {reason}"
        )

        await bot_utils.log_event(
            "ADMIN_ROLE_REMOVE",
            f"{interaction.user.mention} removed elevated role for {user.mention} in clan '{clan_data['name']}': {old_role} -> {new_role}. Reason: {reason}"
        )
        print(f"[ADMIN] ROLE_REMOVE: Management role removed from {user.name} in {clan_data['name']} by {interaction.user.name}. Reason: {reason}")

    @admin_group.command(name="elo_rollback_matches", description="Rollback Elo for matches won by a specific clan (Fair Play)")
    @app_commands.describe(clan_name="Clan to check for wins")
    async def elo_rollback_matches(self, interaction: discord.Interaction, clan_name: str):
        """View recent wins of a clan and select matches to rollback Elo."""
        if not await self.check_mod(interaction):
            return

        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message(f"❌ Clan **{clan_name}** không tồn tại.", ephemeral=True)
            return

        # Get recent wins
        matches = await db.get_won_matches_by_clan(clan["id"], limit=25)
        
        if not matches:
            await interaction.response.send_message(f"ℹ️ Clan **{clan['name']}** chưa thắng trận nào có tính điểm Elo (trong 25 trận gần nhất).", ephemeral=True)
            return

        # view defined later
        view = EloRollbackSelectView(matches, clan, interaction.user)
        await interaction.response.send_message(
            f"🔍 **Fair Play Check**: Tìm thấy {len(matches)} trận thắng của **{clan['name']}**.\n"
            "Chọn các trận đấu cần rollback Elo (hoàn điểm cho đội thua, trừ điểm đội thắng):",
            view=view,
            ephemeral=True
        )

    # =========================================================================
    # MATCH MANAGEMENT
    # =========================================================================
    
    @admin_group.command(name="match_pending", description="Xem danh sách các trận đấu đang chờ kết quả")
    async def match_pending(self, interaction: discord.Interaction):
        """List all matches stuck in 'created' or 'reported' status."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        pending = await db.get_pending_matches()
        
        if not pending:
            return await interaction.followup.send("✅ Không có trận đấu nào đang chờ kết quả.", ephemeral=True)
        
        lines = []
        for m in pending:
            fmt = f" ({m['match_format']})" if m.get('match_format') else ""
            lines.append(
                f"**#{m['id']}** — {m['clan_a_name']} vs {m['clan_b_name']}{fmt}\n"
                f"└ Status: `{m['status']}` | 🕒 {m['created_at']}"
            )
        
        embed = discord.Embed(
            title=f"📋 Trận Đấu Đang Chờ ({len(pending)})",
            description="\n\n".join(lines),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Dùng /admin match_cancel <id> để hủy trận rác")
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"[ADMIN] MATCH_PENDING: {interaction.user.name} listed {len(pending)} pending matches")

    @admin_group.command(name="match_cancel", description="Hủy trận đấu đang chờ kết quả (Admin)")
    @app_commands.describe(
        match_id="ID trận đấu cần hủy",
        reason="Lý do hủy (không bắt buộc)"
    )
    async def match_cancel(self, interaction: discord.Interaction, match_id: int, reason: str = "Admin force cancel"):
        """Force cancel a pending match."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        success = await db.force_cancel_match(match_id, reason)
        if success:
            await interaction.followup.send(
                f"✅ Đã hủy trận đấu **#{match_id}**.\nLý do: {reason}",
                ephemeral=True
            )
            log_msg = f"🗑️ {interaction.user.mention} đã hủy trận đấu **#{match_id}**. Lý do: {reason}"
            await bot_utils.log_event("MATCH_FORCE_CANCEL", log_msg)
            print(f"[ADMIN] MATCH_FORCE_CANCEL: #{match_id} cancelled by {interaction.user.name}. Reason: {reason}")
        else:
            await interaction.followup.send(
                f"❌ Không thể hủy trận **#{match_id}**. Trận này không tồn tại hoặc đã được xử lý.",
                ephemeral=True
            )

    @admin_group.command(name="match_resolve", description="Tạo và tính điểm trận đấu thủ công (Admin)")
    @app_commands.describe(
        clan_a="Tên clan A",
        clan_b="Tên clan B",
        winner="Tên clan thắng (phải trùng clan_a hoặc clan_b)",
        score_a="Số trận thắng của clan A (VD: 2)",
        score_b="Số trận thắng của clan B (VD: 1)",
        reason="Ghi chú (không bắt buộc)"
    )
    async def match_resolve(
        self, interaction: discord.Interaction,
        clan_a: str, clan_b: str, winner: str,
        score_a: int, score_b: int,
        reason: str = "Admin manual resolve"
    ):
        """Create a match record and apply Elo manually."""
        if not await self.check_mod(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        # Look up clans
        clan_a_data = await db.get_clan(clan_a)
        if not clan_a_data:
            clan_a_data = await db.get_clan_any_status(clan_a)
        if not clan_a_data:
            return await interaction.followup.send(f"❌ Không tìm thấy clan **{clan_a}**.", ephemeral=True)

        clan_b_data = await db.get_clan(clan_b)
        if not clan_b_data:
            clan_b_data = await db.get_clan_any_status(clan_b)
        if not clan_b_data:
            return await interaction.followup.send(f"❌ Không tìm thấy clan **{clan_b}**.", ephemeral=True)

        if clan_a_data["id"] == clan_b_data["id"]:
            return await interaction.followup.send("❌ Không thể tạo trận giữa cùng một clan.", ephemeral=True)

        # Determine winner
        winner_data = None
        if winner.lower() == clan_a_data["name"].lower():
            winner_data = clan_a_data
        elif winner.lower() == clan_b_data["name"].lower():
            winner_data = clan_b_data
        else:
            return await interaction.followup.send(
                f"❌ Tên clan thắng phải trùng với **{clan_a_data['name']}** hoặc **{clan_b_data['name']}**.",
                ephemeral=True
            )

        # Validate score matches winner
        if winner_data["id"] == clan_a_data["id"] and score_a <= score_b:
            return await interaction.followup.send(
                f"❌ Score không hợp lệ: **{clan_a_data['name']}** thắng nhưng score_a ({score_a}) <= score_b ({score_b}).",
                ephemeral=True
            )
        if winner_data["id"] == clan_b_data["id"] and score_b <= score_a:
            return await interaction.followup.send(
                f"❌ Score không hợp lệ: **{clan_b_data['name']}** thắng nhưng score_b ({score_b}) <= score_a ({score_a}).",
                ephemeral=True
            )

        # Get admin user record
        admin_user = await db.get_user(str(interaction.user.id))
        admin_user_id = admin_user["id"] if admin_user else 0

        # Create match in resolved status
        match_id = await db.create_admin_match(
            clan_a_id=clan_a_data["id"],
            clan_b_id=clan_b_data["id"],
            winner_clan_id=winner_data["id"],
            score_a=score_a,
            score_b=score_b,
            admin_user_id=admin_user_id,
            note=f"{reason} (by {interaction.user.display_name})"
        )

        # Apply Elo
        elo_result = await elo.apply_match_result(match_id, winner_data["id"])

        if elo_result["success"]:
            loser_name = clan_b_data["name"] if winner_data["id"] == clan_a_data["id"] else clan_a_data["name"]
            explanation = elo.format_elo_explanation_vn(elo_result)

            embed = discord.Embed(
                title="✅ Trận Đấu Đã Được Tạo & Tính Điểm",
                description=(
                    f"**{clan_a_data['name']}** vs **{clan_b_data['name']}**\n"
                    f"Match #{match_id}\n\n"
                    f"🏆 Kết quả: **{winner_data['name']}** thắng {score_a}-{score_b}\n\n"
                    f"{explanation}"
                ),
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            log_msg = (
                f"⚖️ {interaction.user.mention} tạo trận thủ công **#{match_id}**: "
                f"{clan_a_data['name']} vs {clan_b_data['name']} — "
                f"{winner_data['name']} thắng {score_a}-{score_b} "
                f"(+{elo_result.get('final_delta_a', 0)}/{elo_result.get('final_delta_b', 0)}). "
                f"Lý do: {reason}"
            )
            await bot_utils.log_event("MATCH_ADMIN_RESOLVE", log_msg)
            print(f"[ADMIN] MATCH_RESOLVE: #{match_id} created by {interaction.user.name}")
        else:
            await interaction.followup.send(
                f"⚠️ Trận #{match_id} đã tạo nhưng không thể tính Elo.\n"
                f"Lý do: {elo_result.get('reason', 'Unknown')}\n"
                f"Clans inactive: {', '.join(elo_result.get('inactive_clans', []))}\n"
                f"Clans frozen: {', '.join(elo_result.get('frozen_clans', []))}",
                ephemeral=True
            )

    # =========================================================================
    # DASHBOARD COMMAND
    # =========================================================================

    @matchmaking_group.command(name="lock", description="Temporarily lock all matchmaking challenges")
    @app_commands.describe(reason="Reason for the lock")
    async def match_lock(self, interaction: discord.Interaction, reason: str = "System maintenance"):
        """Lock matchmaking."""
        if not await self.check_mod(interaction):
            return
        
        await db.set_system_setting("matchmaking_locked", "1")
        await db.set_system_setting("matchmaking_lock_reason", reason)
        
        await interaction.response.send_message(
            f"🔒 **Đã khóa hệ thống War/Thách đấu.**\nLý do: {reason}",
            ephemeral=False 
        )
        await bot_utils.log_event("MATCHMAKING_LOCKED", f"{interaction.user.mention} locked matchmaking. Reason: {reason}")
        print(f"[ADMIN] MATCHMAKING_LOCKED by {interaction.user.name}. Reason: {reason}")

    @matchmaking_group.command(name="unlock", description="Unlock matchmaking challenges")
    async def match_unlock(self, interaction: discord.Interaction):
        """Unlock matchmaking."""
        if not await self.check_mod(interaction):
            return
        
        await db.set_system_setting("matchmaking_locked", "0")
        
        await interaction.response.send_message(
            f"🔓 **Đã mở lại hệ thống War/Thách đấu.**",
            ephemeral=False
        )
        await bot_utils.log_event("MATCHMAKING_UNLOCKED", f"{interaction.user.mention} unlocked matchmaking.")
        print(f"[ADMIN] MATCHMAKING_UNLOCKED by {interaction.user.name}")


    async def clan_name_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for clan names."""
        clans = await db.search_clans(current, limit=25)
        return [
            app_commands.Choice(name=c["name"], value=c["name"])
            for c in clans
        ]

    @matchmaking_group.command(name="create_result", description="Manually create a finished match with results (Backfill)")
    @app_commands.describe(
        clan_a_name="Name of Clan A",
        clan_b_name="Name of Clan B",
        score_a="Score of Clan A",
        score_b="Score of Clan B"
    )
    @app_commands.autocomplete(clan_a_name=clan_name_autocomplete, clan_b_name=clan_name_autocomplete)
    async def match_create_result(
        self, 
        interaction: discord.Interaction, 
        clan_a_name: str, 
        clan_b_name: str, 
        score_a: int, 
        score_b: int
    ):
        """Manually create and resolve a match (for backfilling/fixing)."""
        if not await self.check_mod(interaction):
            return

        await interaction.response.defer(ephemeral=False)
        
        # 1. Validate Clans
        clan_a = await db.get_clan_any_status(clan_a_name)
        if not clan_a:
            await interaction.followup.send(f"❌ Clan **{clan_a_name}** không tồn tại.", ephemeral=True)
            return
            
        clan_b = await db.get_clan_any_status(clan_b_name)
        if not clan_b:
            await interaction.followup.send(f"❌ Clan **{clan_b_name}** không tồn tại.", ephemeral=True)
            return
            
        if clan_a["id"] == clan_b["id"]:
            await interaction.followup.send("❌ Hai clan phải khác nhau.", ephemeral=True)
            return

        # 2. Validate Scores
        if score_a == score_b:
            await interaction.followup.send("❌ Tỉ số hòa không được hỗ trợ tính Elo.", ephemeral=True)
            return
        
        winner_id = clan_a["id"] if score_a > score_b else clan_b["id"]
        winner_name = clan_a["name"] if score_a > score_b else clan_b["name"]
        
        # 3. Create Match
        match_id = await db.create_finished_match(clan_a["id"], clan_b["id"], score_a, score_b)
        
        # 4. Apply Elo
        elo_result = await elo.apply_match_result(match_id, winner_id)
        
        if elo_result["success"]:
            # Success
            msg = (
                f"✅ **Đã tạo và xử lý Match #{match_id} (Backfill)**\n"
                f"⚔️ **{clan_a['name']}** {score_a} - {score_b} **{clan_b['name']}**\n\n"
                f"{elo.format_elo_explanation_vn(elo_result)}"
            )
            await interaction.followup.send(msg)
            
            # Log
            log_msg = f"Backfill Match #{match_id}: {clan_a['name']} vs {clan_b['name']} ({score_a}-{score_b}). Created by {interaction.user.mention}"
            await bot_utils.log_event("ADMIN_MATCH_CREATE", log_msg)
            print(f"[ADMIN] MATCH_BACKFILL: #{match_id} created by {interaction.user.name}")
        else:
            # Failed to apply Elo (e.g. frozen/banned clans)
            await interaction.followup.send(
                f"⚠️ Trận #{match_id} đã được tạo nhưng **không thể tính Elo**.\n"
                f"Lý do: {elo_result.get('reason', 'Unknown')}\n"
                f"Chi tiết: {elo_result}",
                ephemeral=True
            )
    
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

    @loan_admin_group.command(name="status", description="Xem danh sách tất cả các thành viên đang được loan")
    async def loan_status(self, interaction: discord.Interaction):
        """View all active loans."""
        if not await self.check_mod(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        
        loans = await db.get_all_active_loans()
        
        if not loans:
            await interaction.followup.send("✅ Hiện tại không có thành viên nào đang được loan.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 Danh Sách Active Loans",
            description=f"Tổng cộng: **{len(loans)}** members",
            color=discord.Color.blue()
        )

        lines = []
        now = datetime.now(timezone.utc)
        
        for loan in loans:
            # Calculate remaining time
            try:
                end_str = loan['end_date'].replace('Z', '+00:00')
                if ' ' in end_str and 'T' not in end_str:
                    end_str = end_str.replace(' ', 'T')
                end_dt = datetime.fromisoformat(end_str)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                
                remaining = end_dt - now
                days = remaining.days
                hours = remaining.seconds // 3600
                
                if remaining.total_seconds() < 0:
                    time_str = "⚠️ Đã hết hạn"
                else:
                    time_str = f"Còn **{days} ngày {hours} giờ**"
            except Exception:
                time_str = "N/A"

            member_line = f"<@{loan['member_discord_id']}>"
            clans_line = f"**{loan['lending_clan_name']}** ➡️ **{loan['borrowing_clan_name']}**"
            detail_line = f"📅 {(loan['start_date'] or '')[:10]} đến {(loan['end_date'] or '')[:10]} • {time_str}"
            
            lines.append(f"{member_line}\n{clans_line}\n{detail_line}")
        
        # Paginate if too long (simple split for now)
        chunks = [lines[i:i + 10] for i in range(0, len(lines), 10)]
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                embed.description = f"Tổng cộng: **{len(loans)}** members\n\n" + "\n\n".join(chunk)
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                extra_embed = discord.Embed(
                    description="\n\n".join(chunk),
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=extra_embed, ephemeral=True)

    # =============================================================================
    # BALANCE SYSTEM ADMIN COMMANDS (Phase 4)
    # =============================================================================
    
    balance_group = app_commands.Group(name="balance", description="Balance system management", parent=admin_group)

    @balance_group.command(name="toggle", description="Toggle a balance feature on/off")
    @app_commands.describe(
        feature="Feature key to toggle",
        enabled="Enable (True) or disable (False)"
    )
    @app_commands.choices(feature=[
        app_commands.Choice(name="Recruitment Cap", value="recruitment_cap"),
        app_commands.Choice(name="Elo Decay", value="elo_decay"),
        app_commands.Choice(name="Win Rate Modifier", value="win_rate_modifier"),
        app_commands.Choice(name="Activity Bonus", value="activity_bonus"),
        app_commands.Choice(name="Underdog Bonus", value="underdog_bonus"),
        app_commands.Choice(name="Rank Enforcement", value="rank_enforcement"),
        app_commands.Choice(name="Rank Cap", value="rank_cap"),
        app_commands.Choice(name="Rank Modifier", value="rank_modifier"),
        app_commands.Choice(name="Match Roster", value="match_roster"),
        app_commands.Choice(name="Elo Gain Cap", value="elo_gain_cap"),
    ])
    async def balance_toggle(self, interaction: discord.Interaction, feature: str, enabled: bool):
        """Toggle a balance feature."""
        if not await self.check_mod(interaction):
            return
        
        await db.toggle_balance_feature(feature, enabled)
        status = "✅ BẬT" if enabled else "❌ TẮT"
        await interaction.response.send_message(
            f"⚙️ Balance feature **{feature}**: {status}",
            ephemeral=False
        )
        await bot_utils.log_event(
            "BALANCE_TOGGLE",
            f"{interaction.user.mention} {'enabled' if enabled else 'disabled'} balance feature: **{feature}**"
        )
    
    @balance_group.command(name="status", description="View status of all balance features")
    async def balance_status(self, interaction: discord.Interaction):
        """View all balance feature statuses."""
        if not await self.check_mod(interaction):
            return
        
        features = [
            "recruitment_cap", "elo_decay", "win_rate_modifier",
            "activity_bonus", "underdog_bonus", "rank_enforcement",
            "rank_cap", "rank_modifier", "match_roster", "elo_gain_cap"
        ]
        
        lines = []
        for f in features:
            enabled = await db.is_balance_feature_enabled(f)
            icon = "✅" if enabled else "❌"
            lines.append(f"{icon} `{f}`")
        
        embed = discord.Embed(
            title="⚙️ Balance System Status",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @balance_group.command(name="set_rank", description="Đặt rank Valorant cho một thành viên (Mod only)")
    @app_commands.describe(user="Thành viên cần đặt rank")
    async def balance_set_rank(self, interaction: discord.Interaction, user: discord.Member):
        """Admin manually set a member's rank via a dropdown select menu."""
        if not await self.check_mod(interaction):
            return
        
        db_user = await db.get_user(str(user.id))
        if not db_user:
            return await interaction.response.send_message("❌ User chưa đăng ký.", ephemeral=True)
        
        clan_data = await db.get_user_clan(db_user["id"])
        if not clan_data:
            return await interaction.response.send_message("❌ User chưa có clan.", ephemeral=True)
        
        # Import rank options
        from cogs.clan import RANK_OPTIONS, RANK_SCORE_TO_NAME
        
        # Build a view with a rank select menu
        view = discord.ui.View(timeout=120)
        select = discord.ui.Select(
            placeholder=f"Chọn rank cho {user.display_name}...",
            options=[o for o in RANK_OPTIONS if o.value != "0"],  # Exclude score=0 (max 25)
            min_values=1,
            max_values=1,
        )
        
        _user_ref = user
        _db_user_ref = db_user
        _clan_ref = clan_data
        _mod_ref = interaction.user
        
        async def rank_set_callback(sel_interaction: discord.Interaction):
            rank_score = int(sel_interaction.data["values"][0])
            rank_name = RANK_SCORE_TO_NAME.get(rank_score, f"Unknown ({rank_score})")
            await db.update_member_rank(_db_user_ref["id"], _clan_ref["id"], rank_name, rank_score)
            await sel_interaction.response.edit_message(
                content=f"✅ Đã set rank **{rank_name}** cho {_user_ref.mention}.",
                view=None
            )
            await bot_utils.log_event(
                "ADMIN_SET_RANK",
                f"{_mod_ref.mention} set rank for {_user_ref.mention}: **{rank_name}** (score={rank_score})"
            )
        
        select.callback = rank_set_callback
        view.add_item(select)
        
        async def rank_noplay_callback(btn_interaction: discord.Interaction):
            rank_name = "Không chơi Valorant"
            rank_score = 0
            await db.update_member_rank(_db_user_ref["id"], _clan_ref["id"], rank_name, rank_score)
            await btn_interaction.response.edit_message(
                content=f"✅ Đã set rank **{rank_name}** cho {_user_ref.mention}.",
                view=None
            )
            await bot_utils.log_event(
                "ADMIN_SET_RANK",
                f"{_mod_ref.mention} set rank for {_user_ref.mention}: **{rank_name}** (score={rank_score})"
            )
            
        btn_noplay = discord.ui.Button(
            label="Không chơi Valorant",
            style=discord.ButtonStyle.secondary,
            emoji="➖",
        )
        btn_noplay.callback = rank_noplay_callback
        view.add_item(btn_noplay)
        
        await interaction.response.send_message(
            f"🎯 **Đặt Rank cho {user.display_name}**\n"
            f"Clan hiện tại: **{clan_data['name']}**\n\n"
            f"Chọn rank bên dưới:",
            view=view,
            ephemeral=True
        )
    
    @balance_group.command(name="clan_rank", description="View clan's average rank and undeclared members")
    @app_commands.describe(clan_name="Name of the clan")
    async def balance_clan_rank(self, interaction: discord.Interaction, clan_name: str):
        """View clan rank info."""
        if not await self.check_mod(interaction):
            return
        
        clan = await db.get_clan(clan_name)
        if not clan:
            clan = await db.get_clan_any_status(clan_name)
        if not clan:
            return await interaction.response.send_message(f"❌ Clan '{clan_name}' không tồn tại.", ephemeral=True)
        
        avg_rank = await db.get_clan_avg_rank(clan["id"])
        high_count = await db.count_high_rank_members(clan["id"])
        undeclared = await db.get_undeclared_members(clan["id"])
        
        from services.elo import RANK_SCORE_TO_NAME
        avg_name = RANK_SCORE_TO_NAME.get(round(avg_rank), f"~{avg_rank:.1f}") if avg_rank > 0 else "N/A"
        
        embed = discord.Embed(
            title=f"🎯 Rank Info — {clan['name']}",
            color=discord.Color.purple()
        )
        embed.add_field(name="Avg Rank", value=f"**{avg_name}** (Score: {avg_rank:.1f})", inline=True)
        embed.add_field(name="High Rank (Imm2+)", value=f"**{high_count}** / {config.RANK_CAP_MAX_HIGH_RANK} max", inline=True)
        
        if undeclared:
            names = ", ".join(f"<@{m['discord_id']}>" for m in undeclared[:10])
            embed.add_field(name=f"⚠️ Undeclared ({len(undeclared)})", value=names, inline=False)
        else:
            embed.add_field(name="✅ Declaration", value="All members declared", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @balance_group.command(name="adjust_elo", description="Manually adjust a clan's Elo with reason")
    @app_commands.describe(
        clan_name="Clan name",
        amount="Elo change (positive or negative)",
        reason="Reason for adjustment"
    )
    async def balance_adjust_elo(self, interaction: discord.Interaction, clan_name: str, amount: int, reason: str):
        """Admin Elo adjustment with logging."""
        if not await self.check_mod(interaction):
            return
        
        clan = await db.get_clan(clan_name)
        if not clan:
            clan = await db.get_clan_any_status(clan_name)
        if not clan:
            return await interaction.response.send_message(f"❌ Clan '{clan_name}' không tồn tại.", ephemeral=True)
        
        old_elo = clan["elo"]
        new_elo = max(0, old_elo + amount)
        
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE clans SET elo = ?, updated_at = datetime('now') WHERE id = ?",
                (new_elo, clan["id"])
            )
            await conn.execute(
                """INSERT INTO elo_history (clan_id, old_elo, new_elo, change_amount, reason)
                   VALUES (?, ?, ?, ?, ?)""",
                (clan["id"], old_elo, new_elo, amount, f"admin_adjust: {reason}")
            )
            await conn.commit()
        
        await interaction.response.send_message(
            f"✅ Adjusted Elo for **{clan['name']}**: {old_elo} → {new_elo} ({amount:+d})\nReason: {reason}",
            ephemeral=False
        )
        await bot_utils.log_event(
            "ADMIN_ELO_ADJUST",
            f"{interaction.user.mention} adjusted Elo for **{clan['name']}**: {old_elo} → {new_elo} ({amount:+d}). Reason: {reason}"
        )
    
    @balance_group.command(name="run_weekly", description="Manually trigger weekly balance task")
    async def balance_run_weekly(self, interaction: discord.Interaction):
        """Force run the weekly balance task."""
        if not await self.check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Reset the gate so it runs immediately
        await db.set_system_setting("last_weekly_run", "")
        
        # Import and call the task directly
        from main import weekly_balance_task
        # We can't call it directly, but we can do the logic inline
        from datetime import datetime, timezone
        
        results = []
        
        # Elo Decay
        if await db.is_balance_feature_enabled("elo_decay"):
            decayed = await db.get_clans_for_decay()
            for clan in decayed:
                await db.apply_elo_decay(clan["id"], config.ELO_DECAY_AMOUNT)
            results.append(f"📉 Elo Decay: {len(decayed)} clans")
        else:
            results.append("📉 Elo Decay: DISABLED")
        
        # Activity Bonus
        if await db.is_balance_feature_enabled("activity_bonus"):
            all_clans = await db.get_all_active_clans()
            bonus_count = 0
            for clan in all_clans:
                # Same check as main.py: under 1000 elo, >= 3 matches
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
                                (clan["id"], clan["elo"], clan["elo"] + bonus, bonus, "activity_bonus_manual")
                            )
                            await conn.commit()
                        bonus_count += 1
            results.append(f"📈 Activity Bonus: {bonus_count} clans (+{config.ACTIVITY_BONUS_AMOUNT} Elo)")
        else:
            results.append("📈 Activity Bonus: DISABLED")
        
        # Update run time
        from datetime import datetime, timezone
        await db.set_system_setting("last_weekly_run", datetime.now(timezone.utc).isoformat())

        embed = discord.Embed(
            title="Manual Weekly Balance Task",
            description="\n".join(results),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        await bot_utils.log_event(
            "BALANCE_WEEKLY_MANUAL",
            f"{interaction.user.mention} manually triggered weekly balance task"
        )

    @balance_group.command(name="activity_info", description="View which clans are receiving the weekly activity bonus")
    async def balance_activity_info(self, interaction: discord.Interaction):
        """Show clans eligible for activity bonus and their match counts."""
        if not await self.check_mod(interaction):
            return
            
        await interaction.response.defer(ephemeral=False)
        
        all_clans = await db.get_all_active_clans()
        eligible_clans = []
        ineligible_clans = []
        
        for clan in all_clans:
            activity = await db.get_clan_activity_count(clan["id"])
            if clan["elo"] < config.ACTIVITY_BONUS_ELO_THRESHOLD:
                if activity >= config.ACTIVITY_BONUS_MIN_MATCHES:
                    eligible_clans.append(f"✅ **{clan['name']}**: {activity} trận (Đủ điều kiện nhận +{config.ACTIVITY_BONUS_AMOUNT})")
                else:
                    ineligible_clans.append(f"❌ **{clan['name']}**: {activity}/{config.ACTIVITY_BONUS_MIN_MATCHES} trận (Chưa đủ trận)")
            else:
                ineligible_clans.append(f"⛔ **{clan['name']}**: {clan['elo']} Elo (Đã vượt {config.ACTIVITY_BONUS_ELO_THRESHOLD} Elo)")
                
        # Format output
        desc = f"**Cấu hình**: Tối thiểu `{config.ACTIVITY_BONUS_MIN_MATCHES}` trận/tuần, mức Elo dưới `{config.ACTIVITY_BONUS_ELO_THRESHOLD}`\n\n"
        
        if eligible_clans:
            desc += "**ĐANG NHẬN THƯỞNG:**\n" + "\n".join(eligible_clans) + "\n\n"
        else:
            desc += "**ĐANG NHẬN THƯỞNG:** Không có clan nào đủ điều kiện.\n\n"
            
        if ineligible_clans:
            desc += "**KHÔNG ĐƯỢC NHẬN:**\n" + "\n".join(ineligible_clans)
            
        # Truncate if too long
        if len(desc) > 4000:
            desc = desc[:4000] + "...\n*(Danh sách quá dài đã bị cắt bớt)*"
            
        embed = discord.Embed(
            title="📈 Activity Bonus Status",
            description=desc,
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)

    # =============================================================================
    # ANNOUNCE COMMAND
    # =============================================================================

    @admin_group.command(name="announce", description="Mở form soạn thông báo và đăng lên #chat-arena với @player")
    async def admin_announce(self, interaction: discord.Interaction):
        """Open an announcement modal and post to #chat-arena tagging @player."""
        if not await self.check_mod(interaction):
            return
        # Send a Modal so the user can paste multiline text with proper newlines
        await interaction.response.send_modal(AnnounceModal())



# =============================================================================
# ELO ROLLBACK VIEW
# =============================================================================

class EloRollbackSelectView(discord.ui.View):
    def __init__(self, matches: list, target_clan: dict, author: discord.User):
        super().__init__(timeout=180)
        self.matches = matches
        self.target_clan = target_clan
        self.author = author
        self.selected_matches = []

        # Create Select Menu
        options = []
        for m in matches:
            # Determine opponent (Victim)
            opponent_name = m["clan_b_name"] if m["clan_a_id"] == target_clan["id"] else m["clan_a_name"]
            
            # Formatting timestamp
            dt = datetime.fromisoformat(m["created_at"])
            date_str = dt.strftime("%d/%m")
            
            # Points gained by winner (target_clan)
            # We need to check which delta belongs to target clan
            points = 0
            if m["clan_a_id"] == target_clan["id"]:
                points = m["final_delta_a"]
            else:
                points = m["final_delta_b"]
                
            label = f"{date_str} vs {opponent_name}"
            desc = f"Match #{m['id']} | +{points} Elo won"
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(m["id"])
            ))

        # Split into chunks if > 25 (though DB limits to 25)
        # Discord allows max 25 options per select
        self.select = discord.ui.Select(
            placeholder="Chọn các trận đấu cần Rollback...",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("Không phải lệnh của bạn.", ephemeral=True)
        
        self.selected_matches = self.select.values
        await interaction.response.defer(ephemeral=True)
        
        # Disable view
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

        # Process Rollbacks
        results = []
        mod_user = await db.get_user(str(self.author.id))
        mod_id = mod_user["id"] if mod_user else 0
        
        for match_id_str in self.selected_matches:
            match_id = int(match_id_str)
            res = await moderation.rollback_match_elo(match_id, mod_id)
            
            if res["success"]:
                # Parse details for notification
                victim_info = None
                for d in res["rollback_details"]:
                    if d["clan_id"] != self.target_clan["id"]:
                        victim_info = d
                        break
                
                results.append(f"✅ Match #{match_id}: Rolled back.")
                
                # Notify Victim
                if victim_info:
                    try:
                        victim_clan = await db.get_clan_by_id(victim_info["clan_id"])
                        if victim_clan and victim_clan.get("discord_channel_id"):
                            guild = interaction.guild
                            chan = guild.get_channel(int(victim_clan["discord_channel_id"]))
                            if chan:
                                embed = discord.Embed(
                                    title="⚖️ Fair Play Update (Hoàn điểm Elo)",
                                    description=(
                                        f"Kết quả trận đấu **#{match_id}** đã bị hủy bỏ do phát hiện vi phạm từ đối thủ.\n\n"
                                        f"✅ **Điểm Elo được hoàn trả**: {victim_info['after']} (Hồi phục {victim_info['reverted_change']:+d})\n"
                                        f"Chúng tôi cam kết môi trường thi đấu công bằng cho ClanVXT."
                                    ),
                                    color=discord.Color.green()
                                )
                                await chan.send(embed=embed)
                    except Exception as e:
                        print(f"[ROLLBACK] Failed to notify victim clan {victim_info['clan_id']}: {e}")

            else:
                results.append(f"❌ Match #{match_id}: Failed ({res['reason']})")

        # Summary Report
        embed = discord.Embed(title="🔄 Elo Rollback Report", color=discord.Color.orange())
        embed.description = "\n".join(results)
        await interaction.followup.send(embed=embed, ephemeral=True)


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

