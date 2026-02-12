
# 📜 ClanVXT Changelog

This document provides a cumulative history of all technical improvements, fixes, and feature updates for the ClanVXT system.

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
==================================================
2026-02-10 00:45:36 INFO     discord.client logging in using static token
2026-02-10 00:45:37 INFO     discord.gateway Shard ID None has connected to Gateway (Session ID: 89399bf58c4d5ffeb74eadfb6a21d8ae).
Logged in as Vê Xê Tê#4969 (ID: 1465685214134276096)
--------------------------------------------------
Target guild: Quốc Hội Thiểu Năng
✓ Found verified role: Thiểu Năng Con
✓ Found mod role: Hội đồng quản trị
✓ Found log channel: #log
✓ Found category: CLANS
✓ Found update channel: #update-bot
Database initialized at /home/container/data/clan.db
  ✓ Schema up to date (15 tables)
✓ Database initialized
2026-02-10 00:45:39 ERROR    discord.client Ignoring exception in on_ready
Traceback (most recent call last):
  File "/home/container/.local/lib/python3.14/site-packages/discord/ext/commands/bot.py", line 962, in _load_from_module_spec
    spec.loader.exec_module(lib)  # type: ignore
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^
  File "<frozen importlib._bootstrap_external>", line 755, in exec_module
  File "<frozen importlib._bootstrap_external>", line 893, in get_code
  File "<frozen importlib._bootstrap_external>", line 823, in source_to_code
  File "<frozen importlib._bootstrap>", line 491, in _call_with_frames_removed
  File "/home/container/cogs/clan.py", line 393
    )
    ^
SyntaxError: unmatched ')'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/container/.local/lib/python3.14/site-packages/discord/client.py", line 504, in _run_event
    await coro(*args, **kwargs)
  File "/home/container/main.py", line 127, in on_ready
    await bot.load_extension("cogs.clan")
  File "/home/container/.local/lib/python3.14/site-packages/discord/ext/commands/bot.py", line 1040, in load_extension
    await self._load_from_module_spec(spec, name)
  File "/home/container/.local/lib/python3.14/site-packages/discord/ext/commands/bot.py", line 965, in _load_from_module_spec
    raise errors.ExtensionFailed(key, e) from e
discord.ext.commands.errors.ExtensionFailed: Extension 'cogs.clan' raised an error: SyntaxError: unmatched ')' (clan.py, line 393)
#### 🔧 Technical Details
- **Bug 1**: `Interaction already acknowledged` (40060) trong `handle_clan_accept`/`handle_clan_decline` — cả `AcceptDeclineView.callback` VÀ `on_interaction` đều fire
  - Fix: Callbacks trong `AcceptDeclineView` và `InviteAcceptDeclineView` giờ là `pass` (no-op)
  - `handle_clan_accept` và `handle_clan_decline` dùng `is_done()` check + try/except fallback
- **Bug 2**: `FOREIGN KEY constraint failed` trong `create_create_request` khi tạo clan
  - Fix: Wrap `create_create_request` trong try/except, skip member nếu FK lỗi, log error
- Dọn leftover code từ old decline_callback trong AcceptDeclineView
- Files: `cogs/clan.py`

---

## [1.2.16] - 2026-02-10
### 🐛 Fix: Dual-handler bug trong Loans & Transfers

#### 📢 Discord Update
> **[v1.2.16] Sửa lỗi tiềm ẩn trong Loan & Transfer!**
> Các nút Accept cho Loan và Transfer giờ hoạt động ổn định hơn, không còn risk lỗi "Interaction already acknowledged".

#### 🔧 Technical Details
- Áp dụng cùng pattern đã fix ở matches.py cho loans.py và transfers.py
- Button callbacks trong `LoanAcceptView` và `TransferAcceptView` giờ là `pass` (no-op)
- Toàn bộ logic xử lý qua `on_interaction` → `handle_loan_accept` / `handle_transfer_accept`
- Xóa duplicate imports (`from services import db, permissions, cooldowns...` x2)
- Files: `cogs/loans.py`, `cogs/transfers.py`

---

## [1.2.15] - 2026-02-10
### 🐛 Fix: Interaction Already Acknowledged (Error 40060) trong Matches

#### 📢 Discord Update
> **[v1.2.15] Sửa lỗi crash khi bấm nút trong Match!**
> Các nút Report, Confirm, Dispute, Cancel giờ hoạt động ổn định. Không còn lỗi "Interaction has already been acknowledged".

