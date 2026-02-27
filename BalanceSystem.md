# Balance System — Implementation Plan

> **9 features** để cân bằng hệ thống clan, giải quyết cả vấn đề hiện tại (clan quá mạnh) lẫn tương lai.

---

## Tổng Quan Features

| # | Feature | Mục đích |
|---|---------|----------|
| 1 | **Recruitment Cap** (1/tuần, trừ clan mới) | Ngăn hút talent quá nhanh |
| 2 | **Elo Decay** (>1050, -15/tuần) | Phạt không hoạt động |
| 3 | **Win Rate Modifier** (>70% → giảm gain) | Tự cân bằng clan dominant |
| 4 | **Activity Bonus** (+10 cho clan <1000 đánh ≥3/tuần) | Khuyến khích clan yếu |
| 5 | **Underdog Bonus** (+5~10 khi clan yếu thắng mạnh) | Thưởng upset |
| 6 | **Mandatory Rank Declaration** (Select Menu khi join) | Minh bạch, anti-fake, cơ sở cho F7/F8/F9 |
| 7 | **Rank Cap** (max 5 Immortal 2+ per clan) | Ngăn stacking trực tiếp |
| 8 | **Rank Elo Modifier** (roster avg rank → modifier) | Cân bằng skill chênh lệch |
| 9 | **Match Roster Declaration** (khai roster trước đấu) | Elo tính theo roster thực tế |

---

## Feature 1 — Recruitment Cap (1 người/tuần, trừ clan mới)

### Logic
- Clan **active** đã có ≥1 trận → max **1 invite/recruit thành công** mỗi 7 ngày
- Clan **mới** (0 trận `matches_played`) → không giới hạn

### Cách kiểm tra
Đếm `invite_requests` có `status='accepted'` + `responded_at` trong 7 ngày gần nhất cho clan đó.

### Config
```python
RECRUITMENT_CAP_PER_WEEK: int = 1       # Max invite/recruit thành công per 7 days
RECRUITMENT_CAP_EXEMPT_MATCHES: int = 0 # Clan với matches_played <= giá trị này → miễn cap
```

### DB Changes (`services/db.py`)
```python
async def count_recent_accepted_invites(clan_id: int, days: int = 7) -> int:
    """
    Đếm số invite_requests có status='accepted' 
    VÀ responded_at trong N ngày gần nhất cho clan.
    Dùng cho Recruitment Cap check.
    """
```

> **Lưu ý**: Dùng `responded_at` thay vì `created_at` vì ta muốn tính thời điểm người đó thực sự join.

### Code Changes (`cogs/clan.py`)
- **Vị trí**: `clan_invite()` (L1307) và `clan_recruit()` (L1442)
- Thêm check **SAU** validate clan active, **TRƯỚC** tạo invite:

```python
# --- Recruitment Cap Check ---
clan = await db.get_clan_by_id(clan_data["id"])
if clan and clan["matches_played"] > config.RECRUITMENT_CAP_EXEMPT_MATCHES:
    recent_count = await db.count_recent_accepted_invites(clan_data["id"], days=7)
    if recent_count >= config.RECRUITMENT_CAP_PER_WEEK:
        await interaction.response.send_message(
            f"❌ Clan đã đạt giới hạn tuyển quân ({config.RECRUITMENT_CAP_PER_WEEK} thành viên/tuần)."
            f" Vui lòng đợi đến tuần sau.",
            ephemeral=True
        )
        return
```

### ⚠️ Lưu ý
- Check ở thời điểm **GỬI** invite, không phải lúc ACCEPT (tránh UX tệ)
- KHÔNG sửa `handle_invite_accept()`

---

## Feature 2 — Elo Decay (>1050, -15/tuần)

### Logic
- Mỗi tuần, clan **active** có Elo **>1050** và **KHÔNG** đánh trận nào → trừ **15 Elo**
- Elo sàn decay = **1000** (không trừ dưới 1000)
- Gửi thông báo vào channel riêng clan

### Config
```python
ELO_DECAY_THRESHOLD: int = 1050     # Elo tối thiểu để bắt đầu decay
ELO_DECAY_AMOUNT: int = 15          # Elo trừ mỗi tuần không hoạt động
ELO_DECAY_FLOOR: int = 1000         # Elo sàn cho decay
```

### DB Changes (`services/db.py`)
```python
async def get_clans_for_decay(threshold: int = 1050) -> List[Dict]:
    """
    Lấy all active clans có elo > threshold 
    VÀ KHÔNG có match nào (confirmed/resolved) trong 7 ngày gần nhất.
    
    Query:
    SELECT c.* FROM clans c
    WHERE c.status = 'active' AND c.elo > ?
    AND c.id NOT IN (
        SELECT DISTINCT m.clan_a_id FROM matches m 
        WHERE m.status IN ('confirmed','resolved') AND m.created_at >= ?
        UNION
        SELECT DISTINCT m.clan_b_id FROM matches m 
        WHERE m.status IN ('confirmed','resolved') AND m.created_at >= ?
    )
    """

async def apply_elo_decay(clan_id: int, amount: int, floor: int = 1000) -> Dict:
    """
    Trừ Elo cho clan, enforce floor.
    Ghi vào elo_history với reason='decay'.
    Returns: {old_elo, new_elo, change}
    """
```

