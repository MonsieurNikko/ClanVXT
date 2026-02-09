
# 📜 ClanVXT Changelog

This document provides a cumulative history of all technical improvements, fixes, and feature updates for the ClanVXT system.

---

## [1.2.2] - 2026-02-09
### 📝 Rules & Rewards Overhaul
- **Balanced Personalization**: Kết hợp lời mở đầu tâm huyết của Nikko với các quy định thi đấu chuyên nghiệp, gọn nhẹ trong `ANNOUNCEMENT_SERVER.md`.
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
*Last Updated: 2026-02-08*
