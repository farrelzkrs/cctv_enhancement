"""
generate_samples.py
Membuat 2 gambar CCTV malam SINTETIS (bukan data pribadi) di folder samples/ untuk uji coba cepat.
Untuk laporan, gunakan gambar CCTV malam asli yang boleh dipakai (milik sendiri / lisensi terbuka).
"""
import os
import cv2
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")
os.makedirs(OUT, exist_ok=True)


def scene(seed, w=1280, h=720):
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.uint8)
    for y in range(h // 2):                                   # langit/gedung
        img[y] = (120 + y // 6, 95 + y // 8, 80)
    img[h // 2:] = (90, 90, 95)                               # jalan
    for _ in range(8):                                        # gedung
        x, bw, bh = int(rng.integers(0, w - 150)), int(rng.integers(90, 220)), int(rng.integers(120, 300))
        cv2.rectangle(img, (x, h // 2 - bh), (x + bw, h // 2), tuple(int(v) for v in rng.integers(60, 140, 3)), -1)
    for x in range(0, w, 160):                                # marka jalan
        cv2.rectangle(img, (x, int(h * .78)), (x + 80, int(h * .78) + 8), (200, 200, 200), -1)
    for i in range(2):                                        # kendaraan sederhana + plat
        x, y = int(rng.integers(100, w - 360)), int(h * .58) + i * 90
        cv2.rectangle(img, (x, y), (x + 220, y + 70), tuple(int(v) for v in rng.integers(40, 200, 3)), -1)
        cv2.rectangle(img, (x + 50, y - 35), (x + 170, y), (170, 190, 200), -1)
        cv2.circle(img, (x + 45, y + 72), 18, (20, 20, 20), -1); cv2.circle(img, (x + 175, y + 72), 18, (20, 20, 20), -1)
        cv2.rectangle(img, (x + 80, y + 35), (x + 140, y + 55), (235, 235, 235), -1)
        cv2.putText(img, f"B {1200 + i * 37 + seed} XY", (x + 82, y + 51), cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 0, 0), 1)
    return img


def to_night(img, seed):
    rng = np.random.default_rng(seed + 100)
    f = (img / 255.0) ** 2.6 * 0.55                           # gelapkan dengan gamma tinggi
    out = f * 255
    for _ in range(3):                                        # lampu jalan
        c = (int(rng.integers(100, 1180)), int(rng.integers(60, 200)))
        glow = np.zeros(img.shape[:2], np.float32); cv2.circle(glow, c, 22, 1.0, -1)
        out += cv2.GaussianBlur(glow, (0, 0), 38)[..., None] * np.array([120, 190, 255]) * 1.4
    out += rng.normal(0, 3.5, img.shape)                      # noise sensor
    return np.clip(out, 0, 255).astype(np.uint8)


for i in (1, 2):
    path = os.path.join(OUT, f"cctv_malam_{i}.jpg")
    cv2.imencode(".jpg", to_night(scene(i), i), [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tofile(path)
    print("dibuat:", path)
