"""
Database Initialization Script
Creates all tables from schema.sql
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db import init_db, DB_PATH


async def main():
    """Initialize the database."""
    print("=" * 50)
    print("Clan System - Database Initialization")
    print("=" * 50)
    print()
    
    try:
        await init_db()
        print()
        print(f"✓ Database created at: {DB_PATH}")
        print("✓ All tables initialized successfully!")
        print()
        print("Tables created:")
        print("  - users (Discord users with Riot ID)")
        print("  - clans (Clan entities with Elo)")
        print("  - clan_members (Membership records)")
        print("  - create_requests (5-accept flow)")
        print("  - matches (Match records)")
        print("  - elo_history (Elo audit trail)")
        print("  - loans (Member loans)")
        print("  - transfers (Permanent transfers)")
        print("  - cases (Report cases)")
        print("  - appeals (Case appeals)")
        print()
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
