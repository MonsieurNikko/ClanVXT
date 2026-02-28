# 📜 ClanVXT Changelog

This document provides a cumulative history of all technical improvements, fixes, and feature updates for the ClanVXT system.


## [1.7.4] - 2026-02-28
### 🔧 Fix & Improvement: Rank Declaration

>**Author: Nikko**

#### 📢 Discord Update
> - **Sửa lỗi Khai Rank trùng lặp**: Khắc phục lỗi hệ thống ghi nhận rank 2 lần mỗi lần chọn.
> - **Thêm lựa chọn "Không chơi Valorant"**: Thành viên không chơi Valorant có thể chọn option này thay vì bắt buộc khai rank. Lựa chọn này **không tính vào rank trung bình** của clan.

#### 🔧 Technical Details
- **Bug Fix**: `cogs/clan.py` — Removed `select.callback` from `RankDeclarationView` to prevent double-firing (both View callback and `on_interaction` persistent handler were processing the same interaction, causing duplicate logs and DB writes).
- **Feature**: Added "Không chơi Valorant" option (score=0) to `RANK_OPTIONS` in `cogs/clan.py` and `RANK_SCORE_TO_NAME` in `services/elo.py`.
- **DB Query**: `services/db.py` — `get_clan_avg_rank` updated to `AND valorant_rank_score > 0`, excluding non-players from avg rank calculation.
- **Files**: `cogs/clan.py`, `services/elo.py`, `services/db.py`

## [1.7.3] - 2026-02-28
### 🚑 Hotfix: Rank Declaration Persistent Handler

>**Author: Nikko**

#### 📢 Discord Update
> - **Khai Rank không hết hạn**: Thành viên giờ có thể khai Rank bất cứ lúc nào, không còn bị giới hạn 5 phút.
> - **Khai Rank sau Restart**: Tin nhắn khai rank gửi trước khi bot restart giờ vẫn hoạt động bình thường.

#### 🔧 Technical Details
- `cogs/clan.py` — `RankDeclarationView`: Changed `timeout=300` → `timeout=None` to prevent select menu expiry.
- `cogs/clan.py` — `on_interaction`: Replaced the stub `return` for `rank_declare:` custom_id with a full persistent handler that parses `user_id`/`clan_id` from custom_id, responds immediately, then saves to DB. This ensures rank selection works even after bot restarts.
- `cogs/clan.py` — Log format: Changed `RANK_DECLARED` logs to use `interaction.user.mention` and display name instead of raw DB IDs per `AGENT_RULES.md`.
- **Files**: `cogs/clan.py`

## [1.7.2] - 2026-02-27
### ✨ Cải thiện UX: Rank & Thông báo

>**Author: Nikko**

#### 📢 Discord Update
> - **Xem Rank trong Team**: Khi bấm xem thông tin Clan tại Arena, danh sách thành viên giờ hiển thị Rank Valorant của từng người. Thành viên chưa khai hiển thị `❓ Chưa khai`.
> - **Sửa lỗi Khai Rank**: Khắc phục lỗi "This interaction failed" khi thành viên chọn rank trong DM.
>
> **📜 Cải thiện lệnh:**
> - `/admin balance set_rank` — Admin giờ chọn rank từ dropdown đầy đủ thay vì nhập số thủ công.
> - `/admin announce` — Đổi sang popup form (Modal) để hỗ trợ paste nội dung nhiều dòng với xuống dòng đúng chuẩn.

#### 🔧 Technical Details
- **Critical Bug Fix (Hotfix 2)**: `cogs/clan.py` — Root cause of "This interaction failed": `db.update_member_rank` was called BEFORE `interaction.response`, so any delay or error prevented Discord from receiving a timely response. Rewrote `rank_selected` to **respond to the interaction immediately first**, then save to DB afterward. Also removed `ephemeral=True` from the DM fallback path (not valid in DM context).
- **UX Upgrade**: `cogs/admin.py` — `/admin balance set_rank` replaced numeric input with a dynamic `discord.ui.Select` (25 rank options) generated from `RANK_OPTIONS` in `cogs/clan.py`.
- **UX Upgrade**: `cogs/admin.py` — `/admin announce` replaced slash command text params with `AnnounceModal` (Discord UI Modal with paragraph TextInput), preserving newlines correctly. Auto-splits messages at 1900-char boundary.
- **UI Enhancement**: `cogs/arena.py` — `ClanDetailSelectView.on_select()` now includes `valorant_rank` for each member. `get_clan_members` already returns `valorant_rank` via `SELECT cm.*`.
- **Files**: `cogs/clan.py`, `cogs/admin.py`, `cogs/arena.py`

## [1.7.1] - 2026-02-27
### 🚑 Hotfix: Weekly Balance Task Errors

>**Author: Nikko**

#### 📢 Discord Update
> - **Chi tiết Tính điểm Elo**: Giờ đây, khi các Clan báo cáo kết quả trận đấu, bảng tổng kết sẽ hiển thị rõ ràng các chỉ số hệ số nhân (Modifiers) đã được áp dụng như: Win Rate, Chênh lệch Rank, và thưởng Underdog Bonus.
> - **Sửa lỗi Trả thưởng Tuần**: Khắc phục lỗi hệ thống không thể chạy tác vụ trừ Elo và cộng điểm hoạt động định kỳ hàng tuần.
> 
> **📜 Lệnh mới:**
> - `/admin balance activity_info` — Xem danh sách các Clan đang đủ (hoặc không đủ) điều kiện nhận thưởng Bonus hoạt động tuần.

#### 🔧 Technical Details
- **UI Enhancements**:
  - `cogs/matches.py`: Modified `handle_match_confirm` and `admin_match_resolve` to use `elo.format_elo_explanation_vn()` for the public embed description. This reveals the exact breakdown of Elo modifiers (Win Rate, Rank Mod, Underdog Bonus) to the users instead of only writing them to the log.
- **Admin Commands**:
  - `cogs/admin.py`: Added `/admin balance activity_info` command to display a detailed breakdown of clans eligible for the weekly activity bonus, including their current match count and Elo threshold status.
- **Hotfixes**:
  - Resolved `NameError: name 'config' is not defined` in `services/db.py` by adding the missing `import config` required by `get_clans_for_decay`.
  - Resolved `AttributeError: module 'config' has no attribute 'ACTIVITY_BONUS_ELO'` in `main.py` by correcting the variable name to `ACTIVITY_BONUS_AMOUNT`.
  - Added correct boundary check in `main.py` so that only clans with Elo `< ACTIVITY_BONUS_ELO_THRESHOLD` receive the weekly activity bonus.
- **Files**: `services/db.py`, `main.py`, `cogs/admin.py`, `cogs/matches.py`

## [1.7.0] - 2026-02-27
### ⚖️ Feat: Balance System (9 Features)

>**Author: Nikko**

#### 📢 Discord Update
> - **Hệ thống Cân Bằng mới**: 9 tính năng giúp cuộc đua Elo công bằng hơn giữa các clan.
> - **Khai báo Rank**: Mọi thành viên phải khai Rank Valorant khi vào clan. Clan chưa khai đủ sẽ không được thi đấu.
> - **Giới hạn tuyển quân**: Mỗi clan chỉ được tuyển tối đa số thành viên nhất định mỗi tuần.
> - **Giới hạn Rank cao**: Mỗi clan chỉ có tối đa thành viên Immortal 2+ (tránh stacking).
> - **Elo thông minh hơn**: Các modifier tự động giúp phân bổ điểm công bằng dựa trên sức mạnh thực tế.
> - **Elo Decay**: Clan không hoạt động lâu sẽ bị giảm Elo tự động.
> - **Thưởng hoạt động**: Clan thi đấu đều đặn sẽ nhận bonus Elo.
> - **Bảng xếp hạng**: Hiển thị thêm Avg Rank bên cạnh Elo của mỗi clan.
> - **Luật lệ cập nhật**: Mục Luật Lệ Arena được bổ sung phần Balance System.

#### 🔧 Technical Details
- **Phase 1 — Foundation**:
  - `config.py`: 15+ balance constants (caps, decay, thresholds, modifiers).
  - `services/db.py`: Auto-migration for 6 new columns (`valorant_rank`, `valorant_rank_score`, `roster_a/b`, `avg_rank_a/b`).
  - `services/db.py`: 14 new balance functions (rank CRUD, recruiting cap, decay, activity, win rate, feature toggle, roster).
  - `services/elo.py`: 3 modifier functions (`get_win_rate_modifier`, `get_underdog_bonus`, `get_rank_modifier`) integrated into `apply_match_result()` with feature toggle checks and Elo gain cap.
