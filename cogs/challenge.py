"""
Challenge Upgrade — "ĐẠI CHIẾN CLANS"
Ban/Pick map phase + voice/text channel management for clan challenges.
Inserted between challenge accept and match creation flow.

v1.3.0 — ImDaMinh
"""

import asyncio
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import discord
from discord.ext import commands, tasks

from services import db, bot_utils, permissions
import config


# =============================================================================
# PERSISTENCE
# =============================================================================

SESSIONS_FILE = Path(__file__).parent.parent / "data" / "challenge_sessions.json"

# In-memory storage for active ban/pick sessions
_active_sessions: Dict[int, "MapBanPickState"] = {}


def _save_sessions():
    """Persist active sessions to disk for bot restart survival."""
    data = {}
    for mid, s in _active_sessions.items():
        data[str(mid)] = {
            "match_id": s.match_id,
            "clan_a_id": s.clan_a_id,
            "clan_b_id": s.clan_b_id,
            "clan_a_name": s.clan_a_name,
            "clan_b_name": s.clan_b_name,
            "clan_a_role_id": s.clan_a_role_id,
            "clan_b_role_id": s.clan_b_role_id,
            "voice_a_id": s.voice_a_id,
            "voice_b_id": s.voice_b_id,
            "text_match_id": s.text_match_id,
            "remaining_maps": s.remaining_maps,
            "bans_a": s.bans_a,
            "bans_b": s.bans_b,
            "picks_a": s.picks_a,
            "picks_b": s.picks_b,
            "random_map": s.random_map,
            "current_turn": s.current_turn,
            "arena_channel_id": s.arena_channel_id,
            "creator_id": s.creator_id,
            "embed_message_id": s.embed_message_id,
            "pending_selection": s.pending_selection,
            "side_choices": s.side_choices,
        }
    try:
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSIONS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[CHALLENGE] Error saving sessions: {e}")


def _load_sessions():
    """Load sessions from disk after bot restart."""
    if not SESSIONS_FILE.exists():
        return
    try:
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        for _mid_str, s in data.items():
            state = MapBanPickState(
                match_id=s["match_id"],
                clan_a_id=s["clan_a_id"],
                clan_b_id=s["clan_b_id"],
                clan_a_name=s["clan_a_name"],
                clan_b_name=s["clan_b_name"],
                clan_a_role_id=s.get("clan_a_role_id"),
                clan_b_role_id=s.get("clan_b_role_id"),
                voice_a_id=s.get("voice_a_id"),
                voice_b_id=s.get("voice_b_id"),
                text_match_id=s.get("text_match_id"),
                remaining_maps=s.get("remaining_maps", list(config.MAP_POOL)),
                bans_a=s.get("bans_a", []),
                bans_b=s.get("bans_b", []),
                picks_a=s.get("picks_a", []),
                picks_b=s.get("picks_b", []),
                random_map=s.get("random_map"),
                current_turn=s.get("current_turn", 0),
                arena_channel_id=s.get("arena_channel_id", 0),
                creator_id=s.get("creator_id", ""),
                embed_message_id=s.get("embed_message_id"),
                pending_selection=s.get("pending_selection", []),
                side_choices=s.get("side_choices", {}),
            )
            _active_sessions[state.match_id] = state
        print(f"[CHALLENGE] Restored {len(_active_sessions)} active sessions from disk")
    except Exception as e:
        print(f"[CHALLENGE] Error loading sessions: {e}")


# =============================================================================
# MAP BAN/PICK STATE
# =============================================================================

@dataclass
class MapBanPickState:
    """Tracks the state of a ban/pick session for a match."""
    match_id: int
    clan_a_id: int
    clan_b_id: int
    clan_a_name: str
    clan_b_name: str
    clan_a_role_id: Optional[int]
    clan_b_role_id: Optional[int]

    # Channel IDs (created for this match)
    voice_a_id: Optional[int] = None
    voice_b_id: Optional[int] = None
    text_match_id: Optional[int] = None

    # Ban/Pick tracking
    remaining_maps: List[str] = field(default_factory=lambda: list(config.MAP_POOL))
    bans_a: List[str] = field(default_factory=list)
    bans_b: List[str] = field(default_factory=list)
    picks_a: List[str] = field(default_factory=list)
    picks_b: List[str] = field(default_factory=list)
    random_map: Optional[str] = None

    # Turn tracking: 0-3=bans, 4-5=picks, 6-7=side picks, 8+=done
    current_turn: int = 0

    # Arena/creator info for continuing flow after ban/pick
    arena_channel_id: int = 0
    creator_id: str = ""

    # Embed message ID (for editing)
    embed_message_id: Optional[int] = None

    # Pending selections before confirm
    pending_selection: List[str] = field(default_factory=list)

    # Side choices: {map_name: {"chooser": "a"|"b", "chooser_side": "attack"|"defense"}}
    side_choices: Dict[str, Dict[str, str]] = field(default_factory=dict)

    @property
    def current_clan_side(self) -> str:
        """Which clan acts this turn: 'a' or 'b'."""
        # Turns 0,2,4 = Clan A; Turns 1,3,5 = Clan B
        # Turn 6 = side pick for Map 1 (Clan A picked) → Clan B picks side
        # Turn 7 = side pick for Map 2 (Clan B picked) → Clan A picks side
        if self.current_turn in (0, 2, 4, 7):
            return "a"
        else:  # 1, 3, 5, 6
            return "b"

    @property
    def current_clan_name(self) -> str:
        return self.clan_a_name if self.current_clan_side == "a" else self.clan_b_name

    @property
    def current_clan_role_id(self) -> Optional[int]:
        return self.clan_a_role_id if self.current_clan_side == "a" else self.clan_b_role_id

    @property
    def is_ban_phase(self) -> bool:
        return self.current_turn <= 3

    @property
    def is_pick_phase(self) -> bool:
        return self.current_turn in (4, 5)

    @property
    def is_side_pick_phase(self) -> bool:
        return self.current_turn in (6, 7)

    @property
    def expected_count(self) -> int:
        """How many maps to select this turn (ban/pick only)."""
        if self.is_ban_phase:
            return 2
        elif self.is_pick_phase:
            return 1
        return 0

    @property
    def is_completed(self) -> bool:
        return self.current_turn >= 8


