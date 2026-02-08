"""
Transfer System Cog
Implements permanent member transfer functionality between clans.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, List

import config
from services import db, permissions, cooldowns
from services import db, permissions, cooldowns
from services import bot_utils

class TransferAcceptView(discord.ui.View):
    """View for 3-party transfer acceptance."""
    
    def __init__(self, transfer_id: int, source_clan_id: int, dest_clan_id: int, member_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.transfer_id = transfer_id
        self.source_clan_id = source_clan_id
        self.dest_clan_id = dest_clan_id
        self.member_id = member_id
        
        # Set dynamic custom_ids for persistence after bot restart
        # Format: transfer_accept_{type}:{transfer_id}:{source_clan_id}:{dest_clan_id}:{member_id}
        for child in self.children:
            if hasattr(child, 'custom_id'):
                if 'source' in child.custom_id:
                    child.custom_id = f"transfer_accept_source:{transfer_id}:{source_clan_id}:{dest_clan_id}:{member_id}"
                elif 'dest' in child.custom_id:
                    child.custom_id = f"transfer_accept_dest:{transfer_id}:{source_clan_id}:{dest_clan_id}:{member_id}"
                elif 'member' in child.custom_id:
                    child.custom_id = f"transfer_accept_member:{transfer_id}:{source_clan_id}:{dest_clan_id}:{member_id}"
        
    async def update_embed(self, interaction: discord.Interaction):
        """Update the embed to show current acceptance status."""
        transfer = await db.get_transfer(self.transfer_id)
        if not transfer or transfer["status"] != "requested":
            # Disable buttons if no longer requested
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            return

        source_clan = await db.get_clan_by_id(self.source_clan_id)
        dest_clan = await db.get_clan_by_id(self.dest_clan_id)
        member_user = await db.get_user_by_id(self.member_id)
        
        # Re-create embed
        embed = discord.Embed(
            title="✈️ Yêu cầu Transfer thành viên",
            description=f"Yêu cầu transfer cho <@{member_user['discord_id']}>",
            color=discord.Color.orange()
        )
        embed.add_field(name="Clan gốc", value=source_clan['name'], inline=True)
        embed.add_field(name="Clan đích", value=dest_clan['name'], inline=True)
        
        # Status indicators
        source_status = "✅ Đã chấp nhận" if transfer["accept_source"] else "⏳ Đang chờ"
        dest_status = "✅ Đã chấp nhận" if transfer["accept_dest"] else "⏳ Đang chờ"
        member_status = "✅ Đã chấp nhận" if transfer["accept_member"] else "⏳ Đang chờ"
        
        embed.add_field(name="Captain gốc", value=source_status, inline=True)
        embed.add_field(name="Captain đích", value=dest_status, inline=True)
        embed.add_field(name="Thành viên", value=member_status, inline=True)
            
        embed.set_footer(text=f"Transfer ID: {self.transfer_id} | Hết hạn sau 48h")
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Check if all accepted
        if transfer["accept_source"] and transfer["accept_dest"] and transfer["accept_member"]:
            await self.complete_transfer(interaction)

    async def complete_transfer(self, interaction: discord.Interaction):
        """Complete the transfer."""
        try:
            # Check source clan member count one last time (P0)
            count = await db.count_clan_members(self.source_clan_id)
            if count <= config.MIN_MEMBERS_ACTIVE:
                await interaction.followup.send(
                    f"❌ Không thể hoàn tất transfer: Clan gốc chỉ còn {count} thành viên. "
                    f"Cần ít nhất {config.MIN_MEMBERS_ACTIVE + 1} thành viên để có thể transfer ra ngoài.",
                    ephemeral=True
                )
                return

            # Execute transfer (atomic)
            if not await db.complete_transfer(self.transfer_id):
                return
            
            # Move member in DB (atomic)
            await db.move_member(self.member_id, self.source_clan_id, self.dest_clan_id, "member")
            
            # Apply sickness
            await cooldowns.apply_transfer_sickness(self.member_id)
            
            # Apply join/leave cooldown (14 days)
            await cooldowns.apply_member_join_cooldown(self.member_id, "Transferred to new clan")
            
            # Disable buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.message.edit(view=self)
            await interaction.followup.send(f"✅ **Transfer hoàn tất!** Thành viên đã được chuyển sang clan mới.")
            
            # [P2 Fix] Notify all parties via DM
            source_clan = await db.get_clan_by_id(self.source_clan_id)
            dest_clan = await db.get_clan_by_id(self.dest_clan_id)
            member_user = await db.get_user_by_id(self.member_id)
            
            msg = (
                f"✅ **Transfer #{self.transfer_id} đã hoàn tất!**\n"
                f"• Member: <@{member_user['discord_id']}>\n"
                f"• Từ clan: **{source_clan['name']}**\n"
                f"• Đến clan: **{dest_clan['name']}**"
            )
            
            # Notify member
            try:
                m = interaction.client.get_user(int(member_user["discord_id"]))
                if m: await m.send(msg)
            except Exception: pass
            
            # Notify source captain
            try:
                cap = interaction.client.get_user(int((await db.get_user_by_id(source_clan["captain_id"]))["discord_id"]))
                if cap: await cap.send(msg)
            except Exception: pass
            
            # Notify dest captain
            try:
                cap = interaction.client.get_user(int((await db.get_user_by_id(dest_clan["captain_id"]))["discord_id"]))
                if cap: await cap.send(msg)
            except Exception: pass

            # Log
            await bot_utils.log_event(
                "TRANSFER_COMPLETED",
                f"Transfer {self.transfer_id} completed. Member {self.member_id} moved from {self.source_clan_id} to {self.dest_clan_id}."
            )
            
            # Update Discord roles if possible (best effort)
            # This requires fetching guild and members, which we can try
            try:
                guild = interaction.guild
                member = guild.get_member(int((await db.get_user_by_id(self.member_id))["discord_id"]))
                
                source_clan = await db.get_clan_by_id(self.source_clan_id)
                dest_clan = await db.get_clan_by_id(self.dest_clan_id)
                
                if source_clan.get("discord_role_id"):
                    role = guild.get_role(int(source_clan["discord_role_id"]))
                    if role: await member.remove_roles(role)
                    
                if dest_clan.get("discord_role_id"):
                    role = guild.get_role(int(dest_clan["discord_role_id"]))
                    if role: await member.add_roles(role)
            except Exception:
                pass
                
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi hoàn tất transfer: {e}", ephemeral=True)

    @discord.ui.button(label="Clan Gốc Chấp Nhận", style=discord.ButtonStyle.primary, custom_id="transfer_accept_source_placeholder")
    async def accept_source(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of source clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký trong hệ thống.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.source_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Chỉ Captain/Vice của clan gốc mới có thể chấp nhận.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, source=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Clan Đích Chấp Nhận", style=discord.ButtonStyle.primary, custom_id="transfer_accept_dest_placeholder")
    async def accept_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of dest clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký trong hệ thống.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.dest_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Chỉ Captain/Vice của clan đích mới có thể chấp nhận.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, dest=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Thành Viên Chấp Nhận", style=discord.ButtonStyle.success, custom_id="transfer_accept_member_placeholder")
    async def accept_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is the member
        user = await db.get_user(str(interaction.user.id))
        if not user or user["id"] != self.member_id:
            return await interaction.response.send_message("Chỉ member được transfer mới có thể chấp nhận.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, member=True)
        await interaction.response.defer()
        await self.update_embed(interaction)


class TransferCog(commands.Cog):
    """Cog for Transfer commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle persistent button interactions for transfers."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        if custom_id:
            print(f"[DEBUG] Transfer Interaction by {interaction.user.id}: {custom_id}")
        
        if interaction.response.is_done():
            return
            
        # Format: transfer_accept_{type}:{transfer_id}:{source_clan_id}:{dest_clan_id}:{member_id}
        if custom_id.startswith("transfer_accept_source:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                transfer_id = int(parts[1])
                source_clan_id = int(parts[2])
                dest_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_transfer_accept(interaction, transfer_id, source_clan_id, dest_clan_id, member_id, "source")
                return

        if custom_id.startswith("transfer_accept_dest:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                transfer_id = int(parts[1])
                source_clan_id = int(parts[2])
                dest_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_transfer_accept(interaction, transfer_id, source_clan_id, dest_clan_id, member_id, "dest")
                return

        if custom_id.startswith("transfer_accept_member:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                transfer_id = int(parts[1])
                source_clan_id = int(parts[2])
                dest_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_transfer_accept(interaction, transfer_id, source_clan_id, dest_clan_id, member_id, "member")
                return

    async def handle_transfer_accept(self, interaction: discord.Interaction, transfer_id: int, source_clan_id: int, dest_clan_id: int, member_id: int, type_key: str):
        """Handle transfer acceptance logic."""
        user = await db.get_user(str(interaction.user.id))
        if not user:
            try: await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            except Exception: pass
            return
            
        # Permissions check
        if type_key == "source":
            clan_data = await db.get_user_clan(user["id"])
            if not clan_data or clan_data["id"] != source_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
                try: await interaction.response.send_message("Chỉ Captain/Vice của clan gốc mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_transfer_acceptance(transfer_id, source=True)
            
        elif type_key == "dest":
            clan_data = await db.get_user_clan(user["id"])
            if not clan_data or clan_data["id"] != dest_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
                try: await interaction.response.send_message("Chỉ Captain/Vice của clan đích mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_transfer_acceptance(transfer_id, dest=True)
            
        elif type_key == "member":
            if user["id"] != member_id:
                try: await interaction.response.send_message("Chỉ thành viên được transfer mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_transfer_acceptance(transfer_id, member=True)
        
        # Update UI
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        view = TransferAcceptView(transfer_id, source_clan_id, dest_clan_id, member_id)
        await view.update_embed(interaction)
    
    transfer_group = app_commands.Group(name="transfer", description="Transfer management commands")
    
    @transfer_group.command(name="request", description="Request to transfer a member to another clan")
    @app_commands.describe(
        member="The member to transfer",
        to_clan_name="The destination clan",
        note="Optional note"
    )
    async def transfer_request(self, interaction: discord.Interaction, member: discord.Member, to_clan_name: str, note: Optional[str] = None):
        """Create a transfer request."""
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký hệ thống.", ephemeral=True)
            
        # Check requester is Captain/Vice of Source Clan
        source_clan = await db.get_user_clan(user["id"])
        if not source_clan or source_clan["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Chỉ Captain/Vice mới có thể yêu cầu transfer.", ephemeral=True)
            
        # Check target member is in Source Clan
        target_user = await db.get_user(str(member.id))
        if not target_user:
            return await interaction.response.send_message("Thành viên này chưa đăng ký hệ thống.", ephemeral=True)
            
        target_member_clan = await db.get_user_clan(target_user["id"])
        if not target_member_clan or target_member_clan["id"] != source_clan["id"]:
            return await interaction.response.send_message("Thành viên này không thuộc clan của bạn.", ephemeral=True)
            
        # [P0 Fix] Cannot transfer the Captain
        if target_member_clan["member_role"] == "captain":
            return await interaction.response.send_message("❌ Không thể transfer Captain của clan.", ephemeral=True)
            
        # [P0 Fix] Check if clan has enough members to transfer
        member_count = await db.count_clan_members(source_clan["id"])
        if member_count <= config.MIN_MEMBERS_ACTIVE:
            return await interaction.response.send_message(
                f"❌ Your clan only has {member_count} members. "
                f"A clan must have at least {config.MIN_MEMBERS_ACTIVE + 1} members to transfer one out.",
                ephemeral=True
            )
            
        # Check Dest Clan exists
        dest_clan = await db.get_clan(to_clan_name)
        if not dest_clan:
            return await interaction.response.send_message(f"Không tìm thấy clan '{to_clan_name}'.", ephemeral=True)
            
        if dest_clan["id"] == source_clan["id"]:
            return await interaction.response.send_message("Không thể transfer cho cùng một clan.", ephemeral=True)
            
        # Permission Checks
        allowed, error = await permissions.can_request_transfer(target_user["id"], source_clan["id"], dest_clan["id"])
        if not allowed:
            return await interaction.response.send_message(f"❌ Không thể yêu cầu transfer: {error}", ephemeral=True)
            
        # Create Transfer
        transfer_id = await db.create_transfer(
            source_clan_id=source_clan["id"],
            dest_clan_id=dest_clan["id"],
            member_user_id=target_user["id"],
            requested_by_user_id=user["id"]
        )
        
        # Send Embed
        view = TransferAcceptView(transfer_id, source_clan["id"], dest_clan["id"], target_user["id"])
        embed = discord.Embed(
            title="✈️ Yêu cầu Transfer thành viên",
            description=f"Yêu cầu transfer cho {member.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Clan gốc", value=source_clan['name'], inline=True)
        embed.add_field(name="Clan đích", value=dest_clan['name'], inline=True)
        embed.add_field(name="Captain gốc", value="✅ Đã chấp nhận (Người tạo)" if user["id"] == user["id"] else "⏳ Đang chờ", inline=True)
        
        # Auto-accept for initiator's side (Source)
        await db.update_transfer_acceptance(transfer_id, source=True)
        
        embed.set_field_at(2, name="Captain gốc", value="✅ Đã chấp nhận", inline=True)
        embed.add_field(name="Captain đích", value="⏳ Đang chờ", inline=True)
        embed.add_field(name="Thành viên", value="⏳ Đang chờ", inline=True)
        
        if note:
            embed.add_field(name="Ghi chú", value=note, inline=False)
            
        embed.set_footer(text=f"Transfer ID: {transfer_id} | Expires in 48h")
        
        await interaction.response.send_message(embed=embed, view=view)
        
        # [P2 Fix] Notify member and destination captain via DM
        msg = (
            f"✈️ **Yêu cầu Transfer mới!**\n"
            f"• Member: {member.mention}\n"
            f"• Từ clan: **{source_clan['name']}**\n"
            f"• Đến clan: **{dest_clan['name']}**\n"
            f"Vui lòng kiểm tra kênh clan để Accept."
        )
        
        # Notify member
        try:
            await member.send(msg)
        except Exception: pass
        
        # Notify destination captain
        try:
            cap_discord_id = (await db.get_user_by_id(dest_clan["captain_id"]))["discord_id"]
            cap = interaction.client.get_user(int(cap_discord_id))
            if not cap: cap = await interaction.client.fetch_user(int(cap_discord_id))
            if cap: await cap.send(msg)
        except Exception: pass

        await bot_utils.log_event(
            "TRANSFER_REQUESTED",
            f"Transfer {transfer_id} requested by {interaction.user.mention}: {member.mention} to '{to_clan_name}'"
        )

    @transfer_group.command(name="status", description="Check status of a transfer")
    @app_commands.describe(transfer_id="Transfer ID (optional, defaults to your pending transfer)")
    async def transfer_status(self, interaction: discord.Interaction, transfer_id: Optional[int] = None):
        """Check transfer status."""
        if transfer_id:
            transfer = await db.get_transfer(transfer_id)
            if not transfer:
                return await interaction.response.send_message("Không tìm thấy transfer.", ephemeral=True)
        else:
            # Try to find pending transfer for user
            user = await db.get_user(str(interaction.user.id))
            if not user:
                return await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            
            transfer = await db.get_user_pending_transfer(user["id"])
            if not transfer:
                return await interaction.response.send_message("Không tìm thấy yêu cầu transfer nào đang chờ.", ephemeral=True)

        # Show status
        source_clan = await db.get_clan_by_id(transfer["source_clan_id"])
        dest_clan = await db.get_clan_by_id(transfer["dest_clan_id"])
        member_user = await db.get_user_by_id(transfer["member_user_id"])
        
        embed = discord.Embed(
            title=f"Trạng thái Transfer (ID: {transfer['id']})",
            color=discord.Color.green() if transfer['status'] == 'completed' else discord.Color.orange()
        )
        embed.add_field(name="Trạng thái", value=transfer['status'].upper(), inline=False)
        embed.add_field(name="Gốc", value=source_clan['name'], inline=True)
        embed.add_field(name="Đích", value=dest_clan['name'], inline=True)
        embed.add_field(name="Thành viên", value=f"<@{member_user['discord_id']}>", inline=True)
        
        view = None
        if transfer['status'] == 'requested':
            view = TransferAcceptView(transfer['id'], transfer['source_clan_id'], transfer['dest_clan_id'], transfer['member_user_id'])
            
        await interaction.response.send_message(embed=embed, view=view)

    @transfer_group.command(name="cancel", description="Cancel a pending transfer request")
    @app_commands.describe(transfer_id="Transfer ID to cancel")
    async def transfer_cancel(self, interaction: discord.Interaction, transfer_id: int):
        """Cancel a transfer request."""
        transfer = await db.get_transfer(transfer_id)
        if not transfer:
            return await interaction.response.send_message("Không tìm thấy transfer.", ephemeral=True)
            
        if transfer["status"] != "requested":
            return await interaction.response.send_message("Không thể hủy một yêu cầu transfer không ở trạng thái chờ.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            
        # Check permission: Initiator OR Captain of Source Clan
        is_initiator = transfer["requested_by_user_id"] == user["id"]
        
        clan_data = await db.get_user_clan(user["id"])
        is_source_captain = False
        if clan_data and clan_data["id"] == transfer["source_clan_id"] and clan_data["member_role"] in ["captain", "vice"]:
            is_source_captain = True
            
        if not (is_initiator or is_source_captain):
            return await interaction.response.send_message("Bạn không có quyền hủy yêu cầu transfer này.", ephemeral=True)
            
        await db.cancel_transfer(transfer_id, user["id"], "Cancelled by user")
        await interaction.response.send_message(f"✅ Transfer {transfer_id} đã bị hủy.")
        
        await bot_utils.log_event(
            "TRANSFER_CANCELLED",
            f"Transfer {transfer_id} cancelled by {interaction.user.mention}"
        )


async def setup(bot: commands.Bot):
    """Required setup function for loading the cog."""
    await bot.add_cog(TransferCog(bot))
