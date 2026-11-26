"""
evaluation.py
=============
Evaluasi sederhana hasil enhancement: brightness, contrast, histogram, ketajaman,
peringatan kualitas, serta PSNR/SSIM (hanya bermakna jika ada citra referensi yang relevan).
"""
import cv2
import numpy as np


def to_gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def image_stats(img: np.ndarray) -> dict:
    """Statistik dasar pada citra grayscale."""
    g = to_gray(img)
    return {
        "brightness": round(float(g.mean()), 2),                       # mean intensity
        "contrast": round(float(g.std()), 2),                          # standar deviasi
        "sharpness": round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 2),  # variansi Laplacian
        "dark_pct": round(float((g <= 40).mean() * 100), 2),           # % piksel sangat gelap
        "saturated_pct": round(float((g >= 250).mean() * 100), 2),     # % piksel hampir putih
    }


def histograms(img: np.ndarray) -> dict:
    """Histogram 256 bin untuk kanal R, G, B, dan grayscale."""
    def h(ch):
        return cv2.calcHist([ch], [0], None, [256], [0, 256]).flatten().astype(int).tolist()
    b, g, r = cv2.split(img)
    return {"r": h(r), "g": h(g), "b": h(b), "gray": h(to_gray(img))}


def psnr(ref: np.ndarray, img: np.ndarray) -> float:
    """PSNR (dB). Hanya valid bila `ref` adalah citra referensi yang sesuai (mis. versi siang hari
    dari adegan yang sama). Terhadap citra asli yang gelap, nilainya TIDAK menunjukkan kualitas."""
    if ref.shape != img.shape:
        raise ValueError("Ukuran citra referensi dan citra uji harus sama.")
    mse = np.mean((ref.astype(np.float64) - img.astype(np.float64)) ** 2)
    return float("inf") if mse == 0 else float(10 * np.log10(255.0 ** 2 / mse))


def ssim(ref: np.ndarray, img: np.ndarray) -> float:
    """SSIM sederhana (jendela Gaussian 11x11, sigma 1.5) pada grayscale. Syarat sama dengan PSNR."""
    if ref.shape != img.shape:
        raise ValueError("Ukuran citra referensi dan citra uji harus sama.")
    a, b = to_gray(ref).astype(np.float64), to_gray(img).astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    blur = lambda x: cv2.GaussianBlur(x, (11, 11), 1.5)
    mu_a, mu_b = blur(a), blur(b)
    var_a, var_b = blur(a * a) - mu_a ** 2, blur(b * b) - mu_b ** 2
    cov = blur(a * b) - mu_a * mu_b
    m = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))
    return float(m.mean())


def compare(orig: np.ndarray, result: np.ndarray, orig_bytes: int, result_bytes: int) -> dict:
    """Bandingkan citra asli dan hasil; kembalikan statistik, selisih, peringatan, dan histogram."""
    so, sr = image_stats(orig), image_stats(result)
    h, w = orig.shape[:2]
    so.update(width=w, height=h, file_size=orig_bytes)
    sr.update(width=w, height=h, file_size=result_bytes)
    delta = {"brightness": round(sr["brightness"] - so["brightness"], 2),
             "contrast": round(sr["contrast"] - so["contrast"], 2)}

    warnings = []
    if sr["saturated_pct"] > 3 and sr["saturated_pct"] > so["saturated_pct"] + 1:
        warnings.append(f"{sr['saturated_pct']}% piksel hasil hampir putih (jenuh). Naikkan nilai gamma atau turunkan clip limit.")
    if sr["contrast"] > 75:
        warnings.append("Kontras hasil sangat tinggi (over-contrast). Turunkan clip limit CLAHE.")
    if so["sharpness"] > 0 and sr["sharpness"] / so["sharpness"] > 6 and sr["sharpness"] > 100:
        warnings.append("Ketajaman naik tajam; noise kemungkinan ikut menguat. Turunkan amount atau naikkan threshold sharpening.")
    if sr["brightness"] < 60:
        warnings.append("Citra hasil masih tergolong gelap. Coba turunkan gamma (mis. 0.5–0.6).")
    if abs(delta["brightness"]) < 3 and abs(delta["contrast"]) < 3:
        warnings.append("Perubahan brightness dan kontras sangat kecil. Periksa metode yang diaktifkan dan parameternya.")

    return {"original": so, "enhanced": sr, "delta": delta, "warnings": warnings,
            "histograms": {"original": histograms(orig), "enhanced": histograms(result)}}
