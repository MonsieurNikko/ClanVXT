# Feature Upgrade Request — Clan Challenge (Valorant) “ĐẠI CHIẾN CLANS”
> ✅ **TRẠNG THÁI: ĐÃ TRIỂN KHAI THÀNH CÔNG (v1.3.0)**
> Shared repo rules apply: minimal changes, no push, reuse existing logic.

---

## 0) IMPORTANT RULE (Must follow)
- Đây là **nâng cấp lệnh thách đấu hiện có**, **KHÔNG phải lệnh mới**.
- Hãy xem qua code hiện tại để hiểu logic hoạt động cũng như các file md để tránh sai sót.
- Nâng cấp này sẽ được làm trong file mới kế bên file logic có lệnh thách đấu hiện tại.
- Hiện tại flow của lệnh thách đấu đang là:
  1) Clan A gửi lời mời thách đấu Clan B  
  2) Clan B đồng ý → bot thông báo đã đồng ý  
  3) Bot gửi embed “⚔️ Trận đấu đang diễn ra” + các nút để báo cáo kết quả  
  4) 2 clan báo cáo kết quả → bot cộng ELO theo logic hiện tại
- Yêu cầu nâng cấp: **giữ nguyên các bước và logic hiện tại**, chỉ **chèn thêm** vào giữa:
  - Tạo room voice + room chat
  - Ban/Pick map
- Mọi thứ phải **đồng bộ 100% với logic hiện tại**:
  - Không đổi cách invite/accept đang hoạt động
  - Không đổi embed “trận đang diễn ra” + nút báo kết quả
  - Không đổi cộng ELO / xác nhận kết quả
  - Chỉ bổ sung các bước mới với minimal diff

---

## 1) Context (Current behavior)
Bot hiện tại có tính năng **thách đấu giữa 2 clan**:
1) Clan A gửi lời mời thách đấu đến Clan B  
2) Khi **Clan B đồng ý**, bot thông báo “đã đồng ý”  
3) Bot gửi embed “⚔️ Trận đấu đang diễn ra” + các nút báo kết quả  
4) Sau trận, 2 clan bấm nút báo kết quả → bot cộng ELO theo logic hiện tại

---

## 2) Goal (Upgrade)
Sau khi 2 clan đồng ý thách đấu, bot phải:
1) **Tạo 2 voice + 1 text channel riêng cho trận**
2) **Dùng role clan có sẵn** trong Discord để set permission (**không tạo role tạm**)
3) **Gửi thông báo vào phòng chat riêng của từng clan**, kèm link dẫn tới:
   - Voice channel của clan đó
   - Text channel match (chung)
4) Trong text channel match, bot chạy **ban/pick map theo luật “ĐẠI CHIẾN CLANS”**
5) Chỉ khi ban/pick hoàn tất → mới tiếp tục flow cũ: embed “⚔️ Trận đấu đang diễn ra” + nút báo kết quả (reuse code hiện tại)
6) Kết thúc → bot thông báo và **sau 5 phút xoá 1 text + 2 voice channel** vừa tạo

---

## 3) Hard Rules / Constraints (Non-negotiable)
- Repo/team code: **không rewrite** phần đang hoạt động.
- Chỉ sửa đúng phạm vi liên quan lệnh thách đấu & map flow.
- **Không đổi** logic báo kết quả / cộng ELO / xác nhận kết quả hiện tại (reuse nguyên).
- Trước khi sửa: **đọc kỹ các file `.md` trong repo** (README, docs, rules, conventions).
- **Không push** (git push) nếu không có yêu cầu rõ ràng.
- Không force push, không sửa history.

---

## 4) Required Investigation (Gate — MUST PASS before any coding)
### A) Clan role resolution evidence (NO guessing)
Output bắt buộc có:
- File path
- Function/class/block resolve clan role
- Nếu mapping/config: chỉ rõ file dữ liệu + key structure  
> Không tìm thấy → DỪNG, không đoán theo string.

### B) Clan chat channel resolution evidence (NO guessing)
Output bắt buộc có:
- File path
- Function/class/block resolve clan chat channel
- Nếu mapping/config: chỉ rõ file dữ liệu + key structure  
> Không tìm thấy → DỪNG, không hardcode naming.

Gate thiếu 1 trong 2 evidence → **không được code**.

---

## 5) New Flow (Insert between “Accept” and “Match in progress”)

### 5.1 Invite + Accept (giữ như hiện tại)
- Clan A thách đấu Clan B
- Clan B đồng ý
- Bot thông báo “đã đồng ý” (như hiện tại)

### 5.2 INSERT: Auto Create Match Rooms + Notify clan channels

#### 5.2.1 Create channels
- Tạo **2 voice channels**:
  - `🎧 Match - <ClanA>`
  - `🎧 Match - <ClanB>`
- Tạo **1 text channel**:
  - `📌 match-<ClanA>-vs-<ClanB>`

#### 5.2.2 Visibility + Permissions (UPDATED per requirement)
**Mọi người đều nhìn thấy (VIEW) cả voice và text**, nhưng chỉ 2 clan mới được “tham gia/ tương tác”.

##### Voice channels (public visible, restricted join)
- @everyone:
  - Allow: `View Channel` = ✅
  - Deny: `Connect` = ❌
  - (Optional) Deny: `Speak` = ❌ (phòng trường hợp connect bị mở nhầm)