### Background Task (`main.py`)
```python
@tasks.loop(minutes=10)
async def weekly_balance_task():
    """Chạy mỗi 10 phút, check nếu 7 ngày đã qua kể từ last run."""
    # Check last_weekly_run trong system_settings
    # Nếu >= 7 ngày:
    #   1. Elo Decay 
    #   2. Activity Bonus (Feature 4)
    #   3. Update last_weekly_run
```

### ⚠️ Lưu ý
- **KHÔNG** dùng `@tasks.loop(hours=168)` — bot restart sẽ reset timer
- Thay vào đó: lưu `last_weekly_run` vào `system_settings`, check mỗi 10 phút
- **KHÔNG** decay clan `inactive` hoặc `disbanded`

---

## Feature 3 — Win Rate Modifier (>70% → giảm gain)

### Logic
Win rate từ **10 trận gần nhất** (confirmed/resolved). Áp dụng **PER CLAN** riêng biệt.

| Win Rate | Elo thắng nhân | Elo thua nhân |
|----------|---------------|---------------|
| ≤ 70% | x1.0 | x1.0 |
| 71-80% | x0.8 | x1.2 |
| 81-90% | x0.6 | x1.4 |
| 91%+ | x0.5 | x1.5 |

### DB Changes (`services/db.py`)
```python
async def get_clan_win_rate(clan_id: int, last_n: int = 10) -> Dict:
    """
    Tính win rate của clan từ N trận gần nhất (confirmed/resolved).
    
    Returns: {
        'total': int,        # tổng trận (có thể < last_n)
        'wins': int,
        'losses': int,
        'win_rate': float    # 0.0 - 1.0
    }
    
    Query: matches WHERE (clan_a_id=? OR clan_b_id=?) 
           AND status IN ('confirmed','resolved')
           ORDER BY created_at DESC LIMIT ?
    """
```

### Elo Changes (`services/elo.py`)
```python
def get_win_rate_modifier(win_rate: float, total_matches: int) -> float:
    """
    If total_matches < 5: return 1.0 (chưa đủ data).
    """
    if total_matches < 5:
        return 1.0
    if win_rate > 0.9: return 0.5
    if win_rate > 0.8: return 0.6
    if win_rate > 0.7: return 0.8
    return 1.0
```

Sửa `apply_match_result()` — **SAU** anti-farm multiplier (L258-259), **TRƯỚC** new_elo (L262-263):

```python
# --- Win Rate Modifier (per clan) ---
wr_a = await db.get_clan_win_rate(clan_a_id, last_n=10)
wr_b = await db.get_clan_win_rate(clan_b_id, last_n=10)

mod_a = get_win_rate_modifier(wr_a["win_rate"], wr_a["total"])
mod_b = get_win_rate_modifier(wr_b["win_rate"], wr_b["total"])

# Khi thắng → nhân modifier; khi thua → nhân inverse (2.0 - mod)
if final_delta_a > 0:  # clan A win
    final_delta_a = round(final_delta_a * mod_a)
    final_delta_b = round(final_delta_b * (2.0 - mod_b))
else:  # clan A lose
    final_delta_a = round(final_delta_a * (2.0 - mod_a))
    final_delta_b = round(final_delta_b * mod_b)
```

### ⚠️ Lưu ý
- Tính **chính xác từ DB** tại thời điểm `apply_match_result()`, KHÔNG cache
- **KHÔNG** include trận hiện tại (chưa commit) trong query
- Nếu match bị rollback → win rate tự cập nhật ở trận tiếp

---

## Feature 4 — Activity Bonus (+10 Elo cho clan <1000 đánh ≥3 trận/tuần)

### Logic
- Clan **active** có Elo **<1000** và đánh **≥3 trận** (confirmed/resolved) trong tuần → +10 Elo
- Gửi thông báo vào channel clan

### Config
```python
ACTIVITY_BONUS_ELO_CEILING: int = 1000   # Chỉ clan dưới Elo này
ACTIVITY_BONUS_MIN_MATCHES: int = 3      # Ít nhất N trận/tuần
ACTIVITY_BONUS_AMOUNT: int = 10          # Bonus Elo
```

### DB Changes (`services/db.py`)
```python
async def get_clans_for_activity_bonus(elo_ceiling: int, min_matches: int) -> List[Dict]:
    """
    Lấy active clans có elo < ceiling 
    VÀ có >= min_matches trận (confirmed/resolved) trong 7 ngày.
    """
```

### Background Task
Tích hợp vào `weekly_balance_task()` trong `main.py`, chạy cùng Elo Decay.

### ⚠️ Lưu ý
- Bonus **có thể** cộng quá 1000 (VD: 995 + 10 = 1005). Lần sau đó clan sẽ không đủ điều kiện <1000 nữa.

---

## Feature 5 — Underdog Bonus (+5~10 khi clan yếu thắng mạnh)

### Logic
Khi clan có Elo **thấp hơn** thắng → bonus thêm. Clan mạnh **KHÔNG** bị phạt thêm.

| Chênh lệch Elo | Bonus cho underdog thắng |
|-----------------|--------------------------|
| 100 – 149 | +5 |
| 150 – 200 | +8 |
| >200 | +10 (cap) |

### Elo Gain Cap (Áp dụng toàn hệ thống)

**Tổng Elo gain tối đa cho 1 trận = +50.** Sau khi tất cả modifiers (anti-farm, win rate, rank, underdog) được tính xong, cap lại nếu vượt quá.