# =============================================================================
# TURN INFO HELPERS
# =============================================================================

_TURN_INFO = [
    {"phase": "BAN",  "side": "a", "count": 2, "label": "Ban 2 maps"},
    {"phase": "BAN",  "side": "b", "count": 2, "label": "Ban 2 maps"},
    {"phase": "BAN",  "side": "a", "count": 2, "label": "Ban 2 maps"},
    {"phase": "BAN",  "side": "b", "count": 2, "label": "Ban 2 maps"},
    {"phase": "PICK", "side": "a", "count": 1, "label": "Pick 1 map"},
    {"phase": "PICK", "side": "b", "count": 1, "label": "Pick 1 map"},
]


def _get_turn_info(turn: int) -> Dict[str, Any]:
    if 0 <= turn < len(_TURN_INFO):
        return _TURN_INFO[turn]
    return {"phase": "DONE", "side": "", "count": 0, "label": "Done"}


# =============================================================================
# EMBED BUILDERS
# =============================================================================

def build_mapbanpick_embed(state: MapBanPickState) -> discord.Embed:
    """Build the main ban/pick status embed."""
    turn_info = _get_turn_info(state.current_turn)

    embed = discord.Embed(
        title="🗺️ ĐẠI CHIẾN CLANS — Ban/Pick Map",
        description=(
            f"**{state.clan_a_name}** ⚔️ **{state.clan_b_name}**\n"
            f"Match #{state.match_id}"
        ),
        color=discord.Color.orange() if state.is_ban_phase else discord.Color.blue(),
    )

    # Remaining maps
    remaining_display = "  ".join(f"`{m}`" for m in state.remaining_maps) if state.remaining_maps else "`Không còn`"
    embed.add_field(
        name=f"🗺️ Maps còn lại ({len(state.remaining_maps)})",
        value=remaining_display,
        inline=False,
    )

    # Bans
    bans_a_text = ", ".join(f"~~{m}~~" for m in state.bans_a) if state.bans_a else "—"
    bans_b_text = ", ".join(f"~~{m}~~" for m in state.bans_b) if state.bans_b else "—"
    embed.add_field(name=f"🚫 {state.clan_a_name} Bans", value=bans_a_text, inline=True)
    embed.add_field(name=f"🚫 {state.clan_b_name} Bans", value=bans_b_text, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Picks
    picks_a_text = ", ".join(f"**{m}**" for m in state.picks_a) if state.picks_a else "—"
    picks_b_text = ", ".join(f"**{m}**" for m in state.picks_b) if state.picks_b else "—"
    embed.add_field(name=f"✅ {state.clan_a_name} Picks", value=picks_a_text, inline=True)
    embed.add_field(name=f"✅ {state.clan_b_name} Picks", value=picks_b_text, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # Random map (if determined)
    if state.random_map:
        embed.add_field(
            name="🎲 Map Ngẫu Nhiên (Map 3)",
            value=f"**{state.random_map}**",
            inline=False,
        )

    # Side choices made so far
    if state.side_choices:
        sides_text = []
        for map_name, info in state.side_choices.items():
            chooser = info["chooser"]
            chooser_side = info["chooser_side"]
            other_side = "defense" if chooser_side == "attack" else "attack"
            chooser_name = state.clan_a_name if chooser == "a" else state.clan_b_name
            other_name = state.clan_b_name if chooser == "a" else state.clan_a_name
            se_c = "⚔️" if chooser_side == "attack" else "🛡️"
            se_o = "⚔️" if other_side == "attack" else "🛡️"
            sides_text.append(
                f"**{map_name}**: {se_c} {chooser_name} ({chooser_side.upper()}) | "
                f"{se_o} {other_name} ({other_side.upper()})"
            )
        embed.add_field(name="🎮 Side Assignments", value="\n".join(sides_text), inline=False)

    # Current turn indicator
    if not state.is_completed:
        if state.is_side_pick_phase:
            # Side pick turn
            if state.current_turn == 6:
                side_map = state.picks_a[0] if state.picks_a else "?"
            else:
                side_map = state.picks_b[0] if state.picks_b else "?"
            embed.add_field(
                name="🎮 Chọn Side",
                value=(
                    f"Map: **{side_map}**\n"
                    f"**{state.current_clan_name}** chọn bên \u2694\ufe0f Attack hoặc \ud83d\udee1\ufe0f Defense"
                ),
                inline=False,
            )
        else:
            phase_emoji = "🚫" if state.is_ban_phase else "✅"
            embed.add_field(
                name="🎯 Lượt hiện tại",
                value=(
                    f"{phase_emoji} **{state.current_clan_name}** — {turn_info['label']}\n"
                    f"Chọn từ menu bên dưới rồi bấm ✅ Confirm"
                ),
                inline=False,
            )

    # Pending selection
    if state.pending_selection:
        pending_text = ", ".join(f"`{m}`" for m in state.pending_selection)
        embed.add_field(
            name="📋 Đã chọn (chờ xác nhận)",
            value=pending_text,
            inline=False,
        )

    embed.set_footer(text="Chỉ thành viên clan tới lượt mới được thao tác • Không giới hạn thời gian")
    return embed


def build_summary_embed(state: MapBanPickState) -> discord.Embed:
    """Build the summary embed after ban/pick is complete."""
    embed = discord.Embed(
        title="🗺️ Ban/Pick Hoàn Tất!",
        description=(
            f"**{state.clan_a_name}** ⚔️ **{state.clan_b_name}**\n"
            f"Match #{state.match_id}"
        ),
        color=discord.Color.green(),
    )

    all_bans_a = ", ".join(f"~~{m}~~" for m in state.bans_a)
    all_bans_b = ", ".join(f"~~{m}~~" for m in state.bans_b)
    embed.add_field(name=f"🚫 {state.clan_a_name} Bans", value=all_bans_a, inline=True)
    embed.add_field(name=f"🚫 {state.clan_b_name} Bans", value=all_bans_b, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    maps_text = []
    all_maps = []
    if state.picks_a:
        all_maps.append((state.picks_a[0], f"{state.clan_a_name} pick", "Map 1"))
    if state.picks_b:
        all_maps.append((state.picks_b[0], f"{state.clan_b_name} pick", "Map 2"))
    if state.random_map:
        all_maps.append((state.random_map, "ngẫu nhiên", "Map 3"))

    for map_name, pick_desc, map_label in all_maps:
        icon = "🎲" if pick_desc == "ngẫu nhiên" else "🗺️"
        line = f"{icon} {map_label} ({pick_desc}): **{map_name}**"
        side_info = state.side_choices.get(map_name)
        if side_info:
            chooser = side_info["chooser"]
            chooser_side = side_info["chooser_side"]
            other_side = "defense" if chooser_side == "attack" else "attack"
            c_name = state.clan_a_name if chooser == "a" else state.clan_b_name
            o_name = state.clan_b_name if chooser == "a" else state.clan_a_name
            se_c = "⚔️" if chooser_side == "attack" else "🛡️"
            se_o = "⚔️" if other_side == "attack" else "🛡️"
            line += f"\n   {se_c} {c_name}: {chooser_side.upper()} | {se_o} {o_name}: {other_side.upper()}"
        maps_text.append(line)

    embed.add_field(
        name="⚔️ Maps + Sides",
        value="\n".join(maps_text),
        inline=False,
    )

    embed.set_footer(text="Trận đấu sẽ bắt đầu ngay sau đây!")
    return embed


# =============================================================================
# CHANNEL MANAGEMENT
# =============================================================================

async def create_match_channels(
    guild: discord.Guild,
    clan_a: Dict[str, Any],
    clan_b: Dict[str, Any],
    match_id: int,
) -> tuple:
    """Create 2 voice (limit 5) + 1 text channels for a match."""
    role_a = guild.get_role(int(clan_a["discord_role_id"])) if clan_a.get("discord_role_id") else None
    role_b = guild.get_role(int(clan_b["discord_role_id"])) if clan_b.get("discord_role_id") else None
    bot_member = guild.me

    category = discord.utils.get(guild.categories, name=config.CATEGORY_CLANS)

    # --- Voice A: only Clan A can connect, limit 5 ---
    voice_a_overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, connect=False, speak=False,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True, connect=True, speak=True, manage_channels=True,
        ),
    }
    if role_a:
        voice_a_overwrites[role_a] = discord.PermissionOverwrite(connect=True, speak=True)

    voice_a = await guild.create_voice_channel(
        name=f"🎧 Match - {clan_a['name']}",
        category=category,
        overwrites=voice_a_overwrites,
        user_limit=6,
        reason=f"Match #{match_id}: {clan_a['name']} vs {clan_b['name']}",
    )

    # --- Voice B: only Clan B can connect, limit 5 ---
    voice_b_overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, connect=False, speak=False,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True, connect=True, speak=True, manage_channels=True,
        ),
    }
    if role_b:
        voice_b_overwrites[role_b] = discord.PermissionOverwrite(connect=True, speak=True)

    voice_b = await guild.create_voice_channel(
        name=f"🎧 Match - {clan_b['name']}",
        category=category,
        overwrites=voice_b_overwrites,
        user_limit=6,
        reason=f"Match #{match_id}: {clan_a['name']} vs {clan_b['name']}",
    )

    # --- Text Match: everyone can view, only bot can send ---
    text_overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, send_messages=False, add_reactions=False,
            create_public_threads=False, create_private_threads=False,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_messages=True,
            embed_links=True, manage_channels=True,
        ),
    }
    if role_a:
        text_overwrites[role_a] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
    if role_b:
        text_overwrites[role_b] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

    safe_a = clan_a["name"].lower().replace(" ", "-")[:20]
    safe_b = clan_b["name"].lower().replace(" ", "-")[:20]

    text_match = await guild.create_text_channel(
        name=f"📌-match-{safe_a}-vs-{safe_b}",
        category=category,
        overwrites=text_overwrites,
        reason=f"Match #{match_id}: {clan_a['name']} vs {clan_b['name']}",
    )

    return voice_a, voice_b, text_match


