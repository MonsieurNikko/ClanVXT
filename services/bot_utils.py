
"""
Bot Utilities
Shared helper functions and state to avoid circular dependencies.
"""

import discord
from datetime import datetime, timezone
from typing import Optional

# Global cache variables
_log_channel: Optional[discord.TextChannel] = None
_clans_category: Optional[discord.CategoryChannel] = None
_verified_role: Optional[discord.Role] = None
_mod_role: Optional[discord.Role] = None

# Setter functions (to be called from main.py on_ready)
def set_log_channel(channel: discord.TextChannel):
    global _log_channel
    _log_channel = channel

def set_clans_category(category: discord.CategoryChannel):
    global _clans_category
    _clans_category = category

def set_verified_role(role: discord.Role):
    global _verified_role
    _verified_role = role

def set_mod_role(role: discord.Role):
    global _mod_role
    _mod_role = role

# Getter functions
def get_log_channel() -> Optional[discord.TextChannel]:
    return _log_channel

def get_clans_category() -> Optional[discord.CategoryChannel]:
    return _clans_category

def get_verified_role() -> Optional[discord.Role]:
    return _verified_role

def get_mod_role() -> Optional[discord.Role]:
    return _mod_role

async def log_event(event_type: str, details: str) -> None:
    """Log an event to the mod-log channel."""
    channel = get_log_channel()
    if channel:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        try:
            await channel.send(f"`[{timestamp}]` **[{event_type}]** {details}")
        except Exception as e:
            print(f"Failed to log event {event_type}: {e}")
    else:
        print(f"[LOG FAILED - NO CHANNEL] [{event_type}] {details}")