```python
ELO_MAX_GAIN_PER_MATCH: int = 50  # Cap tổng gain cho 1 trận
```

### Elo Changes (`services/elo.py`)
```python
def get_underdog_bonus(elo_winner: int, elo_loser: int) -> int:
    """Only applies if winner's Elo < loser's Elo."""
    gap = elo_loser - elo_winner
    if gap < 100: return 0
    if gap < 150: return 5
    if gap <= 200: return 8
    return 10
```

Sửa `apply_match_result()` — **SAU** tính `new_elo_a/b`, **TRƯỚC** commit:

```python
# --- Underdog Bonus ---
winner_elo = elo_a if winner_clan_id == clan_a_id else elo_b
loser_elo = elo_b if winner_clan_id == clan_a_id else elo_a
bonus = get_underdog_bonus(winner_elo, loser_elo)
if bonus > 0:
    if winner_clan_id == clan_a_id:
        new_elo_a += bonus
        final_delta_a += bonus
    else:
        new_elo_b += bonus
        final_delta_b += bonus

# --- Elo Gain Cap ---
final_delta_a = min(final_delta_a, config.ELO_MAX_GAIN_PER_MATCH)
final_delta_b = min(final_delta_b, config.ELO_MAX_GAIN_PER_MATCH)
```

### ⚠️ Lưu ý
- Bonus chỉ cho bên **THẮNG** có Elo thấp hơn. Không trừ thêm bên thua.
- Bonus cộng **SAU** tất cả modifier khác.
- **Elo Gain Cap** áp dụng cuối cùng, sau tất cả modifiers. Chỉ cap gain (positive delta), KHÔNG cap loss (negative delta).

---

## Feature 6 — Mandatory Rank Declaration (Bắt buộc khai Rank)

### Logic
Khi invite/recruit (bao gồm try-out) → người được mời **PHẢI** khai Valorant rank qua **Select Menu** (dropdown). Rank lưu DB, hiển thị trên Arena. **Clan chỉ được thi đấu khi TẤT CẢ thành viên đã khai rank.**

### Bảng Rank → Score

| Rank | Score | Rank | Score |
|------|-------|------|-------|
| Iron 1 | 1 | Iron 2 | 2 | 
| Iron 3 | 3 | Bronze 1 | 4 |
| Bronze 2 | 5 | Bronze 3 | 6 |
| Silver 1 | 7 | Silver 2 | 8 |
| Silver 3 | 9 | Gold 1 | 10 |
| Gold 2 | 11 | Gold 3 | 12 |
| Platinum 1 | 13 | Platinum 2 | 14 |
| Platinum 3 | 15 | Diamond 1 | 16 |
| Diamond 2 | 17 | Diamond 3 | 18 |
| Ascendant 1 | 19 | Ascendant 2 | 20 |
| Ascendant 3 | 21 | Immortal 1 | 22 |
| Immortal 2 | 23 | Immortal 3 | 24 |
| Radiant | 25 |

### Schema Changes (`db/schema.sql`)
Thêm 2 cột vào `clan_members`:
```sql
ALTER TABLE clan_members ADD COLUMN valorant_rank TEXT;           -- VD: "Immortal 2"
ALTER TABLE clan_members ADD COLUMN valorant_rank_score INTEGER;  -- VD: 23
```

> **Lưu ý**: Dùng `clan_members` thay vì `users` vì rank có thể thay đổi. Mỗi lần join clan mới → nhập lại rank.

### DB Changes (`services/db.py`)
1. **`init_db()`**: Thêm migration tự động cho 2 cột (pattern đã tồn tại)
2. Thêm hàm:
```python
async def update_member_rank(user_id: int, clan_id: int, rank: str, rank_score: int):
    """Update valorant rank for a clan member."""

async def get_clan_avg_rank(clan_id: int) -> Dict:
    """Returns avg_rank_score, count_per_rank, etc."""

async def count_high_rank_members(clan_id: int, min_score: int) -> int:
    """Đếm thành viên có rank_score >= min_score. Dùng cho Rank Cap (F7)."""

async def get_undeclared_members(clan_id: int) -> List[Dict]:
    """Lấy danh sách thành viên chưa khai rank (valorant_rank IS NULL). Dùng để block thi đấu."""

async def get_roster_avg_rank(user_ids: List[int], clan_id: int) -> Dict:
    """Tính avg rank score của 1 roster cụ thể (subset of clan members). Dùng cho Feature 9."""
```

### UI Changes (`cogs/clan.py`)
**Select Menu** (KHÔNG dùng TextInput — tránh lỗi format, anti-fake):

```python
class RankDeclarationView(discord.ui.View):
    """View with Select Menu for rank declaration. Used when accepting invite/recruit."""
    def __init__(self, clan_id, user_id, invite_id, is_tryout=False):
        super().__init__(timeout=300)
        self.clan_id = clan_id
        self.user_id = user_id
        self.invite_id = invite_id
        self.is_tryout = is_tryout
        
        # Select Menu với 25 options (Iron 1 → Radiant)
        options = [
            discord.SelectOption(label="Iron 1", value="1"),
            discord.SelectOption(label="Iron 2", value="2"),
            # ... tất cả 25 ranks ...
            discord.SelectOption(label="Radiant", value="25"),
        ]
        select = discord.ui.Select(
            placeholder="Chọn rank Valorant hiện tại của bạn...",
            options=options,
            min_values=1, max_values=1
        )
        select.callback = self.on_select
        self.add_item(select)
    
    async def on_select(self, interaction):
        rank_score = int(self.children[0].values[0])
        rank_name = RANK_SCORE_TO_NAME[rank_score]
        # Check Rank Cap (Feature 7)
        # Save to DB
        # Continue original invite/recruit accept flow
```