- **Phase 2 — Rank Declaration + Enforcement**:
  - `cogs/clan.py`: `RankDeclarationView` (25-rank Select Menu), integrated into invite accept flow, recruitment cap checks, `/clan update_rank` command.
  - `cogs/arena.py`: Rank enforcement in `ChallengeSelectView.confirm()` and `ChallengeAcceptView._accept()`.
  - `cogs/transfers.py`: Rank cap check in `complete_transfer()` and `transfer_request()`.
- **Phase 3 — Roster System**:
  - `cogs/challenge.py`: Auto-save clan roster + avg rank in `_continue_to_match_flow()` after ban/pick.
- **Phase 4 — Admin + Weekly + UI**:
  - `main.py`: `weekly_balance_task` (24h loop, 7-day gate via `system_settings`).
  - `cogs/admin.py`: 6 admin balance commands (`/admin balance toggle/status/set_rank/clan_rank/adjust_elo/run_weekly`).
  - `cogs/admin.py`: `/admin announce` command to post updates to #chat-arena with @player mention.
  - `cogs/arena.py`: Leaderboard shows avg rank, Rules embed has Balance section.
  - `cogs/clan.py`: Help embed updated with balance commands + Elo info.
- **Files**: `config.py`, `services/db.py`, `services/elo.py`, `cogs/clan.py`, `cogs/arena.py`, `cogs/transfers.py`, `cogs/challenge.py`, `main.py`, `cogs/admin.py`

## [1.6.1] - 2026-02-20
### 🐛 Fix: Challenge Flow Bị Bỏ Qua (Ban/Pick + Channels Không Hoạt Động)

>**Author: ImDaMinh**

#### 📢 Discord Update
> - **Sửa lỗi Thách Đấu**: Khắc phục lỗi khi chấp nhận thách đấu, bot bỏ qua bước Ban/Pick Map và tạo kênh Voice/Text — nhảy thẳng tới tạo match. Lỗi interaction trong ban/pick bị xử lý 2 lần.

#### 🔧 Technical Details
- **Root Cause**: `ChallengeSelectView.confirm()` trong `arena.py` dùng class cũ `AcceptDeclineView` (gọi thẳng `matches_cog.create_match_v2()`) thay vì `ChallengeAcceptView` (gọi `start_challenge_flow()` để tạo channels + ban/pick map).
- **Fix 1**: Thay `AcceptDeclineView` bằng `ChallengeAcceptView` trong `ChallengeSelectView.confirm()`.
- **Fix 2**: Thêm `asyncio.sleep(0.5)` trong `ChallengeCog.on_interaction` để tránh double-acknowledge lỗi 40060.
- **Cleanup**: Xóa class `AcceptDeclineView` cũ (99 dòng dead code).
- **Files**: `cogs/arena.py`, `cogs/challenge.py`

## [1.6.0] - 2026-02-20
### 🚑 Hotfix: Backfill OperationalError (Map column)

#### 📢 Discord Update
> - **Sửa lỗi Backfill**: Khắc phục lỗi không thể tạo trận thủ công do xung đột cột dữ liệu Map.

#### 🔧 Technical Details
- **Fix**: Removed `map` column from manual match creation in `services/db.py` and `cogs/admin.py` as it doesn't exist in the current schema.
- **Files**: `cogs/admin.py`, `services/db.py`

## [1.5.9] - 2026-02-20
### 🚑 Hotfix: AdminCog NameError

#### 📢 Discord Update
> - **Sửa lỗi khởi động**: Khắc phục lỗi `NameError` khiến bot không thể khởi động sau cập nhật tính năng Autocomplete.

#### 🔧 Technical Details
- **Fix**: Added missing `List` import in `cogs/admin.py`.
- **Files**: `cogs/admin.py`

## [1.5.8] - 2026-02-20
### ⚡ Feat: Clan Autocomplete

#### 📢 Discord Update
> - **Tiện ích Admin**: Lệnh `/admin matchmaking create_result` giờ hỗ trợ gợi ý tên clan (Autocomplete).
> - **Dễ dàng sử dụng**: Không cần nhớ chính xác tên clan, chỉ cần gõ vài ký tự đầu để chọn từ danh sách.

#### 🔧 Technical Details
- **Autocomplete**: Added `clan_name_autocomplete` to `AdminCog`.
- **DB Helper**: Added `search_clans(query)` using `LIKE %query%`.
- **Files**: `cogs/admin.py`, `services/db.py`

## [1.5.7] - 2026-02-19
### 🛠️ Feat: Admin Match Backfill

#### 📢 Discord Update
> - **Tạo trận thủ công**: Admin có thể tạo và nhập kết quả trận đấu ngay lập tức bằng lệnh `/admin matchmaking create_result`.
> - **Công dụng**: Dùng để nhập lại kết quả các trận đấu diễn ra trong lúc bot bảo trì hoặc bị lỗi, đảm bảo Elo được tính toán chính xác.

#### 🔧 Technical Details
- **New Command**: `/admin matchmaking create_result` in `AdminCog`.
- **DB Helper**: Added `create_finished_match()` in `services/db.py` to insert fully resolved matches.
- **Logic**: Creates match -> Sets status 'resolved' -> Calculates & Applies Elo immediately.
- **Files**: `cogs/admin.py`, `services/db.py`

## [1.5.6] - 2026-02-19
### 📋 Feat: Admin Loan Status

#### 📢 Discord Update
> - **Quản lý Loan**: Admin/Mod có thể xem danh sách tất cả các thành viên đang được loan bằng lệnh `/admin loan status`.
> - **Chi tiết**: Hiển thị rõ ràng thành viên, clan cho mượn/mượn, thời gian bắt đầu/kết thúc và thời gian còn lại.

#### 🔧 Technical Details
- **New Command**: `/admin loan status` in `AdminCog`.
- **DB Helper**: Added `get_all_active_loans()` in `services/db.py` to fetch system-wide active loans with clan names.
- **Files**: `cogs/admin.py`, `services/db.py`

## [1.5.5] - 2026-02-19
### 🧹 Maintenance: Codebase Integrity & Dead Code Removal

#### 📢 Discord Update
> - **Bảo trì hệ thống**: Rà soát toàn bộ mã nguồn để đảm bảo tính ổn định tối đa.
> - **Tối ưu hóa**: Loại bỏ các đoạn mã thừa (dead code) trong hệ thống Match, giúp bot chạy nhẹ và ít lỗi tiềm ẩn hơn.

#### 🔧 Technical Details
- **Cleanup**: Removed dead method `handle_match_report` in `MatchesCog` (`cogs/matches.py`).
- **Context**: This method was referencing a non-existent `db.report_match_v2` function. The actual active flow uses `ReportScoreButton` -> `MatchScoreModal` -> `db.report_match_v3`.
- **Integrity Check**: Verified cross-cog dependencies for `matches.py`, `challenge.py`, `arena.py`, and `db.py`.
- **Files**: `cogs/matches.py`

## [1.5.4] - 2026-02-19
### 🚑 Hotfix: Arena Challenge Acceptance

#### 📢 Discord Update
> - **Sửa lỗi nghiêm trọng**: Khắc phục lỗi không thể chấp nhận thách đấu trong Arena (lỗi `AttributeError`).
> - **Ổn định hệ thống**: Đảm bảo quy trình tạo match từ Arena hoạt động trơn tru.

#### 🔧 Technical Details
- **Fix**: Implemented missing `create_match_v2` method in `MatchesCog` to support Arena-initiated matches.
- **Files**: `cogs/matches.py`

## [1.5.3] - 2026-02-19
### 🛡️ Fix: Transfer System Safeguards & Notifications

#### 📢 Discord Update
> - **Chuyển nhượng an toàn**: Hệ thống Transfer được bổ sung các lớp bảo vệ quan trọng.
> - **Ngăn chặn lỗi**: Không cho phép chuyển nhượng Captain (tránh lỗi clan mất chủ) và đảm bảo clan nguồn luôn giữ đủ số lượng thành viên tối thiểu.
> - **Thông báo minh bạch**: Gửi tin nhắn riêng (DM) cho tất cả các bên liên quan (Thành viên, Captain cũ, Captain mới) để xác nhận giao dịch.

