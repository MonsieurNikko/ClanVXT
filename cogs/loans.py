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
from services import bot_utils

class LoanAcceptView(discord.ui.View):
    """View for 3-party loan acceptance."""
    
    def __init__(self, loan_id: int, lending_clan_id: int, borrowing_clan_id: int, member_id: int):
        super().__init__(timeout=None)  # Persistent view
        self.loan_id = loan_id
        self.lending_clan_id = lending_clan_id
        self.borrowing_clan_id = borrowing_clan_id
        self.member_id = member_id
        
        # Set dynamic custom_ids for persistence after bot restart
        # Format: loan_accept_{type}:{loan_id}:{lending_clan_id}:{borrowing_clan_id}:{member_id}
        for child in self.children:
            if hasattr(child, 'custom_id'):
                if 'lending' in child.custom_id:
                    child.custom_id = f"loan_accept_lending:{loan_id}:{lending_clan_id}:{borrowing_clan_id}:{member_id}"
                elif 'borrowing' in child.custom_id:
                    child.custom_id = f"loan_accept_borrowing:{loan_id}:{lending_clan_id}:{borrowing_clan_id}:{member_id}"
                elif 'member' in child.custom_id:
                    child.custom_id = f"loan_accept_member:{loan_id}:{lending_clan_id}:{borrowing_clan_id}:{member_id}"

        
    async def update_embed(self, interaction: discord.Interaction):
        """Update the embed to show current acceptance status."""
        loan = await db.get_loan(self.loan_id)
        if not loan or loan["status"] != "requested":
            # Disable buttons if no longer requested
            for child in self.children:
                child.disabled = True
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(view=self)
                else:
                    await interaction.message.edit(view=self)
            except Exception: pass
            return

        lending_clan = await db.get_clan_by_id(self.lending_clan_id)
        borrowing_clan = await db.get_clan_by_id(self.borrowing_clan_id)
        member_user = await db.get_user_by_id(self.member_id)
        
        # Re-create embed
        embed = discord.Embed(
            title="🤝 Yêu cầu Loan thành viên",
            description=f"Yêu cầu loan cho <@{member_user['discord_id']}>",
            color=discord.Color.gold()
        )
        embed.add_field(name="Clan cho loan", value=lending_clan['name'], inline=True)
        embed.add_field(name="Clan mượn", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Thời hạn", value=f"{loan['duration_days']} ngày", inline=True)
        
        # Status indicators
        lending_status = "✅ Đã chấp nhận" if loan["accept_lending"] else "⏳ Đang chờ"
        borrowing_status = "✅ Đã chấp nhận" if loan["accept_borrowing"] else "⏳ Đang chờ"
        member_status = "✅ Đã chấp nhận" if loan["accept_member"] else "⏳ Đang chờ"
        
        embed.add_field(name="Captain cho loan", value=lending_status, inline=True)
        embed.add_field(name="Captain mượn", value=borrowing_status, inline=True)
        embed.add_field(name="Thành viên", value=member_status, inline=True)
        
        # Use .get() to avoid KeyError if column missing or None
        if loan.get("note"):
            embed.add_field(name="Ghi chú", value=loan["note"], inline=False)
            
        embed.set_footer(text=f"Loan ID: {self.loan_id} | Hết hạn sau 48h")
        
        # Always use edit_message if possible, fallback to message.edit
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.message.edit(embed=embed, view=self)
        except Exception: pass
        
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
            
            try:
                await interaction.message.edit(view=self)
            except Exception: pass
            
            await interaction.followup.send(f"✅ **Loan đã kích hoạt!** Khoản loan (ID: {self.loan_id}) đã được tất cả các bên chấp nhận và hiện đang có hiệu lực.")
            
            # Notify all parties via DM
            loan = await db.get_loan(self.loan_id)
            if loan:
                lending_clan = await db.get_clan_by_id(loan["lending_clan_id"])
                borrowing_clan = await db.get_clan_by_id(loan["borrowing_clan_id"])
                member_user = await db.get_user_by_id(loan["member_user_id"])
                
                msg = (
                    f"✅ **Loan #{self.loan_id} đã được kích hoạt!**\n"
                    f"• Member: <@{member_user['discord_id']}>\n"
                    f"• Từ clan: **{lending_clan['name']}**\n"
                    f"• Đến clan: **{borrowing_clan['name']}**\n"
                    f"• Thời hạn: {loan['duration_days']} ngày."
                )
                
                # Notify member
                try:
                    m = interaction.client.get_user(int(member_user["discord_id"]))
                    if m: await m.send(msg)
                except Exception: pass
                
                # Notify lending captain
                try:
                    cap = interaction.client.get_user(int((await db.get_user_by_id(lending_clan["captain_id"]))["discord_id"]))
                    if cap: await cap.send(msg)
                except Exception: pass
                
                # Notify borrowing captain
                try:
                    cap = interaction.client.get_user(int((await db.get_user_by_id(borrowing_clan["captain_id"]))["discord_id"]))
                    if cap: await cap.send(msg)
                except Exception: pass

            # Log
            await bot_utils.log_event(
                "LOAN_ACTIVATED",
                f"Loan {self.loan_id} activated. Member {self.member_id} loaned from {self.lending_clan_id} to {self.borrowing_clan_id}."
            )
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Lỗi khi kích hoạt loan: {e}", ephemeral=True)
            except Exception: pass

    @discord.ui.button(label="Clan Cho Loan Chấp Nhận", style=discord.ButtonStyle.primary, custom_id="loan_accept_lending_placeholder")
    async def accept_lending(self, interaction: discord.Interaction, button: discord.ui.Button):
        # All logic moved to LoanCog.on_interaction to avoid "Interaction already acknowledged"
        pass

    @discord.ui.button(label="Clan Mượn Chấp Nhận", style=discord.ButtonStyle.primary, custom_id="loan_accept_borrowing_placeholder")
    async def accept_borrowing(self, interaction: discord.Interaction, button: discord.ui.Button):
        # All logic moved to LoanCog.on_interaction
        pass

    @discord.ui.button(label="Thành Viên Chấp Nhận", style=discord.ButtonStyle.success, custom_id="loan_accept_member_placeholder")
    async def accept_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # All logic moved to LoanCog.on_interaction
        pass


class LoanCog(commands.Cog):
    """Cog for Loan commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Handle persistent button interactions for loans."""
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        
        # Early return if not a loan interaction
        if not custom_id.startswith("loan_"):
            return
        
        print(f"[DEBUG] Loan Interaction by {interaction.user.id}: {custom_id}")
        
        if interaction.response.is_done():
            return
            
        # Format: loan_accept_{type}:{loan_id}:{lending_clan_id}:{borrowing_clan_id}:{member_id}
        if custom_id.startswith("loan_accept_lending:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                loan_id = int(parts[1])
                lending_clan_id = int(parts[2])
                borrowing_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_loan_accept(interaction, loan_id, lending_clan_id, borrowing_clan_id, member_id, "lending")
                return

        if custom_id.startswith("loan_accept_borrowing:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                loan_id = int(parts[1])
                lending_clan_id = int(parts[2])
                borrowing_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_loan_accept(interaction, loan_id, lending_clan_id, borrowing_clan_id, member_id, "borrowing")
                return

        if custom_id.startswith("loan_accept_member:"):
            parts = custom_id.split(":")
            if len(parts) == 5:
                loan_id = int(parts[1])
                lending_clan_id = int(parts[2])
                borrowing_clan_id = int(parts[3])
                member_id = int(parts[4])
                await self.handle_loan_accept(interaction, loan_id, lending_clan_id, borrowing_clan_id, member_id, "member")
                return

    async def handle_loan_accept(self, interaction: discord.Interaction, loan_id: int, lending_clan_id: int, borrowing_clan_id: int, member_id: int, type_key: str):
        """Handle loan acceptance logic."""
        user = await db.get_user(str(interaction.user.id))
        if not user:
            try: await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            except Exception: pass
            return
            
        # Permissions check
        if type_key == "lending":
            clan_data = await db.get_user_clan(user["id"])
            if not clan_data or clan_data["id"] != lending_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
                try: await interaction.response.send_message("Chỉ Captain/Vice của clan cho loan mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_loan_acceptance(loan_id, lending=True)
            
        elif type_key == "borrowing":
            clan_data = await db.get_user_clan(user["id"])
            if not clan_data or clan_data["id"] != borrowing_clan_id or clan_data["member_role"] not in ["captain", "vice"]:
                try: await interaction.response.send_message("Chỉ Captain/Vice của clan mượn mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_loan_acceptance(loan_id, borrowing=True)
            
        elif type_key == "member":
            if user["id"] != member_id:
                try: await interaction.response.send_message("Chỉ thành viên được loan mới có thể chấp nhận.", ephemeral=True)
                except Exception: pass
                return
            await db.update_loan_acceptance(loan_id, member=True)
        
        # Update UI — wrap defer in try/except to handle race condition
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except discord.HTTPException:
            pass
            
        view = LoanAcceptView(loan_id, lending_clan_id, borrowing_clan_id, member_id)
        await view.update_embed(interaction)
    
    loan_group = app_commands.Group(name="loan", description="Loan management commands")
    
    @loan_group.command(name="request", description="Request to loan a member from another clan")
    @app_commands.describe(
        member="The member you want to borrow",
        duration_days="Duration in days (1-7)",
        note="Optional note"
    )
    async def loan_request(self, interaction: discord.Interaction, member: discord.Member, duration_days: int, note: Optional[str] = None):
        """Create a loan request."""
        # Validation
        if not (1 <= duration_days <= 7):
            return await interaction.response.send_message("Thời hạn loan phải từ 1 đến 7 ngày.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký hệ thống.", ephemeral=True)
            
        # Check requester is Captain/Vice of Borrowing Clan (USER is the borrower now)
        borrowing_clan = await db.get_user_clan(user["id"])
        if not borrowing_clan or borrowing_clan["member_role"] not in ["captain", "vice"]:
            return await interaction.response.send_message("Chỉ Captain/Vice của clan mượn mới có thể gửi yêu cầu loan.", ephemeral=True)
            
        # Check target member exists
        target_user = await db.get_user(str(member.id))
        if not target_user:
            return await interaction.response.send_message("Thành viên này chưa đăng ký hệ thống.", ephemeral=True)
            
        # Target must be in a different clan (the lending clan)
        lending_clan = await db.get_user_clan(target_user["id"])
        if not lending_clan:
            return await interaction.response.send_message("Thành viên này hiện đang tự do, hãy dùng /clan invite.", ephemeral=True)
            
        if lending_clan["id"] == borrowing_clan["id"]:
            return await interaction.response.send_message("Thành viên này đã ở trong clan của bạn.", ephemeral=True)
            
        if lending_clan["status"] != "active":
            return await interaction.response.send_message(f"Clan '{lending_clan['name']}' hiện không hoạt động.", ephemeral=True)

        # [P0 Fix] Cannot loan the Captain
        if lending_clan["member_role"] == "captain":
            return await interaction.response.send_message("❌ Không thể loan Captain của clan.", ephemeral=True)
            
        # [P0 Fix] Check if lending clan has enough members to loan
        lending_member_count = await db.count_clan_members(lending_clan["id"])
        if lending_member_count <= config.MIN_MEMBERS_ACTIVE:
            return await interaction.response.send_message(
                f"❌ Clan '{lending_clan['name']}' chỉ có {lending_member_count} thành viên. "
                f"Phải có ít nhất {config.MIN_MEMBERS_ACTIVE + 1} người mới có thể cho mượn.",
                ephemeral=True
            )
            
        # Permission Checks
        allowed, error = await permissions.can_request_loan(target_user["id"], lending_clan["id"])
        if not allowed:
            return await interaction.response.send_message(f"❌ Không thể yêu cầu loan: {error}", ephemeral=True)
            
        # Check Borrowing Clan active loan status (Limit increased to 2)
        active_loans_count = await db.count_active_loans_for_clan(borrowing_clan["id"])
        if active_loans_count >= 2:
            return await interaction.response.send_message(
                f"❌ Clan của bạn đã đạt giới hạn tối đa (2) khoản loan đang hoạt động.", 
                ephemeral=True
            )
            
        # Create Loan
        loan_id = await db.create_loan(
            lending_clan_id=lending_clan["id"],
            borrowing_clan_id=borrowing_clan["id"],
            member_user_id=target_user["id"],
            requested_by_user_id=user["id"],
            duration_days=duration_days,
            note=note
        )
        
        # Auto-accept for initiator's side (Borrowing)
        await db.update_loan_acceptance(loan_id, borrowing=True)
        
        # Build Embed
        view = LoanAcceptView(loan_id, lending_clan["id"], borrowing_clan["id"], target_user["id"])
        embed = discord.Embed(
            title="🤝 Yêu cầu Loan thành viên",
            description=f"Yêu cầu loan cho {member.mention}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Clan cho loan", value=lending_clan['name'], inline=True)
        embed.add_field(name="Clan mượn", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Thời hạn", value=f"{duration_days} ngày", inline=True)
        embed.add_field(name="Captain cho loan", value="⏳ Đang chờ", inline=True)
        embed.add_field(name="Captain mượn", value="✅ Đã chấp nhận (Người tạo)", inline=True)
        embed.add_field(name="Thành viên", value="⏳ Đang chờ", inline=True)
        
        if note:
            embed.add_field(name="Ghi chú", value=note, inline=False)
            
        embed.set_footer(text=f"Loan ID: {loan_id} | Hết hạn sau 48h")
        
        # Send message to LENDING clan's private channel
        lending_channel_id = lending_clan.get("discord_channel_id")
        if lending_channel_id:
            try:
                channel = interaction.client.get_channel(int(lending_channel_id))
                if channel:
                    await channel.send(f"🔔 **Thông báo từ {borrowing_clan['name']}**:", embed=embed, view=view)
                    await interaction.response.send_message(f"✅ Đã gửi yêu cầu loan đến clan **{lending_clan['name']}**.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ Không tìm thấy kênh của clan **{lending_clan['name']}**. Vui lòng báo Mod.", ephemeral=True)
            except Exception as e:
                 await interaction.response.send_message(f"❌ Lỗi khi gửi tin nhắn đến clan đối thủ: {e}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Clan **{lending_clan['name']}** chưa có kênh riêng. Vui lòng báo Mod.", ephemeral=True)

        # [P2 Fix] Notify member via DM (Now with View)
        dm_msg = (
            f"🤝 **Yêu cầu Loan mới!**\n"
            f"• Member: {member.mention}\n"
            f"• Từ clan: **{lending_clan['name']}**\n"
            f"• Đến clan: **{borrowing_clan['name']}**\n"
            f"• Thời hạn: {duration_days} ngày.\n"
            f"Bạn có thể Accept trực tiếp tại đây hoặc trong kênh clan."
        )
        try:
            await member.send(dm_msg, embed=embed, view=view)
        except Exception: pass
        
        # Notify lending captain via DM (Instructions updated)
        dm_cap_msg = (
            f"🤝 **Yêu cầu Loan mới cho thành viên của bạn!**\n"
            f"• Member: {member.mention}\n"
            f"• Từ clan: **{lending_clan['name']}** (Của bạn)\n"
            f"• Đến clan: **{borrowing_clan['name']}**\n"
            f"• Thời hạn: {duration_days} ngày.\n"
            f"Vui lòng kiểm tra kênh clan để Accept."
        )
        try:
            cap_discord_id = (await db.get_user_by_id(lending_clan["captain_id"]))["discord_id"]
            cap = interaction.client.get_user(int(cap_discord_id))
            if cap: await cap.send(dm_cap_msg)
        except Exception: pass

        await bot_utils.log_event(
            "LOAN_REQUESTED",
            f"Loan {loan_id} requested by {interaction.user.mention} (from {borrowing_clan['name']}): {member.mention} from '{lending_clan['name']}'"
        )

    @loan_group.command(name="status", description="Check status of a loan")
    @app_commands.describe(loan_id="Loan ID (optional, defaults to your clan's active loan)")
    async def loan_status(self, interaction: discord.Interaction, loan_id: Optional[int] = None):
        """Check loan status."""
        if loan_id:
            loan = await db.get_loan(loan_id)
            if not loan:
                return await interaction.response.send_message("Không tìm thấy loan.", ephemeral=True)
        else:
            # Try to find active loan for user's clan
            user = await db.get_user(str(interaction.user.id))
            if not user:
                return await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            clan = await db.get_user_clan(user["id"])
            if not clan:
                return await interaction.response.send_message("Bạn không ở trong clan nào.", ephemeral=True)
                
            loan = await db.get_active_loan_for_clan(clan["id"])
            if not loan:
                return await interaction.response.send_message("Không tìm thấy loan nào đang hoạt động cho clan của bạn.", ephemeral=True)

        # Show status
        lending_clan = await db.get_clan_by_id(loan["lending_clan_id"])
        borrowing_clan = await db.get_clan_by_id(loan["borrowing_clan_id"])
        member_user = await db.get_user_by_id(loan["member_user_id"])
        
        embed = discord.Embed(
            title=f"Trạng thái Loan (ID: {loan['id']})",
            color=discord.Color.blue() if loan['status'] == 'active' else discord.Color.gold()
        )
        embed.add_field(name="Trạng thái", value=loan['status'].upper(), inline=False)
        embed.add_field(name="Bên cho mượn", value=lending_clan['name'], inline=True)
        embed.add_field(name="Bên mượn", value=borrowing_clan['name'], inline=True)
        embed.add_field(name="Thành viên", value=f"<@{member_user['discord_id']}>", inline=True)
        
        if loan['status'] == 'active':
            start = datetime.fromisoformat(loan['start_at'])
            end = datetime.fromisoformat(loan['end_at'])
            embed.add_field(name="Bắt đầu", value=discord.utils.format_dt(start, "d"), inline=True)
            embed.add_field(name="Kết thúc", value=discord.utils.format_dt(end, "R"), inline=True)
        
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
            return await interaction.response.send_message("Không tìm thấy loan.", ephemeral=True)
            
        if loan["status"] != "requested":
            return await interaction.response.send_message("Không thể hủy một khoản loan không ở trạng thái chờ.", ephemeral=True)
            
        user = await db.get_user(str(interaction.user.id))
        if not user:
            return await interaction.response.send_message("Bạn chưa đăng ký.", ephemeral=True)
            
        # Check permission: Initiator OR Captain of Lending Clan
        is_initiator = loan["requested_by_user_id"] == user["id"]
        
        clan_data = await db.get_user_clan(user["id"])
        is_lending_captain = False
        if clan_data and clan_data["id"] == loan["lending_clan_id"] and clan_data["member_role"] in ["captain", "vice"]:
            is_lending_captain = True
            
        if not (is_initiator or is_lending_captain):
            return await interaction.response.send_message("Bạn không có quyền hủy khoản loan này.", ephemeral=True)
            
        await db.cancel_loan(loan_id, user["id"], "Cancelled by user")
        await interaction.response.send_message(f"✅ Loan {loan_id} đã bị hủy.")
        
        await bot_utils.log_event(
            "LOAN_CANCELLED",
            f"Loan {loan_id} cancelled by {interaction.user.mention}"
        )


async def setup(bot: commands.Bot):
    """Required setup function for loading the cog."""
    await bot.add_cog(LoanCog(bot))
