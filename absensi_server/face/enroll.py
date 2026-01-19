import cv2, os, sys

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
target = 30

print("\nInstruksi:")
print("- Hadapkan wajah ke kamera (cahaya cukup)")
print("- Tekan SPACE untuk ambil foto")
print("- Target 30 foto")
print("- Tekan Q untuk keluar\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5)

    # draw boxes
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 2)

    cv2.putText(frame, f"{uid}  {count}/{target}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

    cv2.imshow("ENROLL", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    if key == 32:  # SPACE
        if len(faces) == 0:
            print("Tidak ada wajah terdeteksi. Coba lagi.")
            continue

        # ambil wajah terbesar
        faces_sorted = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
        x, y, w, h = faces_sorted[0]
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (200, 200))

        count += 1
        out_path = os.path.join(save_dir, f"{count:03d}.png")
        cv2.imwrite(out_path, face)
        print("Saved:", out_path)

        if count >= target:
            break

cap.release()
cv2.destroyAllWindows()
print("Selesai enroll:", save_dir)
