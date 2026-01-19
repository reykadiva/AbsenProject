import cv2
import os
import sqlite3
import time
import sys

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "absensi.db")
MODEL_PATH = os.path.join(BASE_DIR, "model", "lbph_model.xml")
LABELS_PATH = os.path.join(BASE_DIR, "model", "labels.txt")

CONFIDENCE_THRESHOLD = 45.0  # Slightly relaxed (was 35.0)
DEBOUNCE_SECONDS = 3.0       # Jeda log yang sama

# SET TO True for Raspberry Pi Headless (No Monitor)
# Change to False if you want to debug with GUI window
HEADLESS = True 

# --- DATABASE LOGGING FUNCTION ---
def log_face_event(uid, name, status):
    """
    Mencatat event wajah ke database agar bisa dibaca oleh server.py saat Tap Kartu.
    """
    # Fix: Convert filename format (dash) back to ESP32 format (colon)
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
        print(f"[DB] Logged: {db_uid} | {status}")
    except Exception as e:
        print(f"[DB ERROR] {e}")

# --- LOAD RESOURCES ---
try:
    if not os.path.exists(MODEL_PATH) or not os.path.exists(LABELS_PATH):
        raise RuntimeError(f"Model/Labels not found at {MODEL_PATH}")

    print(f"Loading model: {MODEL_PATH}")
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_PATH)

    label_to_uid = {}
    print(f"Loading labels: {LABELS_PATH}")
    with open(LABELS_PATH, "r") as f:
        for line in f:
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                label_to_uid[int(parts[0])] = parts[1]
    
except Exception as e:
    print(f"[CRITICAL] Failed to load resources: {e}")
    sys.exit(1)

# --- INIT CAMERA & CASCADE ---
# Use local cascade file
cascade_path = os.path.join(BASE_DIR, "cascades", "haarcascade_frontalface_default.xml")

face_cascade = cv2.CascadeClassifier(cascade_path)
if face_cascade.empty():
    print(f"[CRITICAL] Haarcascade failed to load from: {cascade_path}")
    sys.exit(1)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Webcam index 0 failed, trying index 1...")
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("[CRITICAL] No camera found.")
        sys.exit(1)

print("\n=== FACE MONITOR RUNNING ===")
print(f"Threshold: {CONFIDENCE_THRESHOLD}")
print(f"Headless: {HEADLESS}")
print("Press 'q' to quit (if GUI enabled).\n")

# --- MAIN LOOP ---
last_log_time = {} # {uid: timestamp}
last_logged_status = "UNKNOWN"

while True:
    ret, frame = cap.read()
    if not ret:
        time.sleep(0.1)
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray, 
        scaleFactor=1.2, 
        minNeighbors=5, 
        minSize=(30, 30)
    )

    # 1. Logic Wajah Hilang -> Reset Status Local
    if len(faces) == 0:
        if last_logged_status != "UNKNOWN":
            last_logged_status = "UNKNOWN"
            # print("Face lost. Reset status.")
        
        # Hemat CPU saat idle
        if HEADLESS:
            time.sleep(0.05)

    for (x, y, w, h) in faces:
        # Visual Box
        if not HEADLESS:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Predict
        face_roi = gray[y:y+h, x:x+w]
        try:
            label, confidence = recognizer.predict(face_roi)
            
            # Logic Klasifikasi
            uid_found_temp = label_to_uid.get(label, "Unknown")
            print(f"[DEBUG] Pred: {uid_found_temp} | Score: {round(confidence, 1)} | Thr: {CONFIDENCE_THRESHOLD}")

            if confidence < CONFIDENCE_THRESHOLD:
                uid_found = uid_found_temp
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

            # --- LOGGING LOGIC ---
            now = time.time()
            
            # Log jika:
            # 1. Status wajah BERUBAH (Contoh: UNKNOWN -> MATCH)
            # 2. Atau Debounce time sudah lewat (Update berkala)
            is_status_change = (status != last_logged_status)
            last_ts = last_log_time.get(uid_found, 0)
            is_debounce_pass = (now - last_ts > DEBOUNCE_SECONDS)

            if is_status_change or is_debounce_pass:
                # Hindari log spam "UNKNOWN" terus menerus
                # Log UNKNOWN hanya jika sebelumnya MATCH/MISMATCH (status change)
                if status == "UNKNOWN" and not is_status_change:
                    pass 
                else:
                    log_face_event(uid_found, "Auto-Detect", status)
                    last_log_time[uid_found] = now
                    last_logged_status = status

        except Exception as e:
            print(f"Error predict: {e}")

    # GUI handling
    if not HEADLESS:
        cv2.imshow("WebAbsen Face Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    else:
        # Sleep kecil di mode headless agar loop tidak makan CPU 100%
        time.sleep(0.01)

cap.release()
cv2.destroyAllWindows()