#### 🔧 Technical Details
- **Guard Clauses**: Added checks in `transfer_request`:
    - `captain` role cannot participate in transfer.
    - Source clan must have `> MIN_MEMBERS_ACTIVE` members.
- **Notifications**: Implemented DM notifications to Member, Source Captain, and Dest Captain upon request and completion.
- **Files**: `cogs/transfers.py`

## [1.5.2] - 2026-02-19
### 🔧 Bugfix: Stability & DB Cleanup

#### 📢 Discord Update
> - **Sửa lỗi hệ thống**: Khắc phục triệt để lỗi crash bot khi chấp nhận thách đấu trong Arena. Hệ thống vận hành ổn định trở lại.

#### 🔧 Technical Details
- **Fix**: Re-implemented missing `get_clan_member` function in `services/db.py`.
- **Cleanup**: Removed duplicate `count_clan_members` function and redundant sections in `services/db.py` to prevent logic conflicts.
- **Files**: `services/db.py`, `cogs/arena.py`

## [1.5.1] - 2026-02-19
### 🐛 Hotfix: Database Auto-Migration

#### 📢 Discord Update
> - **Sửa lỗi hệ thống**: Cập nhật cơ chế tự động sửa lỗi cơ sở dữ liệu khi khởi động bot. Đảm bảo tính năng Try-Out hoạt động ổn định cho tất cả các clan.

#### 🔧 Technical Details
- **Fix**: Added auto-migration logic in `services/db.py` to ensure `clan_members` (columns `join_type`, `tryout_expires_at`) and `invite_requests` (column `invite_type`) are correctly updated on startup.
- **Files**: `services/db.py`

## [1.5.0] - 2026-02-19
### 🛡️ Feat: Try-Out System & Public Announcements

#### 📢 Discord Update
> - **Chế độ Thử việc (Try-Out)**: Captain có thể mời thành viên mới vào clan dưới dạng recruit (lính mới) với thời hạn 24 giờ.
> - **Quyền lợi & Nghĩa vụ**: Recruit có thể tham gia thi đấu ngay lập tức. Nếu không được thăng chức (Promote) sau 24h, sẽ tự động bị kick.
> - **Không Cooldown**: Nếu recruit bị kick hoặc tự rời trong thời gian thử việc, hoàn toàn **không bị cooldown** gia nhập clan khác.
> - **Thông báo Công khai**: Các sự kiện quan trọng (Gia nhập, Rời clan, Kick, Thăng chức, Kết quả trận đấu) sẽ được thông báo tự động tại kênh `#chat-arena`.
>
> **📜 Cách dùng lệnh mới (Dành cho Captain/Vice):**
> - `/clan recruit <@user>`: Mời thành viên thử việc (Try-out 24h).
> - `/clan promote <@user>`: Thăng chức Recruit lên Member chính thức.
> - `/clan fire <@user>`: Chấm dứt thử việc ngay lập tức (Kick Recruit).

#### 🔧 Technical Details
- **Schema Update**: Added `join_type` ('full'/'tryout') and `tryout_expires_at` to `clan_members`. Added `invite_type` to `invite_requests`.
- **New Commands**:
    - `/clan recruit <user>`: Invite user as Try-out (24h).
    - `/clan promote <user>`: Upgrade Recruit to Member.
    - `/clan fire <user>`: Kick Recruit immediately (bypass cooldown).
- **Background Task**: `check_tryouts_loop` (10 min interval) auto-kicks expired recruits.
- **Cooldown Logic**: Updated `services/cooldowns.py` to allow re-joining *other* clans immediately if `join_type` was 'tryout'. Enforced 3-day cooldown for full members.
- **Announcements**: Implemented `announce_public` service to post embeds to `#chat-arena`. Integrated into all member management flows.
- **Files**: `cogs/clan.py`, `services/db.py`, `services/bot_utils.py`, `services/cooldowns.py`, `db/schema.sql`



## [1.4.5] - 2026-02-19
### ⏳ Config: Giảm Cooldown Rời Clan (14 -> 3 ngày)

#### 📢 Discord Update
> - **Giảm thời gian chờ**: Thời gian cooldown khi rời clan (hoặc bị kick) đã được giảm từ **14 ngày** xuống còn **03 ngày** để tăng tính linh hoạt cho việc chuyển nhượng.

#### 🔧 Technical Details
- **Config Update**: `COOLDOWN_DAYS = 3` (was 14) in `config.py`.
- **Note**: Applies to new cooldowns only. Existing cooldowns remain unchanged unless manually cleared by Admin.

## [1.4.4] - 2026-02-19
### 🐛 Fix: Duplicate Invite Status Error & Safety Update

#### 📢 Discord Update
> - **Sửa lỗi kỹ thuật**: Khắc phục lỗi hệ thống khi người dùng chấp nhận/từ chối lời mời vào clan (do dữ liệu cũ bị trùng lặp).

#### 🔧 Technical Details
- **Database Fix**: Updated `accept_invite`, `decline_invite`, and `create_invite_request` in `services/db.py`.
- **Logic**: Implemented auto-renaming of old `accepted`/`declined`/`cancelled` statuses to prevent `UNIQUE constraint failed` errors when a user re-joins a clan.
- **Safety**: Wrapped DB operations in explicit `BEGIN...COMMIT/ROLLBACK` transactions for atomicity.
- **Files**: `services/db.py`

## [1.4.3] - 2026-02-18
### ✨ Feat: Auto Player Role System

#### 📢 Discord Update
> - **Tự động gán Role 'player'**: Tất cả thành viên clan giờ đây sẽ tự động nhận role `player` khi gia nhập clan hoặc khi clan được phê duyệt.
> - **Tự động thu hồi**: Khi một người rời clan, bị kick, hoặc clan bị giải tán/xóa, role `player` sẽ được thu hồi tự động để đảm bảo danh sách member server chính xác.
> - **Đồng bộ hóa Admin**: Admin có lệnh mới `/admin clan sync_player_role` để gán role cho tất cả thành viên hiện tại chỉ với 1 click.
> - **Sửa lỗi Arena**: Khắc phục lỗi khi bấm "Thách Đấu" hiện thông báo lỗi thay vì thời gian chờ (cooldown).

#### 🔧 Technical Details
- **Configuration**: Added `ROLE_PLAYER` check in `config.py`.
- **New Admin Command**: `/admin clan sync_player_role` — scans all active/inactive/frozen clans and syncs the player role.
- **Logic Integration**:
    - `ClanCog.handle_invite_accept` & `AdminCog.admin_set_member_clan`: Assigns player role on join.
    - `ClanCog.mod_clan_approve`: Assigns player role to all 5 starter members.
    - `ClanCog.clan_leave` & `ClanCog.mod_clan_kick`: Removes player role on exit.
    - `ClanCog.clan_disband` & `ClanCog.mod_clan_delete`: Bulk removes player role from all members.
- **Fix**: Updated `get_won_matches_by_clan` with `COALESCE` for robust legacy match history searching.
- **Fix**: Resolved `NameError` in `cogs/arena.py` by adding missing `datetime`/`timezone` imports and removing redundant local imports.
- **Cleanup**: Fixed typo `TRANSFER_SICKNESS` in `services/cooldowns.py`.
- **Files**: `config.py`, `cogs/admin.py`, `cogs/clan.py`, `services/db.py`, `services/cooldowns.py`, `cogs/arena.py`

## [1.4.2] - 2026-02-18
### 🔒 Feat: Global Matchmaking Lock

#### 📢 Discord Update
> - **Bảo trì hệ thống**: Admin hiện có thể **tạm khóa** tính năng Thách đấu (War Clan) khi cần bảo trì hoặc tổ chức giải đấu.
> - **Trải nghiệm**: Khi hệ thống bị khóa, nút "Gửi Thách Đấu" sẽ bị vô hiệu hóa kèm lý do cụ thể. Các trận đấu đang diễn ra không bị ảnh hưởng.

#### 🔧 Technical Details
- **New Table**: `system_settings` (key-value storage for global configs).
- **Commands**:
    - `/admin matchmaking lock [reason]`
    - `/admin matchmaking unlock`
