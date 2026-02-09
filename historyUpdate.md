
# 📜 ClanVXT Changelog

This document provides a cumulative history of all technical improvements, fixes, and feature updates for the ClanVXT system.

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