#### 🔧 Technical Details
- Root cause: Cả button `callback` method VÀ `on_interaction` listener đều fire cho cùng 1 interaction → double-acknowledge → HTTPException 40060
- Fix: Thêm `safe_send()` và `safe_edit()` helpers kiểm tra `is_done()` trước khi respond
- Button callbacks (`ReportWinButton`, `CancelMatchButton`, `ConfirmButton`, `DisputeButton`) giờ là `pass`
- Toàn bộ logic xử lý qua `on_interaction` → `handle_match_report/cancel/confirm/dispute`
- `DisputeReasonModal.on_submit` cũng dùng safe helpers
- Files: `cogs/matches.py`

---

## [1.2.14] - 2026-02-09
### 🐛 Fix: NameError `cooldowns` trong `/match create`

#### 📢 Discord Update
> **[v1.2.14] Sửa lỗi không tạo được trận đấu**
> Lệnh `/match create` đã hoạt động bình thường trở lại.

#### 🔧 Technical Details
- `cogs/matches.py` thiếu `from services import cooldowns` → gây `NameError` tại dòng 656 khi gọi `cooldowns.check_cooldown()`
- Bỏ dòng `from services import elo` bị duplicate
- Files: `cogs/matches.py`

---

## [1.2.13] - 2026-02-09
### ✨ Feature: Đổi Tên Clan (Captain Only)

#### 📢 Discord Update
> **[v1.2.13] Captain đã có thể đổi tên Clan!**
> Bấm nút 🏷️ **Đổi Tên Clan** trong Arena để thay đổi tên clan của bạn.
> Hệ thống sẽ tự động cập nhật: Database, Role Discord và Kênh Discord.

#### 🔧 Technical Details
- Thêm `update_clan_name()` vào `services/db.py`
- Thêm `ClanRenameModal` vào `cogs/arena.py` để xử lý input và validation
- Tự động rename Discord Role và Text Channel tương ứng
- Thêm log event `CLAN_RENAMED`
- Files: `services/db.py`, `cogs/arena.py`

---

## [1.2.12] - 2026-02-09
### ✨ Feature: Nút Luật Lệ trong Arena

#### 📢 Discord Update
> **[v1.2.12] Xem luật lệ ngay trong Arena!**
> Bấm nút 📜 **Luật Lệ** để xem tóm tắt các quy định quan trọng.

#### 🔧 Technical Details
- Thêm `rules_button` vào `ArenaView` với 5 section: Tổng Quan, Tạo Clan, Cooldown, Trận Đấu, Vi Phạm
- Cập nhật `create_arena_embed()` thêm mô tả nút Luật Lệ
- Files: `cogs/arena.py`

---

## [1.2.11] - 2026-02-09
### 🐛 Bug Fix: Interaction Already Acknowledged Error

#### 📢 Discord Update
> **[v1.2.11] Sửa lỗi Accept/Decline Invite!**
> Các nút Accept/Decline lời mời Clan giờ hoạt động ổn định hơn.

#### 🔧 Technical Details
- Bug: `Interaction has already been acknowledged` khi click nút trong DM
- Fix: Kiểm tra `interaction.response.is_done()` trước khi respond
- Dùng `defer()` + `followup.send()` thay vì `edit_message()`
- Files: `cogs/clan.py`

---

## [1.2.10] - 2026-02-09
### 🎨 UI Improvement: Compact Clan List + Detail Dropdown

#### 📢 Discord Update
> **[v1.2.10] Danh sách Clan gọn gàng hơn + Xem chi tiết!**
> Danh sách compact: Captain + 3 members inline.
> Dropdown bên dưới: Chọn clan để xem đầy đủ thành viên!

#### 🔧 Technical Details
- Format compact: 👑 Captain + 👤 3 members + "...+X khác"
- Thêm `ClanDetailSelectView` với dropdown chọn clan
- Hiển thị chi tiết: Elo, Status, Description, Full members
- Files: `cogs/arena.py`

---

## [1.2.9] - 2026-02-09
### 🐛 Bug Fix: Role Assignment on Invite Accept

#### 📢 Discord Update
> **[v1.2.9] Sửa lỗi nhận role khi accept invite!**
> Giờ khi bạn accept lời mời clan qua DM, role clan sẽ được gán tự động.

#### 🔧 Technical Details
- Bug: `interaction.guild` là `None` trong DM, khiến role không được gán
- Fix: Fetch guild từ `self.bot.get_guild(config.GUILD_ID)` thay vì `interaction.guild`
- Thêm debug logs để dễ troubleshoot
- Files: `cogs/clan.py`