- **UI Enforce**: `ChallengeSelectView` checks `is_matchmaking_locked()` before processing.
- **Cleanup**: Removed duplicate/dead code in `cogs/arena.py`.
- **Files**: `services/db.py`, `cogs/admin.py`, `cogs/arena.py`, `db/schema.sql`

### 🚫 Feat: Soft Ban (Cấm thi đấu có thời hạn)

#### 📢 Discord Update
> - **Cấm thi đấu (Soft Ban)**: Admin giờ có thể cấm một clan thi đấu trong một khoảng thời gian nhất định (ví dụ: 3 ngày, 1 tuần) mà không cần ban vĩnh viễn hay đóng băng toàn bộ clan.
> - **Cơ chế**: Clan bị cấm sẽ **không thể gửi lời thách đấu** và cũng **không thể chấp nhận** lời thách đấu từ người khác.

#### 🔧 Technical Details
- **Command Update**: `/admin cooldown set` now supports `kind="match_create"`.
- **Fix**: Updated `/admin cooldown view` to display `match_create` cooldowns.
- **Fix**: Updated `get_won_matches_by_clan` logic to support legacy matches (pre-v1.3.2) where `winner_clan_id` is NULL.
- **Logic Update**: `ChallengeAcceptView` now checks for `match_create` cooldown (preventing banned clans from accepting matches).
- **Consistency**: Added `is_matchmaking_locked()` check to `ChallengeAcceptView` as well.
- **Files**: `cogs/admin.py`, `cogs/arena.py`, `services/cooldowns.py`

## [1.4.1] - 2026-02-18
### ⚖️ Feat: Elo Refund System (Fair Play)

#### 📢 Discord Update
> - **Fair Play Update**: Hệ thống đã bổ sung tính năng **Hoàn trả Elo** (Elo Rollback).
> - **Công bằng cho mọi người**: Nếu phát hiện Clan gian lận hoặc vi phạm nghiêm trọng, Admin có thể hủy kết quả các trận thắng của họ.
> - **Quyền lợi nạn nhân**: Các Clan thua cuộc trong các trận đấu này sẽ được **hoàn lại toàn bộ số điểm Elo đã mất**. Hệ thống sẽ gửi thông báo đính chính đến kênh riêng của Clan.

#### 🔧 Technical Details
- **New Admin Command**: `/admin elo_rollback_matches <clan_name>` — Interactive UI to select and rollback specific wins.
- **Rollback Logic**: Reverts Elo changes for both sides (Winner loses gains, Loser regains losses).
- **Notifications**: Auto-sends Embed to victim's channel upon rollback.
- **Files**: `cogs/admin.py`, `services/db.py`

## [1.4.0] - 2026-02-17
### 🎥 Feat: Highlight System & Community Voting

#### 📢 Discord Update
> - **Gửi Highlight (`/highlight submit`)**: Bạn có thể gửi link clip (YouTube, Outplayed...) của các trận đấu gần nhất để khoe với cộng đồng.
> - **Community Vote**: Các highlight sẽ được đăng lên kênh `🏆┃2-𝙡𝙖𝙞-𝙠𝙝ô𝙣𝙜-𝙖𝙞-𝙡𝙖𝙞` để mọi người bình chọn (thả tim 🔥).
> - **Share chuyên nghiệp**: Có nút `📤 Share` để bạn copy bài viết (kèm link mời server) đi khoe ở các nơi khác.
> - **Giải thưởng tuần**: Clip được yêu thích nhất tuần (dựa trên lượng vote hợp lệ) sẽ mang về **+7 Elo** cho Clan và danh hiệu **Highlight God** cho khổ chủ.

#### 🔧 Technical Details
- **New Table**: `highlights` (linked to `users`, `matches`, `clans`).
- **New Cog**: `cogs/highlights.py` handles submission flow and weekly cron job.
- **Anti-Farm Logic**: Voting system automatically excludes reactions from members of the *same* clan to ensure fairness.
- **Validation**:
    - Users can only submit clips for matches their clan actually played.
    - Match Selector dropdown shows context (Opponent, Map, Result).
- **Config**: Added `CHANNEL_HIGHLIGHTS` and `SERVER_INVITE_URL`.
- **Files**: `cogs/highlights.py`, `services/db.py`, `config.py`, `db/schema.sql`, `main.py`


## [1.3.15] - 2026-02-17
### 🔧 Update: Agent Rules & Changelog Policy
#### 📢 Discord Update
> - Cập nhật quy trình ghi chép lịch sử phiên bản để phân tách rõ ràng thông tin cho Người chơi và Kỹ thuật.

#### 🔧 Technical Details
- **Agent Rules**: Cập nhật `AGENT_RULES.md` yêu cầu tuyệt đối không để các thông tin về Admin, Mod, Dev, code, log trong phần **Discord Update**.
- **Changelog Refactor**: Rà soát và di chuyển các thông tin lệnh Admin/Mod từ phiên bản 1.3.13 và 1.3.14 xuống phần Technical Details.

## [1.3.14] - 2026-02-17
### 🔧 Feat: Auto User Cleanup + Sync updates

#### 📢 Discord Update
> - **Tự động dọn dẹp User**: Khi một thành viên rời khỏi Discord server, hệ thống sẽ tự động xóa thông tin của họ (hoặc ẩn danh nếu có lịch sử đấu) để giữ database sạch sẽ.
> - **Kế thừa Clan**: Nếu Captain rời server, Vice-Captain sẽ được tự động đôn lên làm Captain. Nếu không có Vice, clan sẽ chuyển sang trạng thái `inactive` để chờ Mod can thiệp.

#### 🔧 Technical Details
- **Sync/Migration**: Pulled 66 commits. Applied DB migrations for `winner_clan_id`, `score_a`, and `score_b` (match scores).
- **New DB function**: `cleanup_user_on_leave(discord_id)` — handles the multi-step cleanup/anonymization process.
- **Event listener**: Added `on_member_remove` in `main.py` to trigger the cleanup flow.
- **Logic**:
    - Users with match history are "anonymized" (banned + `LEAVER_ID`) instead of deleted to maintain FK integrity.
    - Automatic captain promotion logic (Earliest joined Vice -> Captain).
    - Cleanup for `lfg_posts`, `create_requests`, `invite_requests`, `loans`, and `transfers`.
- Files: `main.py`, `services/db.py`, `migrate_db.py`, `scripts/migration_v5_scores.py`


## [1.3.13] - 2026-02-16
### 🔧 Feat: Admin Match Resolve + Channel Cleanup Fix

#### 📢 Discord Update
> - **Fix bug**: Kênh match không tự xóa sau 5 phút khi cancel.
> - **Donation System**: Đã có thể ủng hộ team phát triển qua nút Donate trong Arena! (Xem thông tin qua `/arena` -> Donate).

#### 🔧 Technical Details
- **Admin Match Resolve**: Thêm lệnh `/admin match_resolve` — Tạo trận đấu thủ công và tự tính Elo.
- **New DB function**: `create_admin_match()` — creates match directly in `resolved` status.
- **New admin command**: `match_resolve` — validates clans, score, winner, applies Elo.
- **New feature**: Donation System — added `/arena` Donate button with configurable info (PayPal/Bank).
- **Map Pool Update**: Added full competitive map list (12 maps) to support Ban/Pick logic (8 bans). Added: Breeze, Fracture, Icebox, Abyss, Corrode.
- **Bugfix**: `_cancel_match` now keeps session alive until `_delayed_cleanup` finishes. `_cleanup_checker` deletes channels immediately on restart for cancelled/resolved matches.
- Files: `services/db.py`, `cogs/admin.py`, `cogs/challenge.py`, `cogs/arena.py`, `config.py`

---

## [1.3.12] - 2026-02-16
### 🔧 Feat: Admin Match Management Commands

#### 📢 Discord Update
> - `/admin match_pending` — Xem danh sách tất cả trận đấu đang chờ kết quả.
> - `/admin match_cancel <id> [reason]` — Hủy trận đấu rác/stale theo ID.

#### 🔧 Technical Details
- **New DB functions**: `force_cancel_match(match_id, reason)`, `get_pending_matches()`.
- **New admin commands**: `match_pending`, `match_cancel` in `cogs/admin.py`.
- Files: `services/db.py`, `cogs/admin.py`

---

## [1.3.11] - 2026-02-16
### 🛡️ Feat: Giới hạn 1 trận đấu mỗi clan

