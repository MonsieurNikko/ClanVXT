"""
Highlights Cog
Handles user-submitted gameplay highlights, match linking, and community voting.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiosqlite
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import logging

import config
from services import db, bot_utils

class HighlightModal(discord.ui.Modal, title="Submit Highlight"):
    video_url = discord.ui.TextInput(
        label="Video Link (YouTube/Outplayed/Medal...)",
        placeholder="https://youtu.be/...",
        min_length=5,
        max_length=200,
        required=True
    )
    caption = discord.ui.TextInput(
        label="Caption/Mô tả",
        placeholder="Ace 1v5 siêu đẳng cấp...",
        min_length=5,
        max_length=100,
        required=True
    )

    def __init__(self, match_id: int, clan_id: int):
        super().__init__()
        self.match_id = match_id
        self.clan_id = clan_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        user = interaction.user
        match_id = self.match_id
        clan_id = self.clan_id
        url = self.video_url.value
        caption = self.caption.value

        log_msg = f"[HIGHLIGHT] User {user} (ID: {user.id}) submitting highlight for Match #{match_id}. URL: {url}"
        print(log_msg)
        await bot_utils.log_event("HIGHLIGHT_SUBMIT", log_msg)

        # 1. Validate Link (Basic check)
        valid_domains = ["youtube.com", "youtu.be", "outplayed.tv", "medal.tv", "tiktok.com", "drive.google.com"]
        if not any(domain in url.lower() for domain in valid_domains):
            await interaction.followup.send("⚠️ Link không hợp lệ! Vui lòng dùng: YouTube, Outplayed, Medal, TikTok, hoặc Google Drive.", ephemeral=True)
            return

        # 2. Get Match Details for Embed
        match_data = await db.get_match_by_id(match_id)
        if not match_data:
            await interaction.followup.send("❌ Không tìm thấy thông tin trận đấu.", ephemeral=True)
            return
        
        # Determine opponent and map
        clan_a = await db.get_clan_by_id(match_data["clan_a_id"])
        clan_b = await db.get_clan_by_id(match_data["clan_b_id"])
        
        if not clan_a or not clan_b:
             await interaction.followup.send("❌ Lỗi dữ liệu Clan.", ephemeral=True)
             return

        user_clan_name = clan_a["name"] if clan_a["id"] == clan_id else clan_b["name"]
        opponent_name = clan_b["name"] if clan_a["id"] == clan_id else clan_a["name"]
        
        # Parse maps json if possible, or get from note/result
        # Simulating map info since it's complex in existing DB, might be in 'maps' column
        map_name = "Unknown Map"
        if match_data["maps"]:
            import json
            try:
                maps = json.loads(match_data["maps"])
                if maps: map_name = maps[0] # Take first map for simple display
            except: pass

        result_str = "Kết quả: ???"
        if match_data["winner_clan_id"]:
            if match_data["winner_clan_id"] == clan_id:
                result_str = "🏆 WIN"
            else:
                result_str = "❌ LOSS"
        
        if match_data["score_a"] is not None and match_data["score_b"] is not None:
             s_a = match_data["score_a"]
             s_b = match_data["score_b"]
             # If user is A
             if match_data["clan_a_id"] == clan_id:
                 result_str += f" ({s_a}-{s_b})"
             else:
                 result_str += f" ({s_b}-{s_a})"

        # 3. Post to Channel
        channel = discord.utils.get(interaction.guild.text_channels, name=config.CHANNEL_HIGHLIGHTS)
        if not channel:
            # Fallback by searching ID if name fails (though config uses name)
             await interaction.followup.send(f"❌ Không tìm thấy kênh Highlights: `{config.CHANNEL_HIGHLIGHTS}`", ephemeral=True)
             return

        embed = discord.Embed(
            title=caption,
            description=f"**Match #{match_id}**\n🆚 **{opponent_name}**\n🗺️ **{map_name}** | {result_str}",
            color=discord.Color.gold()
        )
        embed.set_author(name=f"{user.display_name} ({user_clan_name})", icon_url=user.display_avatar.url)
        embed.add_field(name="🎥 Watch Clip", value=url, inline=False)
        embed.set_footer(text=f"ClanVXT Highlights • Match ID: {match_id}")
        
        # View with Share Button
        view = HighlightPostView(user_name=user.display_name, clan_name=user_clan_name, video_url=url)
        
        try:
            msg = await channel.send(embed=embed, view=view)
            await msg.add_reaction("🔥")
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi gửi bài: {e}", ephemeral=True)
            return

        # 4. Save to DB
        async with db.get_connection() as conn:
            await conn.execute(
                """INSERT INTO highlights (user_id, match_id, clan_id, video_url, caption, message_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user.id, match_id, clan_id, url, caption, str(msg.id))
            )
            await conn.commit()

        await interaction.followup.send(f"✅ Đã đăng highlight thành công tại {channel.mention}!", ephemeral=True)