**Vị trí chèn**: Sửa `handle_invite_accept()` (L658-786) VÀ `handle_recruit_accept()`. Sau validate → gửi Select Menu View → trong callback mới gọi `add_member()`.

### Enforcement: Clan phải khai rank đầy đủ

Tại thời điểm **gửi thách đấu** (`ChallengeSelectView.confirm()`) và **chấp nhận thách đấu** (`ChallengeAcceptView._accept()`), kiểm tra:

```python
undeclared = await db.get_undeclared_members(clan_id)
if undeclared:
    names = ", ".join([m["riot_id"] for m in undeclared])
    await interaction.response.send_message(
        f"❌ Clan chưa khai rank đầy đủ. Các thành viên chưa khai: {names}\n"
        f"Yêu cầu tất cả thành viên khai rank trước khi thi đấu.",
        ephemeral=True
    )
    return
```

### Chống khai giả (Anti-Fake)

1. **Mod override**: Thêm lệnh `/admin rank set <@user> <rank> [reason]` để Mod sửa rank nếu phát hiện khai sai.
2. **Report system**: Người chơi có thể `/report create` khai sai rank → Case cho Mod xử lý.
3. **Hiển thị công khai**: Avg Rank clan hiện trên Arena Dashboard → Cộng đồng tự giám sát.
4. **Hình phạt khai giả**: Nếu bị phát hiện → Reset Elo clan, Soft Ban (cấm thi đấu 7 ngày), ghi vào Case.
5. **Lệnh cập nhật rank**: `/clan update_rank` — Cho phép Captain/Vice yêu cầu thành viên khai lại rank (VD: sau khi lên rank mới). Thành viên nhận DM với Select Menu.

### Arena Display (`cogs/arena.py`)
Hiển thị **Avg Rank** bên cạnh Elo trên dashboard → minh bạch cho cộng đồng.

### ⚠️ Lưu ý
- Select Menu bật **mỗi lần accept** invite/recruit (rank có thể đã đổi từ lần trước)
- Dùng **Select Menu** thay vì TextInput → không cần parse, không bao giờ sai format
- **Try-out (recruit)** cũng PHẢI khai rank — vì try-out được thi đấu ngay
- Thành viên hiện tại chưa khai rank → clan bị chặn thi đấu cho đến khi tất cả khai xong

---

## Feature 7 — Rank Cap (Max 5 Immortal 2+ per clan)

### Logic
Mỗi clan max **5 thành viên** có rank ≥ **Immortal 2** (score ≥ 23). Kiểm tra khi invite/recruit/transfer.

### Config
```python
RANK_CAP_THRESHOLD: str = "Immortal 2"
RANK_CAP_THRESHOLD_SCORE: int = 23
RANK_CAP_MAX_COUNT: int = 5
```

### Code Changes
Check trong `RankDeclarationModal.on_submit()` — **SAU** parse rank, **TRƯỚC** add_member:

```python
if rank_score >= config.RANK_CAP_THRESHOLD_SCORE:
    high_count = await db.count_high_rank_members(clan_id, config.RANK_CAP_THRESHOLD_SCORE)
    if high_count >= config.RANK_CAP_MAX_COUNT:
        await interaction.response.send_message(
            f"❌ Clan đã đạt giới hạn {config.RANK_CAP_MAX_COUNT} thành viên rank "
            f"{config.RANK_CAP_THRESHOLD}+. Không thể thêm.",
            ephemeral=True
        )
        return
```

### ⚠️ Lưu ý
- **KHÔNG** kick thành viên hiện tại đã vượt cap → chỉ chặn thêm mới
- Transfer flow (`cogs/transfers.py`) cũng phải check tương tự
- Clan **hiện tại** đã có >5 Immo2+ → KHÔNG bị ảnh hưởng, nhưng KHÔNG invite thêm

---

## Feature 8 — Rank Elo Modifier (Roster avg rank → modifier)

### Logic
Khi 2 clan đánh, Elo modifier dựa trên **avg rank của ROSTER ra sân** (Feature 9), KHÔNG phải avg rank toàn clan. Nếu avg rank roster A > roster B → clan A gain ít hơn khi thắng, mất nhiều hơn khi thua.

| Gap (avg rank score) | Modifier clan cao | Modifier clan thấp |
|----------------------|-------------------|---------------------|
| 0-2 | 1.0 | 1.0 |
| 3-5 | 0.9 | 1.1 |
| 6-8 | 0.8 | 1.2 |
| 9+ | 0.7 | 1.3 |

### Elo Changes (`services/elo.py`)
```python
def get_rank_modifier(avg_rank_a: float, avg_rank_b: float) -> Tuple[float, float]:
    """
    Returns (modifier_a, modifier_b) based on avg rank gap of ROSTERS.
    Input: avg_rank_score từ roster (Feature 9), KHÔNG phải toàn clan.
    Nếu chưa có rank data → return (1.0, 1.0).
    """
    gap = abs(avg_rank_a - avg_rank_b)
    if gap <= 2: return (1.0, 1.0)
    if gap <= 5: mod = 0.9
    elif gap <= 8: mod = 0.8  
    else: mod = 0.7
    
    if avg_rank_a > avg_rank_b:
        return (mod, 2.0 - mod)
    else:
        return (2.0 - mod, mod)
```

