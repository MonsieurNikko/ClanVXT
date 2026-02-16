import sqlite3
import os

db_path = "data/clan.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(matches)")
    rows = cursor.fetchall()
    print("Columns in 'matches':")
    for row in rows:
        print(f" - {row[1]} ({row[2]})")
    
    # Check other tables
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Tables: {', '.join(tables)}")
    conn.close()
