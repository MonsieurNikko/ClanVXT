
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


# =============================================================================
# UPDATE CHANNEL (for user-facing announcements)
# =============================================================================

_update_channel: Optional[discord.TextChannel] = None

def set_update_channel(channel: discord.TextChannel):
    global _update_channel
    _update_channel = channel

def get_update_channel() -> Optional[discord.TextChannel]:
    return _update_channel


async def post_update(title: str, description: str, version: str = None) -> bool:
    """
    Gửi thông báo cập nhật lên kênh #update-bot.
    
    Chỉ dùng cho:
    - ✨ Tính năng mới
    - 🐛 Sửa lỗi quan trọng (ảnh hưởng người dùng)
    
    KHÔNG dùng cho: refactor, docs update, minor fixes.
    
    Args:
        title: Tiêu đề ngắn gọn (VD: "Arena Dashboard nâng cấp!")
        description: Mô tả ngắn gọn, tập trung vào lợi ích người dùng
        version: Phiên bản (VD: "1.2.5"), tùy chọn
    
    Returns:
        True nếu gửi thành công, False nếu không tìm thấy kênh
    """
    channel = get_update_channel()
    if not channel:
        print(f"[UPDATE] No update channel set. Message not sent: {title}")
        return False
    
    embed = discord.Embed(
        title=f"🎉 {title}",
        description=description,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )
    
    if version:
        embed.set_footer(text=f"Phiên bản {version}")
    
    try:
        await channel.send(embed=embed)
        print(f"[UPDATE] Posted: {title}")
        return True
    except Exception as e:
        print(f"[UPDATE] Failed to post: {e}")
        return False

