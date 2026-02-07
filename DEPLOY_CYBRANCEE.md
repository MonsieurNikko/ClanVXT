# 🚀 Cybrancee Deployment Guide

## Prerequisites
- Cybrancee account with Discord Bot Hosting plan
- Discord Bot Token from [Discord Developer Portal](https://discord.com/developers/applications)

## Step 1: Get Your Bot Token
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application → Name it "ClanVXT"
3. Go to **Bot** tab → Click "Add Bot"
4. Copy the **Token** (keep it secret!)
5. Enable **MESSAGE CONTENT INTENT** under Privileged Gateway Intents
6. Go to **OAuth2 → URL Generator**
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator` (or specific permissions)
7. Copy URL and invite bot to your server

## Step 2: Get Discord IDs
You need these IDs from your Discord server:

| Variable | How to Get |
|----------|------------|
| `GUILD_ID` | Right-click server icon → Copy Server ID |
| Role IDs | Right-click role → Copy Role ID |
| Channel IDs | Right-click channel → Copy Channel ID |

> **Enable Developer Mode**: Settings → Advanced → Developer Mode

## Step 3: Prepare Files
Create a `.env` file in the project root:

```env
BOT_TOKEN=your_discord_bot_token_here
GUILD_ID=your_server_id_here
```

## Step 4: Upload to Cybrancee

### Via SFTP (Recommended)
1. Login to Cybrancee Panel
2. Go to **Settings** → Copy SFTP credentials
3. Use FileZilla to connect:
   - Host: from panel
   - Username: from panel
   - Password: your panel password
   - Port: from panel
4. Upload ALL files to the server root

### Via Git Integration (Alternative)
1. In Cybrancee Panel → **Settings** → Git Integration
2. Enter your GitHub repo URL: `https://github.com/MonsieurNikko/ClanVXT.git`
3. The bot will auto-pull latest code on restart

## Step 5: Configure Cybrancee Panel

1. **Docker Image**: Select `Python 3.11` (or latest)
2. **Startup Command**: `python main.py`
3. **Dependencies**: Paste contents of `requirements.txt`:
   ```
   discord.py>=2.0.0
   aiosqlite>=0.17.0
   python-dotenv>=1.0.0
   ```

## Step 6: Set Environment Variables
In Cybrancee Panel → **Startup** → Environment Variables:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | Your Discord bot token |
| `GUILD_ID` | Your server ID |

## Step 7: Start the Bot
1. Click **Start** in Cybrancee Panel
2. Watch console for: `✅ Bot is ready!`
3. In Discord, type `/clan help` to test

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot not starting | Check console for errors, verify token is correct |
| Commands not showing | Wait 1 hour for sync, or kick/re-invite bot |
| Database errors | Check `data/` folder exists, bot has write permission |
| "Guild not found" | Verify GUILD_ID is correct |

## 📂 File Structure on Cybrancee
```
/
├── main.py          ← Startup file
├── config.py
├── requirements.txt
├── .env             ← Your secrets (create this!)
├── cogs/
├── services/
├── data/
│   └── clan.db      ← Created automatically
└── db/
    └── schema.sql
```

## 🔄 Updating the Bot
1. Push changes to GitHub
2. In Cybrancee Panel → Restart (if using Git Integration)
3. Or re-upload files via SFTP

## 💾 Database Backup
Cybrancee has **scheduled backups**. You can also:
1. Go to Cybrancee Panel → **Backups**
2. Create manual backup before major changes
3. Download `data/clan.db` via SFTP for local backup
