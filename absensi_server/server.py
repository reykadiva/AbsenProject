from flask import Flask, render_template, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "absensi.db"

# Database Initialization
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Ensure table exists but DO NOT insert dummy data
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
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('log'))

@app.route('/log')
def log():
    conn = get_db_connection()
    # FIX: Convert stored UTC timestamp to Local Time (Asia/Jakarta) using SQL
    # FIX: Use 'id' for stable ordering
    query = '''
        SELECT 
            id, uid, nama, nim, action, 
            datetime(timestamp, 'localtime') as timestamp 
        FROM attendance 
        ORDER BY id DESC 
        LIMIT 100
    '''
    records = conn.execute(query).fetchall()
    conn.close()
    return render_template('log.html', records=records)

@app.route('/rekap')
def rekap():
    conn = get_db_connection()
    # Logic: Count total 'IN' per student
    query = '''
        SELECT nama, nim, COUNT(*) as total_in 
        FROM attendance 
        WHERE action = 'IN' 
        GROUP BY uid 
        ORDER BY nama ASC
    '''
    summary = conn.execute(query).fetchall()
    conn.close()
    return render_template('rekap.html', summary=summary)

@app.route('/belum-out')
def belum_out():
    conn = get_db_connection()
    # FX: Use MAX(id) to determine absolute latest record (safer than timestamp)
    # FIX: Filter where latest action is 'IN'
    query = '''
        SELECT 
            a.uid, a.nama, a.nim, 
            datetime(a.timestamp, 'localtime') as timestamp, 
            a.action
        FROM attendance a
        INNER JOIN (
            SELECT uid, MAX(id) as max_id
            FROM attendance
            GROUP BY uid
        ) b ON a.uid = b.uid AND a.id = b.max_id
        WHERE a.action = 'IN'
    '''
    inside_users = conn.execute(query).fetchall()
    conn.close()
    return render_template('belum_out.html', inside_users=inside_users)

if __name__ == '__main__':
    init_db()
    # Bind to 0.0.0.0 to be accessible on local network (essential for Pi)
    print("Server running on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