---

## [1.2.8] - 2026-02-09
### ✨ Feature: Auto-Post Updates từ historyUpdate.md

#### 📢 Discord Update
> **[v1.2.8] Hệ thống thông báo hoàn chỉnh!**
> Admin giờ có thể dùng lệnh `/post_latest_update` để tự động đăng thông báo cập nhật.
> Nội dung sẽ được lấy từ phần "Discord Update" trong changelog.

#### 🔧 Technical Details
- Thêm lệnh `/post_latest_update` vào `ArenaCog`
- Parse `historyUpdate.md` bằng regex
- Trích xuất phần `#### 📢 Discord Update`
- Post embed lên `#update-bot`
- Format mới: mỗi version có 2 section (Discord Update + Technical Details)
- Files: `cogs/arena.py`, `historyUpdate.md`

---

## [1.2.7] - 2026-02-09
### ✨ Feature: Tạo Clan từ Arena Dashboard

#### 📢 Discord Update
> **[v1.2.7] Tạo Clan dễ hơn bao giờ hết!**
> Giờ đây bạn có thể tạo clan trực tiếp từ Arena Dashboard bằng nút ➕ **Tạo Clan**.
> Không cần nhớ lệnh, chỉ cần bấm và làm theo hướng dẫn!

#### 🔧 Technical Details
- Thêm nút "Tạo Clan" vào `ArenaView` với `custom_id="arena:create_clan"`
- Validation: verified role, not in clan, no cooldown
- Import và sử dụng `ClanCreateModal` từ `cogs/clan.py`
- Files: `cogs/arena.py`

---

## [1.2.6] - 2026-02-09
### ✨ Feature: Thông Báo Cập Nhật Tự Động

#### 📢 Discord Update
> **[v1.2.6] Kênh #update-bot đi vào hoạt động!**
> Từ giờ các bản cập nhật mới sẽ được thông báo tại đây.
> Theo dõi để không bỏ lỡ tính năng mới nhé! 🔔

#### 🔧 Technical Details
- Thêm `CHANNEL_UPDATE_BOT` vào `config.py`
- Thêm `post_update()` helper vào `bot_utils.py`
- Tìm kênh trong `main.py` on_ready
- Files: `config.py`, `services/bot_utils.py`, `main.py`

---

## [1.2.5] - 2026-02-09
### ✨ Feature: Clan Members in Arena Dashboard

#### 📢 Discord Update
> **[v1.2.5] Xem thành viên clan trong Arena!**
> Nút "Danh sách Clan" giờ hiển thị đầy đủ thành viên của mỗi clan.
> 👑 Captain | ⚔️ Vice | 👤 Member

#### 🔧 Technical Details
- Cập nhật `clan_list_button` trong `ArenaView`
- Fetch members với `db.get_clan_members()`
- Hiển thị role emoji và Discord display name
- Files: `cogs/arena.py`

---

## [1.2.4] - 2026-02-09
### 🐛 Bug Fix: Invitation Persistence

#### 📢 Discord Update
> **[v1.2.4] Sửa lỗi lời mời Clan!**
> Lời mời gia nhập Clan giờ hoạt động ổn định hơn.
> Nếu trước đây bạn không accept được, hãy thử lại nhé!

#### 🔧 Technical Details
- `InviteAcceptDeclineView` custom_id không được xử lý trong `on_interaction`
- Thêm `handle_invite_accept` và `handle_invite_decline` handlers
- Files: `cogs/clan.py`

---


## [1.2.3] - 2026-02-09
### 📝 Refinements & Personal Touch
- **Expanded Rules**: Thêm quy tắc về **Transfer (Chuyển nhượng)** và **Loan (Mượn quân)** vào thông báo server.
- **Nikko's Note**: Thêm lời tâm tình về việc thiếu kinh nghiệm, khao khát sáng tạo và trạng thái **"vừa dùng vừa test"** của bot.
- **Reward Flexibility**: Làm rõ việc phần thưởng Battle Pass có thể chia sẻ linh hoạt trong Clan.

---

