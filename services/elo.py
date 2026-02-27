"""
Elo Calculation Service
Implements Elo rating formula with anti-farm mechanics
"""

from typing import Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from services import db
import config

# Constants — read from config for easy tuning
K_FACTOR_STABLE = config.ELO_K_STABLE        # 32 (post-placement)
K_FACTOR_PLACEMENT = config.ELO_K_PLACEMENT   # 40 (first 10 matches)
PLACEMENT_MATCHES = config.ELO_PLACEMENT_MATCHES  # 10
RATING_SCALE = 400
ELO_INITIAL = config.ELO_INITIAL              # 1000
ELO_FLOOR = config.ELO_FLOOR                  # 100

# Anti-farm multipliers for matches between same clan pair in 24h
ANTI_FARM_MULTIPLIERS = {
    0: 1.0,   # 1st match
    1: 0.7,   # 2nd match
    2: 0.4,   # 3rd match
}
DEFAULT_MULTIPLIER = 0.2  # 4th+ match

# Rank Score → Name mapping (25 ranks)
RANK_SCORE_TO_NAME = {
    1: "Iron 1", 2: "Iron 2", 3: "Iron 3",
    4: "Bronze 1", 5: "Bronze 2", 6: "Bronze 3",
    7: "Silver 1", 8: "Silver 2", 9: "Silver 3",
    10: "Gold 1", 11: "Gold 2", 12: "Gold 3",
    13: "Platinum 1", 14: "Platinum 2", 15: "Platinum 3",
    16: "Diamond 1", 17: "Diamond 2", 18: "Diamond 3",
    19: "Ascendant 1", 20: "Ascendant 2", 21: "Ascendant 3",
    22: "Immortal 1", 23: "Immortal 2", 24: "Immortal 3",
    25: "Radiant",
}
RANK_NAME_TO_SCORE = {v: k for k, v in RANK_SCORE_TO_NAME.items()}


def get_k_factor(matches_played: int) -> int:
    """
    Return the K-factor for a clan based on how many matches it has played.
    During placement phase (< PLACEMENT_MATCHES), K is higher for faster calibration.
    """
    if matches_played < PLACEMENT_MATCHES:
        return K_FACTOR_PLACEMENT
    return K_FACTOR_STABLE


def compute_expected(elo_a: int, elo_b: int) -> float:
    """
    Compute expected score for player/clan A against B.
    Formula: 1 / (1 + 10^((elo_b - elo_a) / 400))
    """
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / RATING_SCALE))


def compute_base_delta(elo_a: int, elo_b: int, score_a: float, k: int = K_FACTOR_STABLE) -> int:
    """
    Compute base Elo delta for clan A.
    
    Args:
        elo_a: Current Elo of clan A
        elo_b: Current Elo of clan B
        score_a: Actual score (1.0 for win, 0.0 for loss)
        k: K-factor (default K_FACTOR_STABLE=32)
    
    Returns:
        Base Elo change (positive for gain, negative for loss)
    """
    expected_a = compute_expected(elo_a, elo_b)
    return round(k * (score_a - expected_a))


def get_pair_multiplier(match_count_24h: int) -> float:
    """
    Get anti-farm multiplier based on number of Elo-counted matches
    between the same clan pair in the past 24 hours.
    
    Args:
        match_count_24h: Number of matches with elo_applied=1 in past 24h
    
    Returns:
        Multiplier (1.0, 0.7, 0.4, or 0.2)
    """
    return ANTI_FARM_MULTIPLIERS.get(match_count_24h, DEFAULT_MULTIPLIER)


def get_win_rate_modifier(win_rate: float, total_matches: int) -> float:
    """
    Get Elo modifier based on clan's recent win rate.
    High win rate → lower gain (modifier < 1.0)
    Low win rate → higher gain (modifier > 1.0)
    Not enough matches → no modifier (1.0)
    """
    if total_matches < config.WIN_RATE_MIN_MATCHES:
        return 1.0
    if win_rate >= config.WIN_RATE_HIGH_THRESHOLD:
        return config.WIN_RATE_HIGH_MODIFIER
    if win_rate <= config.WIN_RATE_LOW_THRESHOLD:
        return config.WIN_RATE_LOW_MODIFIER
    return 1.0


