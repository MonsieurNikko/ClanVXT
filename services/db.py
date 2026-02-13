"""
Clan System Database Helper
Async SQLite operations using aiosqlite
"""

import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "clan.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


# =============================================================================
# CONNECTION MANAGEMENT
# =============================================================================

@asynccontextmanager
async def get_connection():
    """Get a database connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    """Initialize database by executing schema.sql."""
    async with get_connection() as conn:
        # Get existing tables before init
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        existing_tables = {row[0] for row in await cursor.fetchall()}
        
        # Execute schema
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.executescript(schema)
        await conn.commit()
        
        # Get tables after init
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        all_tables = {row[0] for row in await cursor.fetchall()}
        
        # Check for new tables
        new_tables = all_tables - existing_tables
        
        print(f"Database initialized at {DB_PATH}")
        if new_tables:
            print(f"  ✓ New tables created: {', '.join(sorted(new_tables))}")
        else:
            print(f"  ✓ Schema up to date ({len(all_tables)} tables)")

        # --- Automatic Migrations for Existing Tables ---
        
        # Check for cancel_requested_by_clan_id in matches
        cursor = await conn.execute("PRAGMA table_info(matches)")
        match_columns = [row[1] for row in await cursor.fetchall()]
        if "cancel_requested_by_clan_id" not in match_columns:
            print("[DB] Migrating: Adding 'cancel_requested_by_clan_id' to 'matches' table...")
            await conn.execute("ALTER TABLE matches ADD COLUMN cancel_requested_by_clan_id INTEGER")
            await conn.commit()
            print("  ✓ Column added.")
        
        # Check for score_a, score_b in matches
        if "score_a" not in match_columns:
            print("[DB] Migrating: Adding 'score_a' to 'matches' table...")
            await conn.execute("ALTER TABLE matches ADD COLUMN score_a INTEGER")
            await conn.commit()
            print("  ✓ Column added.")
        if "score_b" not in match_columns:
            print("[DB] Migrating: Adding 'score_b' to 'matches' table...")
            await conn.execute("ALTER TABLE matches ADD COLUMN score_b INTEGER")
            await conn.commit()
            print("  ✓ Column added.")

        # Check for note in loans
        cursor = await conn.execute("PRAGMA table_info(loans)")
        loan_columns = [row[1] for row in await cursor.fetchall()]
        if "note" not in loan_columns:
            print("[DB] Migrating: Adding 'note' to 'loans' table...")
            await conn.execute("ALTER TABLE loans ADD COLUMN note TEXT")
            await conn.commit()
            print("  ✓ Column added.")



# =============================================================================
# USER CRUD
# =============================================================================

async def get_user(discord_id: str) -> Optional[Dict[str, Any]]:
    """Get user by Discord ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by internal ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_riot_id(riot_id: str) -> Optional[Dict[str, Any]]:
    """Get user by Valorant Riot ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM users WHERE riot_id = ?", (riot_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(discord_id: str, riot_id: str) -> int:
    """Create a new user. Returns user ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO users (discord_id, riot_id) VALUES (?, ?)",
            (discord_id, riot_id)
        )
        await conn.commit()
        return cursor.lastrowid


async def update_user_cooldown(user_id: int, cooldown_until: Optional[str]) -> None:
    """Set or clear user's join cooldown (FUSED: Now using cooldowns table)."""
    if cooldown_until:
        # Calculate duration in days for backward compatibility with the old API
        try:
            until_dt = datetime.fromisoformat(cooldown_until.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            duration = (until_dt - now).days + 1
            if duration <= 0:
                await clear_cooldown("user", user_id, "join_leave")
            else:
                await set_cooldown("user", user_id, "join_leave", duration, "Updated via legacy API")
        except Exception:
            # Fallback for invalid formats
            async with get_connection() as conn:
                await conn.execute(
                    """INSERT INTO cooldowns (target_type, target_id, kind, until, reason) 
                       VALUES ('user', ?, 'join_leave', ?, 'Legacy fallback') 
                       ON CONFLICT(target_type, target_id, kind) 
                       DO UPDATE SET until = excluded.until""", 
                    (user_id, cooldown_until)
                )
                await conn.commit()
    else:
        await clear_cooldown("user", user_id, "join_leave")

    # Clear legacy column to avoid double-checks
    print(f"[DB] Clearing legacy cooldown_until for user {user_id} (Syncing with new system)")
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET cooldown_until = NULL, updated_at = datetime('now') WHERE id = ?",
            (user_id,)
        )
        await conn.commit()


async def ban_user(user_id: int, reason: str) -> None:
    """Ban user from clan system."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (reason, user_id)
        )
        await conn.commit()


async def unban_user(user_id: int) -> None:
    """Unban user from clan system."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL, updated_at = datetime('now') WHERE id = ?",
            (user_id,)
        )
        await conn.commit()


# =============================================================================
# CLAN CRUD
# =============================================================================