## [1.2.2] - 2026-02-09
### 📝 Rules & Rewards Overhaul
- **Balanced Personalization**: Kết hợp lời mở đầu tâm huyết của Nikko với các quy định thi đấu chuyên nghiệp, gọn nhẹ trong `ANNOUNCEMENT_SERVER.md`.
- **Arena Integration**: Tích hợp hướng dẫn sử dụng kênh `#arena` Dashboard vào thông báo server.
- **Elo System Updates**: Thêm quy định reset Elo theo mỗi mùa giải của **Valorant**.
- **Seasonal Rewards**: Công bố phần thưởng **05 Battle Pass** cho Clan đứng đầu mỗi mùa.
- **Help Command Upgrade**: Nâng cấp lệnh `/clan help` với giao diện gold premium và tích hợp thông tin mùa giải.
- **Rulebook Intact**: Giữ nguyên `RULEBOOK.md` gốc để đảm bảo tính chi tiết.

### 📁 Files Changed
| Action | File |
|--------|------|
| MODIFY | `ANNOUNCEMENT_SERVER.md` |
| MODIFY | `RULEBOOK.md` |
| MODIFY | `cogs/clan.py` |
| MODIFY | `historyUpdate.md` |

## [1.2.1] - 2026-02-09
### 📝 Documentation & Personalization
- **ANNOUNCEMENT_SERVER.md Overhaul**: Cập nhật lại toàn bộ nội dung thông báo server với văn phong cá nhân của Nikko.
- **Improved Guides**: Thêm hướng dẫn chi tiết từng bước cho người mới (Create -> Arena -> Match).
- **Rule Consistency**: Đồng bộ hóa quy tắc 5 người (Captain + 4 members) trên tất cả tài liệu.
- **Arena Documentation**: Cập nhật cách sử dụng Arena Dashboard vào `SPEC.md`.

### 📁 Files Changed
| Action | File |
|--------|------|
| MODIFY | `ANNOUNCEMENT_SERVER.md` |
| MODIFY | `historyUpdate.md` |
| MODIFY | `SPEC.md` |
| MODIFY | `RULEBOOK.md` |

## [1.2.0] - 2026-02-09
### ✨ New Features
- **Arena Dashboard**: Kênh `#arena` với nút bấm tương tác để xem thông tin hệ thống:
  - 🏰 **Danh sách Clan** - Xem tất cả clan active, Elo và số thành viên
  - 🏆 **Bảng xếp hạng** - Top 10 clan theo Elo với huy chương 🥇🥈🥉
  - ⚔️ **Lịch sử Match** - 10 trận đấu gần đây với trạng thái
  - 👤 **Thông tin cá nhân** - Xem clan, role, Elo, cooldown và ban status
  - Bot tự động tìm kênh `#arena` khi khởi động và gửi/cập nhật Dashboard
  - Persistent buttons: nút bấm vẫn hoạt động sau khi bot restart
  - Lệnh admin: `/arena_refresh` để làm mới dashboard

### 🔧 Bug Fixes
- Thêm các helper functions vào db.py cho Arena
- Thêm cooldown/ban helpers: `get_active_cooldown`, `get_all_user_cooldowns`, `is_user_banned`

### 📁 Files Changed
| Action | File |
|--------|------|
| NEW | `cogs/arena.py` |
| MODIFY | `config.py` — Thêm `CHANNEL_ARENA` |
| MODIFY | `main.py` — Load arena cog |
| MODIFY | `services/db.py` — Thêm 6 helper functions |

---

## [1.1.2] - 2026-02-08
### 📝 Documentation Sync
- **Clan Create Flow**: Sửa documentation - Captain chọn 4 người (bạn + 4 = 5 tổng), không phải 5 người.
- **Accept/Decline via DM**: Làm rõ accept/decline lời mời clan là qua button trong DM, không phải slash command.
- **Matchadmin Namespace**: Sửa `/admin match resolve` thành `/matchadmin match resolve` trong tất cả docs và code.
- **Remove /clan register**: Xóa hoàn toàn lệnh `/clan register` vì hệ thống tự động đăng ký user khi cần.

### 🔧 Code Fixes
- **Help Command**: Cập nhật `/clan help` trong `cogs/clan.py` để phản ánh đúng các lệnh thực tế.
- **Log Message**: Sửa lệnh trong thông báo tranh chấp match (`cogs/matches.py`).
- **Clan Delete Fix**: Sửa lỗi `IntegrityError` (FOREIGN KEY constraint failed) khi xóa clan bằng cách xóa tất cả dữ liệu liên quan (matches, loans, transfers, v.v.) trước.

### ✨ New Features
- **Clan Invite Command**: Thêm lệnh `/clan invite <user>` cho Captain/Vice Captain để mời người vào clan đã active.
  - Tạo bảng database mới `invite_requests`
  - Thêm functions trong `services/db.py`
  - Thêm UI component `InviteAcceptDeclineView`
  - Gửi lời mời qua DM với nút Accept/Decline
  - Hết hạn sau 48 giờ
  - Tự động kiểm tra cooldown, role, clan status
  - Vice Captain giờ cũng có quyền invite (cập nhật tất cả docs)

