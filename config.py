"""
Configuration Module
Loads environment variables from .env file
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent / ".env")

# =============================================================================
# REQUIRED ENVIRONMENT VARIABLES
# =============================================================================

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
GUILD_ID: int = int(os.getenv("GUILD_ID", "0"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in .env file")
if not GUILD_ID:
    raise ValueError("GUILD_ID must be set in .env file")

# =============================================================================
# DISCORD ROLES (Pre-existing, DO NOT CREATE)
# =============================================================================

ROLE_VERIFIED: str = "Thiểu Năng Con"  # Required to participate
ROLE_MOD: str = "Hội đồng quản trị"     # Admin privileges

# =============================================================================
# CHANNELS & CATEGORIES
# =============================================================================

CHANNEL_MOD_LOG: str = "log"      # System logs channel
CHANNEL_ARENA: str = "arena"      # Arena dashboard channel (read-only for users)
CHANNEL_UPDATE_BOT: str = "update-bot"  # Update announcements channel (read-only for users)
CATEGORY_CLANS: str = "CLANS"     # Category for clan private channels
CHANNEL_CHAT_ARENA: str = "chat-arena"        # Public chat channel for announcements
CHANNEL_HIGHLIGHTS: str = "🏆┃2-𝙡𝙖𝙞-𝙠𝙝ô𝙣𝙜-𝙖𝙞-𝙡𝙖𝙞" # Highlights channel

SERVER_INVITE_URL: str = "https://discord.gg/qhtn"

# =============================================================================
# SYSTEM CONSTANTS
# =============================================================================

CLAN_CREATE_TIMEOUT_HOURS: int = 48   # Time to gather 4 acceptances (Captain + 4 = 5 total)
MIN_MEMBERS_ACTIVE: int = 5           # Minimum members to keep clan active
COOLDOWN_DAYS: int = 14               # Cooldown after leaving/kicking/loan
LOAN_MAX_DAYS: int = 7                # Maximum loan duration
TRANSFER_COOLDOWN_DAYS: int = 30      # Min time between transfers
TRANSFER_SICKNESS_HOURS: int = 72     # Match ban after transfer
MATCH_LIMIT_24H: int = 2              # Max matches between same clans in 24h
ELO_INITIAL: int = 1000               # Starting Elo
ELO_K_STABLE: int = 32                # K-factor after placement phase
ELO_K_PLACEMENT: int = 40             # K-factor during placement phase (first 10 matches)
ELO_PLACEMENT_MATCHES: int = 10       # Number of placement matches
ELO_FLOOR: int = 100                  # Minimum Elo (can't drop below)
CHALLENGE_COOLDOWN_MINUTES: int = 10  # Cooldown between challenges from same clan
APPEAL_WINDOW_DAYS: int = 7           # Time to appeal a case

# =============================================================================
# DONATION INFO
# =============================================================================

# =============================================================================
# DONATION INFO
# =============================================================================

DONATE_DESCRIPTION: str = """
**☕ Support the Developer**

Bạn có thể ủng hộ mình qua **PayPal**:
📩 Gửi đến: **duy.win1903@gmail.com**
⚠️ **Lưu ý**: Chọn chế độ **"Friends and Family" (Gửi cho bạn bè/người thân)** để **không mất phí**.

*Mọi sự đóng góp dù nhỏ nhất đều giúp duy trì bot và giải thưởng cho server. Cảm ơn bạn! ❤️*
"""
DONATE_IMAGE_URL: str = ""   # Ảnh QR hoặc banner (nếu có)


# =============================================================================
# CHALLENGE UPGRADE — "ĐẠI CHIẾN CLANS"
# =============================================================================

MAP_POOL: list = [
    "Ascent", "Bind", "Haven", "Split", "Lotus", "Pearl", "Sunset",
    "Breeze", "Fracture", "Icebox", "Abyss", "Corrode"
]
MAP_BAN_TIMEOUT_SECONDS: int = 180       # 3 phút mỗi lượt ban/pick
MATCH_CHANNEL_CLEANUP_DELAY: int = 300   # 5 phút sau khi match kết thúc → xoá channels

# =============================================================================
# DATABASE PATH
# =============================================================================

DB_PATH: Path = Path(os.getenv("DB_PATH", Path(__file__).parent / "data" / "clan.db"))