async def get_clan(name: str) -> Optional[Dict[str, Any]]:
    """Get active or pending clan by name."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clans WHERE name = ? AND status NOT IN ('disbanded', 'cancelled', 'rejected')", 
            (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_clan_any_status(name: str) -> Optional[Dict[str, Any]]:
    """Get clan by name regardless of status (for mod commands)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clans WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_clan_by_id(clan_id: int) -> Optional[Dict[str, Any]]:
    """Get clan by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clans WHERE id = ?", (clan_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_clan(name: str, captain_id: int) -> int:
    """Create a new clan in waiting_accept status. Returns clan ID."""
    async with get_connection() as conn:
        # Check if a clan with this name already exists but is not active
        # (This handles cases where a previous creation failed or was cancelled)
        cursor = await conn.execute(
            "SELECT id FROM clans WHERE name = ? AND status != 'active'", (name,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            old_id = existing["id"]
            # Inline hard delete within the SAME connection to avoid
            # opening a second connection (which deadlocks SQLite).
            await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (old_id,))
            await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (old_id,))
            await conn.execute("DELETE FROM invite_requests WHERE clan_id = ?", (old_id,))
            await conn.execute("DELETE FROM clan_flags WHERE clan_id = ?", (old_id,))
            await conn.execute("DELETE FROM elo_history WHERE clan_id = ?", (old_id,))
            await conn.execute("DELETE FROM matches WHERE clan_a_id = ? OR clan_b_id = ?", (old_id, old_id))
            await conn.execute("DELETE FROM loans WHERE lending_clan_id = ? OR borrowing_clan_id = ?", (old_id, old_id))
            await conn.execute("DELETE FROM transfers WHERE source_clan_id = ? OR dest_clan_id = ?", (old_id, old_id))
            await conn.execute("DELETE FROM cooldowns WHERE target_type = 'clan' AND target_id = ?", (old_id,))
            await conn.execute("DELETE FROM cases WHERE target_type = 'clan' AND target_id = ?", (old_id,))
            await conn.execute("DELETE FROM clans WHERE id = ?", (old_id,))
            
        # Now insert the new clan
        cursor = await conn.execute(
            "INSERT INTO clans (name, captain_id, status) VALUES (?, ?, 'waiting_accept')",
            (name, captain_id)
        )
        clan_id = cursor.lastrowid
        # Add captain as member
        await conn.execute(
            "INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, 'captain')",
            (captain_id, clan_id)
        )
        await conn.commit()
        return clan_id


async def update_clan_status(clan_id: int, status: str) -> None:
    """Update clan status."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE clans SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, clan_id)
        )
        await conn.commit()


async def update_clan_elo(clan_id: int, new_elo: int, match_id: Optional[int], reason: str, changed_by: Optional[int] = None) -> None:
    """Update clan Elo and record history. Uses transaction."""
    async with get_connection() as conn:
        # Get current elo
        cursor = await conn.execute("SELECT elo FROM clans WHERE id = ?", (clan_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Clan {clan_id} not found")
        old_elo = row["elo"]
        change_amount = new_elo - old_elo
        
        # Update clan elo
        await conn.execute(
            "UPDATE clans SET elo = ?, updated_at = datetime('now') WHERE id = ?",
            (new_elo, clan_id)
        )
        
        # Record history
        await conn.execute(
            """INSERT INTO elo_history (clan_id, match_id, old_elo, new_elo, change_amount, reason, changed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (clan_id, match_id, old_elo, new_elo, change_amount, reason, changed_by)
        )
        await conn.commit()


async def increment_clan_matches(clan_id: int) -> None:
    """Increment matches_played counter."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE clans SET matches_played = matches_played + 1, updated_at = datetime('now') WHERE id = ?",
            (clan_id,)
        )
        await conn.commit()


async def set_clan_discord_ids(clan_id: int, role_id: str, channel_id: str) -> None:
    """Set Discord role and channel IDs for an approved clan."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE clans SET discord_role_id = ?, discord_channel_id = ?, updated_at = datetime('now') WHERE id = ?",
            (role_id, channel_id, clan_id)
        )
        await conn.commit()


async def update_clan_name(clan_id: int, new_name: str) -> bool:
    """Update clan name. Returns True if successful, False if name already exists."""
    async with get_connection() as conn:
        try:
            await conn.execute(
                "UPDATE clans SET name = ?, updated_at = datetime('now') WHERE id = ?",
                (new_name, clan_id)
            )
            await conn.commit()
            return True
        except aiosqlite.IntegrityError:
            # Name already exists (UNIQUE constraint)
            return False


# =============================================================================
# CLAN MEMBERS CRUD
# =============================================================================

async def add_member(user_id: int, clan_id: int, role: str = "member") -> None:
    """Add a member to a clan. Idempotent: uses INSERT OR IGNORE."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO clan_members (user_id, clan_id, role) VALUES (?, ?, ?)",
            (user_id, clan_id, role)
        )
        await conn.commit()


async def remove_member(user_id: int, clan_id: int) -> None:
    """Remove a member from a clan."""
    async with get_connection() as conn:
        await conn.execute(
            "DELETE FROM clan_members WHERE user_id = ? AND clan_id = ?",
            (user_id, clan_id)
        )
        await conn.commit()


async def move_member(user_id: int, from_clan_id: int, to_clan_id: int, new_role: str = "member") -> None:
    """Move a member from one clan to another in a single transaction."""
    async with get_connection() as conn:
        await conn.execute("BEGIN")
        try:
            await conn.execute(
                "DELETE FROM clan_members WHERE user_id = ? AND clan_id = ?",
                (user_id, from_clan_id)
            )
            await conn.execute(
                "INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, ?)",
                (user_id, to_clan_id, new_role)
            )
            await conn.commit()
        except Exception as e:
            await conn.rollback()
            raise e


async def update_member_role(user_id: int, clan_id: int, role: str) -> None:
    """Update member's role in a clan."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE clan_members SET role = ? WHERE user_id = ? AND clan_id = ?",
            (role, user_id, clan_id)
        )
        await conn.commit()


async def get_clan_members(clan_id: int) -> List[Dict[str, Any]]:
    """Get all members of a clan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT cm.*, u.discord_id, u.riot_id 
               FROM clan_members cm
               JOIN users u ON cm.user_id = u.id
               WHERE cm.clan_id = ?""",
            (clan_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_clan(user_id: int) -> Optional[Dict[str, Any]]:
    """Get the clan a user belongs to (excludes disbanded/cancelled clans)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT c.*, cm.role as member_role
               FROM clans c
               JOIN clan_members cm ON c.id = cm.clan_id
               WHERE cm.user_id = ? AND c.status NOT IN ('disbanded', 'cancelled', 'rejected')""",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def count_clan_members(clan_id: int) -> int:
    """Count members in a clan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM clan_members WHERE clan_id = ?",
            (clan_id,)
        )
        row = await cursor.fetchone()
        return row["count"]


