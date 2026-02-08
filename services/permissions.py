"""
Permission Helpers
Centralized membership and clan status checks for reuse across cogs
"""

from typing import Optional, Dict, Any, Tuple
from services import db


async def get_user_clan_by_discord_id(discord_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user's current clan if any.
    Returns clan dict with member_role, or None if not in a clan.
    """
    user = await db.get_user(discord_id)
    if not user:
        return None
    return await db.get_user_clan(user["id"])


async def is_user_in_clan(discord_id: str, clan_id: int) -> bool:
    """
    Check if user is currently a member of a specific clan.
    Used for validating button clicks on match actions.
    """
    clan_data = await get_user_clan_by_discord_id(discord_id)
    if not clan_data:
        return False
    return clan_data["id"] == clan_id


async def is_clan_active(clan_id: int) -> bool:
    """
    Check if clan status is 'active'.
    Clan becomes inactive when members < 5.
    """
    clan = await db.get_clan_by_id(clan_id)
    if not clan:
        return False
    return clan["status"] == "active"


async def get_user_internal_id(discord_id: str) -> Optional[int]:
    """
    Get user's internal DB ID from Discord ID.
    Returns None if user not registered.
    """
    user = await db.get_user(discord_id)
    return user["id"] if user else None


async def ensure_user_exists(discord_id: str, username: str) -> Dict[str, Any]:
    """
    Ensure user exists in database, create if needed.
    Returns the user dict.
    """
    user = await db.get_user(discord_id)
    if not user:
        await db.create_user(discord_id, f"{username}#0000")
        user = await db.get_user(discord_id)
    return user


async def can_request_loan(member_id: int, clan_id: int) -> Tuple[bool, str]:
    """
    Validate if a loan can be requested for a member.
    Returns (allowed, error_message).
    """
    # 1. Check if member is a captain or vice (Protected)
    member_data = await db.get_user_clan(member_id)
    if member_data and member_data["member_role"] in ["captain", "vice"]:
        return False, f"Không thể cho mượn **{member_data['member_role']}** của clan."
    
    # [P0 Fix] Check source clan size (must not drop below 5)
    source_count = await db.count_clan_members(clan_id)
    if source_count <= 5:
        return False, "Clan nguồn sẽ còn dưới 5 thành viên sau khi cho mượn. Không thể thực hiện."
    
    # 2. Check if member is already on active loan
    active_loan = await db.get_active_loan_for_member(member_id)
    if active_loan:
        return False, "Thành viên này đang được cho mượn ở Clan khác."

    # 3. Check if clan has any active loan (lending or borrowing)
    clan_loan = await db.get_active_loan_for_clan(clan_id)
    if clan_loan:
        return False, "Clan đang có giao dịch mượn/cho mượn thành viên khác chưa kết thúc."

    # 4. Check cooldowns
    # Member cooldown
    from services import cooldowns
    is_cd, until = await cooldowns.check_loan_cooldown("user", member_id)
    if is_cd:
        return False, f"Thành viên đang trong thời gian chờ sau khi mượn (đến {until})."
    
    # Clan cooldown
    is_cd, until = await cooldowns.check_loan_cooldown("clan", clan_id)
    if is_cd:
        return False, f"Clan đang trong thời gian chờ sau khi mượn (đến {until})."

    return True, ""


async def can_request_transfer(member_id: int, source_clan_id: int, dest_clan_id: int) -> Tuple[bool, str]:
    """
    Validate if a transfer can be requested.
    Returns (allowed, error_message).
    """
    # 0. Check if member is a captain or vice (Protected)
    member_data = await db.get_user_clan(member_id)
    if member_data and member_data["member_role"] in ["captain", "vice"]:
        return False, f"Không thể chuyển nhượng **{member_data['member_role']}** của clan."

    # 1. Check member status
    active_loan = await db.get_active_loan_for_member(member_id)
    if active_loan:
        return False, "Thành viên đang được cho mượn, không thể chuyển nhượng."
        
    from services import cooldowns
    is_cd, until = await cooldowns.check_member_join_cooldown(member_id)
    if is_cd:
        return False, f"Thành viên đang trong thời gian chờ gia nhập/rời Clan (đến {until})."

    # 2. Check destination clan status
    dest_clan = await db.get_clan_by_id(dest_clan_id)
    if not dest_clan:
        return False, "Clan đích không tồn tại."
    if dest_clan["status"] != "active":
        return False, "Clan đích chưa Active (cần >= 5 thành viên)."

    # 3. Check source clan size (must not drop below 5)
    # Note: Loaned members count as members of source clan, so we just count total members.
    source_count = await db.count_clan_members(source_clan_id)
    if source_count <= 5:
        return False, "Clan nguồn sẽ còn dưới 5 thành viên sau khi chuyển nhượng. Không thể thực hiện."

    return True, ""
