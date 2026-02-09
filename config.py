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
ELO_PLACEMENT_MATCHES: int = 10       # High K-factor matches
APPEAL_WINDOW_DAYS: int = 7           # Time to appeal a case

# =============================================================================
# DATABASE PATH
# =============================================================================

DB_PATH: Path = Path(os.getenv("DB_PATH", Path(__file__).parent / "data" / "clan.db"))
