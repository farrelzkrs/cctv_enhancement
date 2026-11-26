"""
detection.py  (FITUR OPSIONAL)
==============================
Deteksi objek memakai YOLO pretrained (paket `ultralytics`).
Aplikasi utama TIDAK bergantung pada modul ini: bila ultralytics belum dipasang,
is_available() bernilai False dan menu Deteksi Objek menampilkan petunjuk instalasi.

Catatan: enhancement hanya memperjelas tampilan; ia tidak menambah detail yang tidak ada pada
citra asli, dan hasil deteksi tidak dipakai untuk mengenali identitas seseorang.
"""
import importlib.util
import os

import cv2

# Kelas COCO yang dideteksi
TARGET_CLASSES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
COLORS = {"person": (255, 200, 0), "car": (0, 220, 255), "motorcycle": (80, 200, 80),
          "bus": (60, 120, 255), "truck": (200, 90, 255), "plate": (0, 255, 255)}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLATE_MODEL_PATH = os.path.join(BASE_DIR, "models", "plate.pt")   # opsional, taruh model plat sendiri
_models = {}


def is_available() -> bool:
    return importlib.util.find_spec("ultralytics") is not None


def plate_model_available() -> bool:
    return os.path.exists(PLATE_MODEL_PATH)


def _get_model(name: str):
    if name not in _models:
        from ultralytics import YOLO          # import malas agar aplikasi tetap jalan tanpa paket ini
        _models[name] = YOLO(name)            # "yolov8n.pt" diunduh otomatis saat pertama kali (butuh internet)
    return _models[name]


def _draw(img, box, label, color):
    x1, y1, x2, y2 = [int(v) for v in box]
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(img, (x1, max(0, y1 - th - 6)), (x1 + tw + 6, y1), color, -1)
    cv2.putText(img, label, (x1 + 3, max(th, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def detect(img, conf: float = 0.25):
    """Jalankan deteksi. Mengembalikan (citra_beranotasi, daftar_deteksi)."""
    model = _get_model("yolov8n.pt")
    res = model.predict(img, conf=conf, classes=list(TARGET_CLASSES), verbose=False)[0]
    out, dets = img.copy(), []
    for b in res.boxes:
        name = TARGET_CLASSES[int(b.cls[0])]
        score = float(b.conf[0])
        _draw(out, b.xyxy[0].tolist(), f"{name} {score:.2f}", COLORS[name])
        dets.append({"label": name, "confidence": round(score, 3)})
    if plate_model_available():               # deteksi plat nomor hanya jika model tersedia
        pres = _get_model(PLATE_MODEL_PATH).predict(img, conf=conf, verbose=False)[0]
        for b in pres.boxes:
            score = float(b.conf[0])
            _draw(out, b.xyxy[0].tolist(), f"plate {score:.2f}", COLORS["plate"])
            dets.append({"label": "plate", "confidence": round(score, 3)})
    return out, dets