#### 📢 Discord Update
> - **Chỉ 1 trận đấu cùng lúc**: Mỗi clan chỉ được tham gia tối đa **1 trận đấu chưa hoàn thành** tại một thời điểm.
> - **Kiểm tra 2 chiều**: Hệ thống kiểm tra cả clan gửi lẫn clan nhận trước khi cho phép gửi hoặc chấp nhận thách đấu.
> - **Thông báo rõ ràng**: Nếu bị chặn, người dùng sẽ nhận thông báo cụ thể clan nào đang bận.

#### 🔧 Technical Details
- **New DB function**: `has_active_match(clan_id)` — checks for matches with status `created` or `reported`.
- **Guard checks**: Added to `ChallengeSelectView.confirm` (send) and `AcceptDeclineView.accept` (accept).
- **Structural fix**: Relocated `ChallengeSelectView` & `AcceptDeclineView` as standalone classes outside `on_interaction`.
- Files: `services/db.py`, `cogs/arena.py`

---

## [1.3.10] - 2026-02-15
### ✨ Feat: Map Veto System (BO1/BO3/BO5)

#### 📢 Discord Update
> - **Thêm lựa chọn thể thức**: Captain có thể chọn BO1, BO3 hoặc BO5 khi tạo thách đấu.
> - **Map Veto trực quan**: Hệ thống Ban/Pick map tự động theo lượt với giao diện nút bấm tiện lợi.
> - **Quy trình chuẩn**:
>   - **BO1**: Ban 6 maps -> Map cuối cùng thi đấu.
>   - **BO3/BO5**: Ban 2 maps -> Pick lần lượt -> Map còn lại là Decider (nếu cần).
> - **Map Pool chuẩn**: Ascent, Bind, Haven, Split, Lotus, Pearl, Sunset.

#### 🔧 Technical Details
- **Schema Update**: Added `match_format`, `maps`, `veto_status` to `matches` table.
- **New UI**: `ChallengeSelectView` (Format dropdown) & `MapVetoView` (Interactive Ban/Pick).
- **Core Logic**: Implemented turn-based veto logic handling different sequences for BO1/3/5.
- Files: `cogs/arena.py`, `cogs/matches.py`, `services/db.py`, `config.py`

---

## [1.3.2] - 2026-02-14
### 🐛 Fix: Database missing `winner_clan_id` column

> **Author: Nikko**

#### 📢 Discord Update
> - **Sửa lỗi xác nhận trận đấu**: Khắc phục lỗi bot crash khi xác nhận kết quả trận đấu do thiếu dữ liệu trong database.

#### 🔧 Technical Details
- **Database Migration**: Thêm cột `winner_clan_id` vào bảng `matches` trong `schema.sql`.
- **Auto-Migration**: Cập nhật `services/db.py` để tự động thêm cột `winner_clan_id` nếu database hiện tại chưa có.
- **Manual Fix**: Thực hiện lệnh `ALTER TABLE` trực tiếp trên `clan.db` để bot có thể hoạt động lại ngay lập tức.
- **Git Push**: Đã push toàn bộ thay đổi lên branch `feature/challenge-upgrade-v1.3.1`.
- Files: `db/schema.sql`, `services/db.py`

---

## [1.3.1] - 2026-02-13
### ✨ Feat: Side Pick ATK/DEF + Voice Limit Update

> **Author: Nikko**

#### 📢 Discord Update
> - **Chọn Side (Attack/Defense)**: Sau khi ban/pick map xong, 2 clan sẽ chọn bên ATK hoặc DEF cho từng map. Clan nào pick map thì đối thủ được chọn side cho map đó. Map 3 (random) → side cũng random.
> - **Voice channel**: Tăng giới hạn từ 5 lên **6 người** mỗi phòng voice.
> - **Fix Confirm 1 click**: Sửa lỗi phải bấm Confirm 2 lần — View callbacks giờ xử lý trực tiếp thay vì qua `_noop`.
> - **Fix Cleanup sau Cancel**: Sửa lỗi cleanup không hoạt động khi huỷ match từ nút "Huỷ Match" trong báo cáo kết quả.

#### 🔧 Technical Details
- **Side Pick Phase**: Thêm 2 lượt mới (turn 6-7) sau ban/pick: chọn side ATK/DEF cho Map 1 và Map 2. Map 3 tự động random side.
  - `SidePickView`: UI mới với 2 nút ⚔️ Attack / 🛡️ Defense + ❌ Cancel.
  - `side_choices: Dict[str, Dict[str, str]]` field mới trong `MapBanPickState` — lưu `{"map_name": {"chooser": "a"|"b", "chooser_side": "attack"|"defense"}}`.
  - Turn 6: Clan B chọn side cho Map 1 (Clan A pick). Turn 7: Clan A chọn side cho Map 2 (Clan B pick).
  - `is_completed` updated: `>= 8` (trước: `>= 6`). Thêm `is_side_pick_phase` property.
  - Summary embed hiển thị đầy đủ maps + sides (ai ATK, ai DEF).
- **Voice Limit**: `user_limit=6` (trước: 5).
- **Fix Confirm**: `MapSelectView` callbacks gọi thẳng `handle_mapbp_interaction()` thay vì `_noop`. `on_interaction` giờ chỉ là fallback post-restart.
- **Fix Cleanup**: Thêm `"cancelled"` vào `_cleanup_checker` status check. `_cancel_match` xoá session khỏi `_active_sessions` trước khi spawn `_delayed_cleanup` → tránh double-trigger.
- **Refactor**: `cleanup_all_channels()` → `_delete_channels()` (chỉ xoá channels, không quản lý sessions).
- Files: `cogs/challenge.py`, `config.py`

---

## [1.3.0] - 2026-02-13
### ✨ Feat: ĐẠI CHIẾN CLANS — Challenge Upgrade (Ban/Pick Map + Match Channels)

> **Author: Nikko**

#### 📢 Discord Update
> - **Nâng cấp Thách Đấu**: Khi một clan chấp nhận lời thách đấu, bot sẽ tự động tạo phòng thi đấu riêng (2 voice + 1 text channel) với quyền truy cập đúng cho từng clan.
> - **Ban/Pick Map**: Trước khi trận đấu bắt đầu, 2 clan sẽ thực hiện ban/pick map theo luật: 2-2-2-2 ban, 1-1 pick, random map 3 (tổng 12 maps).
> - **Thông báo tự động**: Bot gửi link phòng voice + text vào channel riêng của từng clan khi match được tạo.
> - **Voice giới hạn**: Mỗi phòng voice chỉ cho tối đa 5 người join.
> - **Báo cáo kết quả**: Embed báo cáo kết quả gửi trực tiếp trong room text match (không gửi trong arena).
> - **Persistent**: Ban/pick embed không hết hạn, hoạt động ngay cả sau khi reset bot. State lưu vào file JSON.
> - **Dọn dẹp tự động**: Channels sẽ bị xoá sau 5 phút khi match kết thúc (báo cáo kết quả thành công hoặc huỷ trận).

#### 🔧 Technical Details
- **New Cog**: `cogs/challenge.py` — chứa toàn bộ logic ban/pick + channel management.
  - `MapBanPickState` dataclass: quản lý trạng thái session (maps, turns, bans, picks, channels, pending_selection).
  - `MapSelectView`: persistent UI (select menu + ✅ Confirm / 🔁 Reset / ❌ Cancel) sử dụng `custom_id` pattern `mapbp_*`.
  - `start_challenge_flow()`: entry point được gọi từ `arena.py`.
  - `handle_mapbp_interaction()`: xử lý tất cả button/select interactions qua `on_interaction` listener.
  - `create_match_channels()`: tạo channels với Discord permission overwrites + `user_limit=5` cho voice.
  - `_continue_to_match_flow()`: sau ban/pick → reuse 100% `MatchCreatedView` từ `cogs/matches.py`, gửi trong text channel.
  - `_delayed_cleanup()`: `asyncio.create_task` chờ 5 phút rồi xoá channels.
  - `_cleanup_checker`: background task (mỗi 2 phút) kiểm tra match status → tự schedule cleanup khi match done.
  - `_save_sessions()` / `_load_sessions()`: persist state ra `data/challenge_sessions.json`.
