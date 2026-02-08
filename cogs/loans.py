"""
Loan System Cog
Implements member loan functionality between clans.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional, List

import config
from services import db, permissions, cooldowns, loan_service
import main as bot_main

class LoanAcceptView(discord.ui.View):
    """View for 3-party loan acceptance."""
    
    def __init__(self, loan_id: int, lending_clan_id: int, borrowing_clan_id: int, member_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.loan_id = loan_id
        self.lending_clan_id = lending_clan_id
        self.borrowing_clan_id = borrowing_clan_id
        self.member_id = member_id
        
    async def update_embed(self, interaction: discord.Interaction):
        """Update the embed to show current acceptance status."""
        loan = await db.get_loan(self.loan_id)
        if not loan or loan["status"] != "requested":
            # Disable buttons if no longer requested
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            return

        lending_clan = await db.get_clan_by_id(self.lending_clan_id)
        borrowing_clan = await db.get_clan_by_id(self.borrowing_clan_id)
        member_user = await db.get_user_by_id(self.member_id)
        
        # Re-create embed
        embed = discord.Embed(
            title="🤝 Member Loan Request",
            description=f"Loan request for <@{member_user['discord_id']}>",
            color=discord.Color.gold()
        )
        embed.add_field(name="Lending Clan", value=lending_clan['name'], inline=True)
        embed.add_field(name="Borrowing Clan", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Duration", value=f"{loan['duration_days']} days", inline=True)
        
        # Status indicators
        lending_status = "✅ Accepted" if loan["accept_lending"] else "⏳ Pending"
        borrowing_status = "✅ Accepted" if loan["accept_borrowing"] else "⏳ Pending"
        member_status = "✅ Accepted" if loan["accept_member"] else "⏳ Pending"
        
        embed.add_field(name="Lending Captain", value=lending_status, inline=True)
        embed.add_field(name="Borrowing Captain", value=borrowing_status, inline=True)
        embed.add_field(name="Member", value=member_status, inline=True)
        
        if loan["note"]:
            embed.add_field(name="Note", value=loan["note"], inline=False)
            
        embed.set_footer(text=f"Loan ID: {self.loan_id} | Expires in 48h")
        
        await interaction.message.edit(embed=embed, view=self)
        
        # Check if all accepted
        if loan["accept_lending"] and loan["accept_borrowing"] and loan["accept_member"]:
            await self.activate_loan(interaction)

    async def activate_loan(self, interaction: discord.Interaction):
        """Activate the loan."""
        try:
            await loan_service.activate_loan(self.loan_id, interaction.guild)
            
            # Disable buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.message.edit(view=self)
            await interaction.followup.send(f"✅ **Loan Active!** The loan (ID: {self.loan_id}) has been fully accepted and is now active.")
            
            # Log
            await bot_main.log_event(
                "LOAN_ACTIVATED",
                f"Loan {self.loan_id} activated. Member {self.member_id} loaned from {self.lending_clan_id} to {self.borrowing_clan_id}."
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error activating loan: {e}", ephemeral=True)

    @discord.ui.button(label="Lending Accept", style=discord.ButtonStyle.primary, custom_id="loan_accept_lending")
    async def accept_lending(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of lending clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.lending_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice of Lending Clan can accept.", ephemeral=True)
            
        await db.update_loan_acceptance(self.loan_id, lending=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Borrowing Accept", style=discord.ButtonStyle.primary, custom_id="loan_accept_borrowing")
    async def accept_borrowing(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is captain/vice of borrowing clan
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        clan_data = await db.get_user_clan(user["id"])
        if not clan_data or clan_data["id"] != self.borrowing_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice of Borrowing Clan can accept.", ephemeral=True)
            
        await db.update_loan_acceptance(self.loan_id, borrowing=True)
        await interaction.response.defer()
        await self.update_embed(interaction)

    @discord.ui.button(label="Member Accept", style=discord.ButtonStyle.success, custom_id="loan_accept_member")
    async def accept_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is the member
        user = await db.get_user(str(interaction.user.id))
        if not user or user["id"] != self.member_id:
            return await interaction.response.send_message("Only the loaned member can accept.", ephemeral=True)
            
        await db.update_loan_acceptance(self.loan_id, member=True)
        await interaction.response.defer()
        await self.update_embed(interaction)


class LoanCog(commands.Cog):
    """Cog for Loan commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    loan_group = app_commands.Group(name="loan", description="Loan management commands")
    
    @loan_group.command(name="request", description="Request to loan a member to another clan")
    @app_commands.describe(
        member="The member to loan",
        to_clan_name="The clan borrowing the member",
        duration_days="Duration in days (1-7)",
        note="Optional note"
    )
    async def loan_request(self, interaction: discord.Interaction, member: discord.Member, to_clan_name: str, duration_days: int, note: Optional[str] = None):
        """Create a loan request."""
        # Validation
        if not (1 <= duration_days <= 7):
            return await interaction.response.send_message("Duration must be between 1 and 7 days.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("You are not registered.", ephemeral=True)
            
        # Check requester is Captain/Vice of Source Clan
        source_clan = await db.get_user_clan(user["id"])
        if not source_clan or source_clan["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Only Captain/Vice can initiate a loan.", ephemeral=True)
            
        # Check target member is in Source Clan
        target_user = await db.get_user(str(member.id))
        if not target_user:
            return await interaction.response.send_message("Member not registered.", ephemeral=True)
            
        target_member_clan = await db.get_user_clan(target_user["id"])
        if not target_member_clan or target_member_clan["id"] != source_clan["id"]:
            return await interaction.response.send_message("Member is not in your clan.", ephemeral=True)
            
        # Check Borrowing Clan exists
        borrowing_clan = await db.get_clan(to_clan_name)
        if not borrowing_clan:
            return await interaction.response.send_message(f"Clan '{to_clan_name}' not found.", ephemeral=True)
            
        if borrowing_clan["id"] == source_clan["id"]:
            return await interaction.response.send_message("Cannot loan to your own clan.", ephemeral=True)
            
        # Permission Checks
        allowed, error = await permissions.can_request_loan(target_user["id"], source_clan["id"])
        if not allowed:
            return await interaction.response.send_message(f"❌ Cannot request loan: {error}", ephemeral=True)
            
        # Check Borrowing Clan active loan status
        borrowing_active_loan = await db.get_active_loan_for_clan(borrowing_clan["id"])
        if borrowing_active_loan:
            return await interaction.response.send_message(f"❌ Borrowing clan '{to_clan_name}' already has an active loan transaction.", ephemeral=True)
            
        # Create Loan
        loan_id = await db.create_loan(
            lending_clan_id=source_clan["id"],
            borrowing_clan_id=borrowing_clan["id"],
            member_user_id=target_user["id"],
            requested_by_user_id=user["id"],
            duration_days=duration_days,
            note=note
        )
        
        # Send Embed
        view = LoanAcceptView(loan_id, source_clan["id"], borrowing_clan["id"], target_user["id"])
        embed = discord.Embed(
            title="🤝 Member Loan Request",
            description=f"Loan request for {member.mention}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Lending Clan", value=source_clan['name'], inline=True)
        embed.add_field(name="Borrowing Clan", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Duration", value=f"{duration_days} days", inline=True)
        embed.add_field(name="Lending Captain", value="✅ Accepted (Initiator)" if user["id"] == user["id"] else "⏳ Pending", inline=True) # Initiator logic handled in View update usually, but here we just show pending for now or auto-accept?
        # Actually, initiator should probably auto-accept. Let's do that.
        
        # Auto-accept for initiator's side (Lending)
        await db.update_loan_acceptance(loan_id, lending=True)
        
        # Re-update embed to show accepted
        embed.set_field_at(3, name="Lending Captain", value="✅ Accepted", inline=True)
        embed.add_field(name="Borrowing Captain", value="⏳ Pending", inline=True)
        embed.add_field(name="Member", value="⏳ Pending", inline=True)
        
        if note:
            embed.add_field(name="Note", value=note, inline=False)
            
        embed.set_footer(text=f"Loan ID: {loan_id} | Expires in 48h")
        
        await interaction.response.send_message(embed=embed, view=view)
        
        await bot_main.log_event(
            "LOAN_REQUESTED",
            f"Loan {loan_id} requested by {interaction.user.mention}: {member.mention} to '{to_clan_name}'"
        )

    @loan_group.command(name="status", description="Check status of a loan")
    @app_commands.describe(loan_id="Loan ID (optional, defaults to your clan's active loan)")
    async def loan_status(self, interaction: discord.Interaction, loan_id: Optional[int] = None):
        """Check loan status."""
        if loan_id:
            loan = await db.get_loan(loan_id)
            if not loan:
                return await interaction.response.send_message("Loan not found.", ephemeral=True)
        else:
            # Try to find active loan for user's clan
            user = await db.get_user(str(interaction.user.id))
            if not user:
                return await interaction.response.send_message("Not registered.", ephemeral=True)
            clan = await db.get_user_clan(user["id"])
            if not clan:
                return await interaction.response.send_message("Not in a clan.", ephemeral=True)
                
            loan = await db.get_active_loan_for_clan(clan["id"])
            if not loan:
                return await interaction.response.send_message("No active loan found for your clan.", ephemeral=True)

        # Show status
        lending_clan = await db.get_clan_by_id(loan["lending_clan_id"])
        borrowing_clan = await db.get_clan_by_id(loan["borrowing_clan_id"])
        member_user = await db.get_user_by_id(loan["member_user_id"])
        
        embed = discord.Embed(
            title=f"Loan Status (ID: {loan['id']})",
            color=discord.Color.blue() if loan['status'] == 'active' else discord.Color.gold()
        )
        embed.add_field(name="Status", value=loan['status'].upper(), inline=False)
        embed.add_field(name="Lending", value=lending_clan['name'], inline=True)
        embed.add_field(name="Borrowing", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Member", value=f"<@{member_user['discord_id']}>", inline=True)
        
        if loan['status'] == 'active':
            start = datetime.fromisoformat(loan['start_at'])
            end = datetime.fromisoformat(loan['end_at'])
            embed.add_field(name="Started", value=discord.utils.format_dt(start, "d"), inline=True)
            embed.add_field(name="Ends", value=discord.utils.format_dt(end, "R"), inline=True)
        
        view = None
        if loan['status'] == 'requested':
            view = LoanAcceptView(loan['id'], loan['lending_clan_id'], loan['borrowing_clan_id'], loan['member_user_id'])
            
        await interaction.response.send_message(embed=embed, view=view)

    @loan_group.command(name="cancel", description="Cancel a pending loan request")
    @app_commands.describe(loan_id="Loan ID to cancel")
    async def loan_cancel(self, interaction: discord.Interaction, loan_id: int):
        """Cancel a loan request."""
        loan = await db.get_loan(loan_id)
        if not loan:
            return await interaction.response.send_message("Loan not found.", ephemeral=True)
            
        if loan["status"] != "requested":
            return await interaction.response.send_message("Cannot cancel a loan that is not pending.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Not registered.", ephemeral=True)
            
        # Check permission: Initiator OR Captain of Lending Clan
        is_initiator = loan["requested_by_user_id"] == user["id"]
        
        clan_data = await db.get_user_clan(user["id"])
        is_lending_captain = False
        if clan_data and clan_data["id"] == loan["lending_clan_id"] and clan_data["member_role"] in ["captain", "vice"]:
            is_lending_captain = True
            
        if not (is_initiator or is_lending_captain):
            return await interaction.response.send_message("You do not have permission to cancel this loan.", ephemeral=True)
            
        await db.cancel_loan(loan_id, user["id"], "Cancelled by user")
        await interaction.response.send_message(f"✅ Loan {loan_id} cancelled.")
        
        await bot_main.log_event(
            "LOAN_CANCELLED",
            f"Loan {loan_id} cancelled by {interaction.user.mention}"
        )


async def setup(bot: commands.Bot):
    """Required setup function for loading the cog."""
    await bot.add_cog(LoanCog(bot))
