"""
Cooldown Management Service
Centralized logic for checking and applying cooldowns.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
from services import db

# Cooldown Kinds
KIND_JOIN_LEAVE = "join_leave"
KIND_LOAN = "loan"
KIND_TRANSFER_SICKNESS = "transfer_sickness"
KIND_MATCH_CREATE = "match_create"

# Default Durations (Days)
DURATION_JOIN_LEAVE = 14
DURATION_LOAN = 14
DURATION_TRANSFER_SICKNESS = 3  # 72 hours

async def check_cooldown(target_type: str, target_id: int, kind: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a target is on cooldown.
    Returns (is_on_cooldown, until_timestamp_iso).
    """
    cooldown = await db.get_cooldown(target_type, target_id, kind)
    if cooldown:
        return True, cooldown["until"]
    return False, None

async def apply_cooldown(target_type: str, target_id: int, kind: str, duration_days: int, reason: str) -> None:
    """Apply a cooldown to a target."""
    await db.set_cooldown(target_type, target_id, kind, duration_days, reason)

async def clear_cooldown(target_type: str, target_id: int, kind: Optional[str] = None) -> None:
    """Clear cooldown(s) for a target."""
    await db.clear_cooldown(target_type, target_id, kind)

# =============================================================================
# SPECIFIC HELPERS
# =============================================================================

async def check_member_join_cooldown(user_id: int, target_clan_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Check if user has a join/leave cooldown. 
    If target_clan_id is provided (Try-out mode), checks if the cooldown is from THIS specific clan.
    """
    # 1. Check new table
    is_cd, until = await check_cooldown("user", user_id, KIND_JOIN_LEAVE)
    
    if is_cd:
        if target_clan_id:
            # TRY-OUT MODE: Only block if cooldown is from the SAME clan
            # We stored the clan ID in the reason field: "... (ClanID: 123)"
            cooldown = await db.get_cooldown("user", user_id, KIND_JOIN_LEAVE)
            reason = cooldown.get("reason", "")
            
            # Check if reason contains the target clan ID
            # Ideally we would have a structured column, but for now we parse the reason
            expected_tag = f"(ClanID: {target_clan_id})"
            if expected_tag in reason:
                return True, until
            else:
                # Cooldown exists but from a DIFFERENT clan -> ALLOW Try-out
                return False, None
        else:
            # NORMAL JOIN MODE: Block regardless of source clan
            return True, until
    
    # 2. Backward compatibility & Lazy Migration (Can be skipped if migrated)
    user = await db.get_user_by_id(user_id)
    if user and user.get("cooldown_until"):
        legacy_until = user["cooldown_until"]
        try:
            # Handle timestamps with and without 'Z'
            if legacy_until.endswith('Z'):
                until_str = legacy_until.replace('Z', '+00:00')
            else:
                until_str = legacy_until
            
            until_dt = datetime.fromisoformat(until_str)
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            
            if until_dt > now:
                # Migrate to the new system
                print(f"[COOLDOWN] Lazy migrating user {user_id} cooldown: {legacy_until}")
                # We don't know the source clan from legacy column, so assume strict cooldown
                await db.set_cooldown("user", user_id, KIND_JOIN_LEAVE, (until_dt - now).days + 1, "Lazy migration from legacy column")
                await db.update_user_cooldown(user_id, None) 
                return True, until_dt.isoformat()
            else:
                await db.update_user_cooldown(user_id, None)
        except Exception as e:
            print(f"[COOLDOWN] Error during lazy migration for user {user_id}: {e}")
            await db.update_user_cooldown(user_id, None)
            
    return False, None

async def apply_member_join_cooldown(user_id: int, reason: str = "Left clan", source_clan_id: Optional[int] = None) -> None:
    """Apply join/leave cooldown to a member. Includes ClanID in reason for try-out logic."""
    final_reason = reason
    if source_clan_id:
        final_reason = f"{reason} (ClanID: {source_clan_id})"
        
    await apply_cooldown("user", user_id, KIND_JOIN_LEAVE, DURATION_JOIN_LEAVE, final_reason)
    # Sync with users table for backward compatibility is skipped as we moved to new system


async def apply_loan_cooldowns(source_clan_id: int, target_clan_id: int, member_id: int) -> None:
    """Apply 14-day loan cooldown to all parties after loan ends."""
    reason = "Loan ended"
    await apply_cooldown("clan", source_clan_id, KIND_LOAN, DURATION_LOAN, reason)
    await apply_cooldown("clan", target_clan_id, KIND_LOAN, DURATION_LOAN, reason)
    await apply_cooldown("user", member_id, KIND_LOAN, DURATION_LOAN, reason)

async def check_loan_cooldown(target_type: str, target_id: int) -> Tuple[bool, Optional[str]]:
    """Check if clan or user has a loan cooldown."""
    return await check_cooldown(target_type, target_id, KIND_LOAN)

async def apply_transfer_sickness(user_id: int) -> None:
    """Apply 72h transfer sickness (match ban) to a member."""
    # 3 days = 72 hours
    await apply_cooldown("user", user_id, KIND_TRANSFER_SICKNESS, DURATION_TRANSFER_SICKNESS, "Transfer completed")
