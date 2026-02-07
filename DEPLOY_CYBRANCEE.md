# 🚀 Hướng dẫn Deploy lên Cybrancee

## Bước 1: Tạo tài khoản Cybrancee
1. Vào [cybrancee.com/discord-bot-hosting](https://cybrancee.com/discord-bot-hosting)
2. Chọn gói **Starter ($1.49/tháng)** hoặc cao hơn
3. Dùng mã **25OFF2026** để giảm giá

---

## Bước 2: Lấy Bot Token từ Discord
1. Vào [Discord Developer Portal](https://discord.com/developers/applications)
2. Tạo Application mới → Vào tab **Bot**
3. Copy **Token** (giữ bí mật!)
4. Bật **MESSAGE CONTENT INTENT**
5. Tab **OAuth2** → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator`
6. Copy URL và invite bot vào server

---

## Bước 3: Setup Git trên Cybrancee

### 3.1. Tạo GitHub Personal Access Token
1. Vào [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Generate new token → **Classic** (không phải Fine-grained)
3. Chọn scope: `repo`
4. Copy token (chỉ hiện 1 lần!)

### 3.2. Cấu hình trên Cybrancee Panel
1. Login vào [panel.cybrancee.com](https://panel.cybrancee.com)
2. Vào tab **Startup**
3. Điền các trường:

| Field | Giá trị |
|-------|---------|
| **GIT REPO ADDRESS** | `https://github.com/MonsieurNikko/ClanVXT.git` |
| **GIT BRANCH** | `main` |
| **AUTO UPDATE** | ✅ ON |
| **BOT PY FILE** | `main.py` |
| **REQUIREMENTS FILE** | `requirements.txt` |
| **GIT USERNAME** | Username GitHub của bạn |
| **GIT ACCESS TOKEN** | Token vừa tạo ở bước 3.1 |

4. **QUAN TRỌNG:** Xóa hết files trong File Manager trước khi setup Git
5. Vào **Settings** → **Reinstall Server**

---

## Bước 4: Cấu hình Environment Variables

Trong tab **Startup**, tìm phần **Variables** hoặc tạo file `.env`:

```env
BOT_TOKEN=your_discord_bot_token_here
GUILD_ID=your_server_id_here
```

**Cách lấy GUILD_ID:**
- Bật Developer Mode trong Discord (Settings → Advanced)
- Click chuột phải vào server → Copy Server ID

---

## Bước 5: Start Bot
1. Nhấn nút **Start** trong Dashboard
2. Xem Console để check logs
3. Nếu thấy `✅ Bot is ready!` → Thành công!
4. Trong Discord, gõ `/clan help` để test

---

## 🔄 Cập nhật code sau này

Khi bạn muốn update code:
1. Push code lên GitHub: `git push`
2. Vào Cybrancee → **Restart** bot
3. Bot sẽ tự `git pull` và chạy code mới

---

## 💾 Về Database

- Bot dùng **SQLite** (file `data/clan.db`)
- File database **TỰ TẠO** khi bot chạy lần đầu
- **KHÔNG BỊ MẤT** khi update code (vì không có trên Git)
- Chỉ mất khi **Reinstall Server** → Nhớ backup trước!

### Backup database:
1. Vào tab **Files** trên Panel
2. Download file `data/clan.db`
3. Hoặc dùng tab **Backups** để backup toàn bộ

---

## 🔧 Troubleshooting

| Lỗi | Giải pháp |
|-----|-----------|
| Bot không start | Check Console, xem lỗi gì |
| "Token invalid" | Kiểm tra lại BOT_TOKEN |
| "Guild not found" | Kiểm tra GUILD_ID |
| Commands không hiện | Chờ 1 tiếng hoặc kick/invite lại bot |
| Database error | Check file `data/clan.db` có tồn tại không |

---

## 📞 Hỗ trợ
- Cybrancee Discord: [discord.gg/cY5wawVnnQ](https://discord.gg/cY5wawVnnQ)
- Cybrancee Support: 24/7

---

> 🎉 Chúc bạn deploy thành công!