---

## [1.1.1] - 2026-02-09
### 🛡️ Concurrency & Stability (P0)
- **Idempotent Acceptance**: Updated `handle_clan_accept` to be idempotent. If a user double-clicks or the system crashes mid-process, subsequent clicks will now "repair" the state and trigger missing notifications.
- **SQLite Integrity Protection**: Added `INSERT OR IGNORE` to `db.add_member` to prevent unique constraint crashes during race conditions.
- **Self-Healing Logic**: Clans "stuck" in enrollment due to previous failures can now be finalized by simply clicking the Accept button again.

### 🔍 Observability
- **Console Debug Logging**: Added descriptive `[DEBUG]` logs for all major button interactions (Clan, Match, Loan, Transfer) to track user actions in real-time.

---

## [1.1.0] - 2026-02-09
### 🛡️ Logic & Security Hardening (P0)
- **Atomic Acceptance**: Modified `services/db.py` to ensure loan/transfer acceptance and completion are atomic. Added `WHERE status = 'requested'` to update queries.
- **Transaction-Safe Movement**: Added `db.move_member` to handle removing a member from one clan and adding them to another in a single SQL transaction.
- **Captain/Vice Protection**: Implemented checks in `services/permissions.py` to prevent Captains and Vice-Captains from being loaned or transferred.
- **Minimum Member Count**: Added validation to ensure a clan never drops below 5 members during a loan or transfer operation.
- **Force-End Loans**: Updated clan disbanding logic (manual and auto) to forcefully terminate any active loans involving the clan before disbanding.

### 🇻🇳 Localization & UX
- **Full Vietnamese Translation**: Translated all user-facing strings, button labels, and embed fields across all 6 cogs and all service layers.
- **DM Notification System**: Added automated DM notifications for loan/transfer requests/activations and match disputes.
- **Match Creation Rate Limit**: Implemented a 5-minute cooldown per clan for creating matches to prevent spam.

### 🔧 Technical Cleanup
- **Standardized Exception Handling**: Replaced bare `except:` blocks with `except Exception:`.
- **Circular Dependency Fixes**: Resolved circular imports by moving some imports inside function local scopes.
- **Database Architecture**: Implemented soft-delete for clans (`status = 'disbanded'`) to preserve ELO history.
- **Task Scheduling**: Verified and localized background tasks for request expiration in `main.py`.

---

## [1.0.0] - Initial Release
- Core clan management features.
- Initial Elo ranking implementation.
- Basic match tracking and reporting.
- Initial database schema and service layer.

---
*Last Updated: 2026-02-09*

---

# 📢 Hướng Dẫn Cho Agent

## Khi Nào Gửi Thông Báo Lên #update-bot?

| ✅ GỬI | ❌ KHÔNG GỬI |
|--------|--------------|
| ✨ Tính năng mới | 📁 Cập nhật documentation |
| 🐛 Sửa lỗi quan trọng (ảnh hưởng người dùng) | 🔧 Refactor code |
| 🎮 Thay đổi gameplay/UX | 📝 Sửa typo, comment |
| | 🔒 Internal fixes (không ai thấy) |

## Cách Gửi Thông Báo

```python
from services import bot_utils

await bot_utils.post_update(
    title="Arena Dashboard nâng cấp!",
    description="Giờ đây bạn có thể xem danh sách thành viên của mỗi Clan ngay trong Arena.",
    version="1.2.5"  # Tùy chọn
)
```

## Nguyên Tắc Viết Thông Báo

1. **Viết tiếng Việt**, ngắn gọn, thân thiện
2. **Tập trung vào lợi ích người dùng**, không chi tiết kỹ thuật
3. **Tiêu đề hấp dẫn**, mô tả điều mới mẻ
4. **Không đề cập** tên file, function, database, etc.

### Ví Dụ Tốt ✅
> **Arena Dashboard nâng cấp!**  
> Giờ đây bạn có thể xem danh sách thành viên của mỗi Clan ngay trong Arena.

### Ví Dụ Xấu ❌
> Đã sửa file cogs/arena.py, thêm hàm get_clan_members vào clan_list_button...

## Quy Trình Sau Khi Commit

1. Cập nhật `historyUpdate.md` với version mới
2. Nếu là **tính năng mới** hoặc **major fix**, gọi `post_update()`
3. Commit và push lên GitHub
