"""
Clan Commands Cog
Implements all clan-related slash commands and UI components
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import config
from services import db, cooldowns

# Import main module helpers (will be available after bot loads this cog)
# Import main module helpers (will be available after bot loads this cog)
from services import bot_utils


# =============================================================================
# ERROR MESSAGES (from SPEC.md)
# =============================================================================

ERRORS = {
    "ALREADY_IN_CLAN": "Bạn đã ở trong một clan rồi.",
    "COOLDOWN_ACTIVE": "Bạn đang trong thời gian chờ. Còn lại: {days} ngày.",
    "NAME_TAKEN": "Tên clan '{name}' đã được sử dụng.",
    "NAME_INVALID": "Tên clan chứa ký tự không hợp lệ hoặc từ cấm.",
    "NOT_VERIFIED": "Bạn cần role '{role}' để tham gia hệ thống clan.",
    "PERMISSION_DENIED": "Bạn không có quyền thực hiện lệnh này.",
    "NOT_IN_CLAN": "Bạn không ở trong clan nào.",
    "NOT_CAPTAIN": "Chỉ Captain của clan mới có thể thực hiện lệnh này.",
    "TARGET_NOT_IN_CLAN": "Người dùng này không thuộc clan của bạn.",
    "CANNOT_KICK_SELF": "Bạn không thể tự kick chính mình. Hãy dùng `/clan leave`.",
    "CANNOT_KICK_CAPTAIN": "Bạn không thể kick Captain của clan.",
    "NO_PENDING_REQUEST": "Bạn không có yêu cầu ứng tuyển nào đang chờ.",
    "CLAN_NOT_FOUND": "Không tìm thấy clan.",
    "NOT_MOD": "Bạn cần role '{role}' để sử dụng lệnh này.",
    "BOT_MISSING_PERMS": "Bot thiếu quyền: {perms}. Vui lòng cấp quyền Manage Roles và Manage Channels.",
    "ROLE_HIERARCHY": "Không thể tạo role - Role của bot phải nằm trên role clan trong danh sách Role.",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def check_verified(interaction: discord.Interaction) -> bool:
    """Check if user has the verified role."""
    user_role_names = [role.name for role in interaction.user.roles]
    if config.ROLE_VERIFIED in user_role_names:
        return True
    await interaction.response.send_message(
        ERRORS["NOT_VERIFIED"].format(role=config.ROLE_VERIFIED),
        ephemeral=True
    )
    return False


async def check_mod(interaction: discord.Interaction) -> bool:
    """Check if user has the mod role."""
    user_role_names = [role.name for role in interaction.user.roles]
    if config.ROLE_MOD in user_role_names:
        return True
    await interaction.response.send_message(
        ERRORS["NOT_MOD"].format(role=config.ROLE_MOD),
        ephemeral=True
    )
    return False


async def get_user_db(discord_id: str) -> Optional[dict]:
    """Get user from database, returns None if not registered."""
    return await db.get_user(discord_id)


async def ensure_user_registered(interaction: discord.Interaction) -> Optional[dict]:
    """Ensure user is registered in DB. Auto-registers if not. Returns user dict."""
    user = await get_user_db(str(interaction.user.id))
    if not user:
        # Auto-register the user
        discord_id = str(interaction.user.id)
        await db.create_user(discord_id, f"{interaction.user.name}#0000")
        user = await get_user_db(discord_id)
    return user


def check_cooldown(cooldown_until: Optional[str]) -> Optional[int]:
    """Check if user is in cooldown. Returns days remaining or None."""
    if not cooldown_until:
        return None
    try:
        cooldown_dt = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if cooldown_dt > now:
            return (cooldown_dt - now).days + 1
    except Exception:
        pass
    return None


# =============================================================================
# UI COMPONENTS: Create Flow
# =============================================================================

class ClanCreateModal(discord.ui.Modal, title="Create Clan"):
    """Modal for entering clan name and description."""
    
    clan_name = discord.ui.TextInput(
        label="Clan Name",
        placeholder="Enter your clan name (unique, 3-32 characters)",
        min_length=3,
        max_length=32,
        required=True
    )
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Describe your clan (optional)",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.clan_name.value.strip()
        
        # Check if name is taken
        existing = await db.get_clan(name)
        if existing:
            await interaction.response.send_message(
                ERRORS["NAME_TAKEN"].format(name=name),
                ephemeral=True
            )
            return
        
        # Show member select
        view = MemberSelectView(name, self.description.value or "")
        await interaction.response.send_message(
            f"**Creating Clan:** {name}\n\nSelect **4 members** to invite (you + 4 = 5 total):",
            view=view,
            ephemeral=True
        )


class MemberSelectView(discord.ui.View):
    """View with member select for choosing 5 clan members."""
    
    def __init__(self, clan_name: str, description: str):
        super().__init__(timeout=300)  # 5 min timeout
        self.clan_name = clan_name
        self.description = description
        self.selected_members: List[discord.Member] = []
    
    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select 4 members to invite...",
        min_values=4,
        max_values=4
    )
    async def member_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        self.selected_members = select.values
        
        # Validate all selected members
        errors = []
        verified_role = bot_utils.get_verified_role()
        
        for member in self.selected_members:
            # Can't select self
            if member.id == interaction.user.id:
                errors.append(f"• You cannot select yourself")
                continue
            
            # Check if member has verified role
            member_role_names = [r.name for r in member.roles]
            if config.ROLE_VERIFIED not in member_role_names:
                errors.append(f"• {member.mention} doesn't have the {config.ROLE_VERIFIED} role")
                continue
            
            # Auto-register member if not registered
            user = await db.get_user(str(member.id))
            if not user:
                await db.create_user(str(member.id), f"{member.name}#0000")
                user = await db.get_user(str(member.id))
            
            # Check if member is already in a clan
            member_clan = await db.get_user_clan(user["id"])
            if member_clan:
                errors.append(f"• {member.mention} is already in clan '{member_clan['name']}'")
                continue
            
            # Check cooldown
            days = check_cooldown(user.get("cooldown_until"))
            if days:
                errors.append(f"• {member.mention} is in cooldown ({days} days remaining)")
        
        if errors:
            await interaction.response.edit_message(
                content=f"**Cannot create clan.** Fix these issues:\n" + "\n".join(errors),
                view=self
            )
            return
        
        # All good - show confirm button
        self.clear_items()
        self.add_item(ConfirmCreateButton(self.clan_name, self.description, self.selected_members))
        self.add_item(CancelButton())
        
        member_list = "\n".join(f"• {m.mention}" for m in self.selected_members)
        await interaction.response.edit_message(
            content=f"**Clan Name:** {self.clan_name}\n\n**Members to invite:**\n{member_list}\n\nClick **Confirm** to send invitations.",
            view=self
        )


class ConfirmCreateButton(discord.ui.Button):
    """Button to confirm clan creation and send invitations."""
    
    def __init__(self, clan_name: str, description: str, members: List[discord.Member]):
        super().__init__(label="Confirm & Send Invitations", style=discord.ButtonStyle.green)
        self.clan_name = clan_name
        self.description = description
        self.members = members
    
    async def callback(self, interaction: discord.Interaction):
        # Defer first to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        # Get captain from DB (auto-register if needed)
        captain = await db.get_user(str(interaction.user.id))
        if not captain:
            await db.create_user(str(interaction.user.id), f"{interaction.user.name}#0000")
            captain = await db.get_user(str(interaction.user.id))
        
        # Create clan in waiting_accept status
        clan_id = await db.create_clan(self.clan_name, captain["id"])
        
        # Calculate expiry (48h from now)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=config.CLAN_CREATE_TIMEOUT_HOURS)).isoformat()
        
        # Create requests for each member
        dm_failures = []
        for member in self.members:
            user = await db.get_user(str(member.id))
            if not user:
                await db.create_user(str(member.id), f"{member.name}#0000")
                user = await db.get_user(str(member.id))
            
            # Create request in DB
            await db.create_create_request(clan_id, user["id"], expires_at)
            
            # Send DM with accept/decline buttons
            try:
                view = AcceptDeclineView(clan_id, user["id"], self.clan_name, interaction.user.display_name)
                await member.send(
                    f"🏰 **Clan Invitation**\n\n"
                    f"**{interaction.user.display_name}** has invited you to join clan **{self.clan_name}**!\n\n"
                    f"You have **48 hours** to respond. All 4 invited members must accept for the clan to be created.\n\n"
                    f"Click a button below to respond:",
                    view=view
                )
            except discord.Forbidden:
                dm_failures.append(member.mention)
        
        # Log event
        member_mentions = ", ".join(m.mention for m in self.members)
        await bot_utils.log_event(
            "CLAN_CREATE_REQUEST",
            f"Captain: {interaction.user.mention}, Clan: '{self.clan_name}', Members: {member_mentions}"
        )
        
        # Response
        msg = f"✅ **Clan '{self.clan_name}' creation started!**\n\n" \
              f"Invitations have been sent to all 4 members.\n" \
              f"They have **48 hours** to accept. The clan will be submitted for mod approval once everyone accepts."
        
        if dm_failures:
            msg += f"\n\n⚠️ Could not DM: {', '.join(dm_failures)} (they may have DMs disabled)"
        
        await interaction.followup.send(content=msg, ephemeral=True)


class CancelButton(discord.ui.Button):
    """Generic cancel button."""
    
    def __init__(self):
        super().__init__(label="Cancel", style=discord.ButtonStyle.grey)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Clan creation cancelled.", view=None)


class AcceptDeclineView(discord.ui.View):
    """View for accepting/declining clan invitation (sent via DM)."""
    
    def __init__(self, clan_id: int, user_id: int, clan_name: str, captain_name: str):
        super().__init__(timeout=None)  # Persistent view
        self.clan_id = clan_id
        self.user_id = user_id
        self.clan_name = clan_name
        self.captain_name = captain_name
        
        # Add buttons with dynamic custom_ids
        accept_btn = discord.ui.Button(
            label="Accept",
            style=discord.ButtonStyle.green,
            custom_id=f"clan_accept:{clan_id}:{user_id}"
        )
        accept_btn.callback = self.accept_callback
        self.add_item(accept_btn)
        
        decline_btn = discord.ui.Button(
            label="Decline",
            style=discord.ButtonStyle.red,
            custom_id=f"clan_decline:{clan_id}:{user_id}"
        )
        decline_btn.callback = self.decline_callback
        self.add_item(decline_btn)
    
    async def accept_callback(self, interaction: discord.Interaction):
        # Check if request still exists and is pending
        request = await db.get_user_pending_request(self.user_id)
        if not request or request["clan_id"] != self.clan_id:
            await interaction.response.edit_message(
                content="This invitation has expired or been cancelled.",
                view=None
            )
            return
        
        # Accept the request
        await db.accept_create_request(self.clan_id, self.user_id)
        
        # Add user to clan_members
        await db.add_member(self.user_id, self.clan_id, "member")
        
        # Check if all 4 accepted
        all_accepted = await db.check_all_accepted(self.clan_id)
        
        await interaction.response.edit_message(
            content=f"✅ You have **accepted** the invitation to join **{self.clan_name}**!",
            view=None
        )
        
        if all_accepted:
            # Update clan status to pending_approval
            await db.update_clan_status(self.clan_id, "pending_approval")
            
            # Notify captain via DM
            try:
                clan = await db.get_clan_by_id(self.clan_id)
                if clan:
                    # Get captain's discord_id from clan_members
                    members = await db.get_clan_members(self.clan_id)
                    captain_member = next((m for m in members if m["role"] == "captain"), None)
                    if captain_member:
                        captain_discord_id = captain_member["discord_id"]
                        # Get discord user
                        captain_user = interaction.client.get_user(int(captain_discord_id))
                        if not captain_user:
                            captain_user = await interaction.client.fetch_user(int(captain_discord_id))
                        if captain_user:
                            await captain_user.send(
                                f"🎉 **Great news!**\n\n"
                                f"All 4 invited members have **accepted** your clan **{self.clan_name}**!\n\n"
                                f"Your clan is now **pending mod approval**. A moderator will review and approve it soon."
                            )
            except Exception as e:
                print(f"Failed to DM captain: {e}")
            
            # Alert mod-log
            await bot_utils.log_event(
                "CLAN_PENDING_APPROVAL",
                f"Clan '{self.clan_name}' - All 4 invited members accepted. Awaiting mod approval. (ID: {self.clan_id})"
            )
    
    async def decline_callback(self, interaction: discord.Interaction):
        # Check if request still exists
        request = await db.get_user_pending_request(self.user_id)
        if not request or request["clan_id"] != self.clan_id:
            await interaction.response.edit_message(
                content="This invitation has expired or been cancelled.",
                view=None
            )
            return
        
        # Decline the request
        await db.decline_create_request(self.clan_id, self.user_id)
        
        # Delete the entire clan creation
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (self.clan_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (self.clan_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (self.clan_id,))
            await conn.commit()
        
        await interaction.response.edit_message(
            content=f"❌ You have **declined** the invitation to join **{self.clan_name}**.\n"
                    f"The clan creation has been cancelled.",
            view=None
        )
        
        await bot_utils.log_event(
            "CLAN_CANCELLED",
            f"Clan '{self.clan_name}' creation cancelled - {interaction.user.mention} declined invitation"
        )


class PersistentAcceptDeclineView(discord.ui.View):
    """Persistent view handler for clan accept/decline buttons (registered on startup)."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="clan_accept_persistent")
    async def accept_placeholder(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This is just a placeholder - actual handling is done via on_interaction
        pass
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="clan_decline_persistent")
    async def decline_placeholder(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass


class InviteAcceptDeclineView(discord.ui.View):
    """View for accepting/declining clan invitation to an existing active clan (sent via DM)."""
    
    def __init__(self, invite_id: int, clan_id: int, user_id: int, clan_name: str, invited_by_name: str):
        super().__init__(timeout=None)  # Persistent view
        self.invite_id = invite_id
        self.clan_id = clan_id
        self.user_id = user_id
        self.clan_name = clan_name
        self.invited_by_name = invited_by_name
        
        # Add buttons with dynamic custom_ids
        accept_btn = discord.ui.Button(
            label="Accept",
            style=discord.ButtonStyle.green,
            custom_id=f"invite_accept:{invite_id}:{user_id}"
        )
        accept_btn.callback = self.accept_callback
        self.add_item(accept_btn)
        
        decline_btn = discord.ui.Button(
            label="Decline",
            style=discord.ButtonStyle.red,
            custom_id=f"invite_decline:{invite_id}:{user_id}"
        )
        decline_btn.callback = self.decline_callback
        self.add_item(decline_btn)
    
    async def accept_callback(self, interaction: discord.Interaction):
        # Check if invite still exists and is pending
        invite = await db.get_invite_by_id(self.invite_id)
        if not invite or invite["status"] != "pending":
            await interaction.response.edit_message(
                content="Lời mời này đã hết hạn hoặc bị hủy.",
                view=None
            )
            return
        
        # Get user record (auto-register if needed)
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await db.create_user(str(interaction.user.id), f"{interaction.user.name}#0000")
            user = await db.get_user(str(interaction.user.id))
        
        # Check if user is already in a clan
        existing_clan = await db.get_user_clan(user["id"])
        if existing_clan:
            await interaction.response.edit_message(
                content=f"❌ Bạn đã ở trong clan **{existing_clan['name']}** rồi. Hãy rời clan trước khi tham gia clan khác.",
                view=None
            )
            return
        
        # Check cooldown
        if user.get("cooldown_until"):
            from datetime import datetime, timezone
            cooldown = datetime.fromisoformat(user["cooldown_until"].replace('Z', '+00:00'))
            if cooldown > datetime.now(timezone.utc):
                await interaction.response.edit_message(
                    content=f"❌ Bạn đang trong thời gian chờ đến **{cooldown.strftime('%Y-%m-%d %H:%M')} UTC**.",
                    view=None
                )
                return
        
        # Accept the invite
        success = await db.accept_invite(self.invite_id)
        if not success:
            await interaction.response.edit_message(
                content="Không thể xử lý lời mời. Vui lòng thử lại.",
                view=None
            )
            return
        
        # Add user to clan
        await db.add_member(user["id"], self.clan_id, "member")
        
        # Assign Discord role if exists
        clan = await db.get_clan_by_id(self.clan_id)
        if clan and clan.get("discord_role_id") and interaction.guild:
            try:
                role = interaction.guild.get_role(int(clan["discord_role_id"]))
                if role:
                    member = interaction.guild.get_member(interaction.user.id)
                    if member:
                        await member.add_roles(role)
            except Exception as e:
                print(f"[DEBUG] Failed to assign role: {e}")
        
        await interaction.response.edit_message(
            content=f"✅ Bạn đã tham gia clan **{self.clan_name}** thành công!",
            view=None
        )
        
        await bot_utils.log_event(
            "MEMBER_JOINED",
            f"{interaction.user.mention} joined clan '{self.clan_name}' via invite from {self.invited_by_name}"
        )
    
    async def decline_callback(self, interaction: discord.Interaction):
        # Check if invite still exists and is pending
        invite = await db.get_invite_by_id(self.invite_id)
        if not invite or invite["status"] != "pending":
            await interaction.response.edit_message(
                content="Lời mời này đã hết hạn hoặc bị hủy.",
                view=None
            )
            return
        
        # Decline the invite
        await db.decline_invite(self.invite_id)
        
        await interaction.response.edit_message(
            content=f"❌ Bạn đã **từ chối** lời mời tham gia **{self.clan_name}**.",
            view=None
        )
        
        await bot_utils.log_event(
            "INVITE_DECLINED",
            f"{interaction.user.mention} declined invite to clan '{self.clan_name}'"
        )


# =============================================================================
# COG DEFINITION
# =============================================================================

class ClanCog(commands.Cog):
    """Cog containing all clan-related commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle persistent button interactions for clan invites."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id.startswith("clan_accept:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                clan_id = int(parts[1])
                user_id = int(parts[2])
                await self.handle_clan_accept(interaction, clan_id, user_id)
                return
        
        if custom_id.startswith("clan_decline:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                clan_id = int(parts[1])
                user_id = int(parts[2])
                await self.handle_clan_decline(interaction, clan_id, user_id)
                return

    async def handle_clan_accept(self, interaction: discord.Interaction, clan_id: int, user_id: int):
        """Handle clan accept button click."""
        discord_user = interaction.user
        print(f"[DEBUG] @{discord_user.name} (DB ID: {user_id}) bấm ACCEPT cho Clan ID {clan_id}")
        
        # Check if request exists (any status) to see if we've already processed it
        request = await db.get_user_request_any_status(clan_id, user_id)
        
        if not request:
            print(f"[DEBUG] Không tìm thấy yêu cầu cho @{discord_user.name} trong clan {clan_id}")
            await interaction.response.edit_message(
                content="Yêu cầu ứng tuyển này đã hết hạn hoặc bị hủy.",
                view=None
            )
            return

        # Get clan name for messages
        clan = await db.get_clan_by_id(clan_id)
        clan_name = clan["name"] if clan else "Unknown"

        # If already accepted but clan still waiting_accept, we might be recovering from a crash
        # or it's a double click. Either way, we proceed to check completion.
        if request["status"] == "accepted":
            print(f"[DEBUG] @{discord_user.name} đã accept rồi. Tiến hành kiểm tra hoàn thành...")
        elif request["status"] == "pending":
            print(f"[DEBUG] Đang xử lý ACCEPT cho @{discord_user.name}...")
            # Accept the request
            await db.accept_create_request(clan_id, user_id)
            # Add user to clan_members (idempotent)
            await db.add_member(user_id, clan_id, "member")
        else:
            print(f"[DEBUG] Yêu cầu của @{discord_user.name} đang ở trạng thái: '{request['status']}'.")
            await interaction.response.edit_message(
                content=f"Yêu cầu của bạn đang ở trạng thái: **{request['status']}**.",
                view=None
            )
            return
        
        # Check if all 4 accepted
        all_accepted = await db.check_all_accepted(clan_id)
        print(f"[DEBUG] Clan '{clan_name}' (ID: {clan_id}) - Đủ 4 người: {all_accepted}")
        
        # Only acknowledge on the interaction if it hasn't been acknowledged yet
        # If the interaction was a double-click, it might already be acknowledged
        try:
            await interaction.response.edit_message(
                content=f"✅ Bạn đã **chấp nhận** tham gia clan **{clan_name}**!",
                view=None
            )
        except (discord.errors.InteractionResponded, discord.errors.HTTPException):
            # Interaction already handled by another listener or timed out
            pass
        
        if all_accepted:
            # Check current clan status to avoid redundant notifications
            if clan and clan["status"] == "waiting_accept":
                print(f"[DEBUG] Finalizing clan {clan_id} ('{clan_name}'). Moving to pending_approval.")
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
                            f"🎉 **Tin vui!**\n\n"
                            f"Tất cả 4 thành viên được mời đã **chấp nhận** tham gia clan **{clan_name}** của bạn!\n\n"
                            f"Clan của bạn hiện đang **chờ Mod phê duyệt**. Moderator sẽ xem xét và phê duyệt sớm."
                        )
            except Exception as e:
                print(f"Failed to DM captain: {e}")
            
            # Alert mod-log
            await bot_utils.log_event(
                "CLAN_PENDING_APPROVAL",
                f"Clan '{clan_name}' - All 4 invited members accepted. Awaiting mod approval. (ID: {clan_id})"
            )

    async def handle_clan_decline(self, interaction: discord.Interaction, clan_id: int, user_id: int):
        """Handle clan decline button click."""
        discord_user = interaction.user
        print(f"[DEBUG] @{discord_user.name} (DB ID: {user_id}) bấm DECLINE cho Clan ID {clan_id}")
        # Check if request exists (any status)
        request = await db.get_user_request_any_status(clan_id, user_id)
        
        if not request:
            print(f"[DEBUG] Không tìm thấy yêu cầu cho @{discord_user.name} trong clan {clan_id}")
            await interaction.response.edit_message(
                content="Lời mời này đã hết hạn hoặc đã bị hủy.",
                view=None
            )
            return
        
        # Get clan name for messages
        clan = await db.get_clan_by_id(clan_id)
        clan_name = clan["name"] if clan else "Unknown"
        
        print(f"[DEBUG] @{discord_user.name} từ chối - Hủy tạo clan '{clan_name}'...")
        # Decline the request
        await db.decline_create_request(clan_id, user_id)
        
        # Delete the entire clan creation
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
            await conn.commit()
        
        await interaction.response.edit_message(
            content=f"❌ Bạn đã **từ chối** lời mời tham gia **{clan_name}**.\n"
                    f"Việc tạo clan đã bị hủy bỏ.",
            view=None
        )
        
        await bot_utils.log_event(
            "CLAN_CANCELLED",
            f"Clan '{clan_name}' creation cancelled - {interaction.user.mention} declined invitation"
        )
    
    # =========================================================================
    # USER COMMANDS
    # =========================================================================
    
    clan_group = app_commands.Group(name="clan", description="Clan management commands")
    
    @clan_group.command(name="help", description="Show available commands based on your role")
    async def clan_help(self, interaction: discord.Interaction):
        """Show help with commands based on user's role."""
        # Check roles by name (more reliable)
        user_role_names = [role.name for role in interaction.user.roles]
        is_mod = config.ROLE_MOD in user_role_names
        is_verified = config.ROLE_VERIFIED in user_role_names
        
        # Get user's clan role
        user = await db.get_user(str(interaction.user.id))
        clan_role = None
        if user:
            clan_data = await db.get_user_clan(user["id"])
            if clan_data:
                clan_role = clan_data.get("member_role")
        
        embed = discord.Embed(
            title="🏰 Hệ Thống Clan - Hướng Dẫn",
            color=discord.Color.blue()
        )
        
        # Basic commands (everyone)
        basic_cmds = """
`/clan info [tên]` - Xem thông tin của một clan
`/clan help` - Hiển thị hướng dẫn này
"""
        embed.add_field(name="📋 Lệnh Cơ Bản", value=basic_cmds, inline=False)
        
        # Verified user commands
        if is_verified:
            user_cmds = """
`/clan create` - Tạo clan mới (mở modal, chọn 4 người)
`/clan leave` - Rời khỏi clan hiện tại (cooldown 14 ngày)
• **Lời mời clan**: Nhận và phản hồi qua **DM** (nút Accept/Decline)
"""
            embed.add_field(name="👤 Lệnh Thành Viên", value=user_cmds, inline=False)
        
        # Match commands (any clan member)
        if clan_role:
            match_cmds = """
`/match create <tên_clan_đối_thủ> [ghi_chú]` - Tạo trận đấu
• Nút **Báo Thắng**: Chỉ người tạo trận mới có thể bấm
• Nút **Hủy**: Hủy trận (trước khi báo kết quả)
• Sau khi báo: Clan đối thủ bấm **Xác Nhận** hoặc **Tranh Chấp**
"""
            embed.add_field(name="⚔️ Lệnh Trận Đấu", value=match_cmds, inline=False)
        
        # Captain/Vice commands
        if clan_role in ("captain", "vice"):
            capvice_cmds = """
`/clan invite @member` - Mời người vào clan (gửi DM)
"""
            embed.add_field(name="⚔️ Lệnh Captain/Vice", value=capvice_cmds, inline=False)
        
        # Captain only commands
        if clan_role == "captain":
            captain_cmds = """
`/clan promote_vice @member` - Thăng cấp thành viên lên Đội Phó
`/clan demote_vice @member` - Giáng cấp Đội Phó xuống Thành Viên
`/clan kick @member` - Kick thành viên khỏi clan
`/clan disband` - Giải tán clan (yêu cầu xác nhận)
"""
            embed.add_field(name="👑 Lệnh Đội Trưởng", value=captain_cmds, inline=False)
        
        # Mod commands
        if is_mod:
            mod_cmds = """
`/mod clan approve <tên>` - Duyệt clan đang chờ
`/mod clan reject <tên> <lý_do>` - Từ chối clan
`/mod clan delete <tên>` - Xóa vĩnh viễn một clan
`/matchadmin match resolve <id> <clan_thắng> <lý_do>` - Xử lý tranh chấp
"""
            embed.add_field(name="🛡️ Lệnh Mod", value=mod_cmds, inline=False)
        
        # Elo info (show if in clan)
        if clan_role:
            elo_txt = """
• **K-Factor**: 24 | **Elo Khởi Điểm**: 1000
• **Chống farm**: Trận 1=100%, Trận 2=70%, Trận 3=40%, Trận 4+=20%
• Elo chỉ tính khi cả 2 clan đều **active**
"""
            embed.add_field(name="📊 Quy Tắc Elo", value=elo_txt, inline=False)
        
        # Info section
        info_txt = """
• Clan cần **5 thành viên** để được duyệt
• Nếu thành viên giảm xuống dưới 5, clan trở thành **inactive**
• Rời clan = **cooldown 14 ngày** trước khi tham gia clan khác
"""
        embed.add_field(name="ℹ️ Thông Tin Chung", value=info_txt, inline=False)
        
        # Footer with role info
        roles = []
        if is_mod:
            roles.append("Mod")
        if is_verified:
            roles.append("Verified")
        if clan_role:
            roles.append(clan_role.title())
        
        embed.set_footer(text=f"Your roles: {', '.join(roles) if roles else 'None'}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @clan_group.command(name="create", description="Create a new clan (you + 4 members = 5 total)")
    async def clan_create(self, interaction: discord.Interaction):
        """Create a new clan."""
        # Check verified role
        if not await check_verified(interaction):
            return
        
        # Check user is registered
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check not already in a clan
        existing_clan = await db.get_user_clan(user["id"])
        if existing_clan:
            await interaction.response.send_message(ERRORS["ALREADY_IN_CLAN"], ephemeral=True)
            return
        
        # Check cooldown
        days = check_cooldown(user.get("cooldown_until"))
        if days:
            await interaction.response.send_message(
                ERRORS["COOLDOWN_ACTIVE"].format(days=days),
                ephemeral=True
            )
            return
        
        # Show modal
        await interaction.response.send_modal(ClanCreateModal())
    
    @clan_group.command(name="info", description="View clan information")
    @app_commands.describe(clan_name="Name of the clan (leave empty for your clan)")
    async def clan_info(self, interaction: discord.Interaction, clan_name: Optional[str] = None):
        """View clan stats and members."""
        if clan_name:
            clan = await db.get_clan(clan_name)
        else:
            user = await get_user_db(str(interaction.user.id))
            if not user:
                await interaction.response.send_message(
                    "Bạn chưa ở trong clan nào. Hãy tạo hoặc được mời vào một clan!",
                    ephemeral=True
                )
                return
            clan_data = await db.get_user_clan(user["id"])
            if not clan_data:
                await interaction.response.send_message(ERRORS["NOT_IN_CLAN"], ephemeral=True)
                return
            clan = await db.get_clan_by_id(clan_data["id"])
        
        if not clan:
            await interaction.response.send_message(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        # Get members
        members = await db.get_clan_members(clan["id"])
        
        # Build embed
        embed = discord.Embed(
            title=f"🏰 {clan['name']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Trạng thái", value=clan["status"].replace("_", " ").title(), inline=True)
        embed.add_field(name="Elo", value=str(clan["elo"]), inline=True)
        embed.add_field(name="Trận đấu", value=str(clan["matches_played"]), inline=True)
        
        # Group members by role
        captain = [m for m in members if m["role"] == "captain"]
        vices = [m for m in members if m["role"] == "vice"]
        regular = [m for m in members if m["role"] == "member"]
        
        member_text = ""
        if captain:
            member_text += f"👑 **Captain:** <@{captain[0]['discord_id']}>\n"
        if vices:
            vice_list = ", ".join(f"<@{v['discord_id']}>" for v in vices)
            member_text += f"⚔️ **Vice Captains:** {vice_list}\n"
        if regular:
            regular_list = ", ".join(f"<@{m['discord_id']}>" for m in regular)
            member_text += f"👥 **Members:** {regular_list}"
        
        embed.add_field(name=f"Thành viên ({len(members)})", value=member_text or "Không có", inline=False)
        embed.set_footer(text=f"Ngày thành lập: {clan['created_at'][:10]}")
        
        await interaction.response.send_message(embed=embed)
    
    @clan_group.command(name="leave", description="Leave your current clan (14-day cooldown)")
    async def clan_leave(self, interaction: discord.Interaction):
        """Leave the current clan."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Get user's clan
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data:
            await interaction.response.send_message(ERRORS["NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Check if user is captain
        if clan_data["member_role"] == "captain":
            await interaction.response.send_message(
                "❌ Với tư cách là Captain, bạn không thể rời clan. Hãy chuyển quyền Captain trước hoặc giải tán clan.",
                ephemeral=True
            )
            return

        clan_name = clan_data["name"]
        clan_id = clan_data["id"]
        
        # Cleanup active loans and pending requests
        active_loan = await db.get_active_loan_for_member(user["id"])
        if active_loan:
            await db.end_loan(active_loan["id"])
            await cooldowns.apply_loan_cooldowns(active_loan["lending_clan_id"], active_loan["borrowing_clan_id"], user["id"])
            await bot_utils.log_event("LOAN_ENDED", f"Loan {active_loan['id']} ended due to member leaving.")
            
        await db.cancel_user_pending_requests(user["id"])
        
        # Remove from clan
        await db.remove_member(user["id"], clan_id)
        
        # Apply cooldown
        cooldown_until = (datetime.now(timezone.utc) + timedelta(days=config.COOLDOWN_DAYS)).isoformat()
        await db.update_user_cooldown(user["id"], cooldown_until)
        
        # Remove Discord role if exists
        if clan_data.get("discord_role_id"):
            try:
                role = interaction.guild.get_role(int(clan_data["discord_role_id"]))
                if role:
                    await interaction.user.remove_roles(role)
            except Exception:
                pass
        
        # Check if clan drops below 5 members - AUTO DISBAND
        member_count = await db.count_clan_members(clan_id)
        if member_count < config.MIN_MEMBERS_ACTIVE and clan_data["status"] == "active":
            # Delete clan role and channel
            if clan_data.get("discord_role_id"):
                try:
                    role = interaction.guild.get_role(int(clan_data["discord_role_id"]))
                    if role:
                        await role.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass
            
            if clan_data.get("discord_channel_id"):
                try:
                    channel = interaction.guild.get_channel(int(clan_data["discord_channel_id"]))
                    if channel:
                        await channel.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass
            
            # [P2 Fix] End all active loans involving this clan
            from services import loan_service
            await loan_service.end_all_clan_loans(clan_id, interaction.guild)
            
            # Update clan status and remove members
            async with db.get_connection() as conn:
                await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
                await conn.execute("UPDATE clans SET status = 'disbanded', updated_at = datetime('now') WHERE id = ?", (clan_id,))
                await conn.commit()
            
            await bot_utils.log_event(
                "CLAN_AUTO_DISBANDED",
                f"Clan '{clan_name}' auto-disbanded (members dropped below {config.MIN_MEMBERS_ACTIVE})"
            )
        
        await bot_utils.log_event(
            "MEMBER_LEAVE",
            f"{interaction.user.mention} left clan '{clan_name}'. Cooldown: {config.COOLDOWN_DAYS} days."
        )
        
        await interaction.response.send_message(
            f"✅ Bạn đã rời clan **{clan_name}**.\n"
            f"⏳ Bạn hiện đang trong thời gian chờ **{config.COOLDOWN_DAYS} ngày** trước khi có thể gia nhập clan khác.",
            ephemeral=True
        )
    
    @clan_group.command(name="disband", description="Disband your clan (Captain only, deletes clan)")
    async def clan_disband(self, interaction: discord.Interaction):
        """Disband the clan entirely (Captain only)."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Get user's clan
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data:
            await interaction.response.send_message(ERRORS["NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Check if user is captain
        if clan_data["member_role"] != "captain":
            await interaction.response.send_message(ERRORS["NOT_CAPTAIN"], ephemeral=True)
            return
        
        clan_name = clan_data["name"]
        clan_id = clan_data["id"]
        
        # Delete clan role and channel if they exist
        if clan_data.get("discord_role_id"):
            try:
                role = interaction.guild.get_role(int(clan_data["discord_role_id"]))
                if role:
                    await role.delete(reason="Clan disbanded")
            except Exception:
                pass
        
        if clan_data.get("discord_channel_id"):
            try:
                channel = interaction.guild.get_channel(int(clan_data["discord_channel_id"]))
                if channel:
                    await channel.delete(reason="Clan disbanded")
            except Exception:
                pass
        
        # [P2 Fix] End all active loans involving this clan
        from services import loan_service
        await loan_service.end_all_clan_loans(clan_id, interaction.guild)
        
        # Remove all members and update clan status to disbanded
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("UPDATE clans SET status = 'disbanded', updated_at = datetime('now') WHERE id = ?", (clan_id,))
            await conn.commit()
        
        await bot_utils.log_event(
            "CLAN_DISBANDED",
            f"Clan '{clan_name}' disbanded by captain {interaction.user.mention}"
        )
        
        await interaction.response.send_message(
            f"✅ Clan **{clan_name}** đã được giải tán.\n"
            f"Tất cả thành viên đã bị xóa. Không áp dụng thời gian chờ.",
            ephemeral=True
        )
    
    @clan_group.command(name="promote_vice", description="Promote a member to Vice Captain")
    @app_commands.describe(member="The member to promote")
    async def clan_promote_vice(self, interaction: discord.Interaction, member: discord.Member):
        """Promote a member to Vice Captain (Captain only)."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check user is captain
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] != "captain":
            await interaction.response.send_message(ERRORS["NOT_CAPTAIN"], ephemeral=True)
            return
        
        # Get target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Check target is in same clan
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan or target_clan["id"] != clan_data["id"]:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        if target_clan["member_role"] == "captain":
            await interaction.response.send_message("Không thể tự thăng chức cho chính mình.", ephemeral=True)
            return
        
        if target_clan["member_role"] == "vice":
            await interaction.response.send_message(f"{member.mention} đã là Vice Captain rồi.", ephemeral=True)
            return
        
        # Promote
        await db.update_member_role(target_user["id"], clan_data["id"], "vice")
        
        await bot_utils.log_event(
            "MEMBER_PROMOTED",
            f"{member.mention} promoted to Vice Captain in '{clan_data['name']}' by {interaction.user.mention}"
        )
        
        await interaction.response.send_message(
            f"✅ {member.mention} đã được thăng chức thành **Vice Captain**!",
            ephemeral=True
        )
    
    @clan_group.command(name="invite", description="Invite a member to join your clan")
    @app_commands.describe(member="The member to invite")
    async def clan_invite(self, interaction: discord.Interaction, member: discord.Member):
        """Invite a member to join your clan (Captain/Vice only)."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check user is captain or vice
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data:
            await interaction.response.send_message(
                "❌ Bạn không ở trong clan nào.",
                ephemeral=True
            )
            return
        
        if clan_data["member_role"] not in ("captain", "vice"):
            await interaction.response.send_message(
                "❌ Chỉ Captain hoặc Vice Captain mới có thể mời thành viên.",
                ephemeral=True
            )
            return
        
        # Check clan is active
        if clan_data["status"] != "active":
            await interaction.response.send_message(
                "❌ Clan của bạn chưa được duyệt hoặc không hoạt động.",
                ephemeral=True
            )
            return
        
        # Check target user
        if member.bot:
            await interaction.response.send_message("❌ Không thể mời bot vào clan.", ephemeral=True)
            return
        
        if member.id == interaction.user.id:
            await interaction.response.send_message("❌ Không thể tự mời chính mình.", ephemeral=True)
            return
        
        # Check if target has verified role
        target_role_names = [role.name for role in member.roles]
        if config.ROLE_VERIFIED not in target_role_names:
            await interaction.response.send_message(
                f"❌ {member.mention} chưa có role `{config.ROLE_VERIFIED}`.",
                ephemeral=True
            )
            return
        
        # Get or create target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await db.create_user(str(member.id), f"{member.name}#0000")
            target_user = await db.get_user(str(member.id))
        
        # Check if target is already in a clan
        target_clan = await db.get_user_clan(target_user["id"])
        if target_clan:
            await interaction.response.send_message(
                f"❌ {member.mention} đã ở trong clan **{target_clan['name']}**.",
                ephemeral=True
            )
            return
        
        # Check cooldown
        if target_user.get("cooldown_until"):
            cooldown = datetime.fromisoformat(target_user["cooldown_until"].replace('Z', '+00:00'))
            if cooldown > datetime.now(timezone.utc):
                await interaction.response.send_message(
                    f"❌ {member.mention} đang trong thời gian chờ đến **{cooldown.strftime('%Y-%m-%d %H:%M')} UTC**.",
                    ephemeral=True
                )
                return
        
        # Check for existing pending invite
        existing_invite = await db.get_pending_invite(target_user["id"], clan_data["id"])
        if existing_invite:
            await interaction.response.send_message(
                f"❌ Đã có lời mời đang chờ cho {member.mention}. Vui lòng đợi họ phản hồi.",
                ephemeral=True
            )
            return
        
        # Create invite request (expires in 48 hours)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        invite_id = await db.create_invite_request(
            clan_data["id"],
            target_user["id"],
            user["id"],
            expires_at
        )
        
        # Send DM to target
        try:
            view = InviteAcceptDeclineView(
                invite_id=invite_id,
                clan_id=clan_data["id"],
                user_id=target_user["id"],
                clan_name=clan_data["name"],
                invited_by_name=interaction.user.display_name
            )
            
            await member.send(
                f"🏰 **Lời mời tham gia clan!**\n\n"
                f"**{interaction.user.display_name}** đã mời bạn tham gia clan **{clan_data['name']}**.\n\n"
                f"⏰ Lời mời này hết hạn sau **48 giờ**.\n\n"
                f"Bấm **Accept** để tham gia hoặc **Decline** để từ chối.",
                view=view
            )
            
            await interaction.response.send_message(
                f"✅ Đã gửi lời mời đến {member.mention}. Họ có 48 giờ để phản hồi.",
                ephemeral=True
            )
            
            await bot_utils.log_event(
                "CLAN_INVITE_SENT",
                f"{interaction.user.mention} invited {member.mention} to clan '{clan_data['name']}'"
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Không thể gửi DM đến {member.mention}. Họ có thể đã tắt DM từ server.",
                ephemeral=True
            )
    
    @clan_group.command(name="demote_vice", description="Demote a Vice Captain to Member")
    @app_commands.describe(member="The Vice Captain to demote")
    async def clan_demote_vice(self, interaction: discord.Interaction, member: discord.Member):
        """Demote a Vice Captain to Member (Captain only)."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check user is captain
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] != "captain":
            await interaction.response.send_message(ERRORS["NOT_CAPTAIN"], ephemeral=True)
            return
        
        # Get target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Check target is in same clan and is vice
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan or target_clan["id"] != clan_data["id"]:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        if target_clan["member_role"] != "vice":
            await interaction.response.send_message(f"{member.mention} không phải là Vice Captain.", ephemeral=True)
            return
        
        # Demote
        await db.update_member_role(target_user["id"], clan_data["id"], "member")
        
        await bot_utils.log_event(
            "MEMBER_DEMOTED",
            f"{member.mention} demoted from Vice Captain in '{clan_data['name']}' by {interaction.user.mention}"
        )
        
        await interaction.response.send_message(
            f"✅ {member.mention} đã bị giáng chức xuống **Thành viên**.",
            ephemeral=True
        )
    
    @clan_group.command(name="kick", description="Kick a member from your clan")
    @app_commands.describe(member="The member to kick")
    async def clan_kick(self, interaction: discord.Interaction, member: discord.Member):
        """Kick a member from the clan (Captain only)."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check user is captain
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] != "captain":
            await interaction.response.send_message(ERRORS["NOT_CAPTAIN"], ephemeral=True)
            return
        
        # Can't kick self
        if member.id == interaction.user.id:
            await interaction.response.send_message(ERRORS["CANNOT_KICK_SELF"], ephemeral=True)
            return
        
        # Get target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        # Check target is in same clan
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan or target_clan["id"] != clan_data["id"]:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return
        
        clan_name = clan_data["name"]
        clan_id = clan_data["id"]
        
        # Cleanup active loans and pending requests
        active_loan = await db.get_active_loan_for_member(target_user["id"])
        if active_loan:
            await db.end_loan(active_loan["id"])
            await cooldowns.apply_loan_cooldowns(active_loan["lending_clan_id"], active_loan["borrowing_clan_id"], target_user["id"])
            await bot_utils.log_event("LOAN_ENDED", f"Loan {active_loan['id']} ended due to member kick.")
            
        await db.cancel_user_pending_requests(target_user["id"])

        # Remove from clan
        await db.remove_member(target_user["id"], clan_id)
        
        # Apply cooldown to kicked member
        cooldown_until = (datetime.now(timezone.utc) + timedelta(days=config.COOLDOWN_DAYS)).isoformat()
        await db.update_user_cooldown(target_user["id"], cooldown_until)
        
        # Remove Discord role if exists
        if clan_data.get("discord_role_id"):
            try:
                role = interaction.guild.get_role(int(clan_data["discord_role_id"]))
                if role:
                    await member.remove_roles(role)
            except Exception:
                pass
        
        # Check if clan drops below 5 members - AUTO DISBAND
        member_count = await db.count_clan_members(clan_id)
        if member_count < config.MIN_MEMBERS_ACTIVE and clan_data["status"] == "active":
            # Delete clan role and channel
            if clan_data.get("discord_role_id"):
                try:
                    role = interaction.guild.get_role(int(clan_data["discord_role_id"]))
                    if role:
                        await role.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass
            
            if clan_data.get("discord_channel_id"):
                try:
                    channel = interaction.guild.get_channel(int(clan_data["discord_channel_id"]))
                    if channel:
                        await channel.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass
            
            # [P2 Fix] End all active loans involving this clan
            from services import loan_service
            await loan_service.end_all_clan_loans(clan_id, interaction.guild)
            
            # Update clan status and remove members
            async with db.get_connection() as conn:
                await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
                await conn.execute("UPDATE clans SET status = 'disbanded', updated_at = datetime('now') WHERE id = ?", (clan_id,))
                await conn.commit()
            
            await bot_utils.log_event(
                "CLAN_AUTO_DISBANDED",
                f"Clan '{clan_name}' auto-disbanded (members dropped below {config.MIN_MEMBERS_ACTIVE}) after kick"
            )
        
        await bot_utils.log_event(
            "MEMBER_KICK",
            f"{member.mention} kicked from '{clan_name}' by {interaction.user.mention}. Cooldown: {config.COOLDOWN_DAYS} days."
        )
        
        await interaction.response.send_message(
            f"✅ {member.mention} đã bị kick khỏi **{clan_name}**.\n"
            f"Họ hiện đang trong thời gian chờ {config.COOLDOWN_DAYS} ngày.",
            ephemeral=True
        )
        
        # Try to DM the kicked member
        try:
            await member.send(
                f"⚠️ Bạn đã bị **kick** khỏi clan **{clan_name}** bởi Captain.\n"
                f"Bạn hiện đang trong thời gian chờ {config.COOLDOWN_DAYS} ngày trước khi có thể gia nhập clan khác."
            )
        except Exception:
            pass
    
    # =========================================================================
    # MOD COMMANDS
    # =========================================================================
    
    mod_group = app_commands.Group(name="mod", description="Moderation commands")
    mod_clan_group = app_commands.Group(name="clan", description="Clan moderation", parent=mod_group)
    
    @mod_clan_group.command(name="approve", description="Approve a pending clan")
    @app_commands.describe(clan_name="The clan name to approve")
    async def mod_clan_approve(self, interaction: discord.Interaction, clan_name: str):
        """Approve a pending clan and create role/channel."""
        if not await check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get clan by name
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.followup.send(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        clan_id = clan["id"]
        
        if clan["status"] != "pending_approval":
            await interaction.followup.send(
                f"Clan '{clan['name']}' không ở trạng thái chờ phê duyệt (trạng thái: {clan['status']}).",
                ephemeral=True
            )
            return
        
        guild = interaction.guild
        
        # Check bot permissions
        if not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                ERRORS["BOT_MISSING_PERMS"].format(perms="Manage Roles"),
                ephemeral=True
            )
            return
        
        if not guild.me.guild_permissions.manage_channels:
            await interaction.followup.send(
                ERRORS["BOT_MISSING_PERMS"].format(perms="Manage Channels"),
                ephemeral=True
            )
            return
        
        # Create clan role (using clan name directly, no "Clan" prefix)
        role_name = clan['name']
        try:
            clan_role = await guild.create_role(
                name=role_name,
                color=discord.Color.random(),
                reason=f"Clan System: Created for clan '{clan['name']}'"
            )
        except discord.Forbidden:
            await interaction.followup.send(ERRORS["ROLE_HIERARCHY"], ephemeral=True)
            return
        
        # Create private channel under CLANS category
        category = bot_utils.get_clans_category()
        if not category:
            await interaction.followup.send(
                "❌ Lỗi: Không tìm thấy category CLANS. Vui lòng kiểm tra cấu hình bot.",
                ephemeral=True
            )
            await clan_role.delete()  # Cleanup role
            return
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            clan_role: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True)
        }
        
        try:
            clan_channel = await guild.create_text_channel(
                name=clan['name'].lower().replace(" ", "-"),
                category=category,
                overwrites=overwrites,
                reason=f"Clan System: Private channel for clan '{clan['name']}'"
            )
        except discord.Forbidden:
            await clan_role.delete()  # Cleanup role
            await interaction.followup.send(
                ERRORS["BOT_MISSING_PERMS"].format(perms="Manage Channels trong category CLANS"),
                ephemeral=True
            )
            return
        
        # Update clan in DB
        await db.set_clan_discord_ids(clan_id, str(clan_role.id), str(clan_channel.id))
        await db.update_clan_status(clan_id, "active")
        
        # Assign role to all members
        members = await db.get_clan_members(clan_id)
        role_assign_failures = []
        
        for member_data in members:
            try:
                discord_member = guild.get_member(int(member_data["discord_id"]))
                if discord_member:
                    await discord_member.add_roles(clan_role)
            except Exception:
                role_assign_failures.append(member_data["discord_id"])
        
        # Log
        await bot_utils.log_event(
            "CLAN_APPROVED",
            f"Clan '{clan['name']}' approved by {interaction.user.mention}. "
            f"Role: {clan_role.mention}, Channel: {clan_channel.mention}"
        )
        
        # Send welcome message to clan channel
        await clan_channel.send(
            f"🎉 **Chào mừng đến với {clan['name']}!**\n\n"
            f"Clan của bạn đã được phê duyệt! Đây là kênh riêng tư của clan.\n"
            f"Chúc các bạn thi đấu tốt và vui vẻ! 🏆"
        )
        
        msg = f"✅ Clan **{clan['name']}** đã được phê duyệt!\n" \
              f"• Role đã tạo: {clan_role.mention}\n" \
              f"• Kênh đã tạo: {clan_channel.mention}"
        
        if role_assign_failures:
            msg += f"\n\n⚠️ Không thể gán role cho: {', '.join(role_assign_failures)}"
        
        await interaction.followup.send(msg, ephemeral=True)
    
    @mod_clan_group.command(name="reject", description="Reject a pending clan")
    @app_commands.describe(clan_name="The clan name to reject", reason="Reason for rejection")
    async def mod_clan_reject(self, interaction: discord.Interaction, clan_name: str, reason: str):
        """Reject a pending clan."""
        if not await check_mod(interaction):
            return
        
        # Get clan by name
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        clan_id = clan["id"]
        
        if clan["status"] != "pending_approval":
            await interaction.response.send_message(
                f"Clan '{clan['name']}' không ở trạng thái chờ phê duyệt (trạng thái: {clan['status']}).",
                ephemeral=True
            )
            return
        
        # Hard delete the clan
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
            await conn.commit()
        
        # Log
        await bot_utils.log_event(
            "CLAN_REJECTED",
            f"Clan '{clan['name']}' rejected and deleted by {interaction.user.mention}. Reason: {reason}"
        )
        
        # Try to notify the captain
        captain = await db.get_user_by_id(clan["captain_id"])
        if captain:
            try:
                guild = interaction.guild
                captain_member = guild.get_member(int(captain["discord_id"]))
                if captain_member:
                    await captain_member.send(
                        f"❌ Clan **{clan['name']}** của bạn đã bị **từ chối** bởi Moderator.\n\n"
                        f"**Lý do:** {reason}"
                    )
            except Exception:
                pass
        
        await interaction.response.send_message(
            f"✅ Clan **{clan['name']}** đã bị từ chối.\nLý do: {reason}",
            ephemeral=True
        )

    @mod_clan_group.command(name="delete", description="Hard delete a clan (Mod only)")
    @app_commands.describe(clan_name="The clan name to delete")
    async def mod_clan_delete(self, interaction: discord.Interaction, clan_name: str):
        """Hard delete a clan (Mod only)."""
        if not await check_mod(interaction):
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get clan by name
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.followup.send(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        clan_id = clan["id"]
        
        # Delete Discord role and channel if they exist
        if clan.get("discord_role_id"):
            try:
                role = interaction.guild.get_role(int(clan["discord_role_id"]))
                if role:
                    await role.delete(reason=f"Clan deleted by mod {interaction.user}")
            except Exception:
                pass
        
        if clan.get("discord_channel_id"):
            try:
                channel = interaction.guild.get_channel(int(clan["discord_channel_id"]))
                if channel:
                    await channel.delete(reason=f"Clan deleted by mod {interaction.user}")
            except Exception:
                pass
        
        # Remove all members and delete clan from DB
        async with db.get_connection() as conn:
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
            await conn.commit()
        
        await bot_utils.log_event(
            "CLAN_DELETED_BY_MOD",
            f"Clan '{clan_name}' (ID: {clan_id}) hard deleted by mod {interaction.user.mention}"
        )
        
        await interaction.followup.send(
            f"✅ Clan **{clan_name}** (ID: {clan_id}) đã bị xóa vĩnh viễn khỏi database.",
            ephemeral=True
        )
    
    @mod_clan_group.command(name="set_captain", description="Set a new captain for a clan (Mod only)")
    @app_commands.describe(clan_name="The clan name", member="The member to make captain")
    async def mod_clan_set_captain(self, interaction: discord.Interaction, clan_name: str, member: discord.Member):
        """Set a new captain for a clan (Mod only)."""
        if not await check_mod(interaction):
            return
        
        # Get clan by name
        clan = await db.get_clan_any_status(clan_name)
        if not clan:
            await interaction.response.send_message(ERRORS["CLAN_NOT_FOUND"], ephemeral=True)
            return
        
        clan_id = clan["id"]
        
        # Get target user from DB
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await db.create_user(str(member.id), f"{member.name}#0000")
            target_user = await db.get_user(str(member.id))
        
        # Check if user is in this clan
        user_clan = await db.get_user_clan(target_user["id"])
        if not user_clan or user_clan["id"] != clan_id:
            await interaction.response.send_message(
                f"❌ {member.mention} không phải là thành viên của clan '{clan_name}'.",
                ephemeral=True
            )
            return
        
        # Update captain in DB - demote old captain, promote new one
        async with db.get_connection() as conn:
            # Demote current captain(s) to member
            await conn.execute(
                "UPDATE clan_members SET role = 'member' WHERE clan_id = ? AND role = 'captain'",
                (clan_id,)
            )
            # Promote new captain
            await conn.execute(
                "UPDATE clan_members SET role = 'captain' WHERE clan_id = ? AND user_id = ?",
                (clan_id, target_user["id"])
            )
            # Update clan's captain_id
            await conn.execute(
                "UPDATE clans SET captain_id = ? WHERE id = ?",
                (target_user["id"], clan_id)
            )
            await conn.commit()
        
        await bot_utils.log_event(
            "CAPTAIN_SET_BY_MOD",
            f"{member.mention} set as captain of '{clan_name}' by mod {interaction.user.mention}"
        )
        
        await interaction.response.send_message(
            f"✅ {member.mention} hiện đã là Captain của **{clan_name}**.",
            ephemeral=True
        )



# =============================================================================
# COG SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(ClanCog(bot))

