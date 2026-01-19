import cv2, os, sys, time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def sanitize_uid(raw_uid):
    return raw_uid.replace(":", "-").strip().upper()

raw_input_uid = input("Masukkan UID (contoh AA:BB:CC:DD): ")
uid = sanitize_uid(raw_input_uid)

print(f"Menggunakan UID Folder: {uid}")

save_dir = os.path.join(BASE_DIR, "dataset", uid)
os.makedirs(save_dir, exist_ok=True)

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("WARNING: Webcam default (0) gagal. Mencoba index 1...")
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        raise RuntimeError("Webcam tidak kebuka. Cek koneksi kamera.")

# Try standard path first, then fallback to built-in OpenCV path
local_cascade = os.path.join(BASE_DIR, "cascades", "haarcascade_frontalface_default.xml")
if os.path.exists(local_cascade):
    CASCADE_PATH = local_cascade
else:
    # Use built-in OpenCV classifier data
    CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

if face_cascade.empty():
    raise RuntimeError(f"Haarcascade gagal load dari: {CASCADE_PATH}")

count = 0
target = 120  # Target dinaikkan (Rekomendasi: 120-150)

print("\n=== AUTO ENROLL MODE ===")
print(f"- Target: {target} foto")
print("- Foto akan diambil otomatis setiap 0.3 detik")
print("- Gerakkan wajah perlahan (Kiri, Kanan, Atas, Bawah, Senyum)")
print("- Tekan 's' untuk START/PAUSE Auto Capture")
print("- Tekan 'q' untuk Keluar\n")

last_capture_time = 0
capturing = False

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5)

    # Draw UI
    status_text = "PAUSED (Tekan 's' to Start)"
    color = (0, 0, 255) # Red
    
    if capturing:
        status_text = "AUTO CAPTURING..."
        color = (0, 255, 0) # Green

    # draw boxes
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

    cv2.putText(frame, f"{uid} | {count}/{target}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
    cv2.putText(frame, status_text, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imshow("ENROLL - Auto Mode", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    
    # Toggle Start/Stop
    if key == ord('s'): 
        capturing = not capturing
        last_capture_time = time.time() # Reset timer biar ga langsung jepret

    # Logic Auto Capture
    if capturing and len(faces) > 0:
        now = time.time()
        # Delay 0.3 detik antar foto biar tidak duplikat persis
        if now - last_capture_time > 0.3:
            # Ambil wajah terbesar
            faces_sorted = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
            x, y, w, h = faces_sorted[0]
            
            # Tambah sedikit margin (padding) biar dagu/jidat ga kepotong
            padding = 10
            h_pad = min(h + 2*padding, gray.shape[0] - y)
            w_pad = min(w + 2*padding, gray.shape[1] - x)
            y_pad = max(0, y - padding)
            x_pad = max(0, x - padding)
            
            face_img = gray[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]

            try:
                face_img = cv2.resize(face_img, (200, 200))
                
                count += 1
                out_path = os.path.join(save_dir, f"{count:03d}.png")
                cv2.imwrite(out_path, face_img)
                print(f"[{count}/{target}] Saved: {out_path}")
                last_capture_time = now
            except Exception as e:
                print(f"Skip frame: {e}")

            if count >= target:
                print("\n✅ Target tercapai! Selesai.")
                break

cap.release()
cv2.destroyAllWindows()
print("Selesai enroll:", save_dir)