- **Config**: Thêm `MAP_POOL` (12 maps Valorant), `MAP_BAN_TIMEOUT_SECONDS = 180`, `MATCH_CHANNEL_CLEANUP_DELAY = 300`.
- **Arena Redirect**: `ChallengeAcceptView._accept()` giờ chỉ validate rồi gọi `start_challenge_flow()`.
- **Channel Permissions**:
  - Voice: `@everyone` view only, clan role = connect + speak, user_limit = 5.
  - Text: `@everyone` view only, no send messages. Clan roles view only. Bot = full send/manage.
- **Persistent sessions**: State lưu vào JSON, khôi phục qua `cog_load()`. Không timeout — embed sống mãi đến khi trận kết thúc.
- Files: `cogs/challenge.py` (NEW), `cogs/arena.py`, `config.py`, `main.py`
## [1.2.30] - 2026-02-13
### ✨ Feat: Enhanced System Observability & Logging

#### 📢 Discord Update
> - **Hệ thống Log chi tiết hơn**: Tăng cường khả năng giám sát hệ thống bằng cách bổ sung log chi tiết cho tất cả các tương tác quan trọng.
> - **Minh bạch hóa hoạt động**: Mọi hành động từ Tìm Clan, Quản lý Clan (Khai trừ, Bổ nhiệm), đến Báo cáo/Xác nhận trận đấu đều được ghi nhận rõ ràng trong kênh log.
> - **Theo dõi real-time**: Admin có thể nắm bắt trạng thái hệ thống ngay lập tức thông qua console và Discord logs.

#### 🔧 Technical Details
- **Console Monitoring**: Added `print` statements to all major interaction flows.
- **Traceability**: Detailed logs for LFG system, clan management, and match lifecycle.
- Files: `cogs/arena.py`, `cogs/clan.py`, `cogs/matches.py`, `cogs/admin.py`

---


## [1.2.29] - 2026-02-13
### ✨ Feat: Updated Arena Dashboard & New Tournament Rules

#### 📢 Discord Update
> - **Cập nhật giao diện Arena**: Dashboard tại kênh `#arena` đã được làm mới, trình bày gọn gàng và chuyên nghiệp hơn.
> - **Quy định thi đấu Online mới**: Bổ sung luật bắt buộc thi đấu trong Voice Server chính, giới hạn 1 người nước ngoài (tây) và các quy định về nhân sự trong trận đấu.
> - **Khung xử phạt nghiêm khắc**: Thiết lập hệ thống phạt 3 cấp độ (Reset Elo -> Xóa Clan -> Ban Server) đối với các hành vi vi phạm quy định thi đấu.

#### 🔧 Technical Details
- **UI Refresh**: Updated `create_arena_embed` in `cogs/arena.py` with the new formatting and added the missing **"Tìm Clan 🤝"** description.
- **Rules Expansion**: Updated `rules_button` in `cogs/arena.py` to include detailed Online Tournament Rules, Penalty Tiers, and Purpose sections.
- **Text Standardization**: Removed bolding from dashboard descriptions for a cleaner look.
- Files: `cogs/arena.py`

---

## [1.2.28] - 2026-02-13
### ✨ Feat: Detailed Elo Explanation & Free Agent System

#### 📢 Discord Update
> - **Hệ thống Tìm Clan (Free Agent)**: Dashboard Arena giờ đây có thêm nút **"Tìm Clan 🤝"**. Người chơi solo có thể đăng Profile (Riot ID, Rank, Role) để tìm kiếm clan phù hợp.
> - **Kết nối Solo**: Các người chơi tự do cũng có thể bấm nút để kết nối với nhau và cùng lập team mới.

#### 🔧 Technical Details
- **Elo Transparency**: Added detailed breakdown for all Elo changes (Match Confirm, Dispute, Manual Adjust, Rollback).
- **Log Helper**: Added `format_elo_explanation_vn` in `services/elo.py` to standardize Vietnamese explanations for Elo calculations.
- **Enhanced Logs**: Updated `MATCH_CONFIRMED`, `MATCH_RESOLVED`, `CASE_ACTION`, and `CLAN_ELO_ADJUSTED` events to include the detailed breakdown in Discord Logs and Console.
- **Free Agent System**: Added `lfg_posts` table and service functions.
- **Interactive UI**: Implemented `LFGModal`, `LFGContactView`, and "Find Clan" button in `ArenaView`.
- Files: `services/elo.py`, `cogs/matches.py`, `cogs/admin.py`, `cogs/arena.py`, `services/db.py`, `db/schema.sql`
---

## [1.2.27f] - 2026-02-13
### 🐛 Fix: Arena Match History Score Display

#### 📢 Discord Update
> - **Sửa lỗi hiển thị tỉ số**: Khắc phục lỗi không hiện tỉ số và người thắng trong Lịch sử Match tại Arena sau khi trận đấu đã confirm.
> - **Hiển thị linh hoạt**: Dashboard giờ đây hiển thị cả tỉ số của các trận đấu đang chờ xác nhận (status reported), giúp theo dõi kết quả nhanh chóng hơn.
> - **Độ ổn định cao**: Khắc phục các trận đấu cũ thiếu thông tin người thắng vẫn hiển thị được tỉ số chính xác.

#### 🔧 Technical Details
- **Winner Persistence**: Updated `services/db.py` to ensure `winner_clan_id` is populated in `confirm_match_v2` and `resolve_match`.
- **Display Resilience**: Updated `cogs/arena.py` to fallback to `reported_winner_clan_id` or `resolved_winner_clan_id` if the final winner ID is missing.
- **Real-time Scoring**: Added support for displaying scores in the "reported" state within the Arena history.
- Files: `cogs/arena.py`, `services/db.py`

---

## [1.2.27e] - 2026-02-13
### ✨ Feat: Admin Manual Role Override (DB-backed)

#### 📢 Discord Update
> - **Lệnh mới cho Mod/Admin**: `/admin role grant` và `/admin role remove` để tự cấp/xóa quyền nội bộ clan cho member.
> - **Chỉnh quyền trực tiếp trong DB**: Role nội bộ (`member/vice/captain`) được cập nhật thẳng vào database để sửa quyền thao tác nhanh khi cần.

#### 🔧 Technical Details
- **New Admin Commands**:
  - `/admin role grant <@user> <vice|captain> <reason>`
  - `/admin role remove <@user> <reason>` (force về `member`)
- **DB Transaction Helper**: Added `admin_set_member_role(clan_id, user_id, new_role)` in `services/db.py`.
- **Captain Safety**:
  - Promoting a user to `captain` auto-demotes old captain to `member` and updates `clans.captain_id`.
  - Directly demoting current captain is blocked to avoid inconsistent clan ownership.
- **Clan Override for Testing**: Added `/admin clan set_member <@user> <clan_name> [role] [reason]` to force move/add a member into any clan for test/fix workflows (with DB update and Discord role sync best-effort).
- Files: `cogs/admin.py`, `services/db.py`

---

## [1.2.27] - 2026-02-12
### ✨ Feat: Reporting Flexibility & Interaction Reliability

#### 📢 Discord Update
> - **Linh hoạt báo cáo**: Giờ đây cả hai clan tham gia trận đấu đều có thể nhấn nút **Báo cáo kết quả**. Sau khi một bên báo cáo, bên kia sẽ nhận được yêu cầu xác nhận.
> - **Hủy Match đồng thuận**: Tính năng hủy trận đấu giờ đây yêu cầu sự xác nhận của cả hai bên. Một bên yêu cầu, bên kia phải bấm 'Hủy Match' để đồng ý hủy bỏ.
> - **Sửa lỗi Interaction**: Khắc phục triệt để lỗi "Interaction has already been acknowledged" (40060) khi bấm các nút Thách đấu hoặc Báo cáo trận đấu.
> - **Độ ổn định cao**: Tối ưu hóa phản hồi nút bấm, đảm bảo bot không bị treo hoặc báo lỗi đỏ khi nhiều người cùng thao tác.

#### 🔧 Technical Details
- **Interaction Safety**: Implemented no-op callbacks for persistent buttons in `ArenaCog` and `MatchesCog`. Handled all logic via `on_interaction` listeners with `is_done()` checks to prevent double-acknowledgment.
- **Matches Cog**: Updated `handle_match_report_btn` and `handle_match_cancel_btn` to support mutual agreement. Added logic to identify the acting clan and track cancellation requests.
- **Database**: Added `cancel_requested_by_clan_id` to `matches` table and added helper functions `request_match_cancel`, `clear_match_cancel_request`.
- **Standardization**: Refactored `ChallengeAcceptView`, `ArenaView`, `MatchCreatedView`, and `MatchReportedView` to follow the standardized interaction handling pattern.
- Files: `cogs/arena.py`, `cogs/matches.py`, `config.py`, `services/bot_utils.py`

