# Clan System Specification

## 1. Commands

### User Commands
| Command | Description | Requirements |
| :--- | :--- | :--- |
| `/clan create <name> <member1> <member2> <member3> <member4> <member5>` | Create a new clan with 5 initial members. | User is Verified, not in clan, not in cooldown. Name unique. All members must have registered Riot ID. |
| `/clan accept` | Accept a clan invitation or creation request. | User has pending request. |
| `/clan decline` | Decline a clan invitation or creation request. | User has pending request. |
| `/clan info [clan_name]` | View clan stats, members, Elo. | None. |
| `/clan leave` | Leave current clan. | User in clan. Starts 14-day cooldown. |
| `/loan request <member> <clan> <days>` | Request to loan a member to another clan. | Captain/Vice of Source. 3-party accept required. |
| `/loan status [id]` | Check status of a loan. | None. |
| `/loan cancel <id>` | Cancel a pending loan request. | Initiator or Source Captain. |
| `/transfer request <member> <clan>` | Request to transfer a member to another clan. | Captain/Vice of Source. 3-party accept required. |
| `/transfer status [id]` | Check status of a transfer. | None. |
| `/transfer cancel <id>` | Cancel a pending transfer request. | Initiator or Source Captain. |
| `/report <target> <reason> [proof]` | Report a user/clan/match. | Creates a Case. |
| `/appeal <case_id> <reason> [proof]` | Appeal a punishment. | Once within 7 days of punishment. |
| `/register <riot_id>` | Register your Valorant Riot ID (e.g., `Name#TAG`). | Required before joining any clan. Must be your real account. |

### Match Commands (Any Clan Member)
| Command | Description | Requirements |
| :--- | :--- | :--- |
| `/match create <opponent_clan> [note]` | Create a custom match against another clan. | User must be in a clan. Match created on behalf of user's clan. |

**Match Button Workflow:**
- After creation, message shows: `[Clan A Win]` `[Clan B Win]` `[Cancel]`
- **Report**: Only match creator can report result or cancel.
- **Cancel**: Only allowed before result is reported.
- After report, message shows: `[Confirm]` `[Dispute]`
- **Confirm/Dispute**: Any member of opponent clan can click (1 person needed).

### Captain/Vice Commands
| Command | Description | Permission |
| :--- | :--- | :--- |
| `/clan invite <user>` | Invite a new member. | Captain/Vice. Target not in clan/cooldown. |
| `/clan kick <user>` | Kick a member. | Captain. Target gets 14-day cooldown. |
| `/clan promote_vice <user>` | Promote member to Vice Captain. | Captain. |
| `/clan demote_vice <user>` | Demote Vice Captain to Member. | Captain. |
| `/loan request ...` | (See User Commands - Captain/Vice only) | |
| `/transfer request ...` | (See User Commands - Captain/Vice only) | |

### Mod Commands
| Command | Description | Permission |
| :--- | :--- | :--- |
| `/mod clan approve <clan_id>` | Approve a pending clan. | Mod Role. |
| `/mod clan reject <clan_id> <reason>` | Reject a pending clan. | Mod Role. |
| `/mod clan disband <clan_name> <reason>` | Force disband a clan. | Mod Role. |
| `/mod clan ban <user_id>` | Ban user from clan system. | Mod Role. |
| `/mod case resolve <case_id> <verdict>` | Resolve a report/appeal case. | Mod Role. |
| `/mod elo set <clan_name> <value>` | Manually set clan Elo. | Mod Role. |
| `/mod elo rollback <match_id>` | Revert Elo change from a match. | Mod Role. |
| `/admin match resolve <match_id> <winner_clan> <reason>` | Resolve a disputed match. | Mod Role. |
| `/admin cooldown view <target>` | View active cooldowns. | Mod Role. |
| `/admin cooldown set <target> <kind> <days> <reason>` | Set/Overwrite a cooldown. | Mod Role. |
| `/admin cooldown clear <target> [kind]` | Clear cooldowns. | Mod Role. |
| `/admin case list [status] [target_type]` | List cases with optional filters. | Mod Role. |
| `/admin case view <case_id>` | View detailed case info. | Mod Role. |
| `/admin case action <case_id> <action_type> <reason> [target]` | Perform mod action on case. | Mod Role. |
| `/admin case close <case_id> [decision]` | Close a case. | Mod Role. |
| `/admin ban user <user> <reason>` | System ban a user. | Mod Role. |
| `/admin ban clan <clan_name> <reason>` | System ban a clan. | Mod Role. |
| `/admin unban <user\|clan> <target>` | Remove system ban. | Mod Role. |
| `/admin freeze clan <clan_name> <reason>` | Freeze clan (no Elo applied). | Mod Role. |
| `/admin unfreeze <clan_name>` | Unfreeze a clan. | Mod Role. |

### Report & Appeal Commands
| Command | Description | Requirements |
| :--- | :--- | :--- |
| `/report create <target_type> <target> <description> [evidence]` | Report a user, clan, or match. | Creates a Case. |
| `/report status <case_id>` | View case status (public-safe). | None. |
| `/appeal create <case_id> <description> [evidence]` | Appeal a case verdict. | Once within 7 days of resolution. |
| `/appeal status <case_id>` | View appeal status. | None. |

