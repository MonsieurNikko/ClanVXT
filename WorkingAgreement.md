# Working Agreement (Shared Repo Rules)

## Context
- Repo/git này **không phải của tôi**. Tôi đang làm việc trên repo của **đồng nghiệp / team**.
- Mục tiêu: hỗ trợ sửa lỗi / thêm tính năng **an toàn**, không phá vỡ phần đang chạy.

## Hard Rules (Bắt buộc)
1. **KHÔNG push** (git push) dưới mọi hình thức **nếu không có yêu cầu rõ ràng** từ tôi.
2. **KHÔNG force push**, không sửa history (rebase --force, push -f).
3. **KHÔNG sửa hoặc rewrite những phần code đang hoạt động ổn**.
   - Chỉ sửa đúng phần liên quan bug / task được giao.
   - Giữ nguyên cấu trúc, biến, logic, style nếu không bắt buộc đổi.
4. Trước khi bắt đầu sửa code, **phải đọc kỹ toàn bộ file `.md` liên quan** (README, CONTRIBUTING, docs/, ARCHITECTURE, CHANGELOG…).
5. Nếu tài liệu `.md` mâu thuẫn với yêu cầu của tôi, **dừng lại và báo** chứ không tự quyết.

## Workflow bắt buộc
- Bước 1: Scan nhanh repo (cấu trúc thư mục, entrypoints, config).
- Bước 2: Đọc các file `.md` quan trọng và tóm tắt ngắn: “repo làm gì, cách chạy, conventions”.
- Bước 3: Xác định phạm vi thay đổi tối thiểu (minimal diff).
- Bước 4: Đề xuất plan + rủi ro (có thể break chỗ nào) trước khi chỉnh.
- Bước 5: Chỉ sau khi có hướng rõ ràng mới sửa code.
- Bước 6: Khi xong:
  - chạy/test theo hướng dẫn trong `.md` (nếu có)
  - cung cấp `git diff` rõ ràng
  - **KHÔNG push**
## Git Safety (Command guardrails)
- Các lệnh bị cấm trừ khi tôi nói rõ:
  - `git push`
  - `git push --force` / `git push -f`
  - `git rebase` (đặc biệt interactive) nếu repo team chưa cho phép
- Khi cần commit: hỏi tôi trước (nếu tôi muốn commit message theo convention nào).

## Output format mong muốn khi bạn trả lời
- Tóm tắt phát hiện từ `.md`
- Kế hoạch thay đổi (3–6 gạch đầu dòng)
- Diff / patch nhỏ, dễ review
- Nêu rõ: “không đụng phần đang chạy” đã được đảm bảo thế nào
