# 🏰 ClanVXT - Quy Chế Hệ Thống Clan (Official Rulebook)

Chào mừng bạn đến với hệ thống Clan chính thức của server! Đây là nơi các đội nhóm tranh tài, khẳng định vị thế và xây dựng cộng đồng Valorant văn minh, chuyên nghiệp.

> [!IMPORTANT]
> Việc tham gia vào hệ thống Clan đồng nghĩa với việc bạn đã đọc, hiểu và cam kết tuân thủ các quy định dưới đây. Mọi quyết định cuối cùng thuộc về **Ban Quản Trị (Mod)**.

---

## 💎 1. Khái Niệm Cơ Bản

Hệ thống Clan được vận hành bởi bot, đảm bảo tính công bằng và minh bạch tuyệt đối qua các chỉ số:
- **Clan**: Một tập hợp tối thiểu **5 thành viên** có cùng lý tưởng và mục tiêu.
- **Elo**: Chỉ số phản ánh trình độ của **cả Clan**. Không có Elo cá nhân.
- **Arena Dashboard**: Trung tâm tương tác tại kênh `#arena`, nơi bạn thực hiện mọi thao tác tra cứu và thách đấu.

### Các Vai Trò Trong Clan
| Vai Trò | Emoji | Quyền Hạn Chính |
| :--- | :---: | :--- |
| **Captain** | 👑 | Toàn quyền quản lý, mời/kick thành viên, đổi tên, giải tán clan. |
| **Vice Captain** | ⚔️ | Mời thành viên, tạo trận, thách đấu, yêu cầu mượn/chuyển người. |
| **Member** | 👥 | Tham gia thi đấu, báo cáo kết quả trận đấu, rời clan. |
| **Player** | 🎮 | Role tự động dành cho tất cả thành viên thuộc bất kỳ clan nào. |

---

## 🏗️ 2. Vòng Đời Của Một Clan

### 2.1. Khởi Tạo (Create)
Để tạo clan, bạn cần gõ lệnh `/clan create` hoặc bấm nút **Tạo Clan** tại `#arena`.
- **Yêu cầu**: Phải có role `Thiểu Năng Con`, không thuộc clan nào và không trong cooldown.
- **Nhân sự**: Bạn + 4 thành viên (Tổng 5). Cả 4 người phải xác nhận qua DM trong **48 giờ**.
- **Duyệt**: Sau khi đủ người, Mod sẽ xem xét và phê duyệt (Approve/Reject).

### 2.2. Hoạt Động (Active vs Inactive)
- **Active**: Clan có đủ ≥ 5 thành viên. Được phép thi đấu tính Elo.
- **Inactive**: Khi clan tụt xuống < 5 thành viên, hệ thống sẽ tạm khóa tính năng thi đấu cho đến khi có đủ người.

### 2.3. Thừa Kế & Giải Tán
- **Thừa kế**: Nếu Captain rời server, bot tự động đôn **Vice Captain** gia nhập sớm nhất lên thay. Nếu không có Vice, clan sẽ chuyển sang `Inactive`.
- **Giải tán**: Chỉ Captain hoặc Mod mới có quyền giải tán clan. Khi giải tán, các kênh chat và role riêng sẽ bị xóa.

---

## ⚔️ 3. Hệ Thống Thi Đấu

Hệ thống hỗ trợ 2 hình thức thi đấu chính:

### 3.1. Match Create (`/match create`)
Phù hợp cho các trận đấu tập nhanh. Một thành viên tạo trận -> đối thủ xác nhận -> đánh xong báo cáo kết quả.

### 3.2. Đại Chiến Clans (Challenge)
Đây là tính năng cao cấp cho các trận đấu chính thức:
1. **Thách đấu**: Gửi lời thách (BO1/BO3/BO5) qua Dashboard Arena.
2. **Chấp nhận**: Đối thủ đồng ý -> Bot tự tạo **1 kênh chat + 2 kênh voice** riêng biệt.
3. **Map Veto (Ban/Pick)**:
    - **Pool**: 12 bản đồ Valorant mới nhất.
    - **Ban Phase**: Mỗi bên ban 2 lượt (Tổng 8 map bị loại).
    - **Pick Phase**: Mỗi bên pick 1 map. Map còn lại (Decider) được chọn ngẫu nhiên.
    - **Side Pick**: Clan không pick map được chọn phe (Công/Thủ).
