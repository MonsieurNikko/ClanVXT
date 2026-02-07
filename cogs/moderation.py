"""
Moderation Cog
Implements /report and /appeal commands for users.
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

import config
from services import db, permissions
import main as bot_main


# =============================================================================
# ERROR MESSAGES
# =============================================================================

ERRORS = {
    "NOT_REGISTERED": "Bạn chưa đăng ký trong hệ thống. Hãy sử dụng `/register` trước.",
    "CASE_NOT_FOUND": "Không tìm thấy case #{case_id}.",
    "APPEAL_EXISTS": "Bạn đã appeal case này rồi. Mỗi case chỉ được appeal 1 lần.",
    "APPEAL_EXPIRED": "Thời hạn appeal đã hết (7 ngày kể từ khi case được xử lý).",
    "CASE_NOT_RESOLVED": "Case này chưa được xử lý. Bạn chỉ có thể appeal sau khi có quyết định.",
    "NOT_YOUR_CASE": "Bạn không phải là đối tượng của case này và không thể appeal.",
    "TARGET_NOT_FOUND": "Không tìm thấy đối tượng được report.",
    "SYSTEM_BANNED": "Bạn đang bị cấm sử dụng hệ thống clan.",
}


# =============================================================================
# COG DEFINITION
# =============================================================================

class ModerationCog(commands.Cog):
    """Cog for user-facing moderation commands (report, appeal)."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    # =========================================================================
    # REPORT COMMANDS
    # =========================================================================
    
    report_group = app_commands.Group(name="report", description="Report users, clans, or matches")
    
    @report_group.command(name="create", description="Tạo báo cáo mới")
    @app_commands.describe(
        target_type="Loại đối tượng: user (người chơi), clan, match",
        target="Tên/ID của đối tượng (user mention, tên clan, hoặc match ID)",
        description="Mô tả chi tiết vấn đề",
        evidence="Bằng chứng (link ảnh, video, v.v.)"
    )
    async def report_create(
        self, 
        interaction: discord.Interaction, 
        target_type: Literal["user", "clan", "match", "other"],
        target: str,
        description: str,
        evidence: Optional[str] = None
    ):
        """Create a new report which automatically creates a case."""
        await interaction.response.defer(ephemeral=True)
        
        # Get reporter
        reporter = await db.get_user(str(interaction.user.id))
        if not reporter:
            await interaction.followup.send(ERRORS["NOT_REGISTERED"], ephemeral=True)
            return
        
        # Check if reporter is system banned
        if await db.is_user_system_banned(reporter["id"]):
            await interaction.followup.send(ERRORS["SYSTEM_BANNED"], ephemeral=True)
            return
        
        # Resolve target ID
        target_id = 0
        target_name = target
        
        if target_type == "user":
            # Try to parse mention or find by name
            try:
                # Handle mention format <@123456789>
                if target.startswith("<@") and target.endswith(">"):
                    user_id = target.strip("<@!>")
                    target_user = await db.get_user(user_id)
                    if target_user:
                        target_id = target_user["id"]
                        target_name = f"User ID: {user_id}"
                else:
                    # Assume it's a Discord user ID
                    target_user = await db.get_user(target)
                    if target_user:
                        target_id = target_user["id"]
                        target_name = f"User ID: {target}"
            except Exception:
                pass
        elif target_type == "clan":
            clan = await db.get_clan_any_status(target)
            if clan:
                target_id = clan["id"]
                target_name = clan["name"]
        elif target_type == "match":
            try:
                match_id = int(target)
                match = await db.get_match(match_id)
                if match:
                    target_id = match["id"]
                    target_name = f"Match #{match_id}"
            except ValueError:
                pass
        
        # Create case
        case_id = await db.create_case(
            reporter_id=reporter["id"],
            target_type=target_type,
            target_id=target_id,
            reason=description,
            proof=evidence
        )
        
        # Send confirmation
        embed = discord.Embed(
            title="📋 Report Đã Được Gửi",
            description=f"Case **#{case_id}** đã được tạo và gửi đến đội ngũ Mod.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Loại", value=target_type, inline=True)
        embed.add_field(name="Đối tượng", value=target_name, inline=True)
        embed.add_field(name="Mô tả", value=description[:200] + ("..." if len(description) > 200 else ""), inline=False)
        if evidence:
            embed.add_field(name="Bằng chứng", value=evidence[:100], inline=False)
        embed.set_footer(text=f"Sử dụng /report status {case_id} để theo dõi tiến độ")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log to mod channel
        await bot_main.log_event(
            "CASE_OPENED",
            f"Case #{case_id} opened by {interaction.user.mention}. "
            f"Type: {target_type}, Target: {target_name}"
        )
        
        # Send alert to mod log
        log_channel = bot_main.get_log_channel()
        if log_channel:
            mod_role = bot_main.get_mod_role()
            ping = mod_role.mention if mod_role else ""
            
            alert_embed = discord.Embed(
                title=f"🚨 Báo Cáo Mới - Case #{case_id}",
                description=description[:500],
                color=discord.Color.orange()
            )
            alert_embed.add_field(name="Loại", value=target_type, inline=True)
            alert_embed.add_field(name="Đối tượng", value=target_name, inline=True)
            alert_embed.add_field(name="Người báo cáo", value=interaction.user.mention, inline=True)
            if evidence:
                alert_embed.add_field(name="Bằng chứng", value=evidence, inline=False)
            alert_embed.set_footer(text=f"Sử dụng /admin case view {case_id} để xem chi tiết")
            
            await log_channel.send(ping, embed=alert_embed)
    
    @report_group.command(name="status", description="Xem trạng thái case")
    @app_commands.describe(case_id="ID của case")
    async def report_status(self, interaction: discord.Interaction, case_id: int):
        """View public-safe status of a case."""
        await interaction.response.defer(ephemeral=True)
        
        case = await db.get_case(case_id)
        if not case:
            await interaction.followup.send(
                ERRORS["CASE_NOT_FOUND"].format(case_id=case_id), 
                ephemeral=True
            )
            return
        
        # Build public-safe embed (no sensitive info)
        status_emoji = {
            "open": "🔵",
            "investigating": "🔍",
            "needs_info": "❓",
            "resolved": "✅",
            "appealed": "📝",
            "closed": "⬛"
        }
        
        status_text = {
            "open": "Đang chờ xử lý",
            "investigating": "Đang điều tra",
            "needs_info": "Cần thêm thông tin",
            "resolved": "Đã xử lý",
            "appealed": "Đang xem xét kháng cáo",
            "closed": "Đã đóng"
        }
        
        embed = discord.Embed(
            title=f"📋 Case #{case_id}",
            color=discord.Color.blue() if case["status"] != "closed" else discord.Color.dark_grey()
        )
        embed.add_field(
            name="Trạng thái", 
            value=f"{status_emoji.get(case['status'], '❔')} {status_text.get(case['status'], case['status'])}", 
            inline=True
        )
        embed.add_field(name="Loại", value=case["target_type"], inline=True)
        embed.add_field(name="Ngày tạo", value=case["created_at"][:10], inline=True)
        
        # Show verdict if resolved (public version only)
        if case["status"] in ("resolved", "closed") and case.get("verdict"):
            verdict_text = {
                "guilty": "Vi phạm",
                "innocent": "Không vi phạm",
                "dismissed": "Bác bỏ"
            }
            embed.add_field(
                name="Kết luận", 
                value=verdict_text.get(case["verdict"], case["verdict"]), 
                inline=False
            )
        
        # Show appeal info
        if case["status"] == "resolved" and case.get("appeal_deadline"):
            try:
                deadline = datetime.fromisoformat(case["appeal_deadline"])
                now = datetime.utcnow()
                if deadline > now:
                    days_left = (deadline - now).days
                    embed.add_field(
                        name="Kháng cáo",
                        value=f"Còn {days_left} ngày để kháng cáo",
                        inline=False
                    )
            except Exception:
                pass
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # =========================================================================
    # APPEAL COMMANDS
    # =========================================================================
    
    appeal_group = app_commands.Group(name="appeal", description="Appeal case decisions")
    
    @appeal_group.command(name="create", description="Kháng cáo quyết định của case")
    @app_commands.describe(
        case_id="ID của case cần kháng cáo",
        description="Lý do kháng cáo",
        evidence="Bằng chứng bổ sung (nếu có)"
    )
    async def appeal_create(
        self, 
        interaction: discord.Interaction, 
        case_id: int,
        description: str,
        evidence: Optional[str] = None
    ):
        """Create an appeal for a resolved case (once within 7 days)."""
        await interaction.response.defer(ephemeral=True)
        
        # Get user
        user = await db.get_user(str(interaction.user.id))
        if not user:
            await interaction.followup.send(ERRORS["NOT_REGISTERED"], ephemeral=True)
            return
        
        # Check if system banned
        if await db.is_user_system_banned(user["id"]):
            await interaction.followup.send(ERRORS["SYSTEM_BANNED"], ephemeral=True)
            return
        
        # Get case
        case = await db.get_case(case_id)
        if not case:
            await interaction.followup.send(
                ERRORS["CASE_NOT_FOUND"].format(case_id=case_id), 
                ephemeral=True
            )
            return
        
        # Check case status
        if case["status"] not in ("resolved",):
            if case["status"] in ("appealed", "closed"):
                await interaction.followup.send(
                    "Case này đã được kháng cáo hoặc đã đóng.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(ERRORS["CASE_NOT_RESOLVED"], ephemeral=True)
            return
        
        # Check if appeal already exists
        existing_appeal = await db.get_appeal_by_case(case_id)
        if existing_appeal:
            await interaction.followup.send(ERRORS["APPEAL_EXISTS"], ephemeral=True)
            return
        
        # Check 7-day window
        if case.get("appeal_deadline"):
            try:
                deadline = datetime.fromisoformat(case["appeal_deadline"])
                if datetime.utcnow() > deadline:
                    await interaction.followup.send(ERRORS["APPEAL_EXPIRED"], ephemeral=True)
                    return
            except Exception:
                pass
        
        # Optional: Check if user is the target of the case
        # For now, allow any registered user to appeal if they believe they're affected
        
        # Create appeal
        appeal_id = await db.create_appeal(
            case_id=case_id,
            user_id=user["id"],
            reason=description,
            proof=evidence
        )
        
        # Send confirmation
        embed = discord.Embed(
            title="📝 Kháng Cáo Đã Được Gửi",
            description=f"Kháng cáo **#{appeal_id}** cho Case #{case_id} đã được gửi đến đội ngũ Mod.",
            color=discord.Color.gold()
        )
        embed.add_field(name="Lý do", value=description[:200] + ("..." if len(description) > 200 else ""), inline=False)
        if evidence:
            embed.add_field(name="Bằng chứng bổ sung", value=evidence[:100], inline=False)
        embed.set_footer(text=f"Sử dụng /appeal status {case_id} để theo dõi")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log
        await bot_main.log_event(
            "APPEAL_CREATED",
            f"Appeal #{appeal_id} created for Case #{case_id} by {interaction.user.mention}"
        )
        
        # Alert mods
        log_channel = bot_main.get_log_channel()
        if log_channel:
            mod_role = bot_main.get_mod_role()
            ping = mod_role.mention if mod_role else ""
            
            await log_channel.send(
                f"{ping}\n"
                f"📝 **Kháng Cáo Mới - Appeal #{appeal_id}** cho Case #{case_id}\n"
                f"• Người kháng cáo: {interaction.user.mention}\n"
                f"• Lý do: {description[:200]}"
            )
    
    @appeal_group.command(name="status", description="Xem trạng thái kháng cáo")
    @app_commands.describe(case_id="ID của case")
    async def appeal_status(self, interaction: discord.Interaction, case_id: int):
        """View appeal status for a case."""
        await interaction.response.defer(ephemeral=True)
        
        appeal = await db.get_appeal_by_case(case_id)
        if not appeal:
            await interaction.followup.send(
                f"Không tìm thấy kháng cáo cho Case #{case_id}.", 
                ephemeral=True
            )
            return
        
        status_text = {
            "pending": "🔵 Đang chờ xem xét",
            "reviewing": "🔍 Đang xem xét",
            "upheld": "✅ Giữ nguyên quyết định",
            "reduced": "⬇️ Giảm nhẹ hình phạt",
            "overturned": "🔄 Hủy bỏ quyết định"
        }
        
        embed = discord.Embed(
            title=f"📝 Kháng Cáo #{appeal['id']} (Case #{case_id})",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Trạng thái", 
            value=status_text.get(appeal["status"], appeal["status"]), 
            inline=True
        )
        embed.add_field(name="Ngày tạo", value=appeal["created_at"][:10], inline=True)
        
        if appeal.get("reviewed_at"):
            embed.add_field(name="Ngày xem xét", value=appeal["reviewed_at"][:10], inline=True)
        
        if appeal.get("mod_verdict") and appeal["status"] != "pending":
            embed.add_field(name="Kết quả", value=appeal["mod_verdict"], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)


# =============================================================================
# COG SETUP
# =============================================================================

async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(ModerationCog(bot))
