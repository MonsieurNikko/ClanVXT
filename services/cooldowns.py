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

async def check_member_join_cooldown(user_id: int) -> Tuple[bool, Optional[str]]:
    """Check if user has a join/leave cooldown. FUSED: Includes lazy migration."""
    # 1. Check new table
    is_cd, until = await check_cooldown("user", user_id, KIND_JOIN_LEAVE)
    if is_cd:
        return True, until
    
    # 2. Backward compatibility & Lazy Migration
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
                await db.set_cooldown("user", user_id, KIND_JOIN_LEAVE, (until_dt - now).days + 1, "Lazy migration from legacy column")
                
                # Clear legacy column
                await db.update_user_cooldown(user_id, None) 
                
                return True, until_dt.isoformat()
            else:
                # Expired legacy cooldown - just clear it
                await db.update_user_cooldown(user_id, None)
        except Exception as e:
            print(f"[COOLDOWN] Error during lazy migration for user {user_id}: {e}")
            # Clear invalid legacy data
            await db.update_user_cooldown(user_id, None)
            
    return False, None

async def apply_member_join_cooldown(user_id: int, reason: str = "Left clan") -> None:
    """Apply 14-day join/leave cooldown to a member."""
    await apply_cooldown("user", user_id, KIND_JOIN_LEAVE, DURATION_JOIN_LEAVE, reason)
    # Sync with users table for backward compatibility
    # We can just update the users table directly here or let the new system take over.
    # For safety, let's update users table too via db helper if it existed, but we didn't add that specific update method.
    # We'll rely on the new table primarily.

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
