import sqlite3
from pathlib import Path

DB_PATH = Path("data/clan.db")

def debug():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    print("--- SEARCHING FOR 'linh' (CASE-INSENSITIVE) ---")
    cursor = conn.execute("SELECT * FROM users WHERE LOWER(riot_id) LIKE '%linh%'")
    for row in cursor.fetchall():
        print(dict(row))
        
    print("\n--- ALL USERS (Full ID, DiscordID, RiotID) ---")
    cursor = conn.execute("SELECT id, discord_id, riot_id FROM users")
    for row in cursor.fetchall():
        print(f"ID: {row['id']} | DiscordID: {row['discord_id']} | RiotID: {row['riot_id']}")

    conn.close()

if __name__ == "__main__":
    debug()
