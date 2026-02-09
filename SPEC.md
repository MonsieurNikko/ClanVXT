# Clan System Specification

## 1. Commands

### User Commands
| Command | Description | Requirements |
| :--- | :--- | :--- |
| `/clan create` | Mở modal để tạo clan mới. Nhập tên clan và chọn 4 thành viên (bạn + 4 = 5 tổng). | User is Verified, not in clan, not in cooldown. Name unique. |
| `/clan help` | Hiển thị hướng dẫn lệnh theo role của bạn. | None. |
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
- Sau khi tạo, tin nhắn hiển thị: `[Tên Clan A Thắng]` `[Tên Clan B Thắng]` `[Hủy]`
- **Report**: Chỉ người tạo trận mới có thể báo cáo kết quả hoặc hủy.
- **Hủy**: Chỉ được phép trước khi kết quả được báo cáo.
- **Cooldown**: Có thời gian chờ 5 phút giữa các lần tạo trận tương tự để tránh spam.
- Sau khi report, tin nhắn hiển thị: `[Xác Nhận]` `[Tranh Chấp]`
- **Xác Nhận/Tranh Chấp**: Bất kỳ thành viên nào của clan đối phương đều có thể click (chỉ cần 1 người).
- **Tranh Chấp**: Nếu có tranh chấp, Mod sẽ nhận được thông báo DM.

### Captain/Vice Commands
| Command | Description | Permission |
| :--- | :--- | :--- |
| `/clan invite <user>` | Mời người vào clan (đã active). Gửi DM với nút Accept/Decline. | Captain/Vice. |
| `/loan request ...` | (See User Commands) | Captain/Vice. |
| `/transfer request ...` | (See User Commands) | Captain/Vice. |

### Captain Only Commands
| Command | Description | Permission |
| :--- | :--- | :--- |
| `/clan kick <user>` | Kick a member. | Captain only. Target gets 14-day cooldown. |
| `/clan promote_vice <user>` | Promote member to Vice Captain. | Captain only. |
| `/clan demote_vice <user>` | Demote Vice Captain to Member. | Captain only. |
| `/clan disband` | Giải tán clan (yêu cầu xác nhận). | Captain only. |

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
| `/matchadmin match resolve <match_id> <winner_clan> <reason>` | Resolve a disputed match. | Mod Role. |
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

### Arena Dashboard
Kênh `#arena` chứa Dashboard với các nút bấm tương tác. User bấm nút → Bot gửi thông tin (ephemeral).

| Button | Mô tả |
| :--- | :--- |
| 🏰 Danh sách Clan | Xem top 15 clan active với Elo và số thành viên. |
| 🏆 Bảng xếp hạng | Top 10 clan theo Elo với huy chương. |
| ⚔️ Lịch sử Match | 10 trận đấu gần đây với status. |
| 👤 Thông tin của tôi | Xem thông tin cá nhân: Riot ID, clan, role, cooldown, ban status. |

**Admin Command:** `/arena_refresh` — Làm mới dashboard (xóa và gửi lại).

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
- **Vice Captain**: Appointed by Captain. Can invite, match, loan, transfer. Cannot kick.
- **Member**: Standard member.

## 3. Logging Rules

All events must be logged to the **Mod Log Channel** (`log`).

### Log Format
`[TIMESTAMP] [EVENT_TYPE] Details...`

### Events to Log
1.  **Clan Lifecycle**:
    -   `CLAN_CREATE_REQUEST`: Captain + 4 members (tổng 5).
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

| Mã Lỗi | Thông báo |
| :--- | :--- |
| `ALREADY_IN_CLAN` | "Bạn đã ở trong một clan rồi." |
| `COOLDOWN_ACTIVE` | "Bạn đang trong thời gian chờ. Còn lại: {days} ngày." |
| `NAME_TAKEN` | "Tên clan '{name}' đã được sử dụng." |
| `NAME_INVALID` | "Tên clan chứa ký tự không hợp lệ hoặc từ cấm." |
| `NOT_VERIFIED` | "Bạn cần role '{role}' để tham gia hệ thống clan." |
| `PERMISSION_DENIED` | "Bạn không có quyền thực hiện lệnh này." |
| `NOT_IN_CLAN` | "Bạn không ở trong clan nào." |
| `NOT_CAPTAIN` | "Chỉ Captain của clan mới có thể thực hiện lệnh này." |
| `TARGET_NOT_IN_CLAN` | "Người dùng này không thuộc clan của bạn." |
| `CANNOT_KICK_SELF` | "Bạn không thể tự kick chính mình. Hãy dùng `/clan leave`." |
| `CANNOT_KICK_CAPTAIN` | "Bạn không thể kick Captain của clan." |
| `NO_PENDING_REQUEST` | "Bạn không có yêu cầu ứng tuyển nào đang chờ." |
| `CLAN_NOT_FOUND` | "Không tìm thấy clan." |
| `NOT_MOD` | "Bạn cần role '{role}' để sử dụng lệnh này." |
| `BOT_MISSING_PERMS` | "Bot thiếu quyền: {perms}. Vui lòng cấp quyền Manage Roles và Manage Channels." |
| `ROLE_HIERARCHY` | "Không thể tạo role - Role của bot phải nằm trên role clan trong danh sách Role." |
| `NO_RIOT_ID` | "Bạn phải đăng ký Riot ID bằng `/register` trước khi gia nhập clan." |
| `RIOT_ID_TAKEN` | "Riot ID này đã được đăng ký bởi người dùng khác." |
