import sqlite3
import os

db_path = "data/clan.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(matches)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "winner_clan_id" not in columns:
        print("Adding 'winner_clan_id' to 'matches'...")
        conn.execute("ALTER TABLE matches ADD COLUMN winner_clan_id INTEGER")
        conn.commit()
        print("Done.")
    else:
        print("'winner_clan_id' already exists.")
    conn.close()
