from flask import Flask, render_template, request
import sqlite3
from datetime import datetime
import pytz
import os

app = Flask(__name__)
DB_NAME = "absensi.db"

# Setup Timezone WIB
def get_wib_time():
    utc_now = datetime.now(pytz.utc)
    return utc_now.astimezone(pytz.timezone('Asia/Jakarta'))

# Database Initialization
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            nama TEXT,
            nim TEXT,
            action TEXT,
            timestamp DATETIME
        )
    ''')
    
    # Check if data exists, if not add dummy data
    c.execute('SELECT count(*) FROM attendance')
    if c.fetchone()[0] == 0:
        print("Adding dummy data...")
        dummy_data = [
            # User 1: Masuk dan Keluar (Selesai)
            ("E2:45:1A:99", "Budi Santoso", "1012023001", "IN", "2026-01-17 08:00:00"),
            ("E2:45:1A:99", "Budi Santoso", "1012023001", "OUT", "2026-01-17 10:00:00"),
            
            # User 2: Masuk dan Belum Keluar (Masih di kelas)
            ("A1:B2:C3:D4", "Siti Aminah", "1012023005", "IN", "2026-01-17 08:05:00"),
            
            # User 3: Ditolak
            ("UNKNOWN", "Unknown", "-", "DENIED", "2026-01-17 08:10:00"),
            
            # User 4: Masuk dan Belum Keluar (Masih di kelas)
            ("55:66:77:88", "Ahmad Dhani", "1012023012", "IN", "2026-01-17 09:30:00"),
            
            # User 1 Masuk Lagi (Sesi Siang)
            ("E2:45:1A:99", "Budi Santoso", "1012023001", "IN", "2026-01-17 13:00:00"),
        ]
        c.executemany('INSERT INTO attendance (uid, nama, nim, action, timestamp) VALUES (?, ?, ?, ?, ?)', dummy_data)
        conn.commit()
    
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- ROUTES ---

@app.route('/')
def index():
    return log() # Default to log page

@app.route('/log')
def log():
    conn = get_db_connection()
    # Get last 100 records, newest first
    records = conn.execute('SELECT * FROM attendance ORDER BY timestamp DESC LIMIT 100').fetchall()
    conn.close()
    return render_template('log.html', records=records)

@app.route('/rekap')
def rekap():
    conn = get_db_connection()
    # Count total 'IN' per student
    summary = conn.execute('''
        SELECT nama, nim, COUNT(*) as total_in 
        FROM attendance 
        WHERE action = 'IN' 
        GROUP BY uid 
        ORDER BY nama ASC
    ''').fetchall()
    conn.close()
    return render_template('rekap.html', summary=summary)

@app.route('/belum-out')
def belum_out():
    conn = get_db_connection()
    # Logic: Get latest action for each UID. If 'IN', they are inside.
    query = '''
        SELECT a.uid, a.nama, a.nim, a.timestamp, a.action
        FROM attendance a
        INNER JOIN (
            SELECT uid, MAX(timestamp) as max_time
            FROM attendance
            GROUP BY uid
        ) b ON a.uid = b.uid AND a.timestamp = b.max_time
        WHERE a.action = 'IN'
    '''
    inside_users = conn.execute(query).fetchall()
    conn.close()
    return render_template('belum_out.html', inside_users=inside_users)

if __name__ == '__main__':
    init_db()
    print("Server running on http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