- Clan role tương ứng:
  - Voice A: `role_clanA` allow `Connect` ✅ + `Speak` ✅
  - Voice B: `role_clanB` allow `Connect` ✅ + `Speak` ✅
- Bot/admin: full permissions

=> Kết quả: ai cũng thấy kênh, nhưng **chỉ đúng clan mới join được**.

##### Text match channel (public visible, restricted interaction)
- @everyone:
  - Allow: `View Channel` = ✅
  - Deny: `Send Messages` = ❌
  - Deny: `Add Reactions` = ❌
  - Deny: `Create Public Threads`/`Create Private Threads` = ❌ (nếu dùng threads)
- Clan roles (A & B):
  - Allow: `View Channel` = ✅
  - Deny/Allow theo mục tiêu:
    - **Không chat**: `Send Messages` = ❌
    - **Nhưng vẫn tương tác được với bot**:
      - Bot sẽ dùng button/select menu; user vẫn click được dù không có Send Messages.
      - Nếu implementation cần phản hồi ephemeral thì vẫn ok.
- Bot/admin:
  - Allow: `Send Messages` ✅, `Manage Messages` ✅, `Embed Links` ✅, v.v.

=> Kết quả: ai cũng thấy room chat, người ngoài **chỉ xem**, 2 clan **chỉ bấm nút/select của bot** (không chat).

#### 5.2.3 MUST use existing clan roles
- `role_clanA` và `role_clanB` phải resolve bằng logic hiện tại (Gate).
- Không tạo role tạm.

#### 5.2.4 Notify each clan’s clan-chat channel (NEW)
Ngay khi tạo xong channels, bot gửi tin nhắn vào clan chat channel của từng clan:
- Nội dung có:
  - thông báo room đã tạo
  - link tới voice clan đó
  - link tới text match room
- Ví dụ:
  - `🔔 Match Ready: <ClanA> vs <ClanB>`
  - `🎧 Voice của clan bạn: <#voice_channel_id>`
  - `📌 Room trận: <#match_text_channel_id>`

---

## 6) Map Phase — BAN/PICK “ĐẠI CHIẾN CLANS” (12 map pool)

### 6.1 Setup (Pool + message)
- Pool 12 map, khai báo 1 chỗ duy nhất (constant/config).
- Trong text room match, bot gửi **1 embed cố định** và edit liên tục:
  - Remaining maps
  - Bans A/B
  - Picks A/B
  - Turn + clan tới lượt + số lượng cần chọn
- UI:
  - Select menu (multi cho ban 2; single cho pick 1)
  - `✅ Confirm`
  - `🔁 Reset turn`
  - `❌ Cancel match`

### 6.2 Turn ownership
- Chỉ user thuộc role clan tương ứng (hoặc leader/đại diện theo logic hiện tại) mới thao tác khi tới lượt.
- Sai lượt → bot từ chối.

### 6.3 Ban Phase (8 bans, 2-2-2-2)
- Turn 1: A ban 2
- Turn 2: B ban 2
- Turn 3: A ban 2
- Turn 4: B ban 2

### 6.4 Pick Phase (2 picks)
- Remaining còn 4
- Turn 5: A pick 1
- Turn 6: B pick 1
- Remaining còn 2

### 6.5 Random Map 3
- Random 1 trong 2 map còn lại
- Hiển thị minh bạch candidates + kết quả

### 6.6 Summary + Transition
- Embed tổng kết: bans/picks/random
- Chỉ khi completed → tiếp tục flow cũ

---

## 7) CONTINUE EXISTING FLOW: Match In Progress + Report Result (reuse code hiện tại)
- Bot gửi embed “⚔️ Trận đấu đang diễn ra” + nút báo kết quả
- Báo cáo → xác nhận thắng → cộng ELO như hiện tại

---

## 8) Cleanup after 5 minutes
- Thông báo sẽ xoá sau 5 phút
- Xoá 1 text + 2 voice channels

---

## 9) Data / State Requirements (must persist)
- match_id
- clanA_id, clanB_id
- role IDs (existing)
- clan chat channel IDs (existing)
- created channel IDs
- map state (remaining/bans/picks/random)
- status + timestamps

---

## 10) Timeout / Fail-safe
- Timeout mỗi lượt 3–5 phút
- Nhắc 1 lần
- Quá thêm thời gian: cancel+cleanup (ưu tiên) hoặc auto-random (chọn 1)

---

## 11) Acceptance Criteria (UPDATED visibility/interaction)
- [ ] Voice & text channels: @everyone **View ✅**, nhưng:
  - [ ] Voice: @everyone **Connect ❌**, chỉ clan role đúng mới Connect ✅
  - [ ] Text: @everyone **Send ❌**, chỉ 2 clan được tương tác qua bot components
- [ ] Gate evidence đầy đủ (role + clan channel resolution)
- [ ] Ban/pick đúng 12 pool, ban 2-2-2-2, pick 1-1, random map3
- [ ] Chỉ khi ban/pick done mới gửi “match in progress” (flow cũ)
- [ ] Result/ELO không đổi logic
- [ ] Cleanup sau 5 phút xoá đúng 3 channels
- [ ] Timeout không để kẹt match

---

## 12) Output you must provide (when implementing)
1) `.md` conventions summary
2) Evidence resolve role + clan chat channel (file + function)
3) Plan minimal diff
4) Patch/diff
5) Manual test cases (happy path + sai lượt + timeout + cleanup)