# =============================================================================
# CREATE REQUESTS CRUD (5-Accept Flow)
# =============================================================================

async def create_create_request(clan_id: int, user_id: int, expires_at: str) -> int:
    """Create a new clan creation request for a member."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO create_requests (clan_id, user_id, expires_at) VALUES (?, ?, ?)",
            (clan_id, user_id, expires_at)
        )
        await conn.commit()
        return cursor.lastrowid


async def accept_create_request(clan_id: int, user_id: int) -> None:
    """Accept a clan creation request."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE create_requests SET status = 'accepted', responded_at = datetime('now') WHERE clan_id = ? AND user_id = ?",
            (clan_id, user_id)
        )
        await conn.commit()


async def decline_create_request(clan_id: int, user_id: int) -> None:
    """Decline a clan creation request."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE create_requests SET status = 'declined', responded_at = datetime('now') WHERE clan_id = ? AND user_id = ?",
            (clan_id, user_id)
        )
        await conn.commit()


async def get_pending_create_requests(clan_id: int) -> List[Dict[str, Any]]:
    """Get all pending create requests for a clan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM create_requests WHERE clan_id = ? AND status = 'pending'",
            (clan_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_user_pending_request(user_id: int) -> Optional[Dict[str, Any]]:
    """Get pending request for a user."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM create_requests WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_request_any_status(clan_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Get request for a user in a specific clan regardless of status."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM create_requests WHERE clan_id = ? AND user_id = ?",
            (clan_id, user_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def check_all_accepted(clan_id: int) -> bool:
    """Check if all 4 invited members have accepted."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM create_requests WHERE clan_id = ? AND status = 'accepted'",
            (clan_id,)
        )
        row = await cursor.fetchone()
        return row["count"] >= 4


# =============================================================================
# INVITE REQUESTS CRUD (Invite to existing active clan)
# =============================================================================