async def notify_clan_channels(
    bot: commands.Bot,
    clan_a: Dict[str, Any],
    clan_b: Dict[str, Any],
    voice_a: discord.VoiceChannel,
    voice_b: discord.VoiceChannel,
    text_match: discord.TextChannel,
    match_id: int,
):
    """Send notifications to each clan's private channel."""
    for clan, voice in [(clan_a, voice_a), (clan_b, voice_b)]:
        if clan.get("discord_channel_id"):
            try:
                channel = bot.get_channel(int(clan["discord_channel_id"]))
                if channel:
                    embed = discord.Embed(
                        title="🔔 Match Ready!",
                        description=(
                            f"**{clan_a['name']}** ⚔️ **{clan_b['name']}**\n"
                            f"Match #{match_id}\n\n"
                            f"🎧 Voice của clan bạn: {voice.mention}\n"
                            f"📌 Room trận: {text_match.mention}\n\n"
                            f"Hãy vào room trận để ban/pick map!"
                        ),
                        color=discord.Color.orange(),
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                print(f"[CHALLENGE] Error notifying clan {clan['name']}: {e}")


async def _delete_channels(bot: commands.Bot, state: MapBanPickState):
    """Delete ALL match channels (voice + text). Does NOT manage _active_sessions."""
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    for ch_id in [state.voice_a_id, state.voice_b_id, state.text_match_id]:
        if ch_id:
            try:
                channel = guild.get_channel(ch_id)
                if channel:
                    await channel.delete(reason=f"Match #{state.match_id} cleanup")
                    print(f"[CHALLENGE] Deleted channel {channel.name} (ID: {ch_id})")
            except Exception as e:
                print(f"[CHALLENGE] Error deleting channel {ch_id}: {e}")

    print(f"[CHALLENGE] Cleaned up all channels for match #{state.match_id}")


# =============================================================================
# BAN/PICK UI VIEW
# =============================================================================

class MapSelectView(discord.ui.View):
    """View with select menu + confirm/reset/cancel buttons for ban/pick.
    Callbacks handle interactions directly (no _noop). on_interaction is fallback for post-restart."""

    def __init__(self, state: MapBanPickState, bot: commands.Bot = None):
        super().__init__(timeout=None)  # Persistent — no timeout
        self._bot = bot
        mid = state.match_id

        turn_info = _get_turn_info(state.current_turn)
        is_ban = turn_info["phase"] == "BAN"
        max_sel = turn_info["count"]

        options = [
            discord.SelectOption(
                label=m,
                value=m,
                emoji="🚫" if is_ban else "✅",
            )
            for m in state.remaining_maps
        ]

        if options:
            select = discord.ui.Select(
                placeholder=f"{'Ban' if is_ban else 'Pick'} {max_sel} map(s)...",
                options=options,
                min_values=max_sel,
                max_values=max_sel,
                custom_id=f"mapbp_select:{mid}",
            )
            select.callback = self._handle
            self.add_item(select)

        # Confirm button
        confirm_btn = discord.ui.Button(
            label="✅ Confirm",
            style=discord.ButtonStyle.success,
            custom_id=f"mapbp_confirm:{mid}",
        )
        confirm_btn.callback = self._handle
        self.add_item(confirm_btn)

        # Reset turn button
        reset_btn = discord.ui.Button(
            label="🔁 Reset",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mapbp_reset:{mid}",
        )
        reset_btn.callback = self._handle
        self.add_item(reset_btn)

        # Cancel match button
        cancel_btn = discord.ui.Button(
            label="❌ Cancel Match",
            style=discord.ButtonStyle.danger,
            custom_id=f"mapbp_cancel:{mid}",
        )
        cancel_btn.callback = self._handle
        self.add_item(cancel_btn)

    async def _handle(self, interaction: discord.Interaction):
        """Directly handle interactions."""
        bot = self._bot or interaction.client
        await handle_mapbp_interaction(bot, interaction)


class SidePickView(discord.ui.View):
    """View with Attack/Defense buttons for side pick phase."""

    def __init__(self, state: MapBanPickState, bot: commands.Bot = None):
        super().__init__(timeout=None)
        self._bot = bot
        mid = state.match_id

        atk_btn = discord.ui.Button(
            label="⚔️ Attack",
            style=discord.ButtonStyle.danger,
            custom_id=f"mapbp_side_atk:{mid}",
        )
        atk_btn.callback = self._handle
        self.add_item(atk_btn)

        def_btn = discord.ui.Button(
            label="🛡️ Defense",
            style=discord.ButtonStyle.primary,
            custom_id=f"mapbp_side_def:{mid}",
        )
        def_btn.callback = self._handle
        self.add_item(def_btn)

        cancel_btn = discord.ui.Button(
            label="❌ Cancel Match",
            style=discord.ButtonStyle.secondary,
            custom_id=f"mapbp_cancel:{mid}",
        )
        cancel_btn.callback = self._handle
        self.add_item(cancel_btn)

    async def _handle(self, interaction: discord.Interaction):
        bot = self._bot or interaction.client
        await handle_mapbp_interaction(bot, interaction)


# =============================================================================
# TURN VALIDATION
# =============================================================================

async def _validate_turn_user(interaction: discord.Interaction, state: MapBanPickState) -> bool:
    """Check if the interacting user belongs to the clan whose turn it is."""
    user = await db.get_user(str(interaction.user.id))
    if not user:
        await interaction.response.send_message("❌ Bạn chưa có trong hệ thống.", ephemeral=True)
        return False

    membership = await db.get_user_clan(user["id"])
    if not membership:
        await interaction.response.send_message("❌ Bạn không thuộc clan nào.", ephemeral=True)
        return False

    expected_clan_id = state.clan_a_id if state.current_clan_side == "a" else state.clan_b_id
    if membership["id"] != expected_clan_id:
        await interaction.response.send_message(
            f"❌ Chưa đến lượt clan bạn! Đang chờ **{state.current_clan_name}**.",
            ephemeral=True,
        )
        return False

    return True


# =============================================================================
# MATCH CANCELLATION
# =============================================================================

async def _cancel_match(bot: commands.Bot, state: MapBanPickState, reason: str = ""):
    """Cancel an in-progress ban/pick session and clean up."""
    # Notify in text channel
    guild = bot.get_guild(config.GUILD_ID)
    if guild and state.text_match_id:
        text_ch = guild.get_channel(state.text_match_id)
        if text_ch:
            cancel_embed = discord.Embed(
                title="❌ Trận Đấu Đã Bị Huỷ",
                description=(
                    f"**{state.clan_a_name}** vs **{state.clan_b_name}**\n"
                    f"Match #{state.match_id}\n\n"
                    f"Lý do: {reason}"
                ),
                color=discord.Color.red(),
            )
            try:
                await text_ch.send(embed=cancel_embed)
                # Remove buttons from ban/pick embed
                if state.embed_message_id:
                    try:
                        msg = await text_ch.fetch_message(state.embed_message_id)
                        await msg.edit(view=None)
                    except Exception:
                        pass
            except Exception:
                pass

    # Cancel the match in DB
    try:
        await db.update_match_status_atomic(state.match_id, "created", "cancelled")
    except Exception as e:
        print(f"[CHALLENGE] Error cancelling match #{state.match_id} in DB: {e}")

    # Remove from active sessions BEFORE delayed cleanup to prevent double-trigger
    _active_sessions.pop(state.match_id, None)
    _save_sessions()

    # Schedule delayed cleanup (5 min)
    asyncio.create_task(_delayed_cleanup(bot, state))

    await bot_utils.log_event(
        "CHALLENGE_CANCELLED",
        f"Match #{state.match_id}: {state.clan_a_name} vs {state.clan_b_name} — {reason}",
    )


# =============================================================================
# CONTINUE TO EXISTING MATCH FLOW
# =============================================================================

async def _delayed_cleanup(bot: commands.Bot, state: MapBanPickState):
    """Wait 5 minutes then delete all match channels."""
    try:
        guild = bot.get_guild(config.GUILD_ID)
        if guild and state.text_match_id:
            text_ch = guild.get_channel(state.text_match_id)
            if text_ch:
                await text_ch.send(
                    f"⏳ Các kênh match sẽ bị xoá sau **{config.MATCH_CHANNEL_CLEANUP_DELAY // 60} phút**."
                )
        await asyncio.sleep(config.MATCH_CHANNEL_CLEANUP_DELAY)
        await _delete_channels(bot, state)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[CHALLENGE] Cleanup error for match #{state.match_id}: {e}")


async def _continue_to_match_flow(bot: commands.Bot, state: MapBanPickState):
    """After ban/pick is complete, send match report embed in the TEXT channel."""
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return

    text_ch = guild.get_channel(state.text_match_id) if state.text_match_id else None

    # Send summary embed
    if text_ch:
        summary_embed = build_summary_embed(state)
        await text_ch.send(embed=summary_embed)

    # Build match embed using existing code (reuse 100%)
    from cogs.matches import create_match_embed, MatchCreatedView

    match = await db.get_match_with_clans(state.match_id)
    if not match:
        print(f"[CHALLENGE] ERROR: Match #{state.match_id} not found in DB")
        return

    embed = create_match_embed(
        match,
        "🆕 **Đang chờ kết quả...**\n\nHãy báo cáo kết quả sau khi hoàn thành trận.",
        discord.Color.blue(),
    )
    view = MatchCreatedView(
        match_id=state.match_id,
        creator_id=state.creator_id,
        clan_a_id=state.clan_a_id,
        clan_b_id=state.clan_b_id,
        clan_a_name=state.clan_a_name,
        clan_b_name=state.clan_b_name,
    )

    # Send match report embed in TEXT MATCH channel (not arena)
    if text_ch:
        msg = await text_ch.send(embed=embed, view=view)
        await db.update_match_message_ids(state.match_id, str(msg.id), str(text_ch.id))
    else:
        # Fallback: send in arena
        arena_channel = bot.get_channel(state.arena_channel_id)
        if arena_channel:
            msg = await arena_channel.send(embed=embed, view=view)
            await db.update_match_message_ids(state.match_id, str(msg.id), str(arena_channel.id))

    # Ban/pick done — keep session for cleanup checker to handle
    # Channels will be cleaned after match is confirmed/voided/cancelled

    await bot_utils.log_event(
        "CHALLENGE_BANPICK_DONE",
        f"Match #{state.match_id}: {state.clan_a_name} vs {state.clan_b_name} — "
        f"Maps: {', '.join(state.picks_a + state.picks_b + ([state.random_map] if state.random_map else []))}",
    )


# =============================================================================
# MAIN ENTRY POINT — Called from arena.py _accept()
# =============================================================================

async def start_challenge_flow(
    interaction: discord.Interaction,
    challenger: Dict[str, Any],
    opponent: Dict[str, Any],
    creator_id: str,
    arena_channel_id: int,
):
    """Start the challenge flow: create channels, send notifications, begin ban/pick."""
    guild = interaction.guild or interaction.client.get_guild(config.GUILD_ID)
    if not guild:
        await interaction.followup.send("❌ Không tìm thấy server.", ephemeral=True)
        return

    if not challenger.get("discord_role_id") or not opponent.get("discord_role_id"):
        await interaction.followup.send(
            "❌ Một hoặc cả hai clan chưa có Discord Role. Không thể tạo phòng match.",
            ephemeral=True,
        )
        return

    # Get creator user record
    creator_user = await db.get_user(creator_id)
    if not creator_user:
        creator_user = await permissions.ensure_user_exists(creator_id, "Unknown")

    # Create match in DB
    match_id = await db.create_match_v2(
        clan_a_id=challenger["id"],
        clan_b_id=opponent["id"],
        creator_user_id=creator_user["id"],
        note=f"ĐẠI CHIẾN CLANS — chấp nhận bởi {interaction.user.display_name}",
    )

    # Create channels
    try:
        voice_a, voice_b, text_match = await create_match_channels(
            guild, challenger, opponent, match_id,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Bot không có quyền tạo kênh. Hãy kiểm tra permissions.", ephemeral=True,
        )
        return
    except Exception as e:
        print(f"[CHALLENGE] Error creating channels: {e}")
        await interaction.followup.send(f"❌ Lỗi khi tạo kênh: {e}", ephemeral=True)
        return

    # Initialize state
    state = MapBanPickState(
        match_id=match_id,
        clan_a_id=challenger["id"],
        clan_b_id=opponent["id"],
        clan_a_name=challenger["name"],
        clan_b_name=opponent["name"],
        clan_a_role_id=int(challenger["discord_role_id"]) if challenger.get("discord_role_id") else None,
        clan_b_role_id=int(opponent["discord_role_id"]) if opponent.get("discord_role_id") else None,
        voice_a_id=voice_a.id,
        voice_b_id=voice_b.id,
        text_match_id=text_match.id,
        arena_channel_id=arena_channel_id,
        creator_id=creator_id,
    )
    _active_sessions[match_id] = state

    # Update challenge message to show accepted
    accepted_embed = discord.Embed(
        title="⚔️ Thách Đấu Đã Được Chấp Nhận!",
        description=(
            f"**{challenger['name']}** vs **{opponent['name']}**\n\n"
            f"✅ Chấp nhận bởi {interaction.user.mention}\n"
            f"📋 Match #{match_id} đã được tạo\n"
            f"📌 Room trận: {text_match.mention}"
        ),
        color=discord.Color.green(),
    )
    try:
        await interaction.message.edit(embed=accepted_embed, view=None)
    except Exception as e:
        print(f"[CHALLENGE] Error updating challenge message: {e}")

    # Notify clan channels
    await notify_clan_channels(
        interaction.client, challenger, opponent,
        voice_a, voice_b, text_match, match_id,
    )

    # Notify challenger clan (like original flow)
    if challenger.get("discord_channel_id"):
        try:
            chal_channel = interaction.client.get_channel(int(challenger["discord_channel_id"]))
            if chal_channel:
                await chal_channel.send(
                    f"✅ Clan **{opponent['name']}** đã **chấp nhận** lời thách đấu!\n"
                    f"Match #{match_id} đã được tạo."
                )
        except Exception as e:
            print(f"[CHALLENGE] Error notifying challenger clan: {e}")

    # Send ban/pick embed + view in text match channel
    bp_embed = build_mapbanpick_embed(state)
    bp_view = MapSelectView(state, interaction.client)
    msg = await text_match.send(embed=bp_embed, view=bp_view)
    state.embed_message_id = msg.id

    # Save to disk
    _save_sessions()

    # Followup
    await interaction.followup.send(
        f"✅ Đã tạo phòng thi đấu! Hãy vào {text_match.mention} để ban/pick map.",
        ephemeral=True,
    )

    await bot_utils.log_event(
        "CHALLENGE_FLOW_STARTED",
        f"Match #{match_id}: {challenger['name']} vs {opponent['name']} — "
        f"Channels created, ban/pick started",
    )


# =============================================================================
# INTERACTION HANDLER — Process ban/pick actions
# =============================================================================

async def handle_mapbp_interaction(bot: commands.Bot, interaction: discord.Interaction):
    """Handle all mapbp_* custom_id interactions."""
    custom_id = interaction.data.get("custom_id", "")
    if not custom_id.startswith("mapbp_"):
        return

    parts = custom_id.split(":")
    if len(parts) < 2:
        return

    action = parts[0]
    try:
        match_id = int(parts[1])
    except ValueError:
        return

    state = _active_sessions.get(match_id)
    if not state:
        await interaction.response.send_message(
            "❌ Phiên ban/pick này không còn tồn tại.", ephemeral=True,
        )
        return

    if state.is_completed:
        await interaction.response.send_message(
            "✅ Ban/pick đã hoàn tất.", ephemeral=True,
        )
        return

    # === SELECT (store pending, wait for confirm) ===
    if action == "mapbp_select":
        if not await _validate_turn_user(interaction, state):
            return

        selected = interaction.data.get("values", [])
        turn_info = _get_turn_info(state.current_turn)

        # Validate count
        if len(selected) != turn_info["count"]:
            await interaction.response.send_message(
                f"❌ Bạn phải chọn đúng **{turn_info['count']}** map.", ephemeral=True,
            )
            return

        # Validate maps available
        for m in selected:
            if m not in state.remaining_maps:
                await interaction.response.send_message(
                    f"❌ Map `{m}` không còn trong danh sách.", ephemeral=True,
                )
                return

        # Store pending selection (user must click Confirm to apply)
        state.pending_selection = list(selected)
        _save_sessions()

        await interaction.response.defer()

        # Update embed to show pending
        try:
            guild = bot.get_guild(config.GUILD_ID)
            text_ch = guild.get_channel(state.text_match_id) if guild else None
            if text_ch and state.embed_message_id:
                msg = await text_ch.fetch_message(state.embed_message_id)
                await msg.edit(embed=build_mapbanpick_embed(state), view=MapSelectView(state, bot))
        except Exception as e:
            print(f"[CHALLENGE] Error updating embed after select: {e}")

    # === CONFIRM ===
    elif action == "mapbp_confirm":
        if not await _validate_turn_user(interaction, state):
            return

        if not state.pending_selection:
            await interaction.response.send_message(
                "❌ Bạn chưa chọn map nào. Hãy chọn từ menu trước.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        turn_info = _get_turn_info(state.current_turn)
        selected = state.pending_selection
        state.pending_selection = []

        # Apply selection
        if turn_info["phase"] == "BAN":
            if state.current_clan_side == "a":
                state.bans_a.extend(selected)
            else:
                state.bans_b.extend(selected)
        elif turn_info["phase"] == "PICK":
            if state.current_clan_side == "a":
                state.picks_a.extend(selected)
            else:
                state.picks_b.extend(selected)

        for m in selected:
            if m in state.remaining_maps:
                state.remaining_maps.remove(m)

        # Advance turn
        state.current_turn += 1

        # Entering side pick phase (turn 6): auto-select random map + random side for Map 3
        if state.current_turn == 6 and len(state.remaining_maps) >= 2:
            state.random_map = random.choice(state.remaining_maps)
            state.remaining_maps = [m for m in state.remaining_maps if m != state.random_map]
            # Auto-assign random side for Map 3
            random_chooser = random.choice(["a", "b"])
            random_side = random.choice(["attack", "defense"])
            state.side_choices[state.random_map] = {
                "chooser": random_chooser, "chooser_side": random_side,
            }

        # Save state
        _save_sessions()

        # Update embed
        try:
            guild = bot.get_guild(config.GUILD_ID)
            text_ch = guild.get_channel(state.text_match_id) if guild else None
            if text_ch and state.embed_message_id:
                msg = await text_ch.fetch_message(state.embed_message_id)

                if state.is_completed:
                    await msg.edit(embed=build_mapbanpick_embed(state), view=None)
                    await _continue_to_match_flow(bot, state)
                elif state.is_side_pick_phase:
                    new_view = SidePickView(state, bot)
                    await msg.edit(embed=build_mapbanpick_embed(state), view=new_view)
                else:
                    new_view = MapSelectView(state, bot)
                    await msg.edit(embed=build_mapbanpick_embed(state), view=new_view)
        except Exception as e:
            print(f"[CHALLENGE] Error updating embed after confirm: {e}")

    # === RESET ===
    elif action == "mapbp_reset":
        if not await _validate_turn_user(interaction, state):
            return

        state.pending_selection = []
        _save_sessions()

        await interaction.response.send_message(
            "🔁 Đã reset lượt chọn. Chọn lại từ menu.",
            ephemeral=True,
        )

        # Update embed
        try:
            guild = bot.get_guild(config.GUILD_ID)
            text_ch = guild.get_channel(state.text_match_id) if guild else None
            if text_ch and state.embed_message_id:
                msg = await text_ch.fetch_message(state.embed_message_id)
                await msg.edit(embed=build_mapbanpick_embed(state), view=MapSelectView(state, bot))
        except Exception as e:
            print(f"[CHALLENGE] Error updating embed after reset: {e}")

    # === SIDE PICK (ATK/DEF) ===
    elif action in ("mapbp_side_atk", "mapbp_side_def"):
        if not state.is_side_pick_phase:
            await interaction.response.send_message("❌ Không đang trong giai đoạn chọn side.", ephemeral=True)
            return
        if not await _validate_turn_user(interaction, state):
            return

        chosen_side = "attack" if action == "mapbp_side_atk" else "defense"
        await interaction.response.defer()

        # Determine which map and who chose
        if state.current_turn == 6:
            map_name = state.picks_a[0] if state.picks_a else "?"
            chooser = "b"  # Clan B picks side for Clan A's map
        else:  # turn 7
            map_name = state.picks_b[0] if state.picks_b else "?"
            chooser = "a"  # Clan A picks side for Clan B's map

        state.side_choices[map_name] = {"chooser": chooser, "chooser_side": chosen_side}
        state.current_turn += 1
        _save_sessions()

        # Update embed
        try:
            guild = bot.get_guild(config.GUILD_ID)
            text_ch = guild.get_channel(state.text_match_id) if guild else None
            if text_ch and state.embed_message_id:
                msg = await text_ch.fetch_message(state.embed_message_id)
                if state.is_completed:
                    await msg.edit(embed=build_mapbanpick_embed(state), view=None)
                    await _continue_to_match_flow(bot, state)
                else:
                    await msg.edit(embed=build_mapbanpick_embed(state), view=SidePickView(state, bot))
        except Exception as e:
            print(f"[CHALLENGE] Error updating embed after side pick: {e}")

    # === CANCEL ===
    elif action == "mapbp_cancel":
        user = await db.get_user(str(interaction.user.id))
        if user:
            membership = await db.get_user_clan(user["id"])
            if membership and membership["id"] in (state.clan_a_id, state.clan_b_id):
                await interaction.response.defer()
                await _cancel_match(bot, state, reason=f"Huỷ bởi {interaction.user.display_name}")
                return

        await interaction.response.send_message(
            "❌ Chỉ thành viên của 2 clan mới có thể huỷ trận.", ephemeral=True,
        )


# =============================================================================
# COG
# =============================================================================

class ChallengeCog(commands.Cog):
    """Handles the challenge upgrade flow: match channels + ban/pick maps."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[CHALLENGE] ChallengeCog initialized")

    async def cog_load(self):
        """Restore active sessions from disk on bot startup."""
        _load_sessions()
        if _active_sessions:
            print(f"[CHALLENGE] {len(_active_sessions)} active ban/pick sessions restored")
        # Start cleanup checker
        self._cleanup_checker.start()

    async def cog_unload(self):
        self._cleanup_checker.cancel()

    @tasks.loop(minutes=2)
    async def _cleanup_checker(self):
        """Periodically check if matches have been resolved → schedule delayed cleanup."""
        if not _active_sessions:
            return

        to_cleanup = []
        for mid, state in list(_active_sessions.items()):
            try:
                match = await db.get_match(mid)
                if match and match["status"] in ("confirmed", "voided", "cancelled"):
                    to_cleanup.append(state)
            except Exception:
                pass

        for state in to_cleanup:
            print(f"[CHALLENGE] Match #{state.match_id} resolved — scheduling cleanup in {config.MATCH_CHANNEL_CLEANUP_DELAY // 60} min")
            # Remove from active sessions first so we don't trigger again
            _active_sessions.pop(state.match_id, None)
            _save_sessions()
            asyncio.create_task(_delayed_cleanup(self.bot, state))

    @_cleanup_checker.before_loop
    async def _before_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Fallback handler for post-restart: handles mapbp interactions when
        no View is in memory (bot was restarted while ban/pick was active)."""
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("mapbp_"):
            return

        # If the View's _handle callback already handled this, skip
        if interaction.response.is_done():
            return

        # Post-restart fallback: no View in memory, handle here
        await handle_mapbp_interaction(self.bot, interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChallengeCog(bot))
    print("[CHALLENGE] ChallengeCog loaded")