---

## [1.2.27a] - 2026-02-12
### 🐛 Fix: Loan KeyError + Interaction Race Condition

#### 📢 Discord Update
> - **Sửa lỗi Loan**: Khắc phục lỗi `KeyError: 'note'` khi bấm nút chấp nhận loan.
> - **Sửa lỗi Interaction**: Khắc phục race condition gây lỗi "Interaction already acknowledged" liên tục khi bấm nút loan.

#### 🔧 Technical Details
- **Loan Cog**: Replaced `loan["note"]` with `loan.get("note")` to handle missing column gracefully.
- **Race Condition**: Wrapped `defer()` in `try/except discord.HTTPException` to handle TOCTOU race between View callback and `on_interaction` handler.
- **Cleanup**: Removed duplicate import `from services import db, permissions, cooldowns, loan_service`.
- **Schema**: Added `note TEXT` column to `loans` table in `schema.sql`.
- Files: `cogs/loans.py`, `db/schema.sql`

---

## [1.2.27b] - 2026-02-12
### 🐛 Fix: Loan Channel Lookup + Remove Redundant Button

#### 📢 Discord Update
> - **Sửa lỗi Loan**: Khắc phục lỗi "Clan chưa có kênh riêng" khi tạo yêu cầu loan — trước đó mọi clan đều bị báo lỗi dù đã có kênh Discord.
> - **Gọn giao diện**: Xóa nút "Clan Mượn Chấp Nhận" thừa — clan mượn tạo request = tự động chấp nhận, không cần bấm thêm.

#### 🔧 Technical Details
- **Channel Key Fix**: Changed `lending_clan.get("private_channel_id")` → `lending_clan.get("discord_channel_id")` — wrong key caused all clans to fail.
- **Remove Borrowing Button**: Removed `accept_borrowing` button from `LoanAcceptView`, removed `loan_accept_borrowing` handler from `on_interaction`, removed borrowing case from `handle_loan_accept`. Borrowing clan auto-accepts on request creation.
- Files: `cogs/loans.py`

---

## [1.2.27c] - 2026-02-12
### 🐛 Fix: Loan Activation Crash (datetime + guild None)

#### 📢 Discord Update
> - **Sửa lỗi kích hoạt Loan**: Khắc phục 2 lỗi khi loan được tất cả bên chấp nhận — role không được chuyển và thông báo công khai không gửi được.
> - **Lệnh mới**: `/admin loan fix_roles` — quét tất cả loan đang hoạt động và sửa role Discord cho member bị lệch.

#### 🔧 Technical Details
- **Missing Import**: `loan_service.py` used `datetime.now(timezone.utc)` without importing `datetime`/`timezone` → added `from datetime import datetime, timezone`.
- **Guild None**: When member accepts loan via DM, `interaction.guild` is `None` → added fallback `interaction.client.get_guild(config.GUILD_ID)` in `activate_loan()`.
- **Admin Command**: Added `/admin loan fix_roles` — scans all active loans, removes lending clan role, adds borrowing clan role for each loaned member. Reports fixed count and errors.
- Files: `services/loan_service.py`, `cogs/loans.py`, `cogs/admin.py`

---

## [1.2.27d] - 2026-02-12
### 🐛 Fix: DB Auto-Migration for Missing Columns

#### 📢 Discord Update
> - **Sửa lỗi Database**: Khắc phục lỗi "no such column: score_a" khi báo cáo kết quả trận đấu — database cũ thiếu cột mới.
> - **Tự động nâng cấp DB**: Bot giờ tự kiểm tra và thêm các cột thiếu khi khởi động, không cần xóa lại database.

#### 🔧 Technical Details
- **Root Cause**: Production DB was created from older `schema.sql`. `CREATE TABLE IF NOT EXISTS` doesn't ALTER existing tables, so new columns (`score_a`, `score_b`, `note`) were missing.
- **Auto-Migration**: `init_db()` now uses `PRAGMA table_info()` to check existing columns and runs `ALTER TABLE ADD COLUMN` for any missing ones:
  - `matches`: `cancel_requested_by_clan_id`, `score_a`, `score_b`
  - `loans`: `note`
- **Zero downtime**: Migration runs on every bot startup, safe to re-run (idempotent).
- Files: `services/db.py`

---

## [1.2.26] - 2026-02-12
### ✨ Feat: Elo Adjustment Command & Clean Match History

#### 📢 Discord Update
> - **Báo cáo bằng tỉ số**: Giờ đây bạn có thể nhập tỉ số cụ thể (VD: 2-1) thay vì chỉ chọn Thắng/Thua.
> - **Xác nhận chéo an toàn**: Khi một bên báo cáo, bot sẽ gửi nút Xác nhận vào kênh chat riêng của đối thủ. Trận đấu chỉ được tính khi cả 2 bên đồng ý.
> - **Tăng giới hạn Loan**: Mỗi clan giờ được phép mượn/cho mượn tối đa **02 thành viên** (trước đây là 01).
> - **Quy trình Loan mới**: Clan mượn giờ chủ động gửi yêu cầu `/loan request` đến clan cho mượn. Yêu cầu sẽ xuất hiện trực tiếp trong kênh chat riêng của clan đối thủ để Captain bên đó duyệt.
> - **Thông báo công khai**: Tự động thông báo các hợp đồng loan thành công vào kênh `#chat-arena` để toàn server cùng biết.
> - **Tiện lợi cho Member**: Thành viên được mượn giờ đây có thể bấm Accept ngay trong DM của bot thay vì phải tìm kênh clan.
> - **Cập nhật /clan help**: Bổ sung đầy đủ lệnh Transfer/Loan và quy tắc mới nhất cho Captain/Vice.
> - **Lịch sử trận đấu sạch hơn**: Tự động ẩn các trận đấu đã bị hủy (`cancelled`) và hiện tỉ số cụ thể.
> - **Chi tiết thời gian**: Lịch sử trận đấu hiện đầy đủ Ngày và Giờ.

#### 🔧 Technical Details
- **Match Cog**: Refactored reporting flow to use `MatchScoreModal` and private channel notifications.
- **Database**: Migrated `matches` table to include `score_a` and `score_b`.
- **Elo Service**: Updated to support score-based winner determination.
- **Admin Cog**: Added `/admin clan set_elo` command.
- **Database Service**: Cập nhật `get_recent_matches` để lọc trạng thái `cancelled` theo mặc định.
- **Arena UI**: Nâng cấp `match_history_button` với format hiển thị mới: 
    - Dùng `\n└ 🕒` để tách dòng thời gian.
    - Chuẩn hóa text hiển thị Elo thắng/thua (`+X / -Y`).
    - Parse `created_at` để lấy giờ phút.
- Files: `cogs/admin.py`, `services/db.py`, `cogs/arena.py`

---

## [1.2.25] - 2026-02-12
### ✨ Feat: Cooldown Fusion & Match Rate Limit Fix

#### 📢 Discord Update
> **[v1.2.25] Gộp hệ thống Cooldown & Sửa lỗi hiển thị!**
> - **Hợp nhất Cooldown**: Toàn bộ hệ thống chờ gia nhập/rời clan được quy về một nơi duy nhất. Admin xóa cooldown giờ sẽ có tác dụng ngay lập tức 100%.
> - **Sửa lỗi số âm**: Khắc phục triệt để lỗi hiện "-128 phút" khi tạo trận đấu hoặc thách đấu.
> - **Hiển thị chính xác**: Thời gian chờ được chuẩn hóa múi giờ, hiển thị rõ ràng từng phút từng giây.

