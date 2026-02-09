# 🛡️ THÔNG BÁO CHÍNH THỨC: HỆ THỐNG CLAN VÊ XÊ TÊ (VXT)

Chào toàn thể anh em, mình là **Nikko**.

Sau một quãng thời gian dài mày mò và phát triển, mình chính thức ra mắt Bot **VXT** – "quản gia" tự động cho hệ thống Clan của chúng ta. Đây là dự án mình tự học và tự làm, nên kinh nghiệm chưa nhiều. Vì dự án cần số lượng người đông mới test hết được lỗi, nên mình xin phép vận hành theo kiểu **"Vừa Production – Vừa Test"**.

Nếu bot có "hắt hơi sổ mũi" hay gặp lỗi, mong anh em thông cảm và báo ngay cho mình tại **@nikkosaigon** để mình sửa. Mình luôn **Open Mind** và trân trọng mọi ý tưởng của anh em!

---

### 🏰 1. BẮT ĐẦU VỚI CLAN (QUY ĐỊNH 5 NGƯỜI)

Hệ thống Clan VXT được thiết kế cho sự gắn kết đội nhóm lâu dài:

*   **Quy mô:** Một Clan chuẩn phải có **ít nhất 5 thành viên** (1 Captain + 4 Member). Bạn có thể tuyển thêm thoải mái sau khi đã thành lập.
*   **Quy trình tạo Clan:**
    *   Sử dụng lệnh `/clan create`.
    *   Bạn cần tag đủ 4 thành viên nòng cốt.
    *   **LƯU Ý:** Bot sẽ gửi **DM (Tin nhắn riêng)** cho 4 người này. Họ có **48 giờ** để bấm **[Accept]**. Nếu không đủ 4 người đồng ý, yêu cầu tạo Clan sẽ tự hủy. Nhớ nhắc đồng đội mở DM người lạ nhé!
*   **Trạng thái Inactive:** Nếu Clan rớt xuống dưới 5 người, hệ thống sẽ tự khóa các lệnh thi đấu cho đến khi bạn tuyển đủ người.

---

### ⚔️ 2. THI ĐẤU & THỨ HẠNG (ELO)

*   **Elo Khởi Điểm:** 1000 điểm.
*   **Tạo Trận:** Dùng `/match create`. Kết quả phải được bên đối thủ xác nhận qua nút bấm mới được tính điểm.
*   **Anti-Farm:** Đánh quá nhiều trận với cùng 1 Clan trong 24h sẽ bị giảm điểm nhận được (tránh trường hợp "bơm" Elo cho nhau).

---

### 👤 3. CHỨC VỤ & QUYỀN HẠN

Để hiểu rõ tất cả các lệnh mà bạn có thể dùng ứng với vai trò của mình, hãy luôn sử dụng lệnh:
👉 **`/clan help`** (Bot sẽ liệt kê các lệnh dành riêng cho bạn).

| Chức vụ | Quyền hạn tiêu biểu | Lệnh bổ nhiệm |
| :--- | :--- | :--- |
| 👑 **Captain** | Toàn quyền mời, kick, giải tán Clan. | `/clan promote_vice @user` |
| ⚔️ **Vice Captain** | Mời người, tạo trận, yêu cầu mượn quân (Loan). | N/A |
| 👥 **Member** | Tham gia trận đấu, rời Clan. | N/A |

---

### ⚠️ 4. LUẬT LỆ & KỶ LUẬT (CỰC KỲ QUAN TRỌNG)

Để giữ sân chơi công bằng, mình sẽ xử phạt rất nghiêm các hành vi sau:

1.  **Cooldown (Thời gian chờ) - 14 Ngày:** Khi rời Clan hoặc bị Kick, bạn phải chờ **14 ngày** mới được vào Clan mới. Đừng nhảy Clan lung tung!
2.  **Blacklist (Sổ đen):** Dành cho lỗi nhẹ (spam lệnh, báo kết quả sai cố ý). Bạn sẽ bị cấm tham gia mảng Clan của bot một thời gian.
3.  **System Ban (Ban vĩnh viễn):** Gian lận Elo, dùng Acc Clone (mỗi người chỉ 1 acc Discord), lách luật Cooldown. Hình phạt là **xóa vĩnh viễn** khỏi hệ thống Clan.

---

### ❓ 5. PHẦN Q&A (HỎI ĐÁP NHANH)

**Q: Tại sao tạo Clan lại cần tới 5 người ngay từ đầu?**
**A:** Đây là tiêu chuẩn để đảm bảo Clan có đủ nhân lực thi đấu ổn định và tránh tình trạng tạo "Clan rác" chiếm tên.

**Q: Làm sao để tôi biết mình có thể dùng những lệnh nào?**
**A:** Rất đơn giản, bạn chỉ cần gõ **`/clan help`**. Bot sẽ tự động nhận diện bạn là Captain, Vice Captain hay Member để hiển thị bảng hướng dẫn phù hợp nhất cho bạn.

**Q: Tại sao tôi không nhận được DM xác nhận của Bot?**
**A:** Bạn hãy kiểm tra lại cài đặt Privacy của Discord (Cho phép tin nhắn từ thành viên cùng server) hoặc kiểm tra xem có vô tình chặn Bot không nhé.

**Q: Tôi có thể mượn người từ Clan khác để đánh giải không?**
**A:** Có! Sử dụng lệnh `/loan request`. Tuy nhiên bạn chỉ được mượn tối đa 1 người và trong tối đa 7 ngày. Sau khi trả người, cả 2 bên sẽ chịu cooldown 14 ngày.

**Q: Làm sao để mời thêm người thứ 6, 7...?**
**A:** Captain hoặc Vice dùng `/clan invite @user`. Người đó chỉ cần bấm Accept trong DM là vào thẳng Clan (không cần Mod duyệt lại).

**Q: Nếu tôi bị phạt Cooldown, có cách nào xin giảm không?**
**A:** Cooldown 14 ngày là tự động để đảm bảo tính ổn định. Admin chỉ can thiệp nếu đó là lỗi do Bot. Hãy cân nhắc kỹ trước khi rời Clan!

---

🤝 **Nikko:** Mọi báo cáo lỗi hoặc góp ý xin gửi về **@nikkosaigon**. Cảm ơn mọi người đã cùng mình xây dựng cộng đồng VXT!
