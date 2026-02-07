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
import main as bot_main

class TransferAcceptView(discord.ui.View):
    """View for 3-party transfer acceptance."""
    
    def __init__(self, transfer_id: int, source_clan_id: int, dest_clan_id: int, member_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.transfer_id = transfer_id
        self.source_clan_id = source_clan_id
        self.dest_clan_id = dest_clan_id
        self.member_id = member_id
        
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
            title="✈️ Member Transfer Request",
            description=f"Transfer request for <@{member_user['discord_id']}>",
            color=discord.Color.orange()
        )
        embed.add_field(name="Source Clan", value=source_clan['name'], inline=True)
        embed.add_field(name="Destination Clan", value=dest_clan['name'], inline=True)
        
        # Status indicators
        source_status = "✅ Accepted" if transfer["accept_source"] else "⏳ Pending"
        dest_status = "✅ Accepted" if transfer["accept_dest"] else "⏳ Pending"
        member_status = "✅ Accepted" if transfer["accept_member"] else "⏳ Pending"
        
        embed.add_field(name="Source Captain", value=source_status, inline=True)
        embed.add_field(name="Dest Captain", value=dest_status, inline=True)
        embed.add_field(name="Member", value=member_status, inline=True)
            
        embed.set_footer(text=f"Transfer ID: {self.transfer_id} | Expires in 48h")
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Check if all accepted
        if transfer["accept_source"] and transfer["accept_dest"] and transfer["accept_member"]:
            await self.complete_transfer(interaction)

    async def complete_transfer(self, interaction: discord.Interaction):
        """Complete the transfer."""
        try:
            # Execute transfer
            await db.complete_transfer(self.transfer_id)
            
            # Move member in DB
            await db.remove_member(self.member_id, self.source_clan_id)
            await db.add_member(self.member_id, self.dest_clan_id, "member")
            
            # Apply sickness
            await cooldowns.apply_transfer_sickness(self.member_id)
            
            # Apply join/leave cooldown (14 days)
            await cooldowns.apply_member_join_cooldown(self.member_id, "Transferred to new clan")
            
            # Disable buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.message.edit(view=self)
            await interaction.followup.send(f"✅ **Transfer Completed!** Member has been moved to the new clan.")
            
            # Log
            await bot_main.log_event(
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
            except:
                pass
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error completing transfer: {e}", ephemeral=True)

    @discord.ui.button(label="Source Accept", style=discord.ButtonStyle.primary, custom_id="transfer_accept_source")
    async def accept_source(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of source clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.source_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice of Source Clan can accept.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, source=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Dest Accept", style=discord.ButtonStyle.primary, custom_id="transfer_accept_dest")
    async def accept_dest(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of dest clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.dest_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice of Destination Clan can accept.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, dest=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Member Accept", style=discord.ButtonStyle.success, custom_id="transfer_accept_member")
    async def accept_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is the member
        user = await db.get_user(str(interaction.user.id))
        if not user or user["id"] != self.member_id:
            return await interaction.response.send_message("Only the transferring member can accept.", ephemeral=True)
            
        await db.update_transfer_acceptance(self.transfer_id, member=True)
        await interaction.response.defer()
        await self.update_embed(interaction)


class TransferCog(commands.Cog):
    """Cog for Transfer commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
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
            return await interaction.response.send_message("You are not registered.", ephemeral=True)
            
        # Check requester is Captain/Vice of Source Clan
        source_clan = await db.get_user_clan(user["id"])
        if not source_clan or source_clan["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice can initiate a transfer.", ephemeral=True)
            
        # Check target member is in Source Clan
        target_user = await db.get_user(str(member.id))
        if not target_user:
            return await interaction.response.send_message("Member not registered.", ephemeral=True)
            
        target_member_clan = await db.get_user_clan(target_user["id"])
        if not target_member_clan or target_member_clan["id"] != source_clan["id"]:
            return await interaction.response.send_message("Member is not in your clan.", ephemeral=True)
            
        # Check Dest Clan exists
        dest_clan = await db.get_clan(to_clan_name)
        if not dest_clan:
            return await interaction.response.send_message(f"Clan '{to_clan_name}' not found.", ephemeral=True)
            
        if dest_clan["id"] == source_clan["id"]:
            return await interaction.response.send_message("Cannot transfer to the same clan.", ephemeral=True)
            
        # Permission Checks
        allowed, error = await permissions.can_request_transfer(target_user["id"], source_clan["id"], dest_clan["id"])
        if not allowed:
            return await interaction.response.send_message(f"❌ Cannot request transfer: {error}", ephemeral=True)
            
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
            title="✈️ Member Transfer Request",
            description=f"Transfer request for {member.mention}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Source Clan", value=source_clan['name'], inline=True)
        embed.add_field(name="Destination Clan", value=dest_clan['name'], inline=True)
        embed.add_field(name="Source Captain", value="✅ Accepted (Initiator)" if user["id"] == user["id"] else "⏳ Pending", inline=True)
        
        # Auto-accept for initiator's side (Source)
        await db.update_transfer_acceptance(transfer_id, source=True)
        
        embed.set_field_at(2, name="Source Captain", value="✅ Accepted", inline=True)
        embed.add_field(name="Dest Captain", value="⏳ Pending", inline=True)
        embed.add_field(name="Member", value="⏳ Pending", inline=True)
        
        if note:
            embed.add_field(name="Note", value=note, inline=False)
            
        embed.set_footer(text=f"Transfer ID: {transfer_id} | Expires in 48h")
        
        await interaction.response.send_message(embed=embed, view=view)
        
        await bot_main.log_event(
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
                return await interaction.response.send_message("Transfer not found.", ephemeral=True)
        else:
            # Try to find pending transfer for user
            user = await db.get_user(str(interaction.user.id))
            if not user:
                return await interaction.response.send_message("Not registered.", ephemeral=True)
            
            transfer = await db.get_user_pending_transfer(user["id"])
            if not transfer:
                return await interaction.response.send_message("No pending transfer found for you.", ephemeral=True)

        # Show status
        source_clan = await db.get_clan_by_id(transfer["source_clan_id"])
        dest_clan = await db.get_clan_by_id(transfer["dest_clan_id"])
        member_user = await db.get_user_by_id(transfer["member_user_id"])
        
        embed = discord.Embed(
            title=f"Transfer Status (ID: {transfer['id']})",
            color=discord.Color.green() if transfer['status'] == 'completed' else discord.Color.orange()
        )
        embed.add_field(name="Status", value=transfer['status'].upper(), inline=False)
        embed.add_field(name="Source", value=source_clan['name'], inline=True)
        embed.add_field(name="Dest", value=dest_clan['name'], inline=True)
        embed.add_field(name="Member", value=f"<@{member_user['discord_id']}>", inline=True)
        
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
            return await interaction.response.send_message("Transfer not found.", ephemeral=True)
            
        if transfer["status"] != "requested":
            return await interaction.response.send_message("Cannot cancel a transfer that is not pending.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        # Check permission: Initiator OR Captain of Source Clan
        is_initiator = transfer["requested_by_user_id"] == user["id"]
        
        clan_data = await db.get_user_clan(user["id"])
        is_source_captain = False
        if clan_data and clan_data["id"] == transfer["source_clan_id"] and clan_data["member_role"] in ["captain", "vice"]:
            is_source_captain = True
            
        if not (is_initiator or is_source_captain):
            return await interaction.response.send_message("You do not have permission to cancel this transfer.", ephemeral=True)
            
        await db.cancel_transfer(transfer_id, user["id"], "Cancelled by user")
        await interaction.response.send_message(f"✅ Transfer {transfer_id} cancelled.")
        
        await bot_main.log_event(
            "TRANSFER_CANCELLED",
            f"Transfer {transfer_id} cancelled by {interaction.user.mention}"
        )
