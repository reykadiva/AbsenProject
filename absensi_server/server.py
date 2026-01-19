from flask import Flask, render_template, redirect, url_for, request, jsonify
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "absensi.db")


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
    
    # V2.5 SAFE MIGRATION: Check if 'face_status' column exists
    # This ensures backward compatibility/read-only safety on existing DBs
    c.execute("PRAGMA table_info(attendance)")
    columns = [row[1] for row in c.fetchall()]
    if 'face_status' not in columns:
        try:
            print("Migrating DB: Adding face_status column...")
            c.execute("ALTER TABLE attendance ADD COLUMN face_status TEXT DEFAULT 'UNKNOWN'")
        except Exception as e:
            print(f"Migration warning: {e}")

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- API ENDPOINTS ---

# Global Heartbeat Tracker
last_device_ping = None

@app.route('/ping', methods=['GET'])
def ping():
    global last_device_ping
    last_device_ping = datetime.now()
    return jsonify({"status": "online", "time": last_device_ping.isoformat()}), 200

@app.route('/tap', methods=['POST'])
def tap():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
            
        uid = (data.get('uid') or '').strip().upper()
        nama = (data.get('nama') or '').strip()
        nim  = (data.get('nim') or '').strip()
        action = (data.get('action') or '').strip().upper() # IN, OUT, DENIED
        
        # V2.5: Optional face verification status from face reco server
        face_status = data.get('face_status', 'UNKNOWN') 
        
        # DEBUG: Log incoming payload
        print(f"[TAP] Payload: {data}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Save/Update User (if not denied/generic error)
        # INSERT OR IGNORE avoids crashing if user exists; valid for simple logging
        if uid and nama and nim:
             cursor.execute('INSERT OR IGNORE INTO users (uid, nama, nim) VALUES (?, ?, ?)', (uid, nama, nim))

        # SYNC FIX: If face_status is UNKNOWN, check if we have a recent (30s) record with a valid status
        # This handles cases where Face Rec writes to DB *before* the ESP32 tap
        if face_status == 'UNKNOWN':
            try:
                recent_face_row = conn.execute('''
                    SELECT face_status FROM attendance 
                    WHERE uid = ? 
                      AND timestamp >= datetime('now', '-30 seconds')
                      AND face_status IN ('MATCH', 'MISMATCH')
                    ORDER BY id DESC LIMIT 1
                ''', (uid,)).fetchone()
                
                if recent_face_row:
                    face_status = recent_face_row['face_status']
                    print(f"[SYNC] Resolved UNKNOWN -> {face_status} for {uid}")
            except Exception as ex:
                print(f"[SYNC WARNING] Failed to lookup recent face: {ex}")

        # 2. Log Attendance
        # timestamp is handled by DEFAULT CURRENT_TIMESTAMP (UTC)
        cursor.execute('''
            INSERT INTO attendance (uid, nama, nim, action, face_status) 
            VALUES (?, ?, ?, ?, ?)
        ''', (uid, nama, nim, action, face_status))

        
        conn.commit()
        conn.close()

        # Update Heartbeat on tap as well, just in case
        global last_device_ping
        last_device_ping = datetime.now()

        # RETURN Face Status to ESP32 for LCD Feedback
        return jsonify({
            "status": "ok", 
            "face_status": face_status,
            "message": "Absensi Berhasil" if face_status == 'MATCH' else "Wajah Tidak Dikenali"
        }), 200

    except Exception as e:
        print(f"[ERROR TAP] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- DASHBOARD ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('monitor')) # Redirect to Monitor as default for V2

@app.route('/monitor')
def monitor():
    conn = get_db_connection()
    # Logic: Get the very last action for each UID using MAX(id)
    # V2.5: Added face_status to selection
    query = '''
        SELECT 
            a.uid, a.nama, a.nim, a.action, a.face_status,
            datetime(a.timestamp, 'localtime') as timestamp
        FROM attendance a
        INNER JOIN (
            SELECT uid, MAX(id) as max_id
            FROM attendance
            GROUP BY uid
        ) b ON a.uid = b.uid AND a.id = b.max_id
        ORDER BY a.id DESC
    '''
    records = conn.execute(query).fetchall()
    conn.close()
    
    # Calculate status offline/online based on last ping
    global last_device_ping
    seconds_since_ping = 999
    if last_device_ping:
        delta = datetime.now() - last_device_ping
        seconds_since_ping = int(delta.total_seconds())
        
    return render_template('monitor.html', records=records, seconds_since_ping=seconds_since_ping)

@app.route('/log')
def log():
    conn = get_db_connection()
    
    # Filter Parameters
    search = request.args.get('q', '')
    date_filter = request.args.get('date', 'all')
    
    # Base Query - V2.5: Added face_status
    query = "SELECT id, uid, nama, nim, action, face_status, datetime(timestamp, 'localtime') as timestamp FROM attendance WHERE 1=1"
    params = []

    # Search Logic
    if search:
        query += " AND (nama LIKE ? OR nim LIKE ? OR uid LIKE ?)"
        wildcard_search = f"%{search}%"
        params.extend([wildcard_search, wildcard_search, wildcard_search])

    # Date Filter Logic
    if date_filter == 'today':
        query += " AND date(timestamp, 'localtime') = date('now', 'localtime')"
    elif date_filter == 'week':
        query += " AND date(timestamp, 'localtime') >= date('now', 'localtime', '-7 days')"
        
    query += " ORDER BY id DESC LIMIT 100"

    records = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('log.html', records=records, search=search, date_filter=date_filter)

@app.route('/mahasiswa/<uid>')
def mahasiswa_detail(uid):
    conn = get_db_connection()
    
    # Get Student Info (from latest log or users table)
    # We prefer users table but if empty, use log
    user_query = "SELECT nama, nim FROM users WHERE uid = ?"
    user = conn.execute(user_query, (uid,)).fetchone()
    
    # Get Attendance History - V2.5: Added face_status
    log_query = '''
        SELECT action, face_status, datetime(timestamp, 'localtime') as timestamp 
        FROM attendance 
        WHERE uid = ? 
        ORDER BY id DESC
    '''
    logs = conn.execute(log_query, (uid,)).fetchall()
    
    conn.close()
    
    student_name = user['nama'] if user else (logs[0]['nama'] if logs else 'Unknown')
    student_nim = user['nim'] if user else (logs[0]['nim'] if logs else 'Unknown')
    
    # V2.5: Calculate stats for this student
    match_count = sum(1 for log in logs if log['face_status'] == 'MATCH')
    mismatch_count = sum(1 for log in logs if log['face_status'] == 'MISMATCH')
    
    return render_template('mahasiswa.html', uid=uid, nama=student_name, nim=student_nim, logs=logs, 
                           match_count=match_count, mismatch_count=mismatch_count)

@app.route('/rekap')
def rekap():
    conn = get_db_connection()
    # Logic: Count total 'IN' per student
    query = '''
        SELECT nama, nim, uid, COUNT(*) as total_in 
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
    # Logic: Filter where latest action is 'IN'
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

@app.route('/stats')
def stats():
    conn = get_db_connection()
    
    # 1. Total Students (Unique UIDs in logs)
    total_students = conn.execute("SELECT COUNT(DISTINCT uid) FROM attendance").fetchone()[0]
    
    # 2. Total Events
    total_events = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    
    # 3. Total IN vs TOTAL OUT
    in_count = conn.execute("SELECT COUNT(*) FROM attendance WHERE action='IN'").fetchone()[0]
    out_count = conn.execute("SELECT COUNT(*) FROM attendance WHERE action='OUT'").fetchone()[0]
    
    # 4. Daily Attendance (Last 7 Days)
    # Using SQLite strftime to group by YYYY-MM-DD
    daily_query = '''
        SELECT date(timestamp, 'localtime') as day, count(*) as count 
        FROM attendance 
        WHERE action = 'IN'
        GROUP BY day 
        ORDER BY day DESC 
        LIMIT 7
    '''
    daily_data = conn.execute(daily_query).fetchall()
    
    # V2.5: Face Recognition Stats
    # Aggregate MATCH, MISMATCH, UNKNOWN
    face_stats_query = '''
        SELECT face_status, COUNT(*) as count
        FROM attendance
        WHERE action = 'IN'
        GROUP BY face_status
    '''
    face_rows = conn.execute(face_stats_query).fetchall()
    face_stats = {row['face_status']: row['count'] for row in face_rows}
    
    count_match = face_stats.get('MATCH', 0)
    count_mismatch = face_stats.get('MISMATCH', 0)
    count_unknown = face_stats.get('UNKNOWN', 0) + face_stats.get(None, 0) # Handle nulls if any
    
    total_in_for_calc = count_match + count_mismatch + count_unknown
    success_rate = round((count_match / total_in_for_calc * 100), 1) if total_in_for_calc > 0 else 0
    
    conn.close()
    
    # Format data for Chart.js
    chart_labels = [row['day'] for row in daily_data][::-1] # Reverse to be chronological
    chart_values = [row['count'] for row in daily_data][::-1]
    
    return render_template('stats.html', 
                           total_students=total_students, 
                           total_events=total_events,
                           in_count=in_count, 
                           out_count=out_count,
                           chart_labels=chart_labels,
                           chart_values=chart_values,
                           count_match=count_match,
                           count_mismatch=count_mismatch,
                           count_unknown=count_unknown,
                           success_rate=success_rate)

if __name__ == '__main__':
    init_db()
    # Bind to 0.0.0.0 to be accessible on local network (essential for Pi)
    print("Server running on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
