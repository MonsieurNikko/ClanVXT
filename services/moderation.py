"""
Moderation Service
Centralized helpers for system bans, clan freeze, and Elo rollback operations.
"""

import json
from typing import Dict, Any, Optional, Tuple
import discord
from services import db


# =============================================================================
# SYSTEM BAN CHECKS
# =============================================================================

async def check_user_banned(user_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if user is system banned. Returns (is_banned, ban_info)."""
    ban = await db.get_system_ban("user", user_id)
    return (ban is not None, ban)


async def check_clan_banned(clan_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if clan is system banned. Returns (is_banned, ban_info)."""
    ban = await db.get_system_ban("clan", clan_id)
    return (ban is not None, ban)


async def check_clan_frozen(clan_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if clan is frozen. Returns (is_frozen, flags)."""
    flags = await db.get_clan_flags(clan_id)
    if flags and flags.get("is_frozen") == 1:
        return (True, flags)
    return (False, None)


async def check_elo_eligible(clan_id: int) -> Tuple[bool, str]:
    """
    Check if clan is eligible for Elo changes.
    Returns (is_eligible, reason_if_not).
    """
    # Check clan existence and status
    clan = await db.get_clan_by_id(clan_id)
    if not clan:
        return (False, "Clan không tồn tại")
    
    if clan["status"] != "active":
        return (False, f"Clan không active (status: {clan['status']})")
    
    # Check system ban
    is_banned, _ = await check_clan_banned(clan_id)
    if is_banned:
        return (False, "Clan đang bị cấm hệ thống (system ban)")
    
    # Check frozen
    is_frozen, _ = await check_clan_frozen(clan_id)
    if is_frozen:
        return (False, "Clan đang bị đóng băng (frozen)")
    
    return (True, "")


# =============================================================================
# BAN/UNBAN OPERATIONS
# =============================================================================

async def ban_user_system(user_id: int, reason: str, mod_id: int, expires_at: Optional[str] = None) -> None:
    """Apply system ban to a user."""
    await db.add_system_ban("user", user_id, reason, mod_id, expires_at)


async def unban_user_system(user_id: int) -> bool:
    """Remove system ban from a user. Returns True if was banned."""
    return await db.remove_system_ban("user", user_id)


async def ban_clan_system(clan_id: int, reason: str, mod_id: int) -> None:
    """Apply system ban to a clan."""
    await db.add_system_ban("clan", clan_id, reason, mod_id)


async def unban_clan_system(clan_id: int) -> bool:
    """Remove system ban from a clan. Returns True if was banned."""
    return await db.remove_system_ban("clan", clan_id)


# =============================================================================
# FREEZE/UNFREEZE OPERATIONS
# =============================================================================

async def freeze_clan(clan_id: int, reason: str, mod_id: int) -> None:
    """Freeze a clan (matches allowed but no Elo applied)."""
    await db.set_clan_frozen(clan_id, reason, mod_id)


async def unfreeze_clan(clan_id: int) -> bool:
    """Unfreeze a clan. Returns True if was frozen."""
    return await db.unset_clan_frozen(clan_id)


# =============================================================================
# ELO OPERATIONS
# =============================================================================

async def rollback_match_elo(match_id: int, mod_id: int) -> Dict[str, Any]:
    """
    Rollback Elo changes from a match.
    Returns dict with success status and details.
    """
    # Get match
    match = await db.get_match(match_id)
    if not match:
        return {"success": False, "reason": "Match không tồn tại"}
    
    # Check if Elo was applied
    if not match.get("elo_applied"):
        return {"success": False, "reason": "Match này chưa được áp dụng Elo"}
    
    # Get Elo history for this match
    history = await db.get_elo_history_for_match(match_id)
    if not history:
        return {"success": False, "reason": "Không tìm thấy lịch sử Elo cho match này"}
    
    rollback_details = []
    
    for entry in history:
        clan_id = entry["clan_id"]
        old_elo = entry["old_elo"]
        change = entry["change_amount"]
        
        # Get current clan elo
        clan = await db.get_clan_by_id(clan_id)
        if not clan:
            continue
        
        current_elo = clan["elo"]
        # Revert by subtracting the change
        new_elo = current_elo - change
        
        # Update clan elo
        await db.set_clan_elo_directly(clan_id, new_elo)
        
        # Record rollback in elo_history
        await db.update_clan_elo(
            clan_id, new_elo, match_id, 
            f"rollback_match_{match_id}", 
            mod_id
        )
        
        rollback_details.append({
            "clan_id": clan_id,
            "clan_name": clan["name"],
            "before": current_elo,
            "after": new_elo,
            "reverted_change": -change
        })
    
    # Mark match as elo rolled back
    await db.mark_match_elo_rolled_back(match_id)
    
    return {
        "success": True,
        "match_id": match_id,
        "rollback_details": rollback_details
    }


async def reset_clan_elo(clan_id: int, mod_id: int, new_elo: int = 1000) -> Dict[str, Any]:
    """
    Reset clan Elo to a specific value (default 1000).
    Returns dict with old/new values.
    """
    clan = await db.get_clan_by_id(clan_id)
    if not clan:
        return {"success": False, "reason": "Clan không tồn tại"}
    
    old_elo = clan["elo"]
    
    # Update elo and record history
    await db.update_clan_elo(clan_id, new_elo, None, "elo_reset_by_mod", mod_id)
    
    return {
        "success": True,
        "clan_id": clan_id,
        "clan_name": clan["name"],
        "old_elo": old_elo,
        "new_elo": new_elo
    }


# =============================================================================
# CLAN DISSOLUTION
# =============================================================================

async def dissolve_clan(clan_id: int, mod_id: int, guild: discord.Guild) -> Dict[str, Any]:
    """
    Dissolve (archive) a clan:
    - Set status to 'disbanded'
    - Remove clan role from members
    - Archive/hide clan channel
    Returns dict with operation details.
    """
    clan = await db.get_clan_by_id(clan_id)
    if not clan:
        return {"success": False, "reason": "Clan không tồn tại"}
    
    if clan["status"] == "disbanded":
        return {"success": False, "reason": "Clan đã bị giải tán trước đó"}
    
    results = {
        "clan_name": clan["name"],
        "role_removed": False,
        "channel_archived": False,
        "members_count": 0
    }
    
    # Get members before disbanding
    members = await db.get_clan_members(clan_id)
    results["members_count"] = len(members)
    
    # Remove Discord role from members
    if clan.get("discord_role_id"):
        try:
            role = guild.get_role(int(clan["discord_role_id"]))
            if role:
                for member_data in members:
                    try:
                        member = guild.get_member(int(member_data["discord_id"]))
                        if member and role in member.roles:
                            await member.remove_roles(role, reason="Clan dissolved by mod")
                    except Exception:
                        pass
                # Delete the role
                await role.delete(reason="Clan dissolved by mod")
                results["role_removed"] = True
        except Exception as e:
            results["role_error"] = str(e)
    
    # Archive/hide clan channel
    if clan.get("discord_channel_id"):
        try:
            channel = guild.get_channel(int(clan["discord_channel_id"]))
            if channel:
                await channel.edit(name=f"archived-{clan['name']}", reason="Clan dissolved by mod")
                # Set permissions to hide from everyone except mods
                await channel.set_permissions(guild.default_role, read_messages=False)
                results["channel_archived"] = True
        except Exception as e:
            results["channel_error"] = str(e)
    
    # [P2 Fix] End all active loans involving this clan
    from services import loan_service
    await loan_service.end_all_clan_loans(clan_id, guild)
    
    # Update clan status
    await db.update_clan_status(clan_id, "disbanded")
    
    results["success"] = True
    return results


# =============================================================================
# MATCH VOID
# =============================================================================

async def void_match_result(match_id: int) -> Dict[str, Any]:
    """
    Void a match result (mark as cancelled by mod, no Elo change).
    """
    match = await db.get_match(match_id)
    if not match:
        return {"success": False, "reason": "Match không tồn tại"}
    
    if match["status"] in ("voided", "cancelled"):
        return {"success": False, "reason": "Match đã bị hủy/void trước đó"}
    
    # If Elo was applied, need to rollback first
    if match.get("elo_applied"):
        return {"success": False, "reason": "Match này đã được áp dụng Elo. Hãy rollback Elo trước khi void."}
    
    success = await db.void_match(match_id)
    
    return {
        "success": success,
        "match_id": match_id
    }
