
# 📜 ClanVXT Changelog

This document provides a cumulative history of all technical improvements, fixes, and feature updates for the ClanVXT system.

---

## [1.1.0] - 2026-02-09
### 🛡️ Logic & Security Hardening (P0)
- **Atomic Acceptance**: Modified `services/db.py` to ensure loan/transfer acceptance and completion are atomic. Added `WHERE status = 'requested'` to update queries.
- **Transaction-Safe Movement**: Added `db.move_member` to handle removing a member from one clan and adding them to another in a single SQL transaction.
- **Captain/Vice Protection**: Implemented checks in `services/permissions.py` to prevent Captains and Vice-Captains from being loaned or transferred.
- **Minimum Member Count**: Added validation to ensure a clan never drops below 5 members during a loan or transfer operation.
- **Force-End Loans**: Updated clan disbanding logic (manual and auto) to forcefully terminate any active loans involving the clan before disbanding.

### 🇻🇳 Localization & UX
- **Full Vietnamese Translation**: Translated all user-facing strings, button labels, and embed fields across all 6 cogs and all service layers.
- **DM Notification System**: Added automated DM notifications for loan/transfer requests/activations and match disputes.
- **Match Creation Rate Limit**: Implemented a 5-minute cooldown per clan for creating matches to prevent spam.

### 🔧 Technical Cleanup
- **Standardized Exception Handling**: Replaced bare `except:` blocks with `except Exception:`.
- **Circular Dependency Fixes**: Resolved circular imports by moving some imports inside function local scopes.
- **Database Architecture**: Implemented soft-delete for clans (`status = 'disbanded'`) to preserve ELO history.
- **Task Scheduling**: Verified and localized background tasks for request expiration in `main.py`.

---

## [1.0.0] - Initial Release
- Core clan management features.
- Initial Elo ranking implementation.
- Basic match tracking and reporting.
- Initial database schema and service layer.

---
*Last Updated: 2026-02-09*
