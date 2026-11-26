"""
enhancement.py
==============
Modul inti Image Enhancement: Gamma Correction, CLAHE, dan Unsharp Mask,
serta fungsi pipeline yang menjalankannya secara berurutan.

Semua fungsi menerima/mengembalikan citra OpenCV (numpy array uint8, urutan BGR),
tidak bergantung pada Flask sehingga mudah diuji sendiri.
"""
import cv2
import numpy as np

# Nilai awal parameter (gamma < 1 mencerahkan citra gelap)
DEFAULT_PARAMS = {
    "use_gamma": True, "gamma": 0.7,
    "use_clahe": True, "clip_limit": 2.0, "tile_grid": 8,
    "use_sharpen": True, "amount": 0.8, "sigma": 1.2, "threshold": 3,
}


def gamma_correction(img: np.ndarray, gamma: float = 0.7) -> np.ndarray:
    """Gamma Correction memakai LUT.

    Rumus: s = 255 * (r / 255) ** gamma
    gamma < 1 -> citra lebih terang (cocok untuk citra malam),
    gamma > 1 -> citra lebih gelap.
    LUT dihitung sekali untuk 256 nilai intensitas, lalu diterapkan ke seluruh piksel.
    """
    if gamma <= 0:
        raise ValueError("Gamma harus lebih besar dari 0.")
    table = (np.arange(256) / 255.0) ** gamma * 255.0
    table = np.clip(table, 0, 255).astype(np.uint8)
    return cv2.LUT(img, table)


def apply_clahe(img: np.ndarray, clip_limit: float = 2.0, tile_grid: int = 8) -> np.ndarray:
    """CLAHE pada kanal luminance (L) ruang warna LAB.

    Hanya kanal L yang diubah, kanal a dan b tetap sehingga warna tidak banyak bergeser.
    clip_limit membatasi penguatan kontras (nilai besar -> lebih kontras tetapi lebih berisiko noise).
    tile_grid menentukan jumlah blok (tile_grid x tile_grid) untuk ekualisasi lokal.
    """
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit),
                            tileGridSize=(int(tile_grid), int(tile_grid)))
    if img.ndim == 2:
        return clahe.apply(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def unsharp_mask(img: np.ndarray, amount: float = 0.8, sigma: float = 1.2,
                 threshold: int = 0) -> np.ndarray:
    """Unsharp Mask.

    hasil = citra + amount * (citra - citra_blur)  ==  (1+amount)*citra - amount*blur
    threshold: selisih terhadap blur di bawah nilai ini dianggap noise/area halus
    dan tidak dipertajam, sehingga noise tidak ikut menguat.
    """
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=float(sigma))
    sharp = cv2.addWeighted(img, 1.0 + amount, blurred, -amount, 0)  # saturasi otomatis 0..255
    if threshold > 0:
        diff = cv2.absdiff(img, blurred)
        low = diff < threshold if img.ndim == 2 else (diff.max(axis=2) < threshold)[..., None]
        sharp = np.where(low, img, sharp).astype(np.uint8)
    return sharp


def run_pipeline(img: np.ndarray, p: dict):
    """Pipeline: Input -> Gamma -> CLAHE -> Sharpening -> Output.

    Setiap metode bisa diaktifkan/nonaktifkan lewat p["use_*"].
    Mengembalikan (citra_hasil, daftar_tahap) dengan tiap tahap berisi hasil kumulatif.
    """
    steps, out = [], img.copy()
    if p.get("use_gamma"):
        out = gamma_correction(out, p["gamma"])
        steps.append({"key": "gamma", "label": f"Setelah Gamma (γ={p['gamma']})", "image": out.copy()})
    if p.get("use_clahe"):
        out = apply_clahe(out, p["clip_limit"], p["tile_grid"])
        steps.append({"key": "clahe", "label": f"Setelah CLAHE (clip={p['clip_limit']}, tile={p['tile_grid']}×{p['tile_grid']})",
                      "image": out.copy()})
    if p.get("use_sharpen"):
        out = unsharp_mask(out, p["amount"], p["sigma"], p["threshold"])
        steps.append({"key": "sharpen", "label": f"Setelah Sharpening (amount={p['amount']})", "image": out.copy()})
    return out, steps


def methods_used(p: dict) -> list:
    """Daftar metode aktif beserta parameternya (untuk ditampilkan di UI)."""
    used = []
    if p.get("use_gamma"):
        used.append({"name": "Gamma Correction", "params": f"gamma = {p['gamma']}"})
    if p.get("use_clahe"):
        used.append({"name": "CLAHE (kanal L, LAB)", "params": f"clip limit = {p['clip_limit']}, tile = {p['tile_grid']}×{p['tile_grid']}"})
    if p.get("use_sharpen"):
        used.append({"name": "Unsharp Mask", "params": f"amount = {p['amount']}, sigma = {p['sigma']}, threshold = {p['threshold']}"})
    return used