## 1.5 Elo System Rules

### Base Formula
- **Starting Elo**: 1000 for all clans
- **K-Factor**: 24 (constant)
- **Expected Score**: `E = 1 / (1 + 10^((opponent_elo - your_elo) / 400))`
- **Base Delta**: `round(K * (score - expected))`

### Anti-Farm Mechanics
Diminishing returns for repeated matches between same clan pair in 24h:
| Match # (in 24h) | Multiplier |
| :--- | :--- |
| 1st | 1.0 (100%) |
| 2nd | 0.7 (70%) |
| 3rd | 0.4 (40%) |
| 4th+ | 0.2 (20%) |

`final_delta = round(base_delta * multiplier)`

### Elo Application
- Elo applied only when match is **CONFIRMED** or **RESOLVED** by mod.
- Elo applied only if **both clans are ACTIVE** at apply time.
- Elo NOT applied if either clan is:
  - **INACTIVE**: message shows "Clan không active"
  - **FROZEN** (by mod): message shows "Clan bị đóng băng"
  - **SYSTEM BANNED**: message shows "Clan bị cấm hệ thống"
- Match proceeds normally in all cases, only Elo is skipped.

## 2. Permissions & Roles

### Discord Roles
- **Verified Role**: `Thiểu Năng Con` (Pre-existing server role. **DO NOT CREATE**).
- **Mod Role**: `Hội đồng quản trị` (Pre-existing server role. **DO NOT CREATE**).
- **Clan Role**: Auto-created per clan (e.g., `<ClanName>`). Assigned to all members.

### Internal Roles
- **Captain**: Creator of the clan. Full control.
- **Vice Captain**: Appointed by Captain. Can invite, match, loan. Cannot kick (only Captain can kick per rule "Captain có quyền mời/kick thành viên").
- **Member**: Standard member.

## 3. Logging Rules

All events must be logged to the **Mod Log Channel** (`log`).

### Log Format
`[TIMESTAMP] [EVENT_TYPE] Details...`

### Events to Log
1.  **Clan Lifecycle**:
    -   `CLAN_CREATE_REQUEST`: Captain + 5 members.
    -   `CLAN_APPROVED`: By Mod.
    -   `CLAN_REJECTED`: Reason provided.
    -   `CLAN_DISBANDED`: By Mod or System (inactive).
2.  **Membership**:
    -   `MEMBER_JOIN`: User joined Clan.
    -   `MEMBER_LEAVE`: User left Clan (Cooldown started).
    -   `MEMBER_KICK`: User kicked by Captain (Cooldown started).
    -   `LOAN_START`: Member loaned from Clan A to Clan B.
    -   `LOAN_END`: Member returned (Cooldown started).
    -   `TRANSFER_REQUEST`: Member requested transfer.
    -   `TRANSFER_COMPLETED`: Transfer finalized (3d sickness started).
    -   `TRANSFER_REJECTED`: Request denied/cancelled.
3.  **Match & Elo**:
    -   `MATCH_CREATED`: Clan A vs Clan B.
    -   `MATCH_RESULT`: Winner/Loser, Elo change.
    -   `ELO_MANUAL_UPDATE`: Mod changed Elo.
4.  **Moderation**:
    -   `CASE_OPENED`: Report filed.
    -   `CASE_RESOLVED`: Verdict details.
    -   `CASE_ACTION`: Mod action performed on case.
    -   `CASE_CLOSED`: Case closed.
    -   `APPEAL_CREATED`: Appeal filed.
    -   `SYSTEM_BAN`: User/clan banned from system.
    -   `SYSTEM_UNBAN`: User/clan unbanned.
    -   `CLAN_FROZEN`: Clan frozen (no Elo applied).
    -   `CLAN_UNFROZEN`: Clan unfrozen.

## 4. Error Messages

| Error Code | Message |
| :--- | :--- |
| `ERR_ALREADY_IN_CLAN` | "You are already in a clan." |
| `ERR_COOLDOWN_ACTIVE` | "You are in cooldown. Days remaining: {days}." |
| `ERR_NAME_TAKEN` | "Clan name '{name}' is already taken." |
| `ERR_NAME_INVALID` | "Clan name contains invalid characters or forbidden words." |
| `ERR_NOT_VERIFIED` | "You must have the '{role}' role to participate." |
| `ERR_CLAN_FULL` | "Clan has reached maximum capacity." (If applicable, though not specified in rulebook, usually implied). |
| `ERR_LOAN_LIMIT` | "Clan already has an active loan." |
| `ERR_MATCH_LIMIT` | "Match limit reached (2 matches vs this clan in 24h)." |
| `ERR_INSUFFICIENT_MEMBERS` | "Clan must have at least 5 members to perform this action." |
| `ERR_PERMISSION_DENIED` | "You do not have permission to execute this command." |
| `ERR_TRANSFER_COOLDOWN` | "You can only transfer once every {days} days." |
| `ERR_TRANSFER_SICKNESS` | "You have Transfer Sickness. Cannot play matches for {hours}h." |
| `ERR_NO_RIOT_ID` | "You must register your Valorant Riot ID with `/register` before joining a clan." |
| `ERR_RIOT_ID_TAKEN` | "This Riot ID is already registered by another user." |