#### 🔧 Technical Details
- **FUSION**: Triển khai "Lazy Migration" trong `services/cooldowns.py` - tự động chuyển dữ liệu `users.cooldown_until` cũ sang bảng `cooldowns` mới khi kiểm tra.
- **SQL Fix**: Sử dụng `DATETIME(column)` cho tất cả các câu lệnh SQLite so sánh ngày tháng để khắc phục lỗi so sánh chuỗi ISO (chữ 'T' gây sai lệch).
- **Service Layer**: Cập nhật `services/db.py` để wrap các query cooldown/ban/pop expired.
- **Display Logic**: Chuẩn hóa logic tính toán `time_str` trong `cogs/matches.py` và `cogs/arena.py` (max(0, seconds), UTC normalization, handle space vs 'T').
- **Admin Commands**: Cập nhật `/admin cooldown clear/view` để đồng bộ với cơ chế Fusion.
- Files: `services/db.py`, `services/cooldowns.py`, `cogs/clan.py`, `cogs/admin.py`, `cogs/matches.py`, `cogs/arena.py`

---

## [1.2.24] - 2026-02-11
### ✨ Feat: Elo system overhaul + Arena Challenge + Match history

#### 📢 Discord Update
> **[v1.2.24] Cải thiện hệ thống Elo, Thách đấu & Lịch sử trận!**
> - Elo giờ chính xác hơn: K=40 cho 10 trận đầu (placement), K=32 sau đó
> - Mỗi clan có K-factor riêng — clan mới leo nhanh hơn
> - Elo sàn = 100, không thể xuống thấp hơn
> - Nút **Thách Đấu** mới trong Arena: gửi lời thách đấu vào kênh clan đối thủ, họ bấm Chấp nhận/Từ chối
> - Chống spam: cooldown 10 phút giữa các lần thách đấu
> - **Lịch sử Match** hiển thị rõ hơn: ai thắng ai thua, Elo thay đổi bao nhiêu, ngày tạo, trạng thái chi tiết

#### 🔧 Technical Details
- `services/elo.py`: thêm `get_k_factor(matches_played)` → K=40 (placement <10 matches) / K=32 (stable)
- `services/elo.py`: per-clan K-factor trong `apply_match_result()` — mỗi bên dùng K riêng
- `services/elo.py`: enforce `ELO_FLOOR=100` → `new_elo = max(ELO_FLOOR, elo + delta)`
- `services/elo.py`: import config thay vì hardcode constants
- `config.py`: thêm `ELO_K_STABLE=32`, `ELO_K_PLACEMENT=40`, `ELO_FLOOR=100`, `CHALLENGE_COOLDOWN_MINUTES=10`
- `cogs/arena.py`: thêm nút **Thách Đấu** (row=2) — gửi lời thách đấu vào kênh riêng clan đối thủ
- `cogs/arena.py`: thêm `ChallengeAcceptView` (persistent) với nút Chấp nhận/Từ chối cho clan bị thách
- `cogs/arena.py`: khi chấp nhận → tạo match trong #arena, thông báo cả 2 kênh clan
- `cogs/arena.py`: khi từ chối → thông báo kênh clan thách đấu
- `cogs/arena.py`: lịch sử match hiển thị: thắng/thua, Elo (+/-), ngày, trạng thái chi tiết
- `cogs/arena.py`: fix rules embed — thay text cứng "+25/-15 Elo" bằng mô tả dynamic K-factor
- `cogs/arena.py`: persistent handler cho challenge buttons qua `on_interaction`
- `cogs/matches.py`: fix `CancelMatchButton` guard `is_done()` tránh lỗi 400
- `SPEC.md`, `RULEBOOK.md`: cập nhật Elo section
- Files: `services/elo.py`, `config.py`, `cogs/arena.py`, `cogs/matches.py`, `SPEC.md`, `RULEBOOK.md`

---

## [1.2.23] - 2026-02-10
### ✨ Feat: Mod kick + Help update + DM cooldown

#### 📢 Discord Update
> **[v1.2.23] Nâng cấp quyền Mod & thông báo cooldown!**
> - Mod/Admin có thể kick bất kỳ người trong clan khác
> - `/clan help` hiển thị đầy đủ lệnh admin/mod theo role
> - Khi cooldown được xóa hoặc hết hạn, người dùng sẽ nhận DM thông báo

#### 🔧 Technical Details
- Thêm `/mod clan kick` (kick mọi clan, có xử lý captain và auto-disband nếu cần)
- Cập nhật help để hiển thị đầy đủ lệnh admin/mod
- Thêm task kiểm tra cooldown hết hạn và DM người dùng
- Khi admin clear cooldown, gửi DM thông báo và đồng bộ users table
- Files: `cogs/clan.py`, `cogs/admin.py`, `services/db.py`, `main.py`

---

## [1.2.22] - 2026-02-10
### 🔧 Fix: Tra cứu user bằng picker (gõ tìm)

#### 📢 Discord Update
> **[v1.2.22] Tra cứu user có thể gõ tên!**
> Nút tra cứu ở Arena giờ dùng UserSelect picker, vừa gõ tìm vừa chọn được.

#### 🔧 Technical Details
- Dùng `discord.ui.UserSelect` để cho phép search theo tên trong dropdown
- Files: `cogs/arena.py`

---

## [1.2.21] - 2026-02-10
### 🔧 Fix: Tra cứu user bằng danh sách chọn

#### 📢 Discord Update
> **[v1.2.21] Tra cứu user bằng dropdown!**
> Nút tra cứu ở Arena giờ cho chọn user từ danh sách, không cần gõ tay.

#### 🔧 Technical Details
- Thay modal nhập ID/mention bằng dropdown select 25 user trong server
- Cập nhật text hướng dẫn trong Arena Dashboard
- Files: `cogs/arena.py`

---

## [1.2.20] - 2026-02-10
### ✨ Feat: Arena tra cứu thông tin người khác

#### 📢 Discord Update
> **[v1.2.20] Thêm nút tra cứu thông tin người khác!**
> Arena giờ có nút mới để xem thông tin clan, cooldown và ban của bất kỳ người dùng nào.

#### 🔧 Technical Details
- Thêm `UserInfoModal` để nhập ID/mention và trả về embed thông tin
- Tái sử dụng `_build_user_info_embed()` cho cả "Thông tin của tôi" và tra cứu người khác
- Cập nhật mô tả Arena Dashboard có nút mới
- Files: `cogs/arena.py`

---

## [1.2.19] - 2026-02-10
### 🐛 Fix: Admin Dashboard cooldown query

#### 📢 Discord Update
> **[v1.2.19] Sửa lỗi Dashboard Admin!**
> Tab Members không còn crash khi hiển thị cooldown.

#### 🔧 Technical Details
- Sửa query cooldowns trong `get_members_embed()`
  - Dùng `target_type='user'` và `target_id` theo schema mới
  - Tránh lỗi `no such column: cd.user_id`
- Files: `cogs/admin.py`

---

## [1.2.18] - 2026-02-10
### 🔧 Fix: User Display & #0000 Deprecation

#### 📢 Discord Update
> **[v1.2.18] Cải thiện hiển thị thông tin người dùng!**
> - Admin Dashboard giờ hiển thị đầy đủ thông tin: Discord mention, trạng thái ban/cooldown
> - Người chưa có clan hiển thị "🎯 Lính đánh thuê tự do" thay vì text cũ
> - Riot ID không còn hiện #0000 (Discord đã bỏ discriminator)

#### 🔧 Technical Details
- **Fix 1**: Xóa deprecated `#0000` placeholder trong 8 locations
  - `cogs/clan.py` (7 chỗ): Thay `f"{member.name}#0000"` → `member.display_name`
  - `services/permissions.py` (1 chỗ): Thay `f"{username}#0000"` → `username`
- **Fix 2**: Nâng cấp `get_members_embed()` trong `cogs/admin.py`
  - Thêm query cooldowns count
  - Hiển thị Discord mention `<@id>` thay vì chỉ Riot ID
  - Thêm status indicators: 🚫 (banned), ⏰ (cooldown)
  - Hiển thị "🎯 Tự do" cho user chưa có clan
- **Fix 3**: Cập nhật `my_info_button()` trong `cogs/arena.py`
  - "Chưa tham gia clan nào" → "🎯 Lính đánh thuê tự do"
- Files: `cogs/clan.py`, `cogs/admin.py`, `cogs/arena.py`, `services/permissions.py`

---

## [1.2.17] - 2026-02-10
### 🐛 Fix: Dual-handler 40060 + FK error trong Clan Create Flow

#### 📢 Discord Update
> **[v1.2.17] Sửa lỗi Accept/Decline khi tạo Clan & Invite!**
> Các nút Accept/Decline trong DM giờ hoạt động ổn định. Sửa lỗi crash khi tạo clan mới.