4. **Kết thúc**: Sau khi báo cáo kết quả, các kênh tạm thời sẽ bị xóa sau 5 phút.

---

## 📈 4. Luật Elo & Xếp Hạng

Hệ thống Elo của ClanVXT sử dụng thuật toán quốc tế (tương tự Chess/Valorant) để tính toán điểm số:

### Thông Số Kỹ Thuật
- **Điểm khởi đầu**: 1000 Elo.
- **Giai đoạn Xếp hạng (Placement)**: 10 trận đầu tiên (K=40) giúp xác định rank nhanh chóng.
- **Giai đoạn Ổn định (Stable)**: Sau 10 trận (K=32), điểm số sẽ biến động bền vững hơn.
- **Elo Sàn**: 100 Elo (Không bao giờ âm).

### Chống Cày Thuê (Anti-Farm)
Để tránh việc hai clan cố tình đánh nhau nhiều lần để buff điểm, Elo nhận được sẽ giảm dần trong vòng 24 giờ:
| Trận trong 24h | Tỉ lệ Elo nhận được |
| :---: | :--- |
| Trận 1 | 100% |
| Trận 2 | 70% |
| Trận 3 | 40% |
| Trận 4+ | 20% |

> [!TIP]
> Elo chỉ được áp dụng khi cả hai clan đều ở trạng thái **Active**. Nếu một clan bị Ban hoặc Frozen, trận đấu vẫn diễn ra nhưng Elo sẽ không thay đổi.

---

## 🔄 5. Nhân Sự & Luân Chuyển

| Tính Năng | Đối Tượng | Điều Kiện | Hậu Quả |
| :--- | :--- | :--- | :--- |
| **Loan (Mượn)** | 1-2 người | 3 bên đồng ý (2 Captain + Member) | Tối đa 7 ngày, cooldown 14 ngày sau khi trả. |
| **Transfer (Chuyển)** | 1 người | 3 bên đồng ý, clan cũ còn ≥ 5 người | Cấm thi đấu (Transfer Sickness) **3 ngày**. |
| **Leave/Kick** | Cá nhân | Không giới hạn | Chịu Cooldown **14 ngày** mới được vào clan mới. |

---

## 🛡️ 6. Nội Quy & Xử Phạt

### Các Hành Vi Nghiêm Cấm
1. **Clone/Smurf**: Sử dụng nhiều tài khoản để lách luật hoặc tham gia nhiều clan.
2. **Dàn xếp (Match Fixing)**: Cố tình thua hoặc thắng để thao túng Elo.
3. **Mạo danh**: Đặt tên clan hoặc đổi Riot ID giống Admin/Clan nổi tiếng để lừa đảo.
4. **Toxic/Harassment**: Xúc phạm đối thủ trong kênh chat trận đấu hoặc voice.

### Khung Hình Phạt
- **Cảnh cáo**: Cho các vi phạm nhẹ lần đầu.
- **Reset Elo**: Đưa Elo về 100 hoặc 1000 tùy mức độ.
- **Hủy tư cách Clan**: Giải tán clan và cấm các thành viên chủ chốt.
- **System Ban**: Cấm vĩnh viễn khỏi server và hệ thống clan.

> [!NOTE]
> Bạn có thể sử dụng lệnh `/report create` để tố cáo và `/appeal create` để kháng cáo trong vòng **7 ngày** kể từ khi nhận án phạt.

---

## 👤 7. Tự Động Dọn Dẹp & An Toàn Dữ Liệu

Khi một người rời khỏi server Discord, bot sẽ tự động xử lý để bảo vệ database:
- **Người mới (Không có lịch sử đấu)**: Xóa hoàn toàn dữ liệu.
- **Thành viên cũ (Có lịch sử đấu)**: Ẩn danh thành `DeletedUser#ID` để bảo toàn lịch sử Elo cho các clan họ từng đấu cùng.
- **Hủy yêu cầu**: Mọi yêu cầu loan, transfer hoặc bài đăng tìm clan đang treo sẽ bị hủy ngay lập tức.

---

*Quy chế này được cập nhật lần cuối vào ngày 17/02/2026. Hãy luôn theo dõi kênh thông báo để cập nhật những thay đổi mới nhất!*