class HighlightPostView(discord.ui.View):
    def __init__(self, user_name: str, clan_name: str, video_url: str):
        super().__init__(timeout=None) # Persistent view
        self.user_name = user_name
        self.clan_name = clan_name
        self.video_url = video_url

    @discord.ui.button(label="📤 Share", style=discord.ButtonStyle.secondary, custom_id="hl_share")
    async def share_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        content = (
            f"🔥 **Highlight cực căng từ Quốc Hội Thiểu Năng!**\n"
            f"👤 Player: `{self.user_name}` | Clan: `{self.clan_name}`\n"
            f"🎥 Xem clip: {self.video_url}\n\n"
            f"---------------------------------\n"
            f"🏆 Tham gia tranh tài tại League VXT: {config.SERVER_INVITE_URL}"
        )
        await interaction.response.send_message(content, ephemeral=True)

    @discord.ui.button(label="⚠️ Report", style=discord.ButtonStyle.danger, custom_id="hl_report")
    async def report_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Notify mods log
        await bot_utils.log_event("HIGHLIGHT_REPORT", f"User {interaction.user} reported highlight message {interaction.message.id} by {self.user_name}")
        await interaction.response.send_message("✅ Đã gửi báo cáo cho Admin kiểm tra.", ephemeral=True)


class MatchSelectView(discord.ui.View):
    def __init__(self, matches: List[Dict[str, Any]], clan_id: int):
        super().__init__(timeout=60)
        self.clan_id = clan_id
        
        options = []
        for m in matches:
            mid = m["id"]
            # Determine opponent
            opp_id = m["clan_b_id"] if m["clan_a_id"] == clan_id else m["clan_a_id"]
            # We need to fetch opponent name names are not in match object usually?
            # Actually db.get_recent_matches_for_clan likely joins names? 
            # If not, we'll just show 'Opponent' details in description or need to fetch.
            # Assuming matches have 'opponent_name' if using a specific query, or we fetch.
            # Let's assume standard match object and label generically if needed, but better to query names.
            # For simplicity in this step, I'll update db.py to fetch names or do single lookups. 
            # Wait, view logic shouldn't do async lookups in __init__.
            # The caller should pass enriched data.
            
            lbl = f"Match #{mid}"
            desc = f"{m.get('created_at', '')[:10]}"
            if "opponent_name" in m:
                desc = f"vs {m['opponent_name']} | {desc}"
            
            options.append(discord.SelectOption(label=lbl, description=desc, value=str(mid)))

        self.select = discord.ui.Select(placeholder="Chọn trận đấu...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        match_id = int(self.select.values[0])
        await interaction.response.send_modal(HighlightModal(match_id, self.clan_id))


class HighlightsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_weekly_winner.start()

    def cog_unload(self):
        self.check_weekly_winner.cancel()

    @app_commands.command(name="highlight", description="Submit a highlight or view info")
    async def highlight(self, interaction: discord.Interaction, action: str = "submit"):
        """
        Action: submit
        """
        if action != "submit":
             await interaction.response.send_message("Hiện tại chỉ hỗ trợ `/highlight submit`.", ephemeral=True)
             return

        # 1. Identify User's Clan
        user_data = await db.get_user(str(interaction.user.id))
        if not user_data:
             await interaction.response.send_message("❌ Bạn chưa đăng ký hệ thống! Dùng `/clan register`.", ephemeral=True)
             return
        
        user_id_sql = user_data["id"]
        clan_role = await db.get_user_clan_role(user_id_sql) # Returns (clan_id, role) or None
        
        if not clan_role:
             await interaction.response.send_message("❌ Bạn không thuộc Clan nào cả.", ephemeral=True)
             return
            
        clan_id, role = clan_role

        # 2. Get Recent Matches (Last 5)
        # We need a custom query to get match + opponent name
        recent_matches = []
        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT m.*, 
                       c1.name as clan_a_name, c2.name as clan_b_name 
                FROM matches m
                JOIN clans c1 ON m.clan_a_id = c1.id
                JOIN clans c2 ON m.clan_b_id = c2.id
                WHERE (m.clan_a_id = ? OR m.clan_b_id = ?)
                  AND m.status IN ('confirmed', 'resolved')
                ORDER BY m.created_at DESC
                LIMIT 5
            """, (clan_id, clan_id))
            rows = await cursor.fetchall()
            for r in rows:
                row_dict = dict(r)
                # Formatter for selector
                if row_dict["clan_a_id"] == clan_id:
                    row_dict["opponent_name"] = row_dict["clan_b_name"]
                else:
                    row_dict["opponent_name"] = row_dict["clan_a_name"]
                recent_matches.append(row_dict)

        if not recent_matches:
            await interaction.response.send_message("❌ Clan bạn chưa có trận đấu nào được xác nhận gần đây.", ephemeral=True)
            return

        view = MatchSelectView(recent_matches, clan_id)
        await interaction.response.send_message("👇 **Chọn trận đấu bạn muốn gửi Highlight:**", view=view, ephemeral=True)

    @tasks.loop(time=datetime.now(timezone.utc).replace(hour=23, minute=59, second=0).time()) # Runs daily, check logic inside
    async def check_weekly_winner(self):
        # We want Sunday only.
        now = datetime.now(timezone.utc)
        if now.weekday() != 6: # 0=Mon, 6=Sun
            return
            
        print("[HIGHLIGHT] Starting Weekly Winner Check...")
        await bot_utils.log_event("HIGHLIGHT_WEEKLY", "Starting weekly highlight vote count.")

        # Logic: Get highlights created in last 7 days
        # SQL: created_at >= date('now', '-7 days')
        
        # We need to manually count reactions for each message to filter own-clan votes.
        # This is expensive, so limit to top candidates if possible, but for now scan all active ones.
        
        week_ago_str = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        
        candidates = []
        
        channel = discord.utils.get(self.bot.get_all_channels(), name=config.CHANNEL_HIGHLIGHTS)
        if not channel:
            print("[HIGHLIGHT] Highlights channel not found for weekly calculation.")
            return

        async with db.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT h.*, u.discord_id as submitter_discord_id 
                FROM highlights h
                JOIN users u ON h.user_id = u.id
                WHERE h.created_at >= ? AND h.status = 'active'
            """, (week_ago_str,))
            rows = await cursor.fetchall()
            
            for row in rows:
                h_id = row["id"]
                msg_id = row["message_id"]
                submitter_clan_id = row["clan_id"]
                
                try:
                    msg = await channel.fetch_message(int(msg_id))
                except:
                    continue # Message deleted?
                
                # Count 'FIRE' reactions
                valid_count = 0
                reaction = discord.utils.get(msg.reactions, emoji="🔥")
                
                if reaction:
                    async for user in reaction.users():
                        if user.bot: continue
                        
                        # Validate User: Is he in same clan?
                        # DB Lookup for each voter (Expensive! but strictly requested)
                        voter_data = await db.get_user(str(user.id))
                        if not voter_data:
                            valid_count += 1 # Non-registered users count as 'Public' -> Valid? Yes.
                            continue
                            
                        voter_clan_role = await db.get_user_clan_role(voter_data["id"])
                        if not voter_clan_role:
                            valid_count += 1 # No clan -> Valid
                        else:
                            v_clan_id, _ = voter_clan_role
                            if v_clan_id != submitter_clan_id:
                                valid_count += 1
                            else:
                                # Same clan -> Invalid
                                pass
                
                candidates.append({
                    "id": h_id,
                    "votes": valid_count,
                    "user_id": row["submitter_discord_id"],
                    "clan_id": submitter_clan_id,
                    "url": row["video_url"]
                })
        
        if not candidates:
            print("[HIGHLIGHT] No candidates this week.")
            return
            
        # Sort by votes
        candidates.sort(key=lambda x: x["votes"], reverse=True)
        winner = candidates[0]
        
        if winner["votes"] == 0:
            return # No votes at all

        # Announce Winner
        winner_user = f"<@{winner['user_id']}>"
        
        embed = discord.Embed(title="🏆 HIGHLIGHT OF THE WEEK", color=discord.Color.gold())
        embed.description = (
            f"👑 **Winner:** {winner_user}\n"
            f"🔥 **Valid Votes:** {winner['votes']}\n\n"
            f"🎥 **Clip:** {winner['url']}\n\n"
            f"🎁 **Rewards:** Role `Highlight God` + **7 Elo** for Clan!"
        )
        await channel.send(content="@everyone", embed=embed)
        
        # Apply Rewards
        # 1. Elo
        await db.add_bonus_elo(winner["clan_id"], 7, f"Highlight of the Week (#{winner['id']})")
        
        # 2. Role (If possible)
        # user = guild.get_member(...) -> add_role. 
        # Needs guild context.
        guild = self.bot.get_guild(config.GUILD_ID)
        if guild:
             member = guild.get_member(int(winner["user_id"]))
             role_god = discord.utils.get(guild.roles, name="Highlight God 🎥")
             if member and role_god:
                 await member.add_roles(role_god)
        
        await bot_utils.log_event("HIGHLIGHT_WINNER", f"Winner: {winner_user}, Votes: {winner['votes']}")


async def setup(bot: commands.Bot):
    await bot.add_cog(HighlightsCog(bot))
