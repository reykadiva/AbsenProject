from flask import Flask, render_template, redirect, url_for, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "absensi.db"

# Database Initialization
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Create table `users` (Master Data)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            uid TEXT PRIMARY KEY,
            nama TEXT,
            nim TEXT
        )
    ''')

    # 2. Create table `attendance` (Transaction Log)
    # Using DEFAULT CURRENT_TIMESTAMP so SQLite handles UTC time automatically
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            nama TEXT,
            nim TEXT,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- API ENDPOINTS ---

@app.route('/tap', methods=['POST'])
def tap():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
            
        uid = data.get('uid')
        nama = data.get('nama')
        nim = data.get('nim')
        action = data.get('action') # IN, OUT, DENIED

        # Basic Validation
        if not uid or action not in ['IN', 'OUT', 'DENIED']:
            return jsonify({"status": "error", "message": "Invalid data (missing uid or invalid action)"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Save/Update User (if not denied/generic error)
        # INSERT OR IGNORE avoids crashing if user exists; valid for simple logging
        if uid and nama and nim:
             cursor.execute('INSERT OR IGNORE INTO users (uid, nama, nim) VALUES (?, ?, ?)', (uid, nama, nim))

        # 2. Log Attendance
        # timestamp is handled by DEFAULT CURRENT_TIMESTAMP (UTC)
        cursor.execute('''
            INSERT INTO attendance (uid, nama, nim, action) 
            VALUES (?, ?, ?, ?)
        ''', (uid, nama, nim, action))
        
        conn.commit()
        conn.close()

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# --- DASHBOARD ROUTES ---

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