def get_underdog_bonus(elo_winner: int, elo_loser: int) -> int:
    """Only applies if winner's Elo < loser's Elo. Returns bonus points."""
    gap = elo_loser - elo_winner
    if gap < 100: return 0
    if gap < 150: return 5
    if gap <= 200: return 8
    return 10


def get_rank_modifier(avg_rank_a: float, avg_rank_b: float) -> Tuple[float, float]:
    """
    Returns (modifier_a, modifier_b) based on avg rank gap of rosters.
    Higher avg rank → lower gain when winning, higher loss when losing.
    """
    if avg_rank_a is None or avg_rank_b is None:
        return (1.0, 1.0)
    
    gap = abs(avg_rank_a - avg_rank_b)
    if gap <= 2:
        return (1.0, 1.0)
    if gap <= 5:
        mod = 0.9
    elif gap <= 8:
        mod = 0.8
    else:
        mod = 0.7
    
    if avg_rank_a > avg_rank_b:
        return (mod, 2.0 - mod)
    else:
        return (2.0 - mod, mod)


async def count_elo_matches_between_clans(clan_a_id: int, clan_b_id: int) -> int:
    """
    Count matches between two clans in the past 24 hours where Elo was applied.
    Order-independent (A vs B = B vs A).
    """
    async with db.get_connection() as conn:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        cursor = await conn.execute(
            """SELECT COUNT(*) as count FROM matches 
               WHERE ((clan_a_id = ? AND clan_b_id = ?) OR (clan_a_id = ? AND clan_b_id = ?))
               AND elo_applied = 1
               AND created_at >= ?""",
            (clan_a_id, clan_b_id, clan_b_id, clan_a_id, cutoff)
        )
        row = await cursor.fetchone()
        return row["count"]


