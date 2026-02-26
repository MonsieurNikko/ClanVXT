# Balance System — Implementation Plan

> **8 features** để cân bằng hệ thống clan, giải quyết cả vấn đề hiện tại (clan quá mạnh) lẫn tương lai.

---

## Tổng Quan Features

| # | Feature | Mục đích |
|---|---------|----------|
| 1 | **Recruitment Cap** (1/tuần, trừ clan mới) | Ngăn hút talent quá nhanh |
| 2 | **Elo Decay** (>1050, -15/tuần) | Phạt không hoạt động |
| 3 | **Win Rate Modifier** (>70% → giảm gain) | Tự cân bằng clan dominant |
| 4 | **Activity Bonus** (+10 cho clan <1000 đánh ≥3/tuần) | Khuyến khích clan yếu |
| 5 | **Underdog Bonus** (+5~10 khi clan yếu thắng mạnh) | Thưởng upset |
| 6 | **Mandatory Rank Declaration** (nhập rank khi join) | Minh bạch, cơ sở cho F7/F8 |
| 7 | **Rank Cap** (max 5 Immortal 2+ per clan) | Ngăn stacking trực tiếp |
| 8 | **Rank Elo Modifier** (avg rank cao → giảm gain) | Cân bằng skill chênh lệch |

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
```

### ⚠️ Lưu ý
- Bonus chỉ cho bên **THẮNG** có Elo thấp hơn. Không trừ thêm bên thua.
- Bonus cộng **SAU** tất cả modifier khác.

---

## Feature 6 — Mandatory Rank Declaration (Bắt buộc khai Rank)

### Logic
Khi invite/recruit → người được mời phải khai Valorant rank qua Modal. Rank lưu DB, hiển thị trên Arena.

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
```

### UI Changes (`cogs/clan.py`)
Modal mới khi accept invite:

```python
class RankDeclarationModal(discord.ui.Modal, title="Khai báo Rank Valorant"):
    rank = discord.ui.TextInput(
        label="Rank Valorant hiện tại",
        placeholder="VD: Immortal 2, Diamond 3, Gold 1...",
        min_length=4,
        max_length=15,
        required=True
    )
    
    async def on_submit(self, interaction):
        # Parse rank → score
        # Validate format
        # Check Rank Cap (Feature 7)
        # Save to DB
        # Continue original invite accept flow
```

**Vị trí chèn**: Sửa `handle_invite_accept()` (L658-786). Sau validate → mở Modal → trong callback mới gọi `add_member()`.

### Arena Display (`cogs/arena.py`)
Hiển thị **Avg Rank** bên cạnh Elo trên dashboard → minh bạch cho cộng đồng.

### ⚠️ Lưu ý
- Modal bật **mỗi lần accept** (rank có thể đã đổi từ lần trước)
- Parse rank phải linh hoạt: "immo2", "Immortal 2", "IMMORTAL2" → tất cả map sang "Immortal 2" score 23

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

## Feature 8 — Rank Elo Modifier (Avg rank cao → giảm gain)

### Logic
Khi 2 clan đánh, nếu avg rank score clan A > clan B → clan A gain ít hơn khi thắng, mất nhiều hơn khi thua.

| Gap (avg rank score) | Modifier clan cao | Modifier clan thấp |
|----------------------|-------------------|---------------------|
| 0-2 | 1.0 | 1.0 |
| 3-5 | 0.9 | 1.1 |
| 6-8 | 0.8 | 1.2 |
| 9+ | 0.7 | 1.3 |

### Elo Changes (`services/elo.py`)
```python
async def get_rank_modifier(clan_a_id: int, clan_b_id: int) -> Tuple[float, float]:
    """
    Returns (modifier_a, modifier_b) based on avg rank gap.
    Nếu clan chưa có rank data → return (1.0, 1.0).
    """
```

Áp dụng trong `apply_match_result()` **SAU** win_rate_modifier, **TRƯỚC** underdog bonus.

### ⚠️ Lưu ý
- Nếu 1 clan chưa có rank data → bỏ qua (return 1.0, 1.0)
- **Cap tổng modifier ≥ 0.3**: win_rate + rank modifier cộng dồn có thể đè quá nặng

---

## Thứ tự implement an toàn

```
1. config.py          → Thêm tất cả constants
2. schema.sql + db.py → Migration cột mới + tất cả DB functions mới
3. elo.py             → Win Rate Modifier + Underdog Bonus + Rank Modifier
4. clan.py            → Recruitment Cap + RankDeclarationModal + Rank Cap
5. main.py            → Weekly balance task (Elo Decay + Activity Bonus)
6. arena.py           → Hiển thị Avg Rank trên dashboard
7. transfers.py       → Rank Cap check khi transfer
8. historyUpdate.md   → Changelog
```

**Dependencies**: 
- Feature 7 & 8 phụ thuộc Feature 6 (cần rank data trước)
- Feature 4 tích hợp cùng task với Feature 2

---

## Files cần thay đổi

| File | Thay đổi | Features |
|------|----------|----------|
| `config.py` | Thêm ~10 constants | 1,2,4,7 |
| `services/db.py` | Thêm ~8 hàm mới + migration | 1,2,3,4,6,7 |
| `db/schema.sql` | Thêm 2 cột `valorant_rank`, `valorant_rank_score` | 6,7,8 |
| `services/elo.py` | Thêm 3 functions + sửa `apply_match_result()` | 3,5,8 |
| `cogs/clan.py` | Recruitment Cap + RankDeclarationModal + Rank Cap | 1,6,7 |
| `main.py` | Thêm weekly background task | 2,4 |
| `cogs/arena.py` | Hiển thị Avg Rank | 6 |
| `cogs/transfers.py` | Rank Cap check | 7 |
| `historyUpdate.md` | Changelog entry | ALL |

---

## ⚠️ Những điều cần TRÁNH

1. **KHÔNG** sửa logic match reporting/confirming — chỉ thêm modifiers vào `apply_match_result()`
2. **KHÔNG** thay đổi anti-farm multiplier hiện tại — modifiers mới cộng dồn
3. **KHÔNG** xóa comment/code cũ — minimal diff
4. **DB migration**: Dùng pattern check column exists trước ALTER (giống `init_db()` hiện tại)
5. **KHÔNG** decay clan `inactive` hoặc `disbanded` — chỉ `active`
6. **Weekly task**: Lưu `last_weekly_run` vào `system_settings` để tránh lặp khi restart
7. **Transaction safety**: `apply_match_result()` phải trong 1 transaction
8. **KHÔNG** push trừ khi được yêu cầu (→ lần này được yêu cầu push)