Áp dụng trong `apply_match_result()` **SAU** win_rate_modifier, **TRƯỚC** underdog bonus.
Input `avg_rank_a/b` lấy từ roster data đã lưu trong match (Feature 9).

### ⚠️ Lưu ý
- Nếu 1 clan chưa có rank data → bỏ qua (return 1.0, 1.0)
- **Cap tổng modifier ≥ 0.3**: win_rate + rank modifier cộng dồn có thể đè quá nặng
- Dùng **roster avg rank**, không phải clan avg rank → phản ánh đúng đội hình thực tế ra sân

---

## Feature 9 — Match Roster Declaration (Khai roster trước khi đấu)

### Logic
Khi **gửi thách đấu** hoặc **chấp nhận thách đấu**, Captain/Vice phải khai **danh sách 5 người ra sân** (roster). Elo sẽ được tính dựa trên cả Elo clan VÀ **avg rank của roster**.

### Flow
1. **Clan A gửi thách đấu** → Captain A chọn format (BO1/3/5) + chọn 5 người từ danh sách thành viên
2. **Clan B chấp nhận** → Captain/Vice B chọn 5 người từ danh sách thành viên
3. Bot lưu roster 2 bên vào `matches` table
4. Khi tính Elo → dùng avg rank của roster thay vì toàn clan

### Schema Changes (`db/schema.sql`)
Thêm cột vào `matches`:
```sql
ALTER TABLE matches ADD COLUMN roster_a TEXT;        -- JSON: [{user_id, rank, rank_score}, ...]
ALTER TABLE matches ADD COLUMN roster_b TEXT;        -- JSON: [{user_id, rank, rank_score}, ...]
ALTER TABLE matches ADD COLUMN avg_rank_a REAL;      -- Avg rank score của roster A (pre-computed)
ALTER TABLE matches ADD COLUMN avg_rank_b REAL;      -- Avg rank score của roster B (pre-computed)
```

### Config
```python
ROSTER_SIZE: int = 5  # Số người phải khai cho mỗi roster
```

### UI Changes

#### Khi gửi thách đấu (`cogs/arena.py` — `ChallengeSelectView`)
Sau khi chọn clan đối thủ + format → hiện thêm bước **chọn roster**:

```python
class RosterSelectView(discord.ui.View):
    """Select 5 members for match roster."""
    def __init__(self, clan_id, clan_members, callback):
        super().__init__(timeout=120)
        self.selected = []
        # UserSelect hoặc custom Select với danh sách thành viên clan
        select = discord.ui.UserSelect(
            placeholder="Chọn 5 người ra sân...",
            min_values=5, max_values=5
        )
        select.callback = self.on_select
        self.add_item(select)
    
    async def on_select(self, interaction):
        selected_users = self.children[0].values
        # Validate: tất cả đều là thành viên clan
        # Validate: tất cả đã khai rank
        # Lưu roster → tiếp tục flow thách đấu
```

#### Khi chấp nhận thách đấu (`cogs/arena.py` — `ChallengeAcceptView`)
Sau khi bấm "Chấp nhận" → hiện `RosterSelectView` → chọn 5 người → lưu roster_b → tiếp tục ban/pick flow.

### DB Changes (`services/db.py`)
```python
async def save_match_roster(match_id: int, side: str, roster: List[Dict]):
    """
    Lưu roster cho 1 bên (side='a' hoặc 'b').
    roster = [{user_id, riot_id, valorant_rank, valorant_rank_score}, ...]
    Tính avg_rank_score và lưu cùng lúc.
    """

async def get_match_rosters(match_id: int) -> Dict:
    """
    Returns {roster_a, roster_b, avg_rank_a, avg_rank_b}.
    Dùng trong apply_match_result() để tính Rank Elo Modifier (F8).
    """
```

### Elo Integration
Trong `apply_match_result()`, thay vì dùng clan avg rank:
```python
# --- Rank Modifier (dùng roster avg, KHÔNG phải clan avg) ---
rosters = await db.get_match_rosters(match_id)
if rosters["avg_rank_a"] and rosters["avg_rank_b"]:
    mod_rank_a, mod_rank_b = get_rank_modifier(
        rosters["avg_rank_a"], rosters["avg_rank_b"]
    )
    final_delta_a = round(final_delta_a * mod_rank_a)
    final_delta_b = round(final_delta_b * mod_rank_b)
```

### ⚠️ Lưu ý
- Roster phải đủ **ROSTER_SIZE** (5) người. Thiếu → không cho đấu.
- Tất cả người trong roster **PHẢI** đã khai rank (Feature 6).
- Roster lưu **snapshot** rank tại thời điểm khai roster (không thay đổi nếu member update rank sau).
- Roster chỉ dùng cho **Challenge flow** (thách đấu). `/match create` thủ công tạm thời không yêu cầu roster.
- Try-out members cũng được chọn vào roster (vì try-out được phép thi đấu).

---

## Thứ tự implement an toàn