async def apply_match_result(match_id: int, winner_clan_id: int) -> Dict[str, Any]:
    """
    Apply Elo changes for a confirmed/resolved match.
    
    This function:
    1. Validates match status is CONFIRMED or RESOLVED
    2. Checks both clans are ACTIVE
    3. Computes anti-farm multiplier
    4. Calculates and applies Elo changes
    5. Updates match record with Elo details
    
    Args:
        match_id: The match to apply Elo for
        winner_clan_id: The winning clan's ID
    
    Returns:
        Dict with:
        - success: bool
        - reason: "OK", "CLANS_INACTIVE", "INVALID_STATUS", "MATCH_NOT_FOUND"
        - base_delta_a, base_delta_b: Base Elo changes
        - final_delta_a, final_delta_b: Final Elo changes after multiplier
        - multiplier: The anti-farm multiplier used
        - elo_a_new, elo_b_new: New Elo values
    """
    async with db.get_connection() as conn:
        # Get match with lock-like behavior (single transaction)
        cursor = await conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        match = await cursor.fetchone()
        
        if not match:
            return {"success": False, "reason": "MATCH_NOT_FOUND"}
        
        match = dict(match)
        
        # Validate status
        if match["status"] not in ("confirmed", "resolved"):
            return {"success": False, "reason": "INVALID_STATUS", "current_status": match["status"]}
        
        # Already applied?
        if match["elo_applied"]:
            return {"success": False, "reason": "ALREADY_APPLIED"}
        
        clan_a_id = match["clan_a_id"]
        clan_b_id = match["clan_b_id"]
        
        # Get clan data
        cursor = await conn.execute("SELECT * FROM clans WHERE id = ?", (clan_a_id,))
        clan_a = dict(await cursor.fetchone())
        
        cursor = await conn.execute("SELECT * FROM clans WHERE id = ?", (clan_b_id,))
        clan_b = dict(await cursor.fetchone())
        
        # Determine winner from scores if not provided
        if winner_clan_id is None:
            if match.get("score_a") is not None and match.get("score_b") is not None:
                if match["score_a"] > match["score_b"]:
                    winner_clan_id = clan_a_id
                elif match["score_b"] > match["score_a"]:
                    winner_clan_id = clan_b_id
                else:
                    return {"success": False, "reason": "DRAW_NOT_SUPPORTED"}
            else:
                return {"success": False, "reason": "WINNER_REQUIRED"}

        # Check both clans are active
        if clan_a["status"] != "active" or clan_b["status"] != "active":
            inactive_clans = []
            if clan_a["status"] != "active":
                inactive_clans.append(clan_a["name"])
            if clan_b["status"] != "active":
                inactive_clans.append(clan_b["name"])
            
            # Mark match as processed but no Elo applied
            await conn.execute(
                """UPDATE matches SET 
                   elo_applied = 0,
                   base_delta_a = 0, base_delta_b = 0,
                   multiplier = 0, final_delta_a = 0, final_delta_b = 0
                   WHERE id = ?""",
                (match_id,)
            )
            await conn.commit()
            
            return {
                "success": False,
                "reason": "CLANS_INACTIVE",
                "inactive_clans": inactive_clans
            }
        
        # Check for frozen clans (can play but no Elo)
        frozen_clans = []
        if await db.is_clan_frozen(clan_a_id):
            frozen_clans.append(clan_a["name"])
        if await db.is_clan_frozen(clan_b_id):
            frozen_clans.append(clan_b["name"])
        
        if frozen_clans:
            await conn.execute(
                """UPDATE matches SET 
                   elo_applied = 0,
                   base_delta_a = 0, base_delta_b = 0,
                   multiplier = 0, final_delta_a = 0, final_delta_b = 0
                   WHERE id = ?""",
                (match_id,)
            )
            await conn.commit()
            
            return {
                "success": False,
                "reason": "CLANS_FROZEN",
                "frozen_clans": frozen_clans
            }
        
        # Check for system banned clans
        banned_clans = []
        if await db.is_clan_system_banned(clan_a_id):
            banned_clans.append(clan_a["name"])
        if await db.is_clan_system_banned(clan_b_id):
            banned_clans.append(clan_b["name"])
        
        if banned_clans:
            await conn.execute(
                """UPDATE matches SET 
                   elo_applied = 0,
                   base_delta_a = 0, base_delta_b = 0,
                   multiplier = 0, final_delta_a = 0, final_delta_b = 0
                   WHERE id = ?""",
                (match_id,)
            )
            await conn.commit()
            
            return {
                "success": False,
                "reason": "CLANS_BANNED",
                "banned_clans": banned_clans
            }
        
        elo_a = clan_a["elo"]
        elo_b = clan_b["elo"]
        matches_played_a = clan_a.get("matches_played", 0)
        matches_played_b = clan_b.get("matches_played", 0)
        
        # Per-clan K-factor (placement vs stable)
        k_a = get_k_factor(matches_played_a)
        k_b = get_k_factor(matches_played_b)
        
        # Determine scores
        if winner_clan_id == clan_a_id:
            score_a = 1.0
            score_b = 0.0
        else:
            score_a = 0.0
            score_b = 1.0
        
        # Calculate base deltas (each clan uses its own K-factor)
        base_delta_a = compute_base_delta(elo_a, elo_b, score_a, k=k_a)
        base_delta_b = compute_base_delta(elo_b, elo_a, score_b, k=k_b)
        
        # Get anti-farm multiplier
        match_count = await count_elo_matches_between_clans(clan_a_id, clan_b_id)
        multiplier = get_pair_multiplier(match_count)
        
        # Apply anti-farm multiplier
        final_delta_a = round(base_delta_a * multiplier)
        final_delta_b = round(base_delta_b * multiplier)
        
        # --- Balance System Modifiers ---
        win_rate_mod_a = 1.0
        win_rate_mod_b = 1.0
        rank_mod_a = 1.0
        rank_mod_b = 1.0
        underdog_bonus = 0
        elo_capped = False
        
        # Feature 3 — Win Rate Modifier
        if await db.is_balance_feature_enabled("win_rate_mod"):
            wr_a = await db.get_clan_win_rate(clan_a_id)
            wr_b = await db.get_clan_win_rate(clan_b_id)
            win_rate_mod_a = get_win_rate_modifier(wr_a["win_rate"], wr_a["total"])
            win_rate_mod_b = get_win_rate_modifier(wr_b["win_rate"], wr_b["total"])
            if win_rate_mod_a != 1.0 or win_rate_mod_b != 1.0:
                final_delta_a = round(final_delta_a * win_rate_mod_a)
                final_delta_b = round(final_delta_b * win_rate_mod_b)
        
        # Feature 8 — Rank Elo Modifier (uses roster avg rank from Feature 9)
        if await db.is_balance_feature_enabled("rank_elo_mod"):
            rosters = await db.get_match_rosters(match_id)
            avg_rank_a = rosters.get("avg_rank_a")
            avg_rank_b = rosters.get("avg_rank_b")
            if avg_rank_a is not None and avg_rank_b is not None:
                rank_mod_a, rank_mod_b = get_rank_modifier(avg_rank_a, avg_rank_b)
                if rank_mod_a != 1.0 or rank_mod_b != 1.0:
                    # Cap combined modifier (win_rate * rank) >= 0.3 to avoid over-nerfing
                    combined_mod_a = max(0.3, win_rate_mod_a * rank_mod_a)
                    combined_mod_b = max(0.3, win_rate_mod_b * rank_mod_b)
                    # Recompute with combined modifier instead of stacking
                    final_delta_a = round(round(base_delta_a * multiplier) * combined_mod_a)
                    final_delta_b = round(round(base_delta_b * multiplier) * combined_mod_b)
        
        # Feature 5 — Underdog Bonus
        if await db.is_balance_feature_enabled("underdog_bonus"):
            winner_elo = elo_a if winner_clan_id == clan_a_id else elo_b
            loser_elo = elo_b if winner_clan_id == clan_a_id else elo_a
            underdog_bonus = get_underdog_bonus(winner_elo, loser_elo)
            if underdog_bonus > 0:
                if winner_clan_id == clan_a_id:
                    final_delta_a += underdog_bonus
                else:
                    final_delta_b += underdog_bonus
        
        # Feature 5 — Elo Gain Cap (only cap positive deltas)
        if await db.is_balance_feature_enabled("elo_gain_cap"):
            if final_delta_a > config.ELO_MAX_GAIN_PER_MATCH:
                final_delta_a = config.ELO_MAX_GAIN_PER_MATCH
                elo_capped = True
            if final_delta_b > config.ELO_MAX_GAIN_PER_MATCH:
                final_delta_b = config.ELO_MAX_GAIN_PER_MATCH
                elo_capped = True
        
        # New Elo values (enforce floor)
        new_elo_a = max(ELO_FLOOR, elo_a + final_delta_a)
        new_elo_b = max(ELO_FLOOR, elo_b + final_delta_b)
        
        # Update clan Elos
        await conn.execute(
            "UPDATE clans SET elo = ?, matches_played = matches_played + 1, updated_at = datetime('now') WHERE id = ?",
            (new_elo_a, clan_a_id)
        )
        await conn.execute(
            "UPDATE clans SET elo = ?, matches_played = matches_played + 1, updated_at = datetime('now') WHERE id = ?",
            (new_elo_b, clan_b_id)
        )
        
        # Record Elo history for both clans
        reason_a = "match_win" if winner_clan_id == clan_a_id else "match_loss"
        reason_b = "match_win" if winner_clan_id == clan_b_id else "match_loss"
        
        await conn.execute(
            """INSERT INTO elo_history (clan_id, match_id, old_elo, new_elo, change_amount, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clan_a_id, match_id, elo_a, new_elo_a, final_delta_a, reason_a)
        )
        await conn.execute(
            """INSERT INTO elo_history (clan_id, match_id, old_elo, new_elo, change_amount, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clan_b_id, match_id, elo_b, new_elo_b, final_delta_b, reason_b)
        )
        
        # Update match with Elo details
        await conn.execute(
            """UPDATE matches SET 
               elo_applied = 1,
               base_delta_a = ?, base_delta_b = ?,
               multiplier = ?,
               final_delta_a = ?, final_delta_b = ?
               WHERE id = ?""",
            (base_delta_a, base_delta_b, multiplier, final_delta_a, final_delta_b, match_id)
        )
        
        await conn.commit()
        
        return {
            "success": True,
            "reason": "OK",
            "base_delta_a": base_delta_a,
            "base_delta_b": base_delta_b,
            "multiplier": multiplier,
            "final_delta_a": final_delta_a,
            "final_delta_b": final_delta_b,
            "elo_a_old": elo_a,
            "elo_b_old": elo_b,
            "elo_a_new": new_elo_a,
            "elo_b_new": new_elo_b,
            "clan_a_name": clan_a["name"],
            "clan_b_name": clan_b["name"],
            "match_count_24h": match_count + 1,
            "k_a": k_a,
            "k_b": k_b,
            # Balance modifiers info
            "win_rate_mod_a": win_rate_mod_a,
            "win_rate_mod_b": win_rate_mod_b,
            "rank_mod_a": rank_mod_a,
            "rank_mod_b": rank_mod_b,
            "underdog_bonus": underdog_bonus,
            "elo_capped": elo_capped,
        }

