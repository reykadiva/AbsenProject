import cv2
import os
import numpy as np

DATASET_DIR = "face/dataset"
MODEL_DIR = "face/model"
MODEL_PATH = os.path.join(MODEL_DIR, "lbph_model.xml")
LABELS_PATH = os.path.join(MODEL_DIR, "labels.txt")

os.makedirs(MODEL_DIR, exist_ok=True)

# Ambil semua UID (folder)
uids = sorted([
    d for d in os.listdir(DATASET_DIR)
    if os.path.isdir(os.path.join(DATASET_DIR, d))
])

if not uids:
    raise RuntimeError("Dataset kosong. Jalankan enroll.py dulu.")

print("UID ditemukan:", uids)

uid_to_label = {uid: i for i, uid in enumerate(uids)}

X = []
y = []

for uid, label in uid_to_label.items():
    folder = os.path.join(DATASET_DIR, uid)
    files = sorted(os.listdir(folder))
    print(f"Memproses UID {uid} ({len(files)} gambar)")

    for fn in files:
        if not fn.lower().endswith(".png"):
            continue
        img_path = os.path.join(folder, fn)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print("Gagal baca:", img_path)
            continue
        X.append(img)
        y.append(label)

if not X:
    raise RuntimeError("Tidak ada gambar valid untuk training.")

print("Total gambar:", len(X))

# Pastikan modul face ada
if not hasattr(cv2, "face"):
    raise RuntimeError("cv2.face tidak tersedia. OpenCV-contrib belum terinstall.")

recognizer = cv2.face.LBPHFaceRecognizer_create(
    radius=1,
    neighbors=8,
    grid_x=8,
    grid_y=8
)

recognizer.train(X, np.array(y, dtype=np.int32))
recognizer.save(MODEL_PATH)

with open(LABELS_PATH, "w") as f:
    for uid, label in uid_to_label.items():
        f.write(f"{label},{uid}\n")

print("\nTRAIN SELESAI")
print("Model :", MODEL_PATH)
print("Labels:", LABELS_PATH)
