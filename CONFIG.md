# Configuration Specification

## 1. Configuration Values

### Roles (By Name)
| Config Key | Value | Description |
| :--- | :--- | :--- |
| `ROLE_VERIFIED` | `Thiểu Năng Con` | Required role to participate in the clan system. |
| `ROLE_MOD` | `Hội đồng quản trị` | Role with administrative privileges over the system. |

### Channels & Categories
| Config Key | Value | Description |
| :--- | :--- | :--- |
| `CHANNEL_MOD_LOG` | `log` | Text channel for system logs. |
| `CATEGORY_CLANS` | `CLANS` | Category where clan private channels are created. |

### System Constants
| Config Key | Value | Description |
| :--- | :--- | :--- |
| `CLAN_CREATE_TIMEOUT` | `48h` | Time to gather 5 acceptances. |
| `MIN_MEMBERS_ACTIVE` | `5` | Minimum members to keep clan active. |
| `COOLDOWN_JOIN_LEAVE` | `14d` | Cooldown after leaving/kicking/loan. |
| `LOAN_MAX_DURATION` | `7d` | Maximum duration for a member loan. |
| `LOAN_COOLDOWN` | `14d` | Cooldown after loan ends. |
| `TRANSFER_COOLDOWN` | `30d` | Min time between transfers. |
| `TRANSFER_SICKNESS` | `72h` | Match ban duration after transfer. |
| `MATCH_LIMIT_24H` | `2` | Max matches between same 2 clans in 24h. |
| `ELO_INITIAL` | `1000` | Starting Elo for new clans. |
| `ELO_PLACEMENT_MATCHES` | `10` | Number of matches with high K-factor. |
| `APPEAL_WINDOW` | `7d` | Time window to appeal a case. |

## 2. Loading Mechanism

### Strategy
The bot should load configuration from a `config.json` file or Environment Variables at startup.

### Validation on Startup
1.  **Check Roles**:
    -   Fetch all server roles.
    -   Verify `Thiểu Năng Con` exists. If not, **ERROR** (Stop bot. **DO NOT CREATE**).
    -   Verify `Hội đồng quản trị` exists. If not, **ERROR** (Stop bot. **DO NOT CREATE**).
2.  **Check Channels**:
    -   Fetch all channels.
    -   Verify channel named `log` exists. If not, **WARN** (or create).
    -   Verify category named `CLANS` exists. If not, **WARN** (or create).

### Config File Structure (Example `config.json`)
```json
{
  "roles": {
    "verified": "Thiểu Năng Con",
    "mod": "Hội đồng quản trị"
  },
  "channels": {
    "modLog": "log",
    "clanCategory": "CLANS"
  },
  "constants": {
    "cooldownDays": 14,
    "loanDays": 7,
    "minMembers": 5
  }
}
```