async def create_invite_request(clan_id: int, user_id: int, invited_by_user_id: int, expires_at: str) -> int:
    """Create a new invite request for joining an existing clan. Returns invite ID."""
    async with get_connection() as conn:
        # Cancel any existing pending invites for this user to this clan
        await conn.execute(
            "UPDATE invite_requests SET status = 'cancelled' WHERE clan_id = ? AND user_id = ? AND status = 'pending'",
            (clan_id, user_id)
        )
        cursor = await conn.execute(
            "INSERT INTO invite_requests (clan_id, user_id, invited_by_user_id, expires_at) VALUES (?, ?, ?, ?)",
            (clan_id, user_id, invited_by_user_id, expires_at)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_pending_invite(user_id: int, clan_id: int = None) -> Optional[Dict[str, Any]]:
    """Get pending invite for a user. Optionally filter by clan."""
    async with get_connection() as conn:
        if clan_id:
            cursor = await conn.execute(
                "SELECT * FROM invite_requests WHERE user_id = ? AND clan_id = ? AND status = 'pending'",
                (user_id, clan_id)
            )
        else:
            cursor = await conn.execute(
                "SELECT * FROM invite_requests WHERE user_id = ? AND status = 'pending'",
                (user_id,)
            )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def accept_invite(invite_id: int) -> bool:
    """Accept an invite. Returns True if successful."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE invite_requests SET status = 'accepted', responded_at = datetime('now') WHERE id = ? AND status = 'pending'",
            (invite_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def decline_invite(invite_id: int) -> bool:
    """Decline an invite. Returns True if successful."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE invite_requests SET status = 'declined', responded_at = datetime('now') WHERE id = ? AND status = 'pending'",
            (invite_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_invite_by_id(invite_id: int) -> Optional[Dict[str, Any]]:
    """Get invite by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM invite_requests WHERE id = ?", (invite_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# MATCHES CRUD (v2 - Updated for new workflow)
# =============================================================================

async def create_match_v2(
    clan_a_id: int, 
    clan_b_id: int, 
    creator_user_id: int,
    note: Optional[str] = None,
    message_id: Optional[str] = None,
    channel_id: Optional[str] = None
) -> int:
    """Create a new match. Returns match ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO matches 
               (clan_a_id, clan_b_id, creator_user_id, note, message_id, channel_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clan_a_id, clan_b_id, creator_user_id, note, message_id, channel_id)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_match(match_id: int) -> Optional[Dict[str, Any]]:
    """Get match by ID with all fields."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM matches WHERE id = ?", (match_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_match_message_ids(match_id: int, message_id: str, channel_id: str) -> None:
    """Update Discord message/channel IDs for a match (for button persistence)."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE matches SET message_id = ?, channel_id = ? WHERE id = ?",
            (message_id, channel_id, match_id)
        )
        await conn.commit()


async def update_match_status_atomic(match_id: int, expected_status: str, new_status: str) -> bool:
    """
    Atomically update match status only if it matches expected status.
    Used for concurrency safety (e.g., two users clicking Confirm at same time).
    Returns True if update succeeded, False if status didn't match.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE matches SET status = ? WHERE id = ? AND status = ?",
            (new_status, match_id, expected_status)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def report_match_v3(match_id: int, score_a: int, score_b: int) -> bool:
    """
    Report match result with numerical scores. Sets status to 'reported'.
    Returns True if successful, False if match not in 'created' status.
    """
    async with get_connection() as conn:
        # Determine reported_winner_clan_id based on scores
        # We need to get clan IDs first
        cursor = await conn.execute("SELECT clan_a_id, clan_b_id FROM matches WHERE id = ?", (match_id,))
        match_row = await cursor.fetchone()
        if not match_row:
            return False
            
        clan_a_id = match_row["clan_a_id"]
        clan_b_id = match_row["clan_b_id"]
        
        if score_a > score_b:
            reported_winner_id = clan_a_id
        elif score_b > score_a:
            reported_winner_id = clan_b_id
        else:
            # Draw is not expected in this system, but let's handle it
            reported_winner_id = None
            
        cursor = await conn.execute(
            """UPDATE matches SET 
               score_a = ?,
               score_b = ?,
               reported_winner_clan_id = ?,
               reported_at = datetime('now'),
               status = 'reported'
               WHERE id = ? AND status = 'created'""",
            (score_a, score_b, reported_winner_id, match_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def confirm_match_v2(match_id: int, confirmed_by_user_id: int) -> bool:
    """
    Confirm match result. Sets status to 'confirmed'.
    Returns True if successful, False if match not in 'reported' status.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            """UPDATE matches SET 
               confirmed_by_user_id = ?,
               confirmed_at = datetime('now'),
               status = 'confirmed'
               WHERE id = ? AND status = 'reported'""",
            (confirmed_by_user_id, match_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def dispute_match(match_id: int, disputed_by_user_id: int, reason: Optional[str] = None) -> bool:
    """
    Dispute match result. Sets status to 'dispute'.
    Returns True if successful, False if match not in 'reported' status.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            """UPDATE matches SET 
               disputed_by_user_id = ?,
               disputed_at = datetime('now'),
               dispute_reason = ?,
               status = 'dispute'
               WHERE id = ? AND status = 'reported'""",
            (disputed_by_user_id, reason, match_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def resolve_match(match_id: int, resolved_by_user_id: int, winner_clan_id: int, reason: str) -> bool:
    """
    Resolve disputed match (Mod action). Sets status to 'resolved'.
    Returns True if successful, False if match not in 'dispute' status.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            """UPDATE matches SET 
               resolved_by_user_id = ?,
               resolved_at = datetime('now'),
               resolved_reason = ?,
               resolved_winner_clan_id = ?,
               status = 'resolved'
               WHERE id = ? AND status = 'dispute'""",
            (resolved_by_user_id, reason, winner_clan_id, match_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def cancel_match(match_id: int) -> bool:
    """
    Finalize cancelling a match.
    Returns True if successful.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE matches SET status = 'cancelled' WHERE id = ?",
            (match_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def request_match_cancel(match_id: int, clan_id: int) -> bool:
    """
    Record that a clan requested to cancel the match.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE matches SET cancel_requested_by_clan_id = ? WHERE id = ? AND status = 'created'",
            (clan_id, match_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def clear_match_cancel_request(match_id: int) -> bool:
    """
    Clear a cancellation request (e.g. if someone reports score instead).
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE matches SET cancel_requested_by_clan_id = NULL WHERE id = ?",
            (match_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_match_with_clans(match_id: int) -> Optional[Dict[str, Any]]:
    """Get match with clan names included."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT m.*, 
                      ca.name as clan_a_name, ca.elo as clan_a_elo, ca.status as clan_a_status,
                      cb.name as clan_b_name, cb.elo as clan_b_elo, cb.status as clan_b_status,
                      u.discord_id as creator_discord_id
               FROM matches m
               JOIN clans ca ON m.clan_a_id = ca.id
               JOIN clans cb ON m.clan_b_id = cb.id
               JOIN users u ON m.creator_user_id = u.id
               WHERE m.id = ?""",
            (match_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# ELO HISTORY CRUD
# =============================================================================

async def get_clan_elo_history(clan_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Get Elo history for a clan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM elo_history WHERE clan_id = ? ORDER BY created_at DESC LIMIT ?",
            (clan_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# LOANS CRUD
# =============================================================================

async def create_loan(lending_clan_id: int, borrowing_clan_id: int, member_user_id: int, requested_by_user_id: int, duration_days: int, note: Optional[str] = None) -> int:
    """Create a loan request. Returns loan ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO loans 
               (lending_clan_id, borrowing_clan_id, member_user_id, requested_by_user_id, duration_days, status) 
               VALUES (?, ?, ?, ?, ?, 'requested')""",
            (lending_clan_id, borrowing_clan_id, member_user_id, requested_by_user_id, duration_days)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_loan(loan_id: int) -> Optional[Dict[str, Any]]:
    """Get loan by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM loans WHERE id = ?", (loan_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_loan_acceptance(loan_id: int, lending: Optional[bool] = None, borrowing: Optional[bool] = None, member: Optional[bool] = None) -> None:
    """Update acceptance flags for a loan."""
    async with get_connection() as conn:
        updates = []
        params = []
        if lending is not None:
            updates.append("accept_lending = ?")
            params.append(1 if lending else 0)
        if borrowing is not None:
            updates.append("accept_borrowing = ?")
            params.append(1 if borrowing else 0)
        if member is not None:
            updates.append("accept_member = ?")
            params.append(1 if member else 0)
        
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(loan_id)
            cursor = await conn.execute(
                f"UPDATE loans SET {', '.join(updates)} WHERE id = ? AND status = 'requested'",
                params
            )
            await conn.commit()
            return cursor.rowcount > 0
        return False


async def activate_loan(loan_id: int) -> bool:
    """Activate a loan (all parties accepted). Returns True if status was changed."""
    async with get_connection() as conn:
        # Get duration
        cursor = await conn.execute("SELECT duration_days FROM loans WHERE id = ?", (loan_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Loan {loan_id} not found")
        
        start_at = datetime.now(timezone.utc)
        end_at = start_at + timedelta(days=row["duration_days"])
        
        cursor = await conn.execute(
            "UPDATE loans SET status = 'active', start_at = ?, end_at = ?, updated_at = datetime('now') WHERE id = ? AND status = 'requested'",
            (start_at.isoformat(), end_at.isoformat(), loan_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def end_loan(loan_id: int) -> None:
    """End a loan."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE loans SET status = 'ended', updated_at = datetime('now') WHERE id = ?",
            (loan_id,)
        )
        await conn.commit()


async def cancel_loan(loan_id: int, user_id: int, reason: str) -> None:
    """Cancel a loan request."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE loans SET status = 'cancelled', cancelled_by_user_id = ?, cancelled_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (user_id, reason, loan_id)
        )
        await conn.commit()


async def get_active_loan_for_clan(clan_id: int) -> Optional[Dict[str, Any]]:
    """Check if clan has an active loan (either lending or borrowing)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM loans 
               WHERE (lending_clan_id = ? OR borrowing_clan_id = ?) 
               AND status = 'active'""",
            (clan_id, clan_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def count_active_loans_for_clan(clan_id: int) -> int:
    """Count how many active loans a clan is involved in (lending or borrowing)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT COUNT(*) FROM loans 
               WHERE (lending_clan_id = ? OR borrowing_clan_id = ?) 
               AND status = 'active'""",
            (clan_id, clan_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_active_loans_for_clan(clan_id: int) -> List[Dict[str, Any]]:
    """Get all active loans for a clan (as lending or borrowing)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM loans 
               WHERE (lending_clan_id = ? OR borrowing_clan_id = ?) 
               AND status = 'active'""",
            (clan_id, clan_id)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_active_loan_for_member(user_id: int) -> Optional[Dict[str, Any]]:
    """Check if member is currently in an active loan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM loans WHERE member_user_id = ? AND status = 'active'",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# TRANSFERS CRUD
# =============================================================================

async def create_transfer(source_clan_id: int, dest_clan_id: int, member_user_id: int, requested_by_user_id: int) -> int:
    """Create a transfer request. Returns transfer ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO transfers 
               (source_clan_id, dest_clan_id, member_user_id, requested_by_user_id, status) 
               VALUES (?, ?, ?, ?, 'requested')""",
            (source_clan_id, dest_clan_id, member_user_id, requested_by_user_id)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_transfer(transfer_id: int) -> Optional[Dict[str, Any]]:
    """Get transfer by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM transfers WHERE id = ?", (transfer_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_transfer_acceptance(transfer_id: int, source: Optional[bool] = None, dest: Optional[bool] = None, member: Optional[bool] = None) -> None:
    """Update acceptance flags for a transfer."""
    async with get_connection() as conn:
        updates = []
        params = []
        if source is not None:
            updates.append("accept_source = ?")
            params.append(1 if source else 0)
        if dest is not None:
            updates.append("accept_dest = ?")
            params.append(1 if dest else 0)
        if member is not None:
            updates.append("accept_member = ?")
            params.append(1 if member else 0)
        
        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(transfer_id)
            cursor = await conn.execute(
                f"UPDATE transfers SET {', '.join(updates)} WHERE id = ? AND status = 'requested'",
                params
            )
            await conn.commit()
            return cursor.rowcount > 0
        return False


async def complete_transfer(transfer_id: int) -> bool:
    """Complete a transfer. Returns True if status was changed."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE transfers SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ? AND status = 'requested'",
            (transfer_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def cancel_transfer(transfer_id: int, user_id: int, reason: str) -> None:
    """Cancel a transfer request."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE transfers SET status = 'cancelled', cancelled_by_user_id = ?, cancelled_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (user_id, reason, transfer_id)
        )
        await conn.commit()


async def get_user_pending_transfer(user_id: int) -> Optional[Dict[str, Any]]:
    """Get pending transfer for a user."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM transfers WHERE member_user_id = ? AND status = 'requested'",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# =============================================================================
# COOLDOWNS CRUD
# =============================================================================

async def get_cooldown(target_type: str, target_id: int, kind: str) -> Optional[Dict[str, Any]]:
    """Get active cooldown for a target."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM cooldowns 
               WHERE target_type = ? AND target_id = ? AND kind = ? 
               AND DATETIME(until) > datetime('now')""",
            (target_type, target_id, kind)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_cooldown(target_type: str, target_id: int, kind: str, duration_days: int, reason: str) -> None:
    """Set or update a cooldown in days."""
    async with get_connection() as conn:
        until = (datetime.now(timezone.utc) + timedelta(days=duration_days)).isoformat()
        await conn.execute(
            """INSERT INTO cooldowns (target_type, target_id, kind, until, reason)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(target_type, target_id, kind) 
               DO UPDATE SET until = excluded.until, reason = excluded.reason, updated_at = datetime('now')""",
            (target_type, target_id, kind, until, reason)
        )
        await conn.commit()


async def set_cooldown_minutes(target_type: str, target_id: int, kind, duration_minutes: int, reason: str) -> None:
    """Set or update a cooldown in minutes."""
    async with get_connection() as conn:
        # Use timezone-aware now
        until = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).isoformat()
        await conn.execute(
            """INSERT INTO cooldowns (target_type, target_id, kind, until, reason)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(target_type, target_id, kind) 
               DO UPDATE SET until = excluded.until, reason = excluded.reason, updated_at = datetime('now')""",
            (target_type, target_id, kind, until, reason)
        )
        await conn.commit()


async def clear_cooldown(target_type: str, target_id: int, kind: Optional[str] = None) -> None:
    """Clear cooldown(s) for a target."""
    async with get_connection() as conn:
        if kind:
            await conn.execute(
                "DELETE FROM cooldowns WHERE target_type = ? AND target_id = ? AND kind = ?",
                (target_type, target_id, kind)
            )
        else:
            await conn.execute(
                "DELETE FROM cooldowns WHERE target_type = ? AND target_id = ?",
                (target_type, target_id)
            )
        await conn.commit()


async def pop_expired_cooldowns() -> List[Dict[str, Any]]:
    """Return and clear expired cooldowns from the new cooldowns table."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM cooldowns WHERE DATETIME(until) <= datetime('now')"
        )
        rows = await cursor.fetchall()
        if not rows:
            return []

        ids = [row["id"] for row in rows]
        placeholders = ",".join(["?"] * len(ids))
        await conn.execute(
            f"DELETE FROM cooldowns WHERE id IN ({placeholders})",
            ids
        )
        await conn.commit()
        return [dict(row) for row in rows]


async def pop_expired_user_cooldowns() -> List[Dict[str, Any]]:
    """Return and clear expired legacy join/leave cooldowns from users table."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT id, discord_id, cooldown_until FROM users WHERE cooldown_until IS NOT NULL"
        )
        rows = await cursor.fetchall()

        expired_ids = []
        expired_rows = []
        now = datetime.now(timezone.utc)

        for row in rows:
            try:
                until_str = row["cooldown_until"].replace("Z", "+00:00")
                until_dt = datetime.fromisoformat(until_str)
                if until_dt.tzinfo is None:
                    until_dt = until_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if until_dt <= now:
                expired_ids.append(row["id"])
                expired_rows.append(dict(row))

        if expired_ids:
            placeholders = ",".join(["?"] * len(expired_ids))
            await conn.execute(
                f"UPDATE users SET cooldown_until = NULL, updated_at = datetime('now') WHERE id IN ({placeholders})",
                expired_ids
            )
            await conn.commit()

        return expired_rows


async def cancel_user_pending_requests(user_id: int) -> None:
    """Cancel all pending loan/transfer requests initiated by or involving this user."""
    async with get_connection() as conn:
        now = datetime.now(timezone.utc).isoformat()
        
        # Cancel loans where user is member or initiator
        await conn.execute(
            """UPDATE loans SET status = 'cancelled', cancelled_reason = 'Member left/kicked', updated_at = ? 
               WHERE status = 'requested' AND (member_user_id = ? OR requested_by_user_id = ?)""",
            (now, user_id, user_id)
        )
        
        # Cancel transfers where user is member or initiator
        await conn.execute(
            """UPDATE transfers SET status = 'cancelled', cancelled_reason = 'Member left/kicked', updated_at = ? 
               WHERE status = 'requested' AND (member_user_id = ? OR requested_by_user_id = ?)""",
            (now, user_id, user_id)
        )
        
        await conn.commit()


# =============================================================================
# CASES CRUD
# =============================================================================

async def create_case(reporter_id: int, target_type: str, target_id: int, reason: str, proof: Optional[str] = None) -> int:
    """Create a new report case. Returns case ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO cases (reporter_id, target_type, target_id, reason, proof) VALUES (?, ?, ?, ?, ?)",
            (reporter_id, target_type, target_id, reason, proof)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_case(case_id: int) -> Optional[Dict[str, Any]]:
    """Get case by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_case_status(case_id: int, status: str) -> None:
    """Update case status."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE cases SET status = ? WHERE id = ?",
            (status, case_id)
        )
        await conn.commit()


async def resolve_case(case_id: int, mod_id: int, verdict: str, verdict_reason: str, punishment: Optional[str] = None) -> None:
    """Resolve a case with verdict."""
    async with get_connection() as conn:
        appeal_deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        
        await conn.execute(
            """UPDATE cases SET 
               status = 'resolved', 
               verdict = ?, 
               verdict_reason = ?,
               punishment = ?,
               mod_id = ?,
               resolved_at = datetime('now'),
               appeal_deadline = ?
               WHERE id = ?""",
            (verdict, verdict_reason, punishment, mod_id, appeal_deadline, case_id)
        )
        await conn.commit()


async def get_open_cases() -> List[Dict[str, Any]]:
    """Get all open/investigating cases."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM cases WHERE status IN ('open', 'investigating') ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# APPEALS CRUD
# =============================================================================

async def create_appeal(case_id: int, user_id: int, reason: str, proof: Optional[str] = None) -> int:
    """Create an appeal for a case. Returns appeal ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO appeals (case_id, user_id, reason, proof) VALUES (?, ?, ?, ?)",
            (case_id, user_id, reason, proof)
        )
        # Update case status
        await conn.execute("UPDATE cases SET status = 'appealed' WHERE id = ?", (case_id,))
        await conn.commit()
        return cursor.lastrowid


async def get_appeal(appeal_id: int) -> Optional[Dict[str, Any]]:
    """Get appeal by ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM appeals WHERE id = ?", (appeal_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_appeal_by_case(case_id: int) -> Optional[Dict[str, Any]]:
    """Get appeal for a case."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM appeals WHERE case_id = ?", (case_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def resolve_appeal(appeal_id: int, mod_id: int, status: str, mod_verdict: str, mod_reason: str) -> None:
    """Resolve an appeal."""
    async with get_connection() as conn:
        # Get appeal to find case_id
        cursor = await conn.execute("SELECT case_id FROM appeals WHERE id = ?", (appeal_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Appeal {appeal_id} not found")
        case_id = row["case_id"]
        
        await conn.execute(
            """UPDATE appeals SET 
               status = ?, 
               mod_id = ?,
               mod_verdict = ?,
               mod_reason = ?,
               reviewed_at = datetime('now')
               WHERE id = ?""",
            (status, mod_id, mod_verdict, mod_reason, appeal_id)
        )
        # Update case to final_verdict then closed
        await conn.execute("UPDATE cases SET status = 'closed' WHERE id = ?", (case_id,))
        await conn.commit()


# =============================================================================
# SYSTEM BANS CRUD
# =============================================================================

async def add_system_ban(entity_type: str, entity_id: int, reason: str, mod_id: int, expires_at: Optional[str] = None) -> int:
    """Add a system ban. Returns ban ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO system_bans (entity_type, entity_id, reason, banned_by_mod_user_id, expires_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(entity_type, entity_id) 
               DO UPDATE SET reason = excluded.reason, banned_by_mod_user_id = excluded.banned_by_mod_user_id,
                             banned_at = datetime('now'), expires_at = excluded.expires_at""",
            (entity_type, entity_id, reason, mod_id, expires_at)
        )
        await conn.commit()
        return cursor.lastrowid


async def remove_system_ban(entity_type: str, entity_id: int) -> bool:
    """Remove a system ban. Returns True if removed, False if not found."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "DELETE FROM system_bans WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_system_ban(entity_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
    """Get active system ban for an entity (checks expiration)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM system_bans 
               WHERE entity_type = ? AND entity_id = ?
               AND (expires_at IS NULL OR expires_at > datetime('now'))""",
            (entity_type, entity_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def is_user_system_banned(user_id: int) -> bool:
    """Check if user is system banned."""
    ban = await get_system_ban("user", user_id)
    return ban is not None


async def is_clan_system_banned(clan_id: int) -> bool:
    """Check if clan is system banned."""
    ban = await get_system_ban("clan", clan_id)
    return ban is not None


# =============================================================================
# CLAN FLAGS CRUD
# =============================================================================

async def get_clan_flags(clan_id: int) -> Optional[Dict[str, Any]]:
    """Get clan flags."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clan_flags WHERE clan_id = ?", (clan_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_clan_frozen(clan_id: int, reason: str, mod_id: int) -> None:
    """Freeze a clan (Elo will not be applied)."""
    async with get_connection() as conn:
        await conn.execute(
            """INSERT INTO clan_flags (clan_id, is_frozen, frozen_reason, frozen_by_mod_user_id, frozen_at)
               VALUES (?, 1, ?, ?, datetime('now'))
               ON CONFLICT(clan_id) 
               DO UPDATE SET is_frozen = 1, frozen_reason = excluded.frozen_reason,
                             frozen_by_mod_user_id = excluded.frozen_by_mod_user_id, frozen_at = datetime('now')""",
            (clan_id, reason, mod_id)
        )
        await conn.commit()


async def unset_clan_frozen(clan_id: int) -> bool:
    """Unfreeze a clan. Returns True if was frozen, False otherwise."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE clan_flags SET is_frozen = 0, frozen_reason = NULL, frozen_by_mod_user_id = NULL, frozen_at = NULL WHERE clan_id = ? AND is_frozen = 1",
            (clan_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def is_clan_frozen(clan_id: int) -> bool:
    """Check if clan is frozen."""
    flags = await get_clan_flags(clan_id)
    return flags is not None and flags.get("is_frozen") == 1


# =============================================================================
# CASE ACTIONS CRUD
# =============================================================================

async def add_case_action(case_id: int, action_type: str, mod_id: int, target_info: Optional[str] = None, payload_json: Optional[str] = None) -> int:
    """Log a case action. Returns action ID."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """INSERT INTO case_actions (case_id, action_type, target_info, payload_json, performed_by_mod_user_id)
               VALUES (?, ?, ?, ?, ?)""",
            (case_id, action_type, target_info, payload_json, mod_id)
        )
        await conn.commit()
        return cursor.lastrowid


async def get_case_actions(case_id: int) -> List[Dict[str, Any]]:
    """Get all actions for a case."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM case_actions WHERE case_id = ? ORDER BY performed_at",
            (case_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# EXTENDED CASES QUERIES
# =============================================================================

async def get_cases_filtered(status: Optional[str] = None, target_type: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get cases with optional filters."""
    async with get_connection() as conn:
        query = "SELECT * FROM cases WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if target_type:
            query += " AND target_type = ?"
            params.append(target_type)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def close_case(case_id: int) -> None:
    """Close a case."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE cases SET status = 'closed' WHERE id = ?",
            (case_id,)
        )
        await conn.commit()


# =============================================================================
# MATCH VOID OPERATION
# =============================================================================

async def void_match(match_id: int) -> bool:
    """Void a match (mark as cancelled by mod). Returns True if voided, False if already terminal."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE matches SET status = 'voided' WHERE id = ? AND status NOT IN ('voided', 'cancelled')",
            (match_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0


# =============================================================================
# ELO ROLLBACK HELPERS
# =============================================================================

async def get_elo_history_for_match(match_id: int) -> List[Dict[str, Any]]:
    """Get Elo history entries for a specific match."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM elo_history WHERE match_id = ? ORDER BY created_at",
            (match_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_clan_elo_directly(clan_id: int, new_elo: int) -> int:
    """Set clan Elo directly. Returns old Elo value."""
    async with get_connection() as conn:
        cursor = await conn.execute("SELECT elo FROM clans WHERE id = ?", (clan_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Clan {clan_id} not found")
        old_elo = row["elo"]
        
        await conn.execute(
            "UPDATE clans SET elo = ?, updated_at = datetime('now') WHERE id = ?",
            (new_elo, clan_id)
        )
        await conn.commit()
        return old_elo


async def mark_match_elo_rolled_back(match_id: int) -> None:
    """Mark a match as having its Elo rolled back."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE matches SET elo_applied = 0 WHERE id = ?",
            (match_id,)
        )
        await conn.commit()


async def hard_delete_clan(clan_id: int) -> None:
    """
    Completely remove a clan and all its related data (matches, loans, transfers, etc.)
    from the database. This is used when a mod deletes a clan or creation fails.
    """
    async with get_connection() as conn:
        # 1. Delete basic relations (ON DELETE CASCADE in schema would handle some, 
        # but we do it manually to be safe and clear)
        await conn.execute("DELETE FROM clan_members WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM create_requests WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM invite_requests WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM clan_flags WHERE clan_id = ?", (clan_id,))
        await conn.execute("DELETE FROM elo_history WHERE clan_id = ?", (clan_id,))
        
        # 2. Delete complex relations (these have ON DELETE RESTRICT in schema)
        await conn.execute("DELETE FROM matches WHERE clan_a_id = ? OR clan_b_id = ?", (clan_id, clan_id))
        await conn.execute("DELETE FROM loans WHERE lending_clan_id = ? OR borrowing_clan_id = ?", (clan_id, clan_id))
        await conn.execute("DELETE FROM transfers WHERE source_clan_id = ? OR dest_clan_id = ?", (clan_id, clan_id))
        
        # 3. Delete metadata
        await conn.execute("DELETE FROM cooldowns WHERE target_type = 'clan' AND target_id = ?", (clan_id,))
        await conn.execute("DELETE FROM cases WHERE target_type = 'clan' AND target_id = ?", (clan_id,))
        
        # 4. Finally delete the clan itself
        await conn.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
        await conn.commit()


# =============================================================================
# ARENA DASHBOARD HELPERS
# =============================================================================

async def get_all_active_clans() -> List[Dict[str, Any]]:
    """Get all clans with status 'active'."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM clans WHERE status = 'active' ORDER BY elo DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def count_clan_members(clan_id: int) -> int:
    """Count number of members in a clan."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) as cnt FROM clan_members WHERE clan_id = ?",
            (clan_id,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0


async def get_recent_matches(limit: int = 10, include_cancelled: bool = False) -> List[Dict[str, Any]]:
    """Get recent matches, ordered by created_at descending."""
    async with get_connection() as conn:
        query = "SELECT * FROM matches"
        if not include_cancelled:
            query += " WHERE status != 'cancelled'"
        query += " ORDER BY created_at DESC LIMIT ?"
        
        cursor = await conn.execute(query, (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# =============================================================================
# COOLDOWN & BAN HELPERS (for Arena Dashboard)
# =============================================================================

async def get_active_cooldown(target_id: int, target_type: str, kind: str) -> Optional[Dict[str, Any]]:
    """Get an active cooldown for a target. Returns None if no active cooldown exists."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM cooldowns 
               WHERE target_id = ? AND target_type = ? AND kind = ? 
               AND DATETIME(until) > datetime('now')""",
            (target_id, target_type, kind)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_user_cooldowns(user_id: int) -> List[Dict[str, Any]]:
    """Get all active cooldowns for a user (FUSED: checks both systems)."""
    async with get_connection() as conn:
        # 1. New table
        cursor = await conn.execute(
            """SELECT * FROM cooldowns 
               WHERE target_id = ? AND target_type = 'user' 
               AND DATETIME(until) > datetime('now')""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        cooldowns = [dict(row) for row in rows]
        
        # 2. Legacy check (for UI visibility before lazy migration)
        cursor = await conn.execute(
            "SELECT cooldown_until FROM users WHERE id = ? AND cooldown_until IS NOT NULL",
            (user_id,)
        )
        user_row = await cursor.fetchone()
        
        if user_row:
            legacy_until = user_row["cooldown_until"]
            try:
                # Basic check if it's in the future
                if legacy_until.endswith('Z'):
                    until_str = legacy_until.replace('Z', '+00:00')
                else:
                    until_str = legacy_until
                
                if datetime.fromisoformat(until_str) > datetime.now(timezone.utc):
                    # Check if not already in the list
                    if not any(c["kind"] == "join_leave" for c in cooldowns):
                        cooldowns.append({
                            "target_type": "user",
                            "target_id": user_id,
                            "kind": "join_leave",
                            "until": legacy_until,
                            "reason": "Legacy join cooldown"
                        })
            except Exception:
                pass
                
        return cooldowns


async def is_user_banned(user_id: int) -> Optional[Dict[str, Any]]:
    """Check if a user is system-banned. Returns ban info or None."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """SELECT * FROM system_bans 
               WHERE entity_type = 'user' AND entity_id = ?
               AND (expires_at IS NULL OR DATETIME(expires_at) > datetime('now'))""",
            (user_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

