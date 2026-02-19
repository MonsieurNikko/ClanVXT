# 🏰 ClanVXT - Discord Clan Management Bot

A Discord bot for managing a competitive clan system for Valorant communities. Includes Elo ranking, match tracking, member transfers, and moderation tools.

## ✨ Features

- **Clan Management**: Create, approve, invite/kick members, promote officers
- **Try-Out System**: Recruit new members with a 24-hour probation period (auto-kick if not promoted)
- **Elo System**: Automated Elo calculation with anti-farm mechanics
- **Match Tracking**: Create matches, report results, handle disputes
- **Loan System**: Temporarily loan members between clans
- **Transfer System**: Permanent member transfers with atomic movement logic
- **Moderation**: Reports, appeals, case management, bans
- **User Cleanup**: Automatic handling of users leaving server (Captain inheritance, data anonymization)
- **Localization**: Fully localized in Vietnamese for all user-facing interactions

## 📋 Requirements

- Python 3.10+
- Discord.py 2.0+
- aiosqlite

## 🚀 Setup

1. Clone the repository:
```bash
git clone https://github.com/MonsieurNikko/ClanVXT.git
cd ClanVXT
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file:
```env
DISCORD_TOKEN=your_bot_token
GUILD_ID=your_server_id
MOD_ROLE_ID=your_mod_role_id
VERIFIED_ROLE_ID=your_verified_role_id
LOG_CHANNEL_ID=your_log_channel_id
```

4. Run the bot:
```bash
python main.py
```

## 📁 Project Structure

```
├── main.py              # Bot entry point
├── config.py            # Configuration loader
├── cogs/                # Discord command modules
│   ├── clan.py          # Clan management commands
│   ├── matches.py       # Match commands
│   ├── loans.py         # Loan commands
│   ├── transfers.py     # Transfer commands
│   ├── admin.py         # Admin commands
│   └── moderation.py    # Report/appeal commands
├── services/            # Business logic
│   ├── db.py            # Database operations
│   ├── elo.py           # Elo calculations
│   ├── cooldowns.py     # Cooldown management
│   └── permissions.py   # Permission checks
├── db/                  # Database files
│   └── schema.sql       # Database schema
└── docs/
    ├── SPEC.md          # Technical specification
    ├── RULEBOOK.md      # Game rules (Vietnamese)
    └── STATES.md        # State diagrams
```

## 📖 Documentation

- [SPEC.md](SPEC.md) - Full command specification
- [RULEBOOK.md](RULEBOOK.md) - Clan rules (Vietnamese)
- [STATES.md](STATES.md) - State machine documentation
- [CONFIG.md](CONFIG.md) - Configuration guide

## ⚙️ Elo System

- **Starting Elo**: 1000
- **K-Factor (Placement)**: 40 (first 10 matches — faster calibration)
- **K-Factor (Stable)**: 32 (after 10 matches)
- **Per-clan K-factor**: Each clan uses its own K based on `matches_played`
- **Elo Floor**: 100 (Elo cannot drop below this)
- **Anti-farm**: Diminishing returns for repeated matches (100% → 70% → 40% → 20%)

## ⚔️ Challenge System

- Clans can challenge each other via the ⚔️ button on the Arena dashboard
- Challenge invitation sent to opponent clan's private channel with Accept/Decline buttons
- Anti-spam: 10-minute cooldown between challenges from the same clan
- Accept creates a match automatically in #arena

## 📜 License

MIT License
