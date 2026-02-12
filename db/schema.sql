-- =============================================================================
-- Clan System Database Schema
-- SQLite + aiosqlite
-- =============================================================================

-- -----------------------------------------------------------------------------
-- USERS TABLE
-- Stores Discord users registered in the clan system
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL UNIQUE,                    -- Discord user ID
    riot_id TEXT NOT NULL UNIQUE,                       -- Valorant Riot ID (Name#TAG), required
    is_banned INTEGER DEFAULT 0,                        -- 1 = banned from clan system
    ban_reason TEXT,                                    -- Reason for system ban
    cooldown_until TEXT,                                -- ISO timestamp: can't join clan until this time
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_discord_id ON users(discord_id);
CREATE INDEX IF NOT EXISTS idx_users_riot_id ON users(riot_id);

-- -----------------------------------------------------------------------------
-- CLANS TABLE
-- Stores clan entities with Elo and status
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                          -- Unique clan name
    status TEXT NOT NULL DEFAULT 'waiting_accept',      -- waiting_accept, pending_approval, active, inactive, rejected, disbanded
    elo INTEGER DEFAULT 1000,                           -- Starting Elo = 1000
    matches_played INTEGER DEFAULT 0,                   -- For placement detection (first 10 = high K-factor)
    captain_id INTEGER NOT NULL,                        -- FK to users.id
    discord_role_id TEXT,                               -- Discord role ID when created
    discord_channel_id TEXT,                            -- Private channel ID
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (captain_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_clans_name ON clans(name);
CREATE INDEX IF NOT EXISTS idx_clans_status ON clans(status);

-- -----------------------------------------------------------------------------
-- CLAN MEMBERS TABLE
-- Tracks membership relationships between users and clans
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clan_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,                           -- FK to users.id
    clan_id INTEGER NOT NULL,                           -- FK to clans.id
    role TEXT NOT NULL DEFAULT 'member',                -- captain, vice, member
    joined_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, clan_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clan_members_user ON clan_members(user_id);
CREATE INDEX IF NOT EXISTS idx_clan_members_clan ON clan_members(clan_id);

-- -----------------------------------------------------------------------------
-- CREATE REQUESTS TABLE
-- Tracks the 4-accept flow when creating a new clan (Captain + 4 members = 5)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS create_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL,                           -- FK to clans.id (pending clan)
    user_id INTEGER NOT NULL,                           -- FK to users.id (invited member)
    status TEXT NOT NULL DEFAULT 'pending',             -- pending, accepted, declined, expired
    expires_at TEXT NOT NULL,                           -- 48h timeout
    responded_at TEXT,
    UNIQUE(clan_id, user_id),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_create_requests_clan ON create_requests(clan_id);
CREATE INDEX IF NOT EXISTS idx_create_requests_user ON create_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_create_requests_status ON create_requests(status);

-- -----------------------------------------------------------------------------
-- INVITE REQUESTS TABLE
-- Tracks invitations to join an existing active clan (different from create_requests)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invite_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL,                           -- FK to clans.id (active clan)
    user_id INTEGER NOT NULL,                           -- FK to users.id (invited member)
    invited_by_user_id INTEGER NOT NULL,                -- FK to users.id (captain/vice who invited)
    status TEXT NOT NULL DEFAULT 'pending',             -- pending, accepted, declined, expired, cancelled
    expires_at TEXT NOT NULL,                           -- 48h timeout
    responded_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(clan_id, user_id, status),                   -- Only one pending invite per user per clan
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_invite_requests_clan ON invite_requests(clan_id);
CREATE INDEX IF NOT EXISTS idx_invite_requests_user ON invite_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_invite_requests_status ON invite_requests(status);

-- -----------------------------------------------------------------------------
-- MATCHES TABLE
-- Records matches between clans with full workflow tracking
-- Status flow: created -> reported -> confirmed/dispute -> resolved
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_a_id INTEGER NOT NULL,                         -- Creator's clan
    clan_b_id INTEGER NOT NULL,                         -- Opponent clan
    creator_user_id INTEGER NOT NULL,                   -- User who created the match
    status TEXT NOT NULL DEFAULT 'created',             -- created, reported, confirmed, dispute, resolved, cancelled
    note TEXT,                                          -- Optional match note/description
    -- Reporting phase
    reported_winner_clan_id INTEGER,                    -- Which clan was reported as winner
    reported_at TEXT,                                   -- Timestamp of result report
    -- Confirmation phase
    confirmed_by_user_id INTEGER,                       -- Opponent member who confirmed
    confirmed_at TEXT,
    -- Dispute phase
    disputed_by_user_id INTEGER,                        -- Opponent member who disputed
    disputed_at TEXT,
    dispute_reason TEXT,
    -- Resolution phase (mod intervention)
    resolved_by_user_id INTEGER,                        -- Mod who resolved the dispute
    resolved_at TEXT,
    resolved_reason TEXT,
    resolved_winner_clan_id INTEGER,                    -- Mod-decided winner
    -- Elo tracking
    elo_applied INTEGER DEFAULT 0,                      -- 1 = Elo changes were applied
    base_delta_a INTEGER,                               -- Base Elo change for clan A (before multiplier)
    base_delta_b INTEGER,                               -- Base Elo change for clan B (before multiplier)
    multiplier REAL,                                    -- Anti-farm multiplier (1.0, 0.7, 0.4, 0.2)
    final_delta_a INTEGER,                              -- Final Elo change for clan A
    final_delta_b INTEGER,                              -- Final Elo change for clan B
    -- Score tracking
    score_a INTEGER DEFAULT NULL,                       -- Score for Clan A
    score_b INTEGER DEFAULT NULL,                       -- Score for Clan B
    -- Discord message tracking (for persistent buttons)
    message_id TEXT,                                    -- Discord message ID containing buttons
    channel_id TEXT,                                    -- Discord channel ID
    cancel_requested_by_clan_id INTEGER,                -- ID of clan that requested cancellation
    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (clan_a_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (clan_b_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (creator_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (confirmed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (disputed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (resolved_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_matches_clan_a ON matches(clan_a_id);
CREATE INDEX IF NOT EXISTS idx_matches_clan_b ON matches(clan_b_id);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
CREATE INDEX IF NOT EXISTS idx_matches_created_at ON matches(created_at);
CREATE INDEX IF NOT EXISTS idx_matches_creator ON matches(creator_user_id);

-- -----------------------------------------------------------------------------
-- ELO HISTORY TABLE
-- Audit trail for all Elo changes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS elo_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL,
    match_id INTEGER,                                   -- NULL if manual adjustment
    old_elo INTEGER NOT NULL,
    new_elo INTEGER NOT NULL,
    change_amount INTEGER NOT NULL,                     -- Can be negative
    reason TEXT NOT NULL,                               -- match_win, match_loss, manual_set, rollback
    changed_by INTEGER,                                 -- FK to users.id (mod who made manual change)
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
    FOREIGN KEY (changed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_elo_history_clan ON elo_history(clan_id);
CREATE INDEX IF NOT EXISTS idx_elo_history_match ON elo_history(match_id);

-- -----------------------------------------------------------------------------
-- LOANS TABLE
-- Tracks member loans between clans (max 7 days)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lending_clan_id INTEGER NOT NULL,                   -- Origin clan
    borrowing_clan_id INTEGER NOT NULL,                 -- Destination clan
    member_user_id INTEGER NOT NULL,                    -- Loaned member
    requested_by_user_id INTEGER NOT NULL,              -- Who initiated
    status TEXT NOT NULL DEFAULT 'requested',           -- requested, active, ended, cancelled, expired
    accept_lending INTEGER DEFAULT 0,                   -- 0=pending, 1=accepted
    accept_borrowing INTEGER DEFAULT 0,
    accept_member INTEGER DEFAULT 0,
    duration_days INTEGER NOT NULL DEFAULT 7,
    start_at TEXT,
    end_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    cancelled_by_user_id INTEGER,
    cancelled_reason TEXT,
    FOREIGN KEY (lending_clan_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (borrowing_clan_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (requested_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (cancelled_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_loans_member ON loans(member_user_id);
CREATE INDEX IF NOT EXISTS idx_loans_source ON loans(lending_clan_id);
CREATE INDEX IF NOT EXISTS idx_loans_target ON loans(borrowing_clan_id);
CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);

-- -----------------------------------------------------------------------------
-- TRANSFERS TABLE
-- Tracks permanent transfers between clans
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_clan_id INTEGER NOT NULL,                    -- Origin clan
    dest_clan_id INTEGER NOT NULL,                      -- Destination clan
    member_user_id INTEGER NOT NULL,                    -- Transferring member
    requested_by_user_id INTEGER NOT NULL,              -- Who initiated
    status TEXT NOT NULL DEFAULT 'requested',           -- requested, completed, cancelled, expired
    accept_source INTEGER DEFAULT 0,
    accept_dest INTEGER DEFAULT 0,
    accept_member INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    cancelled_by_user_id INTEGER,
    cancelled_reason TEXT,
    FOREIGN KEY (source_clan_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (dest_clan_id) REFERENCES clans(id) ON DELETE RESTRICT,
    FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (requested_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (cancelled_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------------------
-- COOLDOWNS TABLE
-- Unified cooldown tracking
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cooldowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,                          -- user, clan
    target_id INTEGER NOT NULL,                         -- user_id or clan_id
    kind TEXT NOT NULL,                                 -- join_leave, loan, transfer
    until TEXT NOT NULL,                                -- ISO timestamp
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(target_type, target_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_cooldowns_target ON cooldowns(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_cooldowns_kind ON cooldowns(kind);

CREATE INDEX IF NOT EXISTS idx_transfers_user ON transfers(member_user_id);
CREATE INDEX IF NOT EXISTS idx_transfers_status ON transfers(status);

-- -----------------------------------------------------------------------------
-- CASES TABLE
-- Report/moderation cases
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,                       -- FK to users.id
    target_type TEXT NOT NULL,                          -- user, clan, match
    target_id INTEGER NOT NULL,                         -- ID of target (user_id, clan_id, or match_id)
    reason TEXT NOT NULL,
    proof TEXT,                                         -- URL or description of evidence
    status TEXT NOT NULL DEFAULT 'open',                -- open, investigating, resolved, appealed, final_verdict, closed
    verdict TEXT,                                       -- guilty, innocent, dismissed
    verdict_reason TEXT,
    punishment TEXT,                                    -- warning, elo_reset, match_ban, kick, disband, system_ban
    mod_id INTEGER,                                     -- FK to users.id (mod who resolved)
    resolved_at TEXT,
    appeal_deadline TEXT,                               -- 7 days after resolution
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (mod_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_reporter ON cases(reporter_id);
CREATE INDEX IF NOT EXISTS idx_cases_target ON cases(target_type, target_id);

-- -----------------------------------------------------------------------------
-- APPEALS TABLE
-- Appeals against case verdicts (1 appeal per case)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS appeals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL UNIQUE,                    -- One appeal per case
    user_id INTEGER NOT NULL,                           -- Who is appealing
    reason TEXT NOT NULL,
    proof TEXT,                                         -- New evidence
    status TEXT NOT NULL DEFAULT 'pending',             -- pending, reviewing, upheld, reduced, overturned
    mod_id INTEGER,                                     -- Mod who reviewed
    mod_verdict TEXT,
    mod_reason TEXT,
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (mod_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_appeals_case ON appeals(case_id);
CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status);

-- -----------------------------------------------------------------------------
-- SYSTEM BANS TABLE
-- Tracks system-wide bans for users or clans
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,                          -- 'user' or 'clan'
    entity_id INTEGER NOT NULL,                         -- user_id or clan_id
    reason TEXT NOT NULL,
    banned_by_mod_user_id INTEGER NOT NULL,
    banned_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,                                    -- NULL = permanent ban
    UNIQUE(entity_type, entity_id),
    FOREIGN KEY (banned_by_mod_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_system_bans_entity ON system_bans(entity_type, entity_id);

-- -----------------------------------------------------------------------------
-- CLAN FLAGS TABLE
-- Tracks special flags for clans (frozen, etc.)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clan_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clan_id INTEGER NOT NULL UNIQUE,
    is_frozen INTEGER DEFAULT 0,                        -- 1 = frozen (no Elo applied)
    frozen_reason TEXT,
    frozen_by_mod_user_id INTEGER,
    frozen_at TEXT,
    FOREIGN KEY (clan_id) REFERENCES clans(id) ON DELETE CASCADE,
    FOREIGN KEY (frozen_by_mod_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_clan_flags_clan ON clan_flags(clan_id);
CREATE INDEX IF NOT EXISTS idx_clan_flags_frozen ON clan_flags(is_frozen);

-- -----------------------------------------------------------------------------
-- CASE ACTIONS TABLE
-- Logs all moderator actions taken on cases
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,                          -- warning, freeze_clan, rollback_match, etc.
    target_info TEXT,                                   -- Human-readable target description
    payload_json TEXT,                                  -- JSON blob with action-specific data
    performed_by_mod_user_id INTEGER NOT NULL,
    performed_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
    FOREIGN KEY (performed_by_mod_user_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_case_actions_case ON case_actions(case_id);
CREATE INDEX IF NOT EXISTS idx_case_actions_type ON case_actions(action_type);