def format_elo_explanation_vn(elo_result: Dict[str, Any]) -> str:
    """
    Format a detailed, Vietnamese explanation string from elo_result for logs.
    Updated: includes breakdown of all balance modifiers.
    """
    if not elo_result.get("success"):
        return f"Thất bại: {elo_result.get('reason', 'Lỗi không xác định')}"
    
    # K-factor explanations
    k_a = elo_result.get("k_a", 32)
    k_b = elo_result.get("k_b", 32)
    k_a_desc = "Tân thủ" if k_a == K_FACTOR_PLACEMENT else "Ổn định"
    k_b_desc = "Tân thủ" if k_b == K_FACTOR_PLACEMENT else "Ổn định"
    
    # Anti-farm multiplier
    mult = elo_result.get("multiplier", 1.0)
    match_count = elo_result.get("match_count_24h", 1)
    
    # Delta strings
    delta_a = elo_result.get("final_delta_a", 0)
    delta_b = elo_result.get("final_delta_b", 0)
    delta_a_str = f"+{delta_a}" if delta_a >= 0 else str(delta_a)
    delta_b_str = f"+{delta_b}" if delta_b >= 0 else str(delta_b)
    
    # Base explanation
    lines = [
        f"📊 **Chi tiết Elo Match:**",
        f"• **{elo_result['clan_a_name']}**: {delta_a_str} Elo (K={k_a} {k_a_desc})",
        f"• **{elo_result['clan_b_name']}**: {delta_b_str} Elo (K={k_b} {k_b_desc})",
    ]
    
    # Modifiers breakdown
    modifiers = []
    if mult != 1.0:
        modifiers.append(f"Anti-farm: {mult}x (Trận thứ {match_count}/24h)")
    
    wr_a = elo_result.get("win_rate_mod_a", 1.0)
    wr_b = elo_result.get("win_rate_mod_b", 1.0)
    if wr_a != 1.0 or wr_b != 1.0:
        modifiers.append(f"Win Rate: {elo_result['clan_a_name']} x{wr_a}, {elo_result['clan_b_name']} x{wr_b}")
    
    rm_a = elo_result.get("rank_mod_a", 1.0)
    rm_b = elo_result.get("rank_mod_b", 1.0)
    if rm_a != 1.0 or rm_b != 1.0:
        modifiers.append(f"Rank: {elo_result['clan_a_name']} x{rm_a}, {elo_result['clan_b_name']} x{rm_b}")
    
    ub = elo_result.get("underdog_bonus", 0)
    if ub > 0:
        modifiers.append(f"Underdog Bonus: +{ub}")
    
    if elo_result.get("elo_capped"):
        modifiers.append(f"Elo Cap: max +{config.ELO_MAX_GAIN_PER_MATCH}")
    
    if modifiers:
        lines.append("⚖️ **Modifiers:** " + " | ".join(modifiers))
    
    return "\n".join(lines)
