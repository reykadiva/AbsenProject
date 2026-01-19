import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "absensi_server", "absensi.db")

print(f"Checking DB at: {DB_PATH}")

try:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n=== LAST 10 ATTENDANCE LOGS ===")
    rows = cursor.execute("SELECT * FROM attendance ORDER BY id DESC LIMIT 10").fetchall()
    
    print(f"{'ID':<5} | {'UID':<20} | {'ACTION':<10} | {'FACE':<10} | {'TIME'}")
    print("-" * 65)
    
    for row in rows:
        print(f"{row['id']:<5} | {row['uid']:<20} | {row['action']:<10} | {row['face_status']:<10} | {row['timestamp']}")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
