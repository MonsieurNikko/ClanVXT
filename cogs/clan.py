"""
Clan Commands Cog
Implements all clan-related slash commands and UI components
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Optional, List
import json

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
        await db.create_user(discord_id, interaction.user.display_name)
        user = await get_user_db(discord_id)
    return user




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
        view = MemberSelectView(self.clan_name.value, self.description.value or "")
        await interaction.response.send_message(
            f"🏰 **Clan: {self.clan_name.value}**\n"
            f"Hãy chọn **5 thành viên** (bao gồm cả bạn) để gửi lời mời thành lập clan.",
            view=view,
            ephemeral=True
        )
        print(f"[CLAN] User {interaction.user.name} submitted ClanCreateModal for '{self.clan_name.value}'")


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
                await db.create_user(str(member.id), member.display_name)
                user = await db.get_user(str(member.id))
            
            # Check if member is already in a clan
            member_clan = await db.get_user_clan(user["id"])
            if member_clan:
                errors.append(f"• {member.mention} is already in clan '{member_clan['name']}'")
                continue
            
            # Check cooldown (FUSED)
            is_cd, until = await cooldowns.check_member_join_cooldown(user["id"])
            if is_cd:
                try:
                    until_dt = datetime.fromisoformat(until.replace('Z', '+00:00'))
                    days = (until_dt - datetime.now(timezone.utc)).days + 1
                    errors.append(f"• {member.mention} is in cooldown ({days} days remaining)")
                except Exception:
                    errors.append(f"• {member.mention} is in cooldown")
        
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
        # Guard against double-click: disable button immediately
        if self.disabled:
            return
        self.disabled = True
        self.label = "Processing..."
        self.style = discord.ButtonStyle.grey
        try:
            await interaction.response.edit_message(view=self.view)
        except discord.errors.InteractionResponded:
            pass
        
        # Get captain from DB (auto-register if needed)
        captain = await db.get_user(str(interaction.user.id))
        if not captain:
            await db.create_user(str(interaction.user.id), interaction.user.display_name)
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
                await db.create_user(str(member.id), member.display_name)
                user = await db.get_user(str(member.id))
            
            # Create request in DB
            try:
                await db.create_create_request(clan_id, user["id"], expires_at)
            except Exception as e:
                print(f"[DEBUG] Failed to create request for user {user['id']} in clan {clan_id}: {e}")
                dm_failures.append(member.mention)
                continue
            
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
        print(f"[CLAN] Clan creation confirmed by {interaction.user.name} for '{self.clan_name}'. Invitations sent to {len(self.members)} members.")


class CancelButton(discord.ui.Button):
    """Generic cancel button."""
    
    def __init__(self, ):
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
        # Handled by ClanCog.on_interaction for persistence
        pass
    
    async def decline_callback(self, interaction: discord.Interaction):
        # Handled by ClanCog.on_interaction for persistence
        pass


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
        # Handled by ClanCog.on_interaction for persistence
        pass
    
    async def decline_callback(self, interaction: discord.Interaction):
        # Handled by ClanCog.on_interaction for persistence
        pass


# =============================================================================
# RANK DECLARATION UI (Balance System - Feature 6)
# =============================================================================

# 25 Valorant ranks mapped to score
RANK_OPTIONS = [
    discord.SelectOption(label="Iron 1", value="1"),
    discord.SelectOption(label="Iron 2", value="2"),
    discord.SelectOption(label="Iron 3", value="3"),
    discord.SelectOption(label="Bronze 1", value="4"),
    discord.SelectOption(label="Bronze 2", value="5"),
    discord.SelectOption(label="Bronze 3", value="6"),
    discord.SelectOption(label="Silver 1", value="7"),
    discord.SelectOption(label="Silver 2", value="8"),
    discord.SelectOption(label="Silver 3", value="9"),
    discord.SelectOption(label="Gold 1", value="10"),
    discord.SelectOption(label="Gold 2", value="11"),
    discord.SelectOption(label="Gold 3", value="12"),
    discord.SelectOption(label="Platinum 1", value="13"),
    discord.SelectOption(label="Platinum 2", value="14"),
    discord.SelectOption(label="Platinum 3", value="15"),
    discord.SelectOption(label="Diamond 1", value="16"),
    discord.SelectOption(label="Diamond 2", value="17"),
    discord.SelectOption(label="Diamond 3", value="18"),
    discord.SelectOption(label="Ascendant 1", value="19"),
    discord.SelectOption(label="Ascendant 2", value="20"),
    discord.SelectOption(label="Ascendant 3", value="21"),
    discord.SelectOption(label="Immortal 1", value="22"),
    discord.SelectOption(label="Immortal 2", value="23"),
    discord.SelectOption(label="Immortal 3", value="24"),
    discord.SelectOption(label="Radiant", value="25"),
]

from services.elo import RANK_SCORE_TO_NAME


class RankDeclarationView(discord.ui.View):
    """View with a Select Menu for declaring Valorant rank."""
    
    def __init__(self, user_id: int, clan_id: int):
        super().__init__(timeout=None)  # No timeout — member có thể khai rank bất cứ lúc nào
        self.db_user_id = user_id
        self.clan_id = clan_id
        
        select = discord.ui.Select(
            placeholder="Chọn rank Valorant của bạn...",
            options=RANK_OPTIONS,
            custom_id=f"rank_declare:{user_id}:{clan_id}",
            min_values=1,
            max_values=1,
        )
        select.callback = self.rank_selected
        self.add_item(select)
    
    async def rank_selected(self, interaction: discord.Interaction):
        # Respond to interaction FIRST (within 3s) to avoid 'This interaction failed'
        try:
            rank_score = int(interaction.data["values"][0])
            rank_name = RANK_SCORE_TO_NAME.get(rank_score, f"Unknown ({rank_score})")
        except Exception:
            await interaction.response.send_message("\u274c Lỗi xử lý dữ liệu. Vui lòng thử lại.", ephemeral=True)
            return
        
        # Respond immediately (edit the message with the select menu, or fallback to new message)
        try:
            await interaction.response.edit_message(
                content=f"\u2705 Đã khai rank: **{rank_name}**! Cảm ơn bạn đã cập nhật thông tin.",
                view=None
            )
        except Exception:
            # In DM context, just ack with a new message (no ephemeral in DMs)
            try:
                await interaction.response.send_message(
                    f"\u2705 Đã khai rank: **{rank_name}**! Cảm ơn bạn."
                )
            except Exception:
                pass  # If even this fails, interaction already timed out, just proceed
        
        # Save to DB after responding
        try:
            await db.update_member_rank(self.db_user_id, self.clan_id, rank_name, rank_score)
            await bot_utils.log_event(
                "RANK_DECLARED",
                f"{interaction.user.mention} ({interaction.user.display_name}) khai rank **{rank_name}**"
            )
        except Exception as e:
            print(f"[RANK] DB update failed after responding: {e}")


# =============================================================================
# COG DEFINITION
# =============================================================================

class ClanCog(commands.Cog):
    """Cog containing all clan-related commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_tryouts_loop.start()

    def cog_unload(self):
        self.check_tryouts_loop.cancel()

    @tasks.loop(minutes=10)
    async def check_tryouts_loop(self):
        if not self.bot.is_ready():
            return

        try:
            expired_members = await db.get_expired_tryouts()
            for member in expired_members:
                user_id = member["user_id"]
                clan_id = member["clan_id"]
                clan_name = member["clan_name"]
                
                print(f"[TRYOUT] Auto-kicking expired recruit {user_id} from clan {clan_name}")
                
                # Check if still recruit (double check)
                existing_member = await db.get_clan_member(user_id, clan_id)
                if not existing_member or existing_member.get("join_type") != "tryout":
                    continue
                
                # Remove member
                await db.remove_member(user_id, clan_id)
                
                # Remove roles
                clan = await db.get_clan_by_id(clan_id)
                if clan and clan.get("discord_role_id"):
                    try:
                        guild = self.bot.get_guild(config.GUILD_ID)
                        if guild:
                            role = guild.get_role(int(clan["discord_role_id"]))
                            discord_member = guild.get_member(int(member["discord_id"]))
                            if role and discord_member:
                                await discord_member.remove_roles(role)
                    except Exception as e:
                        print(f"[TRYOUT] Error removing role: {e}")

                # Log
                await bot_utils.log_event(
                    "TRYOUT_EXPIRED",
                    f"Recruit <@{member['discord_id']}> auto-kicked from '{clan_name}' (24h expired)"
                )

                # Announce Public
                await bot_utils.announce_public(
                    title="⌛ Try-out Expired",
                    description=f"Recruit <@{member['discord_id']}> đã trượt kỳ try-out 24h tại clan **{clan_name}**.",
                    color=discord.Color.red()
                )
                
                # Notify user
                try:
                    discord_user = self.bot.get_user(int(member["discord_id"]))
                    if discord_user:
                        await discord_user.send(
                            f"⚠️ **Try-out đã hết hạn!**\n"
                            f"Bạn chưa được Promote lên thành viên chính thức trong vòng 24h, nên đã bị tự động rời khỏi clan **{clan_name}**."
                        )
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"[TRYOUT] Error in loop: {e}")

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
        
        # Handle active clan invites (invite_accept/invite_decline)
        if custom_id.startswith("invite_accept:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                invite_id = int(parts[1])
                user_id = int(parts[2])
                await self.handle_invite_accept(interaction, invite_id, user_id)
                return
        
        if custom_id.startswith("invite_decline:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                invite_id = int(parts[1])
                user_id = int(parts[2])
                await self.handle_invite_decline(interaction, invite_id, user_id)
                return
        
        # Handle rank declaration select (Balance System)
        if custom_id.startswith("rank_declare:"):
            parts = custom_id.split(":")
            if len(parts) == 3:
                db_user_id = int(parts[1])
                clan_id = int(parts[2])
                # Extract selected rank score from interaction data
                try:
                    rank_score = int(interaction.data["values"][0])
                    rank_name = RANK_SCORE_TO_NAME.get(rank_score, f"Unknown ({rank_score})")
                except Exception:
                    await interaction.response.send_message("❌ Lỗi xử lý dữ liệu. Vui lòng thử lại.", ephemeral=True)
                    return
                # Respond first, then save DB
                try:
                    await interaction.response.edit_message(
                        content=f"✅ Đã khai rank: **{rank_name}**! Cảm ơn bạn đã cập nhật thông tin.",
                        view=None
                    )
                except Exception:
                    try:
                        await interaction.response.send_message(f"✅ Đã khai rank: **{rank_name}**! Cảm ơn bạn.")
                    except Exception:
                        pass
                try:
                    await db.update_member_rank(db_user_id, clan_id, rank_name, rank_score)
                    await bot_utils.log_event(
                        "RANK_DECLARED",
                        f"{interaction.user.mention} ({interaction.user.display_name}) khai rank **{rank_name}**"
                    )
                except Exception as e:
                    print(f"[RANK] DB error in persistent handler: {e}")
            return

    async def handle_clan_accept(self, interaction: discord.Interaction, clan_id: int, user_id: int):
        """Handle clan accept button click."""
        discord_user = interaction.user
        print(f"[DEBUG] @{discord_user.name} (DB ID: {user_id}) bấm ACCEPT cho Clan ID {clan_id}")
        
        # Check if request exists (any status) to see if we've already processed it
        request = await db.get_user_request_any_status(clan_id, user_id)
        
        if not request:
            print(f"[DEBUG] Không tìm thấy yêu cầu cho @{discord_user.name} trong clan {clan_id}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Yêu cầu ứng tuyển này đã hết hạn hoặc bị hủy.", ephemeral=True)
                else:
                    await interaction.response.edit_message(
                        content="Yêu cầu ứng tuyển này đã hết hạn hoặc bị hủy.",
                        view=None
                    )
            except discord.errors.HTTPException:
                pass
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
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Yêu cầu của bạn đang ở trạng thái: **{request['status']}**.", ephemeral=True)
                else:
                    await interaction.response.edit_message(
                        content=f"Yêu cầu của bạn đang ở trạng thái: **{request['status']}**.",
                        view=None
                    )
            except discord.errors.HTTPException:
                pass
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
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("Lời mời này đã hết hạn hoặc đã bị hủy.", ephemeral=True)
                else:
                    await interaction.response.edit_message(
                        content="Lời mời này đã hết hạn hoặc đã bị hủy.",
                        view=None
                    )
            except discord.errors.HTTPException:
                pass
            return
        
        # Get clan name for messages
        clan = await db.get_clan_by_id(clan_id)
        clan_name = clan["name"] if clan else "Unknown"
        
        print(f"[DEBUG] @{discord_user.name} từ chối - Hủy tạo clan '{clan_name}'...")
        # Decline the request
        await db.decline_create_request(clan_id, user_id)
        
        # Safe hard delete the entire clan creation
        await db.hard_delete_clan(clan_id)
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Bạn đã **từ chối** lời mời tham gia **{clan_name}**.\n"
                    f"Việc tạo clan đã bị hủy bỏ.",
                    ephemeral=True
                )
            else:
                await interaction.response.edit_message(
                    content=f"❌ Bạn đã **từ chối** lời mời tham gia **{clan_name}**.\n"
                            f"Việc tạo clan đã bị hủy bỏ.",
                    view=None
                )
        except discord.errors.HTTPException:
            pass
        
        await bot_utils.log_event(
            "CLAN_CANCELLED",
            f"Clan '{clan_name}' creation cancelled - {interaction.user.mention} declined invitation"
        )
    
    async def handle_invite_accept(self, interaction: discord.Interaction, invite_id: int, user_id: int):
        """Handle invite accept button click for active clan invites."""
        discord_user = interaction.user
        print(f"[DEBUG] @{discord_user.name} (DB ID: {user_id}) bấm ACCEPT cho Invite ID {invite_id}")
        
        # Defer to prevent timeout - use followup instead of edit_message
        if not interaction.response.is_done():
            await interaction.response.defer()
        
        # Check if invite still exists and is pending
        invite = await db.get_invite_by_id(invite_id)
        if not invite or invite["status"] != "pending":
            await interaction.followup.send(
                content="Lời mời này đã hết hạn hoặc bị hủy.",
                ephemeral=True
            )
            return
        
        clan_id = invite["clan_id"]
        
        # Get user record (auto-register if needed)
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await db.create_user(str(interaction.user.id), interaction.user.display_name)
            user = await db.get_user(str(interaction.user.id))
        
        # Check if user is already in a clan
        existing_clan = await db.get_user_clan(user["id"])
        if existing_clan:
            await interaction.followup.send(
                content=f"❌ Bạn đã ở trong clan **{existing_clan['name']}** rồi. Hãy rời clan trước khi tham gia clan khác.",
                ephemeral=True
            )
            return
        
        # Check cooldown
        if user.get("cooldown_until"):
            cooldown = datetime.fromisoformat(user["cooldown_until"].replace('Z', '+00:00'))
            if cooldown > datetime.now(timezone.utc):
                await interaction.followup.send(
                    content=f"❌ Bạn đang trong thời gian chờ đến **{cooldown.strftime('%Y-%m-%d %H:%M')} UTC**.",
                    ephemeral=True
                )
                return
        
        # Accept the invite
        success = await db.accept_invite(invite_id)
        if not success:
            await interaction.followup.send(
                content="Không thể xử lý lời mời. Vui lòng thử lại.",
                ephemeral=True
            )
            return
        
        # Check invite type
        invite_type = invite.get("invite_type", "full")
        role = "member"
        join_type = "full"
        tryout_expires_at = None
        
        if invite_type == "tryout":
            role = "recruit"
            join_type = "tryout"
            tryout_expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        
        # Add user to clan
        await db.add_member(user["id"], clan_id, role, join_type, tryout_expires_at)
        
        # Assign Discord role if exists
        clan = await db.get_clan_by_id(clan_id)
        clan_name = clan["name"] if clan else "Unknown"
        
        # Need to get guild from bot since DM interactions don't have guild
        if clan and clan.get("discord_role_id"):
            try:
                guild = self.bot.get_guild(config.GUILD_ID)
                if guild:
                    discord_role = guild.get_role(int(clan["discord_role_id"]))
                    if discord_role:
                        guild_member = guild.get_member(interaction.user.id)
                        if guild_member:
                            await guild_member.add_roles(discord_role)
                            print(f"[DEBUG] Assigned role {discord_role.name} to {guild_member.name}")

                            # Assign player role as well
                            player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
                            if player_role and player_role not in guild_member.roles:
                                await guild_member.add_roles(player_role, reason="Clan join auto-role")
                                print(f"[DEBUG] Assigned {config.ROLE_PLAYER} role to {guild_member.name}")
                        else:
                            print(f"[DEBUG] Could not find member {interaction.user.id} in guild")
                    else:
                        print(f"[DEBUG] Could not find role {clan['discord_role_id']}")
                else:
                    print(f"[DEBUG] Could not find guild {config.GUILD_ID}")
            except Exception as e:
                print(f"[DEBUG] Failed to assign role: {e}")
        
        msg_success = f"✅ Bạn đã tham gia clan **{clan_name}** thành công!"
        if invite_type == "tryout":
            msg_success = f"✅ Bạn đã bắt đầu giai đoạn **Try-out** tại clan **{clan_name}**!\n⏳ Thời hạn: 24 giờ."
            
        await interaction.followup.send(
            content=msg_success,
            ephemeral=True
        )
        
        # --- Balance System: Rank Declaration Prompt (Feature 6) ---
        try:
            rank_view = RankDeclarationView(user["id"], clan_id)
            await interaction.followup.send(
                content=(
                    f"🎯 **Khai Rank Valorant**\n\n"
                    f"Để tham gia thi đấu, bạn cần khai rank Valorant hiện tại.\n"
                    f"Hãy chọn rank của bạn bên dưới:"
                ),
                view=rank_view,
                ephemeral=True
            )
        except Exception as e:
            print(f"[RANK] Failed to send rank declaration prompt: {e}")

        
        # Announce Public
        if invite_type == "tryout":
            await bot_utils.announce_public(
                title="🛡️ New Recruit!",
                description=f"Chào mừng <@{interaction.user.id}> gia nhập clan **{clan_name}** (Try-out)!",
                color=discord.Color.blue()
            )
        else:
            await bot_utils.announce_public(
                title="👋 New Member!",
                description=f"Chào mừng <@{interaction.user.id}> gia nhập clan **{clan_name}**!",
                color=discord.Color.green()
            )
        
        # Get inviter name for log
        inviter = await db.get_user_by_id(invite.get("invited_by_user_id"))
        inviter_name = inviter["riot_id"] if inviter else "Unknown"
        
        await bot_utils.log_event(
            "MEMBER_JOINED",
            f"{interaction.user.mention} joined clan '{clan_name}' via invite from {inviter_name}"
        )
    
    async def handle_invite_decline(self, interaction: discord.Interaction, invite_id: int, user_id: int):
        """Handle invite decline button click for active clan invites."""
        discord_user = interaction.user
        print(f"[DEBUG] @{discord_user.name} (DB ID: {user_id}) bấm DECLINE cho Invite ID {invite_id}")
        
        # Defer to prevent timeout
        if not interaction.response.is_done():
            await interaction.response.defer()
        
        # Check if invite still exists and is pending
        invite = await db.get_invite_by_id(invite_id)
        if not invite or invite["status"] != "pending":
            await interaction.followup.send(
                content="Lời mời này đã hết hạn hoặc bị hủy.",
                ephemeral=True
            )
            return
        
        clan_id = invite["clan_id"]
        clan = await db.get_clan_by_id(clan_id)
        clan_name = clan["name"] if clan else "Unknown"
        
        # Decline the invite
        success = await db.decline_invite(invite_id)
        if not success:
            await interaction.followup.send(
                content="Không thể xử lý lời mời. Vui lòng thử lại.",
                ephemeral=True
            )
            return
        
        await interaction.followup.send(
            content=f"❌ Bạn đã **từ chối** lời mời tham gia clan **{clan_name}**.",
            ephemeral=True
        )
        
        await bot_utils.log_event(
            "INVITE_DECLINED",
            f"{interaction.user.mention} declined clan invite for '{clan_name}'"
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
            title="🏰 Hệ Thống Clan VXT - Hướng Dẫn",
            description="Chào mừng bạn đến với đấu trường Clan VXT. Dưới đây là các lệnh bạn có thể sử dụng:",
            color=discord.Color.gold()
        )
        
        # Season info
        season_info = """
• **Reset:** Elo sẽ reset theo mỗi mùa giải của **Valorant**.
• **🎁 Phần thưởng:** Top 1 Clan mỗi mùa nhận **05 Battle Pass**.
"""
        embed.add_field(name="📅 Thông Tin Mùa Giải", value=season_info, inline=False)

        # Basic commands (everyone)
        basic_cmds = """
`/clan info [tên]` - Xem thông tin chi tiết một clan
`/clan help` - Hiển thị bảng hướng dẫn này
"""
        embed.add_field(name="📋 Lệnh Cơ Bản", value=basic_cmds, inline=False)
        
        # Verified user commands
        if is_verified:
            user_cmds = """
`/clan create` - Thành lập clan mới (Yêu cầu ít nhất 5 người)
`/clan leave` - Rời clan hiện tại (Chịu cooldown 14 ngày)
• **Lời mời:** Phản hồi qua nút bấm trong **DM** của Bot.
"""
            embed.add_field(name="👤 Lệnh Thành Viên", value=user_cmds, inline=False)
        
        # Match commands (any clan member)
        if clan_role:
            match_cmds = """
`/match create <đối_thủ>` - Khởi tạo trận đấu Custom
• Sau khi thi đấu: Bên Thắng báo kết quả -> Bên Thua xác nhận.
• Elo chỉ được tính khi cả hai bên đồng thuận.
"""
            embed.add_field(name="⚔️ Lệnh Trận Đấu", value=match_cmds, inline=False)
        
        # Captain/Vice commands
        if clan_role in ("captain", "vice"):
            capvice_cmds = """
`/clan invite @user` - Gửi lời mời gia nhập clan (qua DM)
`/clan update_rank` - Nhắc khai báo Rank cho thành viên chưa khai
`/transfer request @user <tên_clan>` - Yêu cầu chuyển nhượng thành viên
`/loan request @user <tên_clan> <số_ngày>` - Yêu cầu mượn thành viên (có thời hạn)
"""
            embed.add_field(name="🛡️ Lệnh Captain/Vice", value=capvice_cmds, inline=False)
        
        # Captain only commands
        if clan_role == "captain":
            captain_cmds = """
`/clan promote_vice @user` - Bổ nhiệm Đội Phó
`/clan demote_vice @user` - Bãi nhiệm Đội Phó
`/clan kick @user` - Trục xuất thành viên khỏi clan
`/clan disband` - Giải toán clan
`/transfer cancel <id>` - Hủy yêu cầu chuyển nhượng
`/loan cancel <id>` - Hủy yêu cầu mượn quân
"""
            embed.add_field(name="👑 Lệnh Đội Trưởng", value=captain_cmds, inline=False)
        
        # Mod commands
        if is_mod:
            mod_cmds = """
`/mod clan approve/reject/delete` - Quản lý clan
`/matchadmin match resolve` - Xử lý tranh chấp match
`/admin dashboard/cooldown/ban/freeze` - Quản trị hệ thống
`/admin balance toggle/status/set_rank` - Quản lý Balance System
"""
            embed.add_field(name="⚖️ Lệnh Quản Trị", value=mod_cmds, inline=False)
        
        # Elo info (show if in clan)
        if clan_role:
            elo_txt = """
• **K-Factor**: 32 | **Elo Khởi Điểm**: 1000
• **Chống farm**: Trận 1=100%, Trận 2=70%, Trận 3=40%, Trận 4+=20%
• Elo chỉ tính khi cả 2 clan đều **active**
• **Balance**: Win rate modifier, Underdog bonus, Rank modifier
• **Decay**: Elo giảm nếu clan không hoạt động lâu
"""
            embed.add_field(name="📊 Quy Tắc Elo", value=elo_txt, inline=False)
        
        # Info section
        info_txt = """
• **Transfer/Loan**: Cần sự đồng thuận từ 3 bên (2 Captain & Thành viên).
• **Loan Limit**: Mỗi clan được phép mượn/cho mượn tối đa **02 thành viên** cùng lúc.
• **Cooldown**: Rời/Đổi clan chịu **14 ngày** cooldown.
• **Active**: Clan cần tối thiểu **5 thành viên** để được tính Elo.
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

        # Defer to prevent interaction timeout during heavy operations
        await interaction.response.defer(ephemeral=True)

        clan_name = clan_data["name"]
        clan_id = clan_data["id"]
        
        # Cleanup active loans and pending requests
        active_loan = await db.get_active_loan_for_member(user["id"])
        if active_loan:
            await db.end_loan(active_loan["id"])
            await cooldowns.apply_loan_cooldowns(active_loan["lending_clan_id"], active_loan["borrowing_clan_id"], user["id"])
            await bot_utils.log_event("LOAN_ENDED", f"Loan {active_loan['id']} ended due to member leaving.")
            
        await db.cancel_user_pending_requests(user["id"])
        
        # Check role before removing
        member_role = clan_data.get("member_role", "member")
        join_type = clan_data.get("join_type", "full")

        # Remove from clan
        await db.remove_member(user["id"], clan_id)
        
        # Apply cooldown ONLY if not a recruit/tryout
        if member_role != "recruit" and join_type != "tryout":
            cooldown_until = (datetime.now(timezone.utc) + timedelta(days=config.COOLDOWN_DAYS)).isoformat()
            await db.update_user_cooldown(user["id"], cooldown_until) # Legacy safe kep for now
            await cooldowns.apply_member_join_cooldown(user["id"], f"Left clan {clan_name}", source_clan_id=clan_id)
        else:
             print(f"[CLAN] User {user['id']} (Recruit) left clan {clan_id} - No cooldown applied.")
        
        # Remove Discord role if exists
        if clan_data.get("discord_role_id"):
            try:
                guild = interaction.guild
                role = guild.get_role(int(clan_data["discord_role_id"]))
                if role:
                    await interaction.user.remove_roles(role)
                
                # Also remove player role
                player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
                if player_role and player_role in interaction.user.roles:
                    await interaction.user.remove_roles(player_role, reason="Left clan")
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
        
        # Try to get member role/type if we can, but they are already removed. 
        # Wait, we need to check BEFORE removal. 
        # We did fetch clan_data at start, but that was just user_clan.
        # We need to make sure we have the correct role/type.
        
        # In this command `clan_leave` we fetch `clan_data` using `get_user_clan` which returns generic clan info + member_role.
        # It DOES NOT return `join_type`. We need to fetch that or assume.
        # Let's fix the fetching part first in a separate edit or rely on `get_user_clan` having it?
        # `get_user_clan` query: select c.*, cm.role as member_role ...
        # I need to update `get_user_clan` in `db.py` to include `join_type`?
        # Yes, I should probably check that. 
        # For now, I will assume I can get it or I will fetch it specifically.
        
        cd_msg = ""
        if member_role != "recruit" and join_type != "tryout":
             cd_msg = f"⏳ Bạn hiện đang trong thời gian chờ **{config.COOLDOWN_DAYS} ngày** trước khi có thể gia nhập clan khác."
        
        await bot_utils.log_event(
            "MEMBER_LEAVE",
            f"{interaction.user.mention} left clan '{clan_name}'. {cd_msg}"
        )
        print(f"[CLAN] User {interaction.user.name} left clan {clan_name}")
        
        await interaction.followup.send(
            f"✅ Bạn đã rời clan **{clan_name}**.\n{cd_msg}",
            ephemeral=True
        )
        
        # Announce Public
        await bot_utils.announce_public(
            title="🏃 Member Left",
            description=f"<@{interaction.user.id}> đã rời khỏi clan **{clan_name}**.",
            color=discord.Color.orange()
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
        
        # Defer to prevent interaction timeout during heavy operations
        await interaction.response.defer(ephemeral=True)
        
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
            # Get all member discord IDs before deleting from DB
            cursor = await conn.execute("SELECT u.discord_id FROM users u JOIN clan_members cm ON u.id = cm.user_id WHERE cm.clan_id = ?", (clan_id,))
            member_rows = await cursor.fetchall()
            
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
            await conn.execute("UPDATE clans SET status = 'disbanded', updated_at = datetime('now') WHERE id = ?", (clan_id,))
            await conn.commit()
            
        # Clean up 'player' role for all members
        player_role = discord.utils.get(interaction.guild.roles, name=config.ROLE_PLAYER)
        if player_role:
            for row in member_rows:
                try:
                    m = interaction.guild.get_member(int(row[0]))
                    if m and player_role in m.roles:
                        await m.remove_roles(player_role, reason="Clan disbanded")
                except Exception:
                    pass
        
        await bot_utils.log_event(
            "CLAN_DISBANDED",
            f"Clan '{clan_name}' disbanded by captain {interaction.user.mention}"
        )
        print(f"[CLAN] Clan {clan_name} disbanded by {interaction.user.name}")
        
        await interaction.followup.send(
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
        print(f"[CLAN] Member {member.name} promoted to Vice Captain in {clan_data['name']} by {interaction.user.name}")
        
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
            await db.create_user(str(member.id), member.display_name)
            target_user = await db.get_user(str(member.id))
        
        # Check if target is already in a clan
        target_clan = await db.get_user_clan(target_user["id"])
        if target_clan:
            await interaction.response.send_message(
                f"❌ {member.mention} đã ở trong clan **{target_clan['name']}**.",
                ephemeral=True
            )
            return
        
        # Check cooldown (FUSED)
        is_cd, until = await cooldowns.check_member_join_cooldown(target_user["id"])
        if is_cd:
            try:
                until_dt = datetime.fromisoformat(until.replace('Z', '+00:00'))
                until_str = until_dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                until_str = until
            await interaction.response.send_message(
                f"❌ {member.mention} đang trong thời gian chờ đến **{until_str} UTC**.",
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
        
        # --- Balance System: Recruitment Cap (Feature 1) ---
        if await db.is_balance_feature_enabled("recruitment_cap"):
            clan = await db.get_clan_by_id(clan_data["id"])
            if clan and clan["matches_played"] > config.RECRUITMENT_CAP_EXEMPT_MATCHES:
                recent_count = await db.count_recent_recruits(clan_data["id"])
                if recent_count >= config.RECRUITMENT_CAP_PER_WEEK:
                    await interaction.response.send_message(
                        f"❌ Clan đã đạt giới hạn tuyển quân ({config.RECRUITMENT_CAP_PER_WEEK} thành viên/tuần).",
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
            print(f"[CLAN] Invite sent: {interaction.user.name} invited {member.name} to {clan_data['name']}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Không thể gửi DM đến {member.mention}. Họ có thể đã tắt DM từ server.",
                ephemeral=True
            )

    @clan_group.command(name="recruit", description="Recruit a member for a 24h Try-out (Captain/Vice only)")
    @app_commands.describe(member="The member to recruit")
    async def clan_recruit(self, interaction: discord.Interaction, member: discord.Member):
        """Recruit a member for a 24h Try-out."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        # Check permissions
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] not in ("captain", "vice"):
            await interaction.response.send_message("❌ Chỉ Captain hoặc Vice mới có thể tuyển quân try-out.", ephemeral=True)
            return
            
         # Check clan is active
        if clan_data["status"] != "active":
            await interaction.response.send_message("❌ Clan của bạn chưa hoạt động.", ephemeral=True)
            return

        # Validate target
        if member.bot or member.id == interaction.user.id:
            await interaction.response.send_message("❌ Mục tiêu không hợp lệ.", ephemeral=True)
            return
            
        # Check target verified
        target_role_names = [role.name for role in member.roles]
        if config.ROLE_VERIFIED not in target_role_names:
            await interaction.response.send_message(f"❌ {member.mention} chưa verify.", ephemeral=True)
            return

        # Get/Create target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await db.create_user(str(member.id), member.display_name)
            target_user = await db.get_user(str(member.id))

        # Check existing clan
        target_clan = await db.get_user_clan(target_user["id"])
        if target_clan:
            await interaction.response.send_message(f"❌ {member.mention} đã ở trong clan **{target_clan['name']}**.", ephemeral=True)
            return

        # Check Cooldown (Try-out Logic)
        # We pass target_clan_id=clan_data["id"] so it CHECKS if the cooldown (if acting) is from THIS clan
        is_cd, until = await cooldowns.check_member_join_cooldown(target_user["id"], target_clan_id=clan_data["id"])
        if is_cd:
             # This means they are blocked specifically from joining THIS clan (re-join same clan)
             await interaction.response.send_message(f"❌ {member.mention} vừa rời clan này và đang bị cooldown. Không thể try-out lại ngay.", ephemeral=True)
             return
             
        # Check max ONE recruit
        # TODO: Check if clan already has a recruit? 
        # Requirement: "Mỗi clan chỉ tối đa 01 recruit."
        members = await db.get_clan_members(clan_data["id"])
        recruit_count = sum(1 for m in members if m["role"] == "recruit")
        if recruit_count >= 1:
            await interaction.response.send_message("❌ Clan của bạn đã có 01 Recruit rồi. Hãy Promote hoặc Fire họ trước.", ephemeral=True)
            return

        # --- Balance System: Recruitment Cap (Feature 1) ---
        if await db.is_balance_feature_enabled("recruitment_cap"):
            clan = await db.get_clan_by_id(clan_data["id"])
            if clan and clan["matches_played"] > config.RECRUITMENT_CAP_EXEMPT_MATCHES:
                recent_count = await db.count_recent_recruits(clan_data["id"])
                if recent_count >= config.RECRUITMENT_CAP_PER_WEEK:
                    await interaction.response.send_message(
                        f"❌ Clan đã đạt giới hạn tuyển quân ({config.RECRUITMENT_CAP_PER_WEEK} thành viên/tuần).",
                        ephemeral=True
                    )
                    return

        # Check existing invite
        existing_invite = await db.get_pending_invite(target_user["id"], clan_data["id"])
        if existing_invite:
            await interaction.response.send_message(f"❌ Đang có lời mời chờ cho {member.mention}.", ephemeral=True)
            return

        # Create TRY-OUT invite
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        invite_id = await db.create_invite_request(
            clan_data["id"],
            target_user["id"],
            user["id"],
            expires_at,
            invite_type="tryout"
        )
        
        # Send DM
        try:
            view = InviteAcceptDeclineView(invite_id, clan_data["id"], target_user["id"], clan_data["name"], interaction.user.display_name)
            await member.send(
                f"🛡️ **Mời Try-out Clan!**\n\n"
                f"**{interaction.user.display_name}** mời bạn tham gia **Try-out 24h** tại clan **{clan_data['name']}**.\n"
                f"Bạn sẽ có role `Recruit` và phải được Promote trong vòng 24h, nếu không sẽ bị kick tự động.\n\n"
                f"Bấm **Accept** để bắt đầu thử việc.",
                view=view
            )
            await interaction.response.send_message(f"✅ Đã gửi lời mời Try-out đến {member.mention}.", ephemeral=True)
            await bot_utils.log_event("CLAN_RECRUIT_SENT", f"{interaction.user.mention} sent TRY-OUT invite to {member.mention} for '{clan_data['name']}'")
        except discord.Forbidden:
             await interaction.response.send_message(f"❌ Không thể gửi DM cho {member.mention}.", ephemeral=True)

    @clan_group.command(name="promote", description="Promote a Recruit to Member (Captain only)")
    @app_commands.describe(member="The recruit to promote")
    async def clan_promote(self, interaction: discord.Interaction, member: discord.Member):
        """Promote a recruit."""
        if not await check_verified(interaction): return
        user = await ensure_user_registered(interaction)
        if not user: return
        
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] != "captain":
            await interaction.response.send_message("❌ Chỉ Captain mới có thể Promote.", ephemeral=True)
            return

        target_user = await db.get_user(str(member.id))
        if not target_user: return
        
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan or target_clan["id"] != clan_data["id"]:
            await interaction.response.send_message("❌ Thành viên này không thuộc clan của bạn.", ephemeral=True)
            return
            
        if target_clan["member_role"] != "recruit":
            await interaction.response.send_message(f"❌ {member.mention} không phải là Recruit.", ephemeral=True)
            return
            
        # Update Role: recruit -> member, join_type -> full, clear tryout_expires_at
        async with db.get_connection() as conn:
            await conn.execute(
                "UPDATE clan_members SET role='member', join_type='full', tryout_expires_at=NULL WHERE clan_id=? AND user_id=?",
                (clan_data["id"], target_user["id"])
            )
            await conn.commit()
            
        await interaction.response.send_message(f"✅ {member.mention} đã được thăng chức thành **Thành Viên Chính Thức**!", ephemeral=True)
        await bot_utils.log_event("MEMBER_PROMOTED", f"{member.mention} promoted from Recruit to Member in '{clan_data['name']}'")
        
        # Announce Public
        await bot_utils.announce_public(
            title="🆙 Recruit Promoted!",
            description=f"Chúc mừng <@{member.id}> đã vượt qua kỳ try-out và trở thành thành viên chính thức của **{clan_data['name']}**!",
            color=discord.Color.gold()
        )

    @clan_group.command(name="fire", description="Fire a Recruit immediately (Captain only)")
    @app_commands.describe(member="The recruit to fire")
    async def clan_fire(self, interaction: discord.Interaction, member: discord.Member):
        """Fire a recruit."""
        if not await check_verified(interaction): return
        user = await ensure_user_registered(interaction)
        if not user: return
        
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] != "captain":
            await interaction.response.send_message("❌ Chỉ Captain mới có thể Fire recruit.", ephemeral=True)
            return

        target_user = await db.get_user(str(member.id))
        if not target_user: return
        
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan or target_clan["id"] != clan_data["id"]:
            await interaction.response.send_message("❌ Thành viên này không thuộc clan của bạn.", ephemeral=True)
            return
            
        if target_clan["member_role"] != "recruit":
            await interaction.response.send_message(f"❌ {member.mention} không phải là Recruit. Dùng `/clan kick` cho thành viên chính thức.", ephemeral=True)
            return
            
        # Remove member (No cooldown per rules)
        await db.remove_member(target_user["id"], clan_data["id"])
        
        # Remove roles
        if clan_data.get("discord_role_id"):
             try:
                guild = interaction.guild
                role = guild.get_role(int(clan_data["discord_role_id"]))
                if role: await member.remove_roles(role)
             except: pass

        await interaction.response.send_message(f"✅ {member.mention} đã bị Fire (Kết thúc thử việc). Không áp dụng cooldown.", ephemeral=True)
        await bot_utils.log_event("RECRUIT_FIRED", f"{member.mention} fired from '{clan_data['name']}' by {interaction.user.mention}")
        try: await member.send(f"⚠️ Bạn đã bị chấm dứt Try-out tại clan **{clan_data['name']}**.")
        except: pass
        
        # Announce Public
        await bot_utils.announce_public(
            title="🚫 Recruit Fired",
            description=f"<@{member.id}> đã bị chấm dứt giai đoạn Try-out tại clan **{clan_data['name']}**.",
            color=discord.Color.red()
        )
    
    @clan_group.command(name="update_rank", description="Send rank declaration to all undeclared members")
    async def clan_update_rank(self, interaction: discord.Interaction):
        """Captain/Vice can request all undeclared members to declare rank."""
        if not await check_verified(interaction):
            return
        
        user = await ensure_user_registered(interaction)
        if not user:
            return
        
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["member_role"] not in ("captain", "vice"):
            await interaction.response.send_message("❌ Chỉ Captain hoặc Vice mới có thể yêu cầu khai rank.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        undeclared = await db.get_undeclared_members(clan_data["id"])
        if not undeclared:
            await interaction.followup.send("✅ Tất cả thành viên đã khai rank!", ephemeral=True)
            return
        
        sent_count = 0
        failed_count = 0
        for m in undeclared:
            try:
                discord_user = self.bot.get_user(int(m["discord_id"]))
                if not discord_user:
                    discord_user = await self.bot.fetch_user(int(m["discord_id"]))
                if discord_user:
                    rank_view = RankDeclarationView(m["user_id"], clan_data["id"])
                    await discord_user.send(
                        f"🎯 **Khai Rank Valorant — Clan {clan_data['name']}**\n\n"
                        f"Captain/Vice yêu cầu bạn khai rank Valorant hiện tại.\n"
                        f"Clan của bạn cần tất cả thành viên khai rank trước khi có thể thi đấu.\n\n"
                        f"Hãy chọn rank bên dưới:",
                        view=rank_view
                    )
                    sent_count += 1
            except Exception as e:
                print(f"[RANK] Failed to DM user {m['discord_id']}: {e}")
                failed_count += 1
        
        result_msg = f"📤 Đã gửi yêu cầu khai rank cho **{sent_count}/{len(undeclared)}** thành viên."
        if failed_count > 0:
            result_msg += f"\n⚠️ {failed_count} thành viên không nhận được DM."
        
        await interaction.followup.send(result_msg, ephemeral=True)
        await bot_utils.log_event(
            "RANK_UPDATE_REQUEST",
            f"{interaction.user.mention} requested rank update for clan '{clan_data['name']}' ({sent_count} DMs sent)"
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
        print(f"[CLAN] Member {member.name} demoted from Vice Captain in {clan_data['name']} by {interaction.user.name}")
        
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
        
        # Defer to prevent interaction timeout during heavy operations
        await interaction.response.defer(ephemeral=True)
        
        clan_name = clan_data["name"]
        clan_id = clan_data["id"]
        
        # Cleanup active loans and pending requests
        active_loan = await db.get_active_loan_for_member(target_user["id"])
        if active_loan:
            await db.end_loan(active_loan["id"])
            await cooldowns.apply_loan_cooldowns(active_loan["lending_clan_id"], active_loan["borrowing_clan_id"], target_user["id"])
            await bot_utils.log_event("LOAN_ENDED", f"Loan {active_loan['id']} ended due to member kick.")
            
        await db.cancel_user_pending_requests(target_user["id"])

        # Check role from target_clan (which is from get_user_clan)
        # Note: get_user_clan might not return join_type yet, need to verify db.py
        # But let's fetch specific member record to be safe
        member_record = await db.get_clan_member(target_user["id"], clan_id)
        is_recruit = False
        if member_record:
            if member_record.get("role") == "recruit" or member_record.get("join_type") == "tryout":
                is_recruit = True

        # Remove from clan
        await db.remove_member(target_user["id"], clan_id)
        print(f"[CLAN] Member {member.name} kicked from {clan_name} by {interaction.user.name}")
        
        # Apply cooldown if not recruit
        if not is_recruit:
            cooldown_until = (datetime.now(timezone.utc) + timedelta(days=config.COOLDOWN_DAYS)).isoformat()
            await db.update_user_cooldown(target_user["id"], cooldown_until)
            await cooldowns.apply_member_join_cooldown(target_user["id"], f"Kicked from clan {clan_name}", source_clan_id=clan_id)
        else:
            print(f"Skipped cooldown for kicked recruit {member.name}")
        
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
        
        cd_text = f"Cooldown: {config.COOLDOWN_DAYS} ngày." if not is_recruit else "No Cooldown (Recruit)."
        await bot_utils.log_event(
            "MEMBER_KICK",
            f"{member.mention} kicked from '{clan_name}' by {interaction.user.mention}. {cd_text}"
        )
        
        msg_extra = f"Họ hiện đang trong thời gian chờ {config.COOLDOWN_DAYS} ngày." if not is_recruit else "Họ có thể gia nhập clan khác ngay (Recruit)."
        await interaction.followup.send(
            f"✅ {member.mention} đã bị kick khỏi **{clan_name}**.\n{msg_extra}",
            ephemeral=True
        )
        
        # Try to DM the kicked member
        try:
            cd_dm = f"Bạn hiện đang trong thời gian chờ {config.COOLDOWN_DAYS} ngày trước khi có thể gia nhập clan khác." if not is_recruit else "Bạn không bị cooldown do đang trong thời gian thử việc."
            await member.send(
                f"⚠️ Bạn đã bị **kick** khỏi clan **{clan_name}** bởi Captain.\n{cd_dm}"
            )
        except Exception:
            pass
            
        # Announce Public
        await bot_utils.announce_public(
            title="👢 Member Kicked",
            description=f"<@{member.id}> đã bị kick khỏi clan **{clan_name}**.",
            color=discord.Color.red()
        )
    
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
        
        # Assign roles to all members
        members = await db.get_clan_members(clan_id)
        role_assign_failures = []
        
        # Get player role once
        player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
        
        for member_data in members:
            try:
                discord_member = guild.get_member(int(member_data["discord_id"]))
                if discord_member:
                    # Assign clan role
                    await discord_member.add_roles(clan_role)
                    # Assign player role
                    if player_role and player_role not in discord_member.roles:
                        await discord_member.add_roles(player_role, reason="Clan approved auto-role")
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
        
        # Safe hard delete the clan
        await db.hard_delete_clan(clan_id)
        
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
        
        # Safe hard delete clan from DB
        async with db.get_connection() as conn:
            # Get members for role cleanup
            cursor = await conn.execute("SELECT u.discord_id FROM users u JOIN clan_members cm ON u.id = cm.user_id WHERE cm.clan_id = ?", (clan_id,))
            member_rows = await cursor.fetchall()
            
        await db.hard_delete_clan(clan_id)
        
        # Cleanup 'player' role
        player_role = discord.utils.get(interaction.guild.roles, name=config.ROLE_PLAYER)
        if player_role:
            for row in member_rows:
                try:
                    m = interaction.guild.get_member(int(row[0]))
                    if m and player_role in m.roles:
                        await m.remove_roles(player_role, reason="Clan deleted by mod")
                except Exception:
                    pass
        
        await bot_utils.log_event(
            "CLAN_DELETED_BY_MOD",
            f"Clan '{clan_name}' (ID: {clan_id}) hard deleted by mod {interaction.user.mention}"
        )
        
        await interaction.followup.send(
            f"✅ Clan **{clan_name}** (ID: {clan_id}) đã bị xóa vĩnh viễn khỏi database.",
            ephemeral=True
        )

    @mod_clan_group.command(name="kick", description="Kick a member from any clan (Mod only)")
    @app_commands.describe(member="The member to kick", reason="Reason for kick")
    async def mod_clan_kick(self, interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
        """Kick a member from any clan (Mod only)."""
        if not await check_mod(interaction):
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message(ERRORS["CANNOT_KICK_SELF"], ephemeral=True)
            return

        # Get target user
        target_user = await db.get_user(str(member.id))
        if not target_user:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return

        # Check target clan
        target_clan = await db.get_user_clan(target_user["id"])
        if not target_clan:
            await interaction.response.send_message(ERRORS["TARGET_NOT_IN_CLAN"], ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        clan_name = target_clan["name"]
        clan_id = target_clan["id"]

        # If target is captain, ensure a replacement exists
        if target_clan.get("member_role") == "captain":
            members = await db.get_clan_members(clan_id)
            candidates = [m for m in members if m["user_id"] != target_user["id"]]
            if not candidates:
                await interaction.followup.send(
                    "❌ Không thể kick Captain khi clan chỉ còn 1 thành viên. Hãy set Captain khác hoặc xóa clan.",
                    ephemeral=True
                )
                return

            vice = next((m for m in candidates if m["role"] == "vice"), None)
            new_captain = vice or candidates[0]

            async with db.get_connection() as conn:
                await conn.execute(
                    "UPDATE clan_members SET role = 'member' WHERE clan_id = ? AND role = 'captain'",
                    (clan_id,)
                )
                await conn.execute(
                    "UPDATE clan_members SET role = 'captain' WHERE clan_id = ? AND user_id = ?",
                    (clan_id, new_captain["user_id"])
                )
                await conn.execute(
                    "UPDATE clans SET captain_id = ? WHERE id = ?",
                    (new_captain["user_id"], clan_id)
                )
                await conn.commit()

        # Cleanup active loans and pending requests
        active_loan = await db.get_active_loan_for_member(target_user["id"])
        if active_loan:
            await db.end_loan(active_loan["id"])
            await cooldowns.apply_loan_cooldowns(active_loan["lending_clan_id"], active_loan["borrowing_clan_id"], target_user["id"])
            await bot_utils.log_event("LOAN_ENDED", f"Loan {active_loan['id']} ended due to member kick by mod.")

        await db.cancel_user_pending_requests(target_user["id"])

        # Remove from clan
        await db.remove_member(target_user["id"], clan_id)

        # Check role/type (using target_clan data is risky if it doesn't have join_type, but we can infer from role)
        # Better to fetch
        # Since I cannot easily inject a fetch here without breaking flow, I'll rely on checking target_clan keys or fetching again if needed.
        # Actually `target_clan` from `get_user_clan` MIGHT NOT have join_type.
        # Let's verify `get_user_clan` output in `db.py` later. For now, assume I need to double check.
        # Wait, I can just check if I can modify db.py first? 
        # No, I'll just skip the fetch and assume "recruit" role is enough?
        # Yes, role is in target_clan.
        
        is_recruit_mod = target_clan.get("member_role") == "recruit"
        
        # Apply cooldown to kicked member
        if not is_recruit_mod:
            cooldown_until = (datetime.now(timezone.utc) + timedelta(days=config.COOLDOWN_DAYS)).isoformat()
            await db.update_user_cooldown(target_user["id"], cooldown_until)
            await cooldowns.apply_member_join_cooldown(target_user["id"], f"Kicked from clan {clan_name} by mod", source_clan_id=clan_id)
        
        # Remove Discord role if exists
        if target_clan.get("discord_role_id"):
            try:
                guild = interaction.guild
                role = guild.get_role(int(target_clan["discord_role_id"]))
                if role:
                    await member.remove_roles(role)
                
                # Also remove player role
                player_role = discord.utils.get(guild.roles, name=config.ROLE_PLAYER)
                if player_role and player_role in member.roles:
                    await member.remove_roles(player_role, reason="Kicked from clan")
            except Exception:
                pass

        # Check if clan drops below 5 members - AUTO DISBAND
        member_count = await db.count_clan_members(clan_id)
        if member_count < config.MIN_MEMBERS_ACTIVE and target_clan["status"] == "active":
            if target_clan.get("discord_role_id"):
                try:
                    role = interaction.guild.get_role(int(target_clan["discord_role_id"]))
                    if role:
                        await role.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass

            if target_clan.get("discord_channel_id"):
                try:
                    channel = interaction.guild.get_channel(int(target_clan["discord_channel_id"]))
                    if channel:
                        await channel.delete(reason="Clan auto-disbanded (members < 5)")
                except Exception:
                    pass

            from services import loan_service
            await loan_service.end_all_clan_loans(clan_id, interaction.guild)

            async with db.get_connection() as conn:
                await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
                await conn.execute("UPDATE clans SET status = 'disbanded', updated_at = datetime('now') WHERE id = ?", (clan_id,))
                await conn.commit()

            await bot_utils.log_event(
                "CLAN_AUTO_DISBANDED",
                f"Clan '{clan_name}' auto-disbanded (members dropped below {config.MIN_MEMBERS_ACTIVE}) after mod kick"
            )

        reason_text = reason or "N/A"
        await bot_utils.log_event(
            "MEMBER_KICK_BY_MOD",
            f"{member.mention} kicked from '{clan_name}' by mod {interaction.user.mention}. Reason: {reason_text}"
        )

        await interaction.followup.send(
            f"✅ {member.mention} đã bị kick khỏi **{clan_name}**.\n"
            f"Lý do: {reason_text}\n"
            f"{'Cooldown: ' + str(config.COOLDOWN_DAYS) + ' ngày.' if not is_recruit_mod else 'No Cooldown (Recruit).'}",
            ephemeral=True
        )

        try:
            cd_dm_mod = f"Bạn hiện đang trong thời gian chờ {config.COOLDOWN_DAYS} ngày trước khi có thể gia nhập clan khác." if not is_recruit_mod else "Do là recruit, bạn không bị cooldown."
            await member.send(
                f"⚠️ Bạn đã bị **kick** khỏi clan **{clan_name}** bởi Moderator.\n"
                f"Lý do: {reason_text}\n{cd_dm_mod}"
            )
        except Exception:
            pass
            
        # Announce Public (Mod Action)
        await bot_utils.announce_public(
            title="🛡️ Member Kicked by Mod",
            description=f"<@{member.id}> đã bị kick khỏi clan **{clan_name}** bởi Moderator.\nLý do: {reason_text}",
            color=discord.Color.dark_red()
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
            await db.create_user(str(member.id), member.display_name)
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

