import cv2
import os
import sqlite3
import time
import sys

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR) # Naik satu level ke absensi_server
DB_PATH = os.path.join(PROJECT_ROOT, "absensi.db")

CASCADE_PATH = os.path.join(BASE_DIR, "cascades", "haarcascade_frontalface_default.xml")
if not os.path.exists(CASCADE_PATH):
    CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

MODEL_PATH = os.path.join(BASE_DIR, "model", "lbph_model.xml")
LABELS_PATH = os.path.join(BASE_DIR, "model", "labels.txt")

CONFIDENCE_THRESHOLD = 35.0  # Ultra Strict: < 35 is very secure.
DEBOUNCE_SECONDS = 3.0       # Jeda waktu antar log untuk user yang sama

# SET TO True for Raspberry Pi Headless (No Monitor)
HEADLESS = True 

# --- DATABASE SETUP ---
def log_face_event(uid, name, status):
    """
    Mencatat event wajah ke database agar bisa dibaca oleh server.py saat Tap Kartu.
    Kita log dengan action='FACE_LOG' (dummy) atau biarkan action kosong, 
    yang penting face_status terisi.
    """
    # CRITICAL FIX: Convert filename format (dash) back to ESP32 format (colon)
    # Folder: AA-BB-CC-DD -> DB: AA:BB:CC:DD
    db_uid = uid.replace("-", ":")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert event
        cursor.execute('''
            INSERT INTO attendance (uid, nama, nim, action, face_status) 
            VALUES (?, ?, ?, ?, ?)
        ''', (db_uid, name, "-", "FACE_LOG", status))
        
        conn.commit()
        conn.close()
        print(f"[DB] Logged: {db_uid} (from {uid}) | {status}")
    except Exception as e:
        print(f"[DB ERROR] {e}")

# --- LOAD RESOURCES ---
print("Loading model...")
if not hasattr(cv2, "face"):
    raise RuntimeError("cv2.face tidak tersedia. Install opencv-contrib-python.")

recognizer = cv2.face.LBPHFaceRecognizer_create()
try:
    recognizer.read(MODEL_PATH)
except:
    raise RuntimeError(f"Gagal load model dari {MODEL_PATH}. Pastikan sudah training!")

label_to_uid = {}
if os.path.exists(LABELS_PATH):
    with open(LABELS_PATH, "r") as f:
        for line in f:
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                label_to_uid[int(parts[0])] = parts[1]
else:
    print("WARNING: labels.txt tidak ditemukan.")

face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
if face_cascade.empty():
    raise RuntimeError("Haarcascade gagal diload.")

# --- MAIN LOOP ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Mencoba kamera index 1...")
    cap = cv2.VideoCapture(1)

print("\n=== FACE MONITOR RUNNING ===")
print(f"Database: {DB_PATH}")
print("Press 'q' to quit.\n")

last_log_time = {} # {uid: timestamp}

last_logged_status = "UNKNOWN" # State tracker

while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30))

        # 1. Logic Wajah Hilang -> Reset Status
        if len(faces) == 0:
            if last_logged_status != "UNKNOWN":
                # Wajah hilang, kita anggap unknown
                last_logged_status = "UNKNOWN"
            
            # Hemat CPU
            if HEADLESS: time.sleep(0.05)

        for (x, y, w, h) in faces:
            # Visual
            if not HEADLESS:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Predict
            face_roi = gray[y:y+h, x:x+w]
            try:
                label, confidence = recognizer.predict(face_roi)
                
                # Logic Klasifikasi
                if confidence < CONFIDENCE_THRESHOLD:
                    uid_found = label_to_uid.get(label, "Unknown")
                    status = "MATCH"
                    color = (0, 255, 0)
                else:
                    uid_found = "UNKNOWN"
                    status = "MISMATCH"
                    color = (0, 0, 255)

                # Display Text
                if not HEADLESS:
                    text = f"{uid_found} ({round(confidence)})"
                    cv2.putText(frame, text, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                # --- LOGGING LOGIC UPDATE ---
                now = time.time()
                
                # Cek apakah status berubah drastis? (Misal UNKNOWN -> MATCH)
                is_status_change = (status != last_logged_status)
                
                # Cek debounce
                last_ts = last_log_time.get(uid_found, 0)
                is_debounce_pass = (now - last_ts > DEBOUNCE_SECONDS)

                if is_status_change or is_debounce_pass:
                    log_face_event(uid_found, "Auto-Detect", status)
                    last_log_time[uid_found] = now
                    last_logged_status = status # Update status terakhir

            except Exception as e:
                print(f"Error predict: {e}")

    if not HEADLESS:
        cv2.imshow("WebAbsen Face Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        # Hemat CPU saat headless
        time.sleep(0.01)

cap.release()
cv2.destroyAllWindows()
