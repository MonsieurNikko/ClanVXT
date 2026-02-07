# 📖 QUY CHẾ HỆ THỐNG CLAN - BẢN ĐẦY ĐỦ

> *Tài liệu này dành cho những ai muốn hiểu rõ cách hệ thống hoạt động. Nếu bạn chỉ cần biết cách chơi, hãy đọc file `DISCORD_RULES.md`.*

---

## MỤC LỤC

1. [Giới thiệu](#1-giới-thiệu)
2. [Quy định tài khoản](#2-quy-định-tài-khoản)
3. [Cấu trúc Clan](#3-cấu-trúc-clan)
4. [Quy trình tạo Clan](#4-quy-trình-tạo-clan)
5. [Trạng thái Clan](#5-trạng-thái-clan)
6. [Hệ thống Elo](#6-hệ-thống-elo)
7. [Thi đấu](#7-thi-đấu)
8. [Cho mượn (Loan)](#8-cho-mượn-loan)
9. [Chuyển nhượng (Transfer)](#9-chuyển-nhượng-transfer)
10. [Xử phạt & Kháng cáo](#10-xử-phạt--kháng-cáo)
11. [Bảng tham chiếu](#11-bảng-tham-chiếu)

---

## 1. GIỚI THIỆU

Hệ thống Clan là nền tảng quản lý đội thi đấu trong server, được thiết kế để:
- Tổ chức các trận đấu custom giữa các clan
- Theo dõi xếp hạng qua hệ thống Elo
- Đảm bảo tính công bằng và minh bạch

**Nguyên tắc cốt lõi:**
- Mỗi người = 1 tài khoản = 1 clan
- Elo thuộc về clan, không phải cá nhân
- Mọi hoạt động đều được ghi log

---

## 2. QUY ĐỊNH TÀI KHOẢN

### 2.1. Đăng ký hệ thống
- **Bắt buộc:** Gõ `/clan register` trước khi tham gia bất kỳ clan nào
- **Yêu cầu:** Phải có role `Thiểu Năng Con` trong server
- **Riot ID:** Phải khai báo Riot ID thật (ví dụ: `TênBạn#VN1`), cấm dùng smurf

### 2.2. Giới hạn
| Quy định | Chi tiết |
|----------|----------|
| Số tài khoản Discord | 1 duy nhất |
| Số clan cùng lúc | 1 duy nhất |
| Riot ID | 1 duy nhất, phải là tài khoản chính |

### 2.3. Cooldown (Thời gian chờ)
Cooldown là khoảng thời gian bạn không thể thực hiện một số hành động sau khi rời clan.

| Sự kiện | Thời gian chờ | Áp dụng cho |
|---------|---------------|-------------|
| Rời clan tự nguyện | 14 ngày | Người rời |
| Bị kick | 14 ngày | Người bị kick |
| Kết thúc loan | 14 ngày | Người được mượn + 2 clan |
| Transfer | 30 ngày | Người được chuyển (không transfer tiếp) |

---

## 3. CẤU TRÚC CLAN

### 3.1. Các vai trò

**👑 Captain (Đội trưởng)**
- Số lượng: 1 người/clan
- Quyền hạn đầy đủ: invite, kick, promote, demote, match, loan, transfer
- Trách nhiệm: Chịu trách nhiệm chính về mọi hoạt động của clan

**⚔️ Vice Captain (Phó đội trưởng)**
- Số lượng: Không giới hạn
- Quyền hạn: invite, match, loan, transfer
- Giới hạn: KHÔNG được kick thành viên

**👥 Member (Thành viên)**
- Quyền: Tham gia trận đấu, xác nhận kết quả, rời clan
- Không có quyền quản lý

### 3.2. Phân quyền chi tiết

| Hành động | Captain | Vice | Member |
|-----------|:-------:|:----:|:------:|
| Mời thành viên | ✅ | ✅ | ❌ |
| Kick thành viên | ✅ | ❌ | ❌ |
| Promote Vice | ✅ | ❌ | ❌ |
| Demote Vice | ✅ | ❌ | ❌ |
| Tạo trận đấu | ✅ | ✅ | ✅ |
| Report kết quả | Chỉ người tạo trận | | |
| Confirm/Dispute | ✅ | ✅ | ✅ |
| Loan request | ✅ | ✅ | ❌ |
| Transfer request | ✅ | ✅ | ❌ |

---

## 4. QUY TRÌNH TẠO CLAN

### 4.1. Điều kiện của Captain
- Đã đăng ký trong hệ thống (`/clan register`)
- Có role `Thiểu Năng Con`
- Không thuộc clan nào
- Không trong thời gian cooldown
- Không bị System Ban

### 4.2. Quy trình

```
Bước 1: /clan create
        └── Nhập tên clan + tag 5 thành viên

Bước 2: Hệ thống gửi lời mời tới 5 người
        └── Mỗi người nhận thông báo Accept/Decline

Bước 3: Chờ 5 người Accept
        └── Thời hạn: 48 giờ
        └── Nếu không đủ → Yêu cầu tự hủy

Bước 4: Clan chuyển sang trạng thái "Chờ duyệt"
        └── Mod nhận thông báo

Bước 5: Mod duyệt
        └── Approve: Bot tạo role + channel riêng
        └── Reject: Yêu cầu bị từ chối (có ghi lý do)
```

### 4.3. Quy định đặt tên
- **Cấm:** Trùng tên, nhái tên, nội dung không phù hợp, giả mạo admin
- **Khuyến khích:** Tên ngắn gọn, dễ nhớ, thể hiện bản sắc đội

---

## 5. TRẠNG THÁI CLAN

| Trạng thái | Điều kiện | Được phép |
|------------|-----------|-----------|
| **WAITING_ACCEPT** | Đang chờ 5 người accept | Không có |
| **PENDING_APPROVAL** | Đủ accept, chờ Mod | Không có |
| **ACTIVE** | ≥5 thành viên, được duyệt | Tất cả tính năng |
| **INACTIVE** | <5 thành viên | Không thi đấu, không tính Elo |
| **FROZEN** | Bị Mod đóng băng | Thi đấu được, không tính Elo |
| **DISBANDED** | Giải tán bởi Captain/Mod | Không hoạt động |
| **BANNED** | Bị cấm hệ thống | Hoàn toàn không hoạt động |

**Lưu ý:** Clan tự động chuyển INACTIVE ↔ ACTIVE khi số thành viên thay đổi qua ngưỡng 5 người.

---

## 6. HỆ THỐNG ELO

### 6.1. Thông số cơ bản
| Thông số | Giá trị |
|----------|---------|
| Elo khởi điểm | 1000 |
| K-Factor | 24 |
| Placement matches | 10 trận đầu |

### 6.2. Công thức tính

**Bước 1:** Tính Expected Score (xác suất thắng dự kiến)
```
Expected = 1 / (1 + 10^((Elo_đối_thủ - Elo_mình) / 400))
```

**Bước 2:** Tính Elo thay đổi
```
Delta = round(24 × (Kết_quả - Expected))
```
- Kết_quả = 1 nếu thắng, 0 nếu thua

**Ví dụ:**
- Clan A (1000 Elo) thắng Clan B (1200 Elo)
- Expected A = 1 / (1 + 10^(200/400)) = 0.24
- Delta = round(24 × (1 - 0.24)) = +18 Elo

### 6.3. Cơ chế Anti-Farm

Để ngăn việc 2 clan spam trận với nhau, Elo giảm dần theo số trận trong 24h:

| Trận # (trong 24h) | Hệ số | Elo thực nhận |
|--------------------|-------|---------------|
| Trận 1 | 100% | +18 → +18 |
| Trận 2 | 70% | +18 → +13 |
| Trận 3 | 40% | +18 → +7 |
| Trận 4+ | 20% | +18 → +4 |

### 6.4. Điều kiện áp dụng Elo
Elo CHỈ được tính khi:
- Trận được **Confirm** bởi đối thủ, HOẶC
- Trận được **Resolve** bởi Mod
- **Cả 2 clan** đều ở trạng thái ACTIVE

---

## 7. THI ĐẤU

### 7.1. Tạo trận
```
/match create <tên_clan_đối> [ghi_chú]
```
- Ai cũng có thể tạo (Captain, Vice, Member)
- Trận được tạo nhân danh clan của người tạo

### 7.2. Luồng xử lý

```
CREATED ──[Report winner]──► REPORTED ──[Confirm]──► CONFIRMED ──► Elo áp dụng
    │                            │
    │                            └──[Dispute]──► DISPUTE ──[Mod resolve]──► RESOLVED
    │
    └──[Cancel]──► CANCELLED
```

### 7.3. Quyền thao tác
| Hành động | Ai được làm |
|-----------|-------------|
| Report kết quả | CHỈ người tạo trận |
| Cancel trận | CHỈ người tạo (trước khi report) |
| Confirm kết quả | Bất kỳ thành viên clan đối thủ |
| Dispute kết quả | Bất kỳ thành viên clan đối thủ |
| Resolve dispute | CHỈ Mod |

---

## 8. CHO MƯỢN (LOAN)

### 8.1. Mục đích
Cho phép clan mượn tạm thành viên từ clan khác để đủ người đánh trận.

### 8.2. Điều kiện

| Điều kiện | Chi tiết |
|-----------|----------|
| Sự đồng ý | 3 bên: Clan cho mượn + Clan mượn + Thành viên |
| Giới hạn | Mỗi clan chỉ cho mượn/mượn 1 người cùng lúc |
| Thời hạn | Tối đa 7 ngày |
| Thời gian chờ accept | 48 giờ |

### 8.3. Luồng xử lý

```
REQUESTED ──[3 bên Accept]──► ACTIVE ──[Hết hạn/Hủy]──► ENDED
     │
     └──[Cancel/Timeout]──► CANCELLED
```

### 8.4. Sau khi kết thúc
- Thành viên trở về clan gốc
- Cooldown 14 ngày áp dụng cho: thành viên đó + clan cho mượn + clan mượn

### 8.5. Lệnh
| Lệnh | Mô tả |
|------|-------|
| `/loan request <@member> <clan> <days>` | Tạo yêu cầu |
| `/loan status [id]` | Xem trạng thái |
| `/loan cancel <id>` | Hủy yêu cầu |

---

## 9. CHUYỂN NHƯỢNG (TRANSFER)

### 9.1. Mục đích
Chuyển vĩnh viễn thành viên từ clan này sang clan khác.

### 9.2. Điều kiện

| Điều kiện | Chi tiết |
|-----------|----------|
| Sự đồng ý | 3 bên: Clan nguồn + Clan đích + Thành viên |
| Clan nguồn | Phải còn ≥5 người sau khi chuyển |
| Clan đích | Phải đang ACTIVE |
| Thời gian chờ accept | 48 giờ |

### 9.3. Hậu quả sau chuyển nhượng

| Hậu quả | Thời gian |
|---------|-----------|
| Transfer Sickness (cấm thi đấu) | 72 giờ (3 ngày) |
| Cooldown rời clan mới | 14 ngày |
| Cooldown transfer tiếp | 30 ngày |

### 9.4. Lệnh
| Lệnh | Mô tả |
|------|-------|
| `/transfer request <@member> <clan>` | Tạo yêu cầu |
| `/transfer status [id]` | Xem trạng thái |
| `/transfer cancel <id>` | Hủy yêu cầu |

---

## 10. XỬ PHẠT & KHÁNG CÁO

### 10.1. Các hành vi vi phạm

**Gian lận tài khoản:**
- Dùng nhiều tài khoản Discord
- Khai sai Riot ID, dùng smurf
- Giả mạo danh tính

**Gian lận Elo:**
- Dàn xếp kết quả
- Farm Elo với clan đồng minh
- Lợi dụng loan để boost

**Vi phạm khác:**
- Quấy rối, toxic
- Tạo clan rác, chiếm tên

### 10.2. Các mức xử phạt

| Mức độ | Hình phạt |
|--------|-----------|
| Nhẹ | Cảnh cáo (Warning) |
| Trung bình | Rollback Elo + Cấm thi đấu có thời hạn |
| Nặng | Reset Elo về 1000 + Kick khỏi clan |
| Rất nặng | Giải tán clan |
| Nghiêm trọng | System Ban (cấm vĩnh viễn) |

### 10.3. Quy trình Report

```
/report create <loại> <đối_tượng> <mô_tả> [bằng_chứng]
```

- Loại: `user`, `clan`, hoặc `match`
- Mỗi report tạo thành 1 Case
- Mod sẽ xem xét và ra quyết định

### 10.4. Kháng cáo

```
/appeal create <case_id> <lý_do> [bằng_chứng_mới]
```

| Quy định | Chi tiết |
|----------|----------|
| Thời hạn | 7 ngày kể từ khi bị phạt |
| Số lần | 1 lần duy nhất |
| Kết quả | Giữ nguyên / Giảm án / Hủy án |

---

## 11. BẢNG THAM CHIẾU

### 11.1. Tất cả lệnh người dùng

| Lệnh | Mô tả | Quyền |
|------|-------|-------|
| `/clan register` | Đăng ký hệ thống | Ai cũng được |
| `/clan create` | Tạo clan mới | Chưa có clan |
| `/clan info [clan]` | Xem thông tin | Ai cũng được |
| `/clan leave` | Rời clan | Member+ |
| `/clan accept` | Chấp nhận lời mời | Có pending |
| `/clan decline` | Từ chối lời mời | Có pending |
| `/clan invite <user>` | Mời thành viên | Captain/Vice |
| `/clan kick <user>` | Kick thành viên | Captain |
| `/clan promote_vice <user>` | Bổ nhiệm Vice | Captain |
| `/clan demote_vice <user>` | Thu hồi Vice | Captain |
| `/match create <clan>` | Tạo trận | Member+ |
| `/loan request ...` | Cho mượn người | Captain/Vice |
| `/loan status [id]` | Xem loan | Ai cũng được |
| `/loan cancel <id>` | Hủy loan | Initiator |
| `/transfer request ...` | Chuyển người | Captain/Vice |
| `/transfer status [id]` | Xem transfer | Ai cũng được |
| `/transfer cancel <id>` | Hủy transfer | Initiator |
| `/report create ...` | Báo cáo | Ai cũng được |
| `/appeal create ...` | Kháng cáo | Người bị phạt |

### 11.2. Tất cả thông số

| Thông số | Giá trị |
|----------|---------|
| Thời gian chờ tạo clan | 48 giờ |
| Số thành viên tối thiểu | 5 người |
| Cooldown join/leave | 14 ngày |
| Thời hạn loan tối đa | 7 ngày |
| Cooldown loan | 14 ngày |
| Cooldown transfer | 30 ngày |
| Transfer sickness | 72 giờ |
| Elo khởi điểm | 1000 |
| K-Factor | 24 |
| Thời hạn kháng cáo | 7 ngày |

---

> 📅 **Phiên bản:** 2.0  
> 🤖 **Hệ thống:** ClanVXT Bot  
> 📝 **Cập nhật:** Tháng 2/2026