```
1. config.py          → Thêm tất cả constants (bao gồm ELO_MAX_GAIN_PER_MATCH, ROSTER_SIZE)
2. schema.sql + db.py → Migration cột mới + tất cả DB functions mới
3. elo.py             → Win Rate Modifier + Underdog Bonus + Rank Modifier + Elo Gain Cap
4. clan.py            → Recruitment Cap + RankDeclarationView (Select Menu) + Rank Cap + /clan update_rank
5. main.py            → Weekly balance task (Elo Decay + Activity Bonus)
6. arena.py           → Hiển thị Avg Rank + Roster Selection UI + Enforcement check
7. challenge.py       → Roster Selection khi accept challenge
8. transfers.py       → Rank Cap check khi transfer
9. admin.py           → /admin rank set command
10. historyUpdate.md  → Changelog
```

**Dependencies**: 
- Feature 7, 8, 9 phụ thuộc Feature 6 (cần rank data trước)
- Feature 9 phụ thuộc Feature 6 (cần tất cả thành viên khai rank)
- Feature 8 phụ thuộc Feature 9 (dùng roster avg rank)
- Feature 4 tích hợp cùng task với Feature 2

---

## Admin Override & Logging (Lệnh Admin cho Balance System)

### Tổng quan
Tất cả balance features đều cần lệnh Admin để điều chỉnh khi có vấn đề. Mọi hành động Admin đều phải được **log vào Mod Log channel** và **console**.

---

### Admin Commands (`cogs/admin.py`)

#### 🏷️ Rank Management
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin rank set <@user> <rank> [reason]` | Sửa rank của thành viên (override khai giả) | `RANK_OVERRIDE` |
| `/admin rank view <clan_name>` | Xem rank tất cả thành viên clan + avg | — |
| `/admin rank reset_clan <clan_name> [reason]` | Reset rank tất cả thành viên clan → NULL (bắt khai lại) | `RANK_RESET_CLAN` |

```python
# /admin rank set
@admin_group.command(name="rank_set")
async def admin_rank_set(self, interaction, user: discord.Member, 
                         rank: str, reason: str = "Admin override"):
    # Validate rank name → score
    # Update DB
    # Log: [RANK_OVERRIDE] Admin X set rank of User Y to "Immortal 2" (score 23). Reason: ...
```

#### 📉 Elo Decay Management
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin decay run` | Chạy Elo Decay thủ công ngay lập tức (không chờ weekly) | `ELO_DECAY_MANUAL` |
| `/admin decay exempt <clan_name> [reason]` | Miễn decay cho 1 clan (1 lần, tuần này) | `ELO_DECAY_EXEMPT` |
| `/admin decay status` | Xem danh sách clan sắp bị decay + last run time | — |

#### 🎯 Recruitment Cap Management
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin recruit bypass <clan_name> [reason]` | Cho phép clan vượt recruitment cap 1 lần | `RECRUIT_CAP_BYPASS` |
| `/admin recruit status <clan_name>` | Xem số invite/recruit thành công trong tuần | — |

#### 📊 Win Rate & Activity
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin balance winrate <clan_name>` | Xem win rate 10 trận gần nhất + modifier hiện tại | — |
| `/admin balance activity` | Xem danh sách clan đủ điều kiện nhận Activity Bonus | — |
| `/admin balance run_weekly` | Chạy weekly balance task thủ công (Decay + Activity Bonus) | `WEEKLY_BALANCE_MANUAL` |

#### 🎮 Roster Management
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin roster view <match_id>` | Xem roster 2 bên + avg rank của match | — |
| `/admin roster override <match_id> <side> <@user1> <@user2> ... [reason]` | Sửa roster match (VD: khai sai người) | `ROSTER_OVERRIDE` |

#### 🔧 System Toggle
| Lệnh | Mô tả | Log Event |
|-------|--------|-----------|
| `/admin balance toggle <feature> <on\|off> [reason]` | Bật/tắt từng feature riêng lẻ | `BALANCE_TOGGLE` |

Features có thể toggle: `recruitment_cap`, `elo_decay`, `win_rate_mod`, `activity_bonus`, `underdog_bonus`, `rank_enforcement`, `rank_cap`, `rank_elo_mod`, `roster_required`, `elo_gain_cap`.

```python
# Lưu vào system_settings
# Key: "balance_<feature>_enabled", Value: "1" hoặc "0"

async def is_feature_enabled(feature: str) -> bool:
    """Check if a balance feature is enabled. Default = True."""
    setting = await db.get_system_setting(f"balance_{feature}_enabled")
    return setting != "0"  # None hoặc "1" = enabled
