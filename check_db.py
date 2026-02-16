import sqlite3
import os

db_path = "data/clan.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(matches)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns in 'matches': {', '.join(columns)}")
    conn.close()
