# Aplikasi Peningkatan Kualitas Citra CCTV Malam Hari (Flask + OpenCV)

Tugas Pengolahan Citra Digital — bidang kajian *Image Enhancement*.
Aplikasi web lokal untuk memperbaiki citra CCTV minim cahaya dengan **Gamma Correction (LUT) → CLAHE (kanal L, LAB) → Unsharp Mask**,
lengkap dengan comparison slider, histogram, evaluasi brightness/kontras, unduh hasil, riwayat, dan menu Deteksi Objek (opsional).

## Struktur proyek
```
cctv_enhancement/
├── app.py               # Flask: routing, upload + validasi, proses, download, riwayat, API deteksi
├── enhancement.py       # gamma_correction, apply_clahe, unsharp_mask, run_pipeline
├── evaluation.py        # brightness, kontras, histogram, ketajaman, peringatan, PSNR/SSIM (butuh referensi)
├── detection.py         # (opsional) YOLO person/car/motorcycle/bus/truck, plat nomor bila ada models/plate.pt
├── storage.py           # metadata lokal (data/store.json)
├── generate_samples.py  # membuat 2 gambar malam sintetis di samples/
├── requirements.txt
├── data/                # store.json dibuat otomatis
├── models/              # (opsional) plate.pt
├── samples/             # gambar contoh
├── static/{css,js,uploads,results}
└── templates/{base,index,result,history,detection}.html
```

## Instalasi (Windows, terminal VS Code)
Buka folder `cctv_enhancement` di VS Code (File → Open Folder), lalu buka terminal (Ctrl+`).
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Jika PowerShell menolak mengaktifkan venv: `Set-ExecutionPolicy -Scope Process Bypass`, lalu ulangi `venv\Scripts\activate`.
Gunakan Python 3.9–3.12.

## Menjalankan
```powershell
python generate_samples.py   # opsional: membuat samples/cctv_malam_1.jpg dan _2.jpg
python app.py
```
Buka **http://127.0.0.1:5000**. Hentikan dengan Ctrl+C.

## Cara pakai
1. Seret minimal 2 gambar ke area unggah (JPG/JPEG/PNG, maks. 10 MB per file).
2. Klik salah satu kartu gambar untuk memilihnya.
3. Atur metode (toggle) dan parameter (slider), atau pakai preset.
4. Klik **Process Image**. Hasil tampil sebagai slider before/after, berdampingan, dan per tahap, beserta histogram dan evaluasi.
5. Unduh PNG/JPG. Riwayat tersimpan di menu **Riwayat**; tombol hapus membersihkan file sementara.

## Deteksi objek (opsional)
Aplikasi utama berjalan tanpa fitur ini. Untuk mengaktifkan: `pip install ultralytics` (CPU cukup; bobot `yolov8n.pt` diunduh otomatis saat pertama dipakai, butuh internet).
Deteksi plat nomor hanya berjalan jika Anda menaruh model sendiri di `models/plate.pt`.
Enhancement tidak menambah detail yang tidak ada pada citra asli, dan fitur ini tidak dimaksudkan untuk mengenali identitas.

## Catatan evaluasi
Brightness (rata-rata) dan kontras (standar deviasi) dihitung pada grayscale. `evaluation.psnr()` dan `evaluation.ssim()` tersedia, tetapi
hanya valid bila ada citra referensi yang relevan (mis. adegan yang sama pada siang hari, ukuran sama). Terhadap citra malam asli, nilainya tidak menunjukkan kualitas.

## Keamanan dan privasi
Hanya JPG/PNG yang lolos (cek ekstensi, signature file, dan decode OpenCV); ukuran dibatasi; ID file hanya heksadesimal; semua data disimpan lokal.
Server hanya mendengarkan 127.0.0.1. Gunakan data CCTV yang Anda miliki atau yang sudah diizinkan.

## Masalah umum
| Gejala | Solusi |
|---|---|
| `ModuleNotFoundError: cv2` | Aktifkan venv lalu `pip install -r requirements.txt` |
| Port 5000 dipakai | Ubah `port=5000` di akhir `app.py` |
| Menu Deteksi Objek menampilkan "belum aktif" | `pip install ultralytics` (opsional) |
| Hasil terlalu terang/noisy | Naikkan gamma, turunkan clip limit/amount, atau naikkan threshold sharpening |
