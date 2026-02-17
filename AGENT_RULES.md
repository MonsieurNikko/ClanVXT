# 🤖 Agent Rules: VXT Clan System

Tất cả các Agent (AI coding assistant) khi tham gia phát triển dự án này PHẢI tuân thủ các quy tắc sau để đảm bảo tính đồng nhất và ổn định của hệ thống.

## 1. Quy Trình Cập Nhật (Workflow)
- **Changelog**: Bất kỳ thay đổi nào (tính năng mới, sửa lỗi) ĐỀU PHẢI được ghi vào file `historyUpdate.md`.
    - Format: Sử dụng heading `## [Version] - YYYY-MM-DD`.
    - **Versioning**: Sử dụng số thứ tự tăng dần cho mỗi bản cập nhật (ví dụ: `1.2.27` -> `1.2.28`). **KHÔNG** sử dụng chữ cái (ví dụ: `1.2.27a`) trừ khi có lý do cực kỳ đặc biệt.
    - **📢 Discord Update**: Chỉ chứa các thông tin liên quan trực tiếp đến trải nghiệm của người chơi (Player-facing). KHÔNG ghi các thay đổi liên quan đến Admin, Mod, Dev, code hay log tại đây.
    - **🔧 Technical Details**: Ghi nhận toàn bộ thay đổi kỹ thuật, bao gồm cả các công cụ/lệnh cho Admin/Mod, các thay đổi logic phía sau, và các cập nhật môi trường/dev.
- **Git Commit**: Commit message phải rõ ràng, ví dụ: `feat: add something`, `fix: resolve issue`. Đính kèm hash commit vào `walkthrough.md` nếu đang làm việc theo session.

## 2. Tiêu Chuẩn Code (Coding Standards)
- **Cogs Logic**: Dự án sử dụng mô hình Cogs của `discord.py`. Giữ logic liên quan đến UI (buttons, modals) trong cogs (ví dụ: `cogs/arena.py`, `cogs/clan.py`).
- **Services Layer**: Các logic dùng chung hoặc thao tác Database PHẢI được viết trong `services/` (ví dụ: `services/db.py`, `services/bot_utils.py`). Không viết query SQL trực tiếp trong file Cog.
- **Interaction Safety**:
    - Luôn sử dụng `defer()` cho các thao tác tốn thời gian (thao tác DB, API).
    - Kiểm tra `interaction.response.is_done()` trước khi thực hiện `followup` hoặc `send_message` để tránh lỗi "Interaction already acknowledged".
    - Với các tương tác qua DM, lưu ý `interaction.guild` sẽ là `None`. Cần fetch guild qua `config.GUILD_ID`.

## 3. Database (SQLite + aiosqlite)
- **Async**: Tất cả các thao tác DB phải là `async`.
- **Row Factory**: Sử dụng row factory (`aiosqlite.Row`) để truy cập dữ liệu theo tên cột.
- **Transactions**: Sử dụng transaction khi thực hiện nhiều lệnh UPDATE/INSERT có liên quan đến nhau.
- **Integrity**: Tôn trọng các ràng buộc (UNIQUE cho tên clan, Foreign Keys). Luôn bắt lỗi `IntegrityError` khi xử lý dữ liệu trùng lặp.

## 4. Giao Diện Người Dùng (UI/UX)
- **Arena Dashboard**: Đây là trung tâm thông tin. Các View trong Arena phải đặt `timeout=None` để đảm bảo nút luôn hoạt động sau khi bot restart.
- **Emoji**: Sử dụng emoji nhất quán (👑 Captain, ⚔️ Match, 🏰 Clan, 📜 Rules).
- **Compact View**: Với các danh sách dài (như danh sách thành viên), ưu tiên hiển thị inline hoặc dùng Dropdown/Pagination để tránh làm dài tin nhắn.

## 5. Bảo Mật & Quyền Hạn
- **Validation**: Luôn kiểm tra quyền hạn (ví dụ: `member_role == 'captain'`) trước khi cho phép thực hiện các hành động nhạy cảm như đổi tên, kick người, giải tán clan.
- **Verified Role**: Các tính năng tạo clan hoặc tham gia thi đấu yêu cầu role `Thiểu Năng Con` (theo cấu hình trong `config.py`).

## 6. Ghi Nhật Ký (Logging)
- Sử dụng `await bot_utils.log_event(event_type, message)` cho tất cả các hành động quan trọng để lưu vào nhật ký hệ thống và hiển thị cho Mod.

## 7. Console Logging & Ưu Tiên Tên (Priority)
- **Console Logs**: Luôn in ra console (`print`) các bước thực hiện quan trọng để dễ dàng theo dõi quá trình chạy thực tế (ví dụ: `[ARENA] User X clicked button Y`).
- **Tên thay vì ID**: Luôn ưu tiên hiển thị và log bằng **Tên** (Username, Clan Name, Guild Name) thay vì chỉ dùng ID số. ID chỉ nên dùng để truy vấn database hoặc xử lý logic ngầm. Trải nghiệm người dùng và Mod cần thông tin dễ đọc.

---
*Tài liệu này được tạo tự động bởi Antigravity Agent dựa trên quá trình phát triển hệ thống.*
