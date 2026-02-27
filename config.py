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
ROLE_PLAYER: str = "player"          # Auto-assigned to all clan members

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
COOLDOWN_DAYS: int = 3               # Cooldown after leaving/kicking/loan
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
# BALANCE SYSTEM CONSTANTS
# =============================================================================

# Feature 1 — Recruitment Cap
RECRUITMENT_CAP_PER_WEEK: int = 1        # Max invite/recruit thành công per 7 days
RECRUITMENT_CAP_EXEMPT_MATCHES: int = 0  # Clan với matches_played <= giá trị này → miễn cap

# Feature 2 — Elo Decay
ELO_DECAY_THRESHOLD: int = 1050          # Elo tối thiểu để bắt đầu decay
ELO_DECAY_AMOUNT: int = 15              # Elo trừ mỗi tuần không hoạt động
ELO_DECAY_FLOOR: int = 1000             # Elo sàn cho decay (không decay xuống dưới)
ELO_DECAY_INACTIVITY_DAYS: int = 7      # Số ngày không đánh = inactive

# Feature 3 — Win Rate Modifier
WIN_RATE_MIN_MATCHES: int = 5            # Tối thiểu 5 trận mới áp dụng modifier
WIN_RATE_HIGH_THRESHOLD: float = 0.7     # Win rate >= 70% → giảm gain
WIN_RATE_HIGH_MODIFIER: float = 0.5      # Modifier khi win rate cao (gain x0.5)
WIN_RATE_LOW_THRESHOLD: float = 0.3      # Win rate <= 30% → tăng gain
WIN_RATE_LOW_MODIFIER: float = 1.5       # Modifier khi win rate thấp (gain x1.5)

# Feature 4 — Activity Bonus
ACTIVITY_BONUS_AMOUNT: int = 10          # Bonus Elo cho clan hoạt động
ACTIVITY_BONUS_MIN_MATCHES: int = 3      # Tối thiểu 3 trận/tuần
ACTIVITY_BONUS_ELO_THRESHOLD: int = 1000 # Chỉ clan dưới 1000 Elo

# Feature 5 — Underdog Bonus & Elo Gain Cap
ELO_MAX_GAIN_PER_MATCH: int = 50         # Cap tổng gain cho 1 trận

# Feature 7 — Rank Cap
RANK_CAP_THRESHOLD_SCORE: int = 23       # Immortal 2 = score 23
RANK_CAP_MAX_COUNT: int = 5              # Max 5 thành viên rank Immortal 2+

# Feature 9 — Roster
ROSTER_SIZE: int = 5                     # Số người phải khai cho mỗi roster

# =============================================================================
# DATABASE PATH
# =============================================================================

DB_PATH: Path = Path(os.getenv("DB_PATH", Path(__file__).parent / "data" / "clan.db"))
