import cv2
import os

CASCADE_PATH = "face/cascades/haarcascade_frontalface_default.xml"
MODEL_PATH = "face/model/lbph_model.xml"
LABELS_PATH = "face/model/labels.txt"

target_uid = input("Masukkan UID target (contoh 3A:7D:CA:06): ").strip().upper()

# Load label map
label_to_uid = {}
with open(LABELS_PATH, "r") as f:
    for line in f:
        label, uid = line.strip().split(",", 1)
        label_to_uid[int(label)] = uid

# Load model
if not hasattr(cv2, "face"):
    raise RuntimeError("cv2.face tidak tersedia.")

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read(MODEL_PATH)

# Load cascade
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
if face_cascade.empty():
    raise RuntimeError("Haarcascade gagal diload.")

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Webcam tidak bisa dibuka.")

print("\nINSTRUKSI:")
print("- Hadap kamera")
print("- Tekan SPACE untuk verify")
print("- Tekan Q untuk keluar\n")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5)

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255,255,255), 2)

    cv2.imshow("VERIFY FACE", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break

    if key == 32:  # SPACE
        if len(faces) == 0:
            print("❌ Tidak ada wajah terdeteksi")
            continue

        # Ambil wajah terbesar
        faces_sorted = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
        x, y, w, h = faces_sorted[0]
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (200, 200))

        label, confidence = recognizer.predict(face)
        predicted_uid = label_to_uid.get(label, "UNKNOWN")

        print("\nHasil prediksi:")
        print("Predicted UID :", predicted_uid)
        print("Confidence    :", confidence)

        if predicted_uid == target_uid:
            print("✅ MATCH (wajah cocok)")
        else:
            print("❌ MISMATCH (wajah tidak cocok)")

cap.release()
cv2.destroyAllWindows()