```

> **Lưu ý**: Khi feature bị tắt, code vẫn chạy nhưng **skip logic** (return 1.0 cho modifiers, skip checks). Không cần restart bot.

---

### Logging (`services/bot_utils.py`)

Mỗi Balance event phải log theo format chuẩn:

#### Log Events mới
| Event Type | Khi nào | Nội dung |
|------------|---------|----------|
| `ELO_DECAY` | Weekly task trừ Elo | Clan, old_elo, new_elo, change |
| `ELO_DECAY_MANUAL` | Admin chạy decay tay | Admin, số clan bị decay |
| `ELO_DECAY_EXEMPT` | Admin miễn decay | Admin, Clan, reason |
| `ACTIVITY_BONUS` | Weekly task cộng bonus | Clan, old_elo, new_elo, matches_count |
| `WEEKLY_BALANCE_MANUAL` | Admin chạy weekly tay | Admin, timestamp |
| `RANK_OVERRIDE` | Admin sửa rank | Admin, User, old_rank, new_rank, reason |
| `RANK_RESET_CLAN` | Admin reset rank clan | Admin, Clan, member_count, reason |
| `RECRUIT_CAP_BYPASS` | Admin bypass cap | Admin, Clan, reason |
| `ROSTER_OVERRIDE` | Admin sửa roster | Admin, match_id, side, old/new roster |
| `BALANCE_TOGGLE` | Admin bật/tắt feature | Admin, feature, state, reason |
| `RANK_DECLARED` | Thành viên khai rank | User, Clan, rank, score |
| `ROSTER_SUBMITTED` | Roster được submit | Clan, match_id, roster_members, avg_rank |
| `MATCH_BLOCKED_RANK` | Clan bị chặn vì thiếu rank | Clan, undeclared_members |

#### Console Log Format
```python
print(f"[BALANCE] {event_type}: {details}")
# VD: [BALANCE] ELO_DECAY: Clan "VXT Pro" 1080 → 1065 (-15)
# VD: [BALANCE] RANK_OVERRIDE: Admin Nikko set User Minh to "Immortal 2" (was "Gold 3")
# VD: [BALANCE] BALANCE_TOGGLE: Admin Nikko disabled "elo_decay". Reason: Maintenance
```

#### Discord Mod Log Format
```python
embed = discord.Embed(
    title=f"⚖️ Balance: {event_type}",
    color=discord.Color.orange(),
    timestamp=datetime.now(timezone.utc)
)
embed.add_field(name="Action", value=details)
embed.add_field(name="By", value=admin_mention or "System")
embed.set_footer(text=f"Balance System v1.7")
await bot_utils.log_event(event_type, embed)
```

---

### DB Changes (`services/db.py`)

```python
# --- System Settings helpers ---
async def get_system_setting(key: str) -> Optional[str]:
    """Get a system setting value by key."""

async def set_system_setting(key: str, value: str):
    """Set a system setting (INSERT OR REPLACE)."""

# --- Balance Feature Toggle ---
async def is_balance_feature_enabled(feature: str) -> bool:
    """Check if balance feature is enabled. Default = True if not set."""
    val = await get_system_setting(f"balance_{feature}_enabled")
    return val != "0"

async def toggle_balance_feature(feature: str, enabled: bool):
    """Enable/disable a balance feature."""
    await set_system_setting(f"balance_{feature}_enabled", "1" if enabled else "0")
```

---

## Help, Info & Arena Rules Updates

### `/clan help` — Role-Based Content

Lệnh `/clan help` phải hiển thị **khác nhau** tùy theo role (vai trò) của người dùng:

| Role | Nội dung hiển thị |
|------|-------------------|
| **Chưa có clan** | Cách tạo clan, cách tìm clan (LFG), rank declaration khi join |
| **Member** | Lệnh cơ bản, rank declaration, cách xem rank, roster |
| **Captain / Vice** | + Invite/Recruit (kèm recruitment cap), update_rank, roster selection, challenge flow |
| **Admin / Mod** | + Tất cả `/admin balance`, `/admin rank`, `/admin decay`, `/admin roster`, toggle features |

```python
# Logic trong cogs/clan.py hoặc cogs/arena.py
async def build_help_embed(member: discord.Member, user_db, clan) -> discord.Embed:
    embed = discord.Embed(title="📖 Hướng dẫn ClanVXT", color=...)
    
    # === Section chung cho tất cả ===
    embed.add_field(name="📋 Cơ bản", value="...", inline=False)
    
    # === Nếu có clan ===
    if clan:
        role = member_record["role"]
        embed.add_field(name="🎮 Rank & Roster", value=(
            "• Rank được khai khi join clan (Select Menu)\n"
            "• Phải khai rank đầy đủ để thi đấu\n"
            "• Roster 5 người được chọn trước mỗi trận"
        ), inline=False)
        
        if role in ("captain", "vice"):
            embed.add_field(name="👑 Captain/Vice", value=(
                "• `/clan update_rank` — Yêu cầu thành viên khai lại rank\n"
                "• Recruitment cap: 1 invite/recruit mỗi tuần\n"
                "• Chọn roster khi thách đấu/chấp nhận"
            ), inline=False)
    
    # === Nếu là Admin ===
    if is_mod:
        embed.add_field(name="⚙️ Admin Balance", value=(
            "• `/admin balance toggle` — Bật/tắt từng feature\n"
            "• `/admin rank set/view/reset_clan`\n"
            "• `/admin decay run/exempt/status`\n"
            "• `/admin roster view/override`\n"
            "• `/admin balance run_weekly/winrate/activity`\n"
            "• `/admin recruit bypass/status`"
        ), inline=False)
    
    return embed
```

### Arena Dashboard — Cập nhật phần Luật lệ

Nút **📖 Luật lệ** trên Arena Dashboard phải cập nhật thêm các quy tắc mới:

```python
# Trong cogs/arena.py — khi bấm nút "Luật lệ"
rules_embed = discord.Embed(title="📖 QUY TẮC HỆ THỐNG", color=...)

# Thêm section mới:
rules_embed.add_field(name="🏷️ Rank Declaration", value=(
    "• **Bắt buộc** khai Valorant rank khi join clan\n"
    "• Mọi thành viên phải khai rank → clan mới được thi đấu\n"
    "• Khai giả → Reset Elo + Cấm thi đấu 7 ngày"
), inline=False)

rules_embed.add_field(name="📊 Balance System", value=(
    "• **Recruitment Cap**: Max 1 recruit/tuần (trừ clan mới)\n"
    "• **Elo Decay**: Clan >1050 Elo không đánh 7 ngày → -15 Elo/tuần\n"
    "• **Win Rate Modifier**: Win rate >70% → ít Elo hơn khi thắng\n"
    "• **Underdog Bonus**: Clan yếu thắng mạnh → +5~10 bonus\n"
    "• **Elo Gain Cap**: Max +50 Elo mỗi trận\n"
    "• **Rank Cap**: Max 5 Immortal 2+ mỗi clan"
), inline=False)

rules_embed.add_field(name="🎮 Roster", value=(
    "• Trước khi thách đấu phải **khai 5 người ra sân**\n"
    "• Elo được tính dựa trên rank trung bình của roster\n"
    "• Roster cao rank hơn → gain ít Elo hơn khi thắng"
), inline=False)
```

### Slash Command Descriptions

Tất cả slash commands mới phải có `description` bằng **tiếng Việt**, rõ ràng:

| Command | Description |
|---------|-------------|
| `/clan update_rank` | Yêu cầu thành viên khai lại rank Valorant |
| `/admin rank set` | [MOD] Sửa rank thành viên (override) |
| `/admin rank view` | [MOD] Xem rank tất cả thành viên clan |
| `/admin rank reset_clan` | [MOD] Reset rank toàn clan (bắt khai lại) |
| `/admin decay run` | [MOD] Chạy Elo Decay ngay lập tức |
| `/admin decay exempt` | [MOD] Miễn decay cho clan (1 tuần) |
| `/admin decay status` | [MOD] Xem trạng thái Elo Decay |
| `/admin recruit bypass` | [MOD] Cho phép clan vượt giới hạn recruit |
| `/admin recruit status` | [MOD] Xem lịch sử recruit trong tuần |
| `/admin balance toggle` | [MOD] Bật/tắt từng tính năng balance |
| `/admin balance winrate` | [MOD] Xem win rate + modifier clan |
| `/admin balance activity` | [MOD] Xem danh sách clan nhận Activity Bonus |
| `/admin balance run_weekly` | [MOD] Chạy weekly balance thủ công |
| `/admin roster view` | [MOD] Xem roster match |
| `/admin roster override` | [MOD] Sửa roster match |

### Cập nhật `DISCORD_RULES.md` & `DISCORD_RULES_FULL.md`

Sau khi implement xong, cập nhật 2 file rules:
- Thêm section **Rank Declaration** (bắt buộc, anti-fake, hình phạt)
- Thêm section **Balance System** (tóm tắt 9 features ảnh hưởng đến người chơi)
- Thêm section **Roster** (khai đội hình trước khi đấu)
- Cập nhật bảng lệnh (thêm `/clan update_rank`)

---

## Files cần thay đổi

| File | Thay đổi | Features |
|------|----------|----------|
| `config.py` | Thêm ~15 constants | 1,2,4,5,7,9 |
| `services/db.py` | Thêm ~15 hàm mới + migration + system settings helpers | 1,2,3,4,6,7,9,Admin |
| `db/schema.sql` | Thêm cột rank (clan_members) + roster/avg_rank (matches) | 6,7,8,9 |
| `services/elo.py` | Thêm 4 functions + sửa `apply_match_result()` + update `format_elo_explanation_vn()` | 3,5,8 |
| `services/bot_utils.py` | Thêm balance log helpers | Admin |
| `cogs/clan.py` | Recruitment Cap + RankDeclarationView + Rank Cap + `/clan update_rank` + **help embed** | 1,6,7,Help |
| `main.py` | Thêm weekly background task | 2,4 |
| `cogs/arena.py` | Avg Rank display + RosterSelectView + Enforcement + **Rules embed update** | 6,9,Help |
| `cogs/challenge.py` | Roster selection khi accept | 9 |
| `cogs/transfers.py` | Rank Cap check | 7 |
| `cogs/admin.py` | **14 lệnh admin mới** + toggle + **admin help** | 6,Admin |
| `DISCORD_RULES.md` | Thêm sections Rank/Balance/Roster | Help |
| `DISCORD_RULES_FULL.md` | Thêm sections chi tiết Rank/Balance/Roster | Help |
| `historyUpdate.md` | Changelog entry | ALL |

---

## ⚠️ Những điều cần TRÁNH

1. **KHÔNG** sửa logic match reporting/confirming — chỉ thêm modifiers vào `apply_match_result()`
2. **KHÔNG** thay đổi anti-farm multiplier hiện tại — modifiers mới cộng dồn
3. **KHÔNG** xóa comment/code cũ — minimal diff
4. **DB migration**: Dùng pattern check column exists trước ALTER (giống `init_db()` hiện tại)
5. **KHÔNG** decay clan `inactive` hoặc `disbanded` — chỉ `active`
6. **Weekly task**: Lưu `last_weekly_run` vào `system_settings` dưới dạng **ISO UTC** để tránh lặp khi restart
7. **Transaction safety**: `apply_match_result()` phải trong 1 transaction
8. **KHÔNG** push trừ khi được yêu cầu
9. **Elo explanation**: Cập nhật `format_elo_explanation_vn()` trong `services/elo.py` để show **breakdown chi tiết** tất cả modifiers mới (win rate, rank, underdog, cap) trong Discord logs
