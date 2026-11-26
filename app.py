"""
app.py
======
Aplikasi Flask: routing, upload + validasi, pemrosesan, penyimpanan hasil, download, riwayat,
dan menu opsional Deteksi Objek. Logika pengolahan citra ada di enhancement.py / evaluation.py.
"""
import io
import os
import re
import uuid
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

import detection
import enhancement
import evaluation
import storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
RESULT_DIR = os.path.join(BASE_DIR, "static", "results")
for d in (UPLOAD_DIR, RESULT_DIR):
    os.makedirs(d, exist_ok=True)
storage.init(os.path.join(BASE_DIR, "data", "store.json"))

ALLOWED_EXT = {"jpg", "jpeg", "png"}
MAX_FILE_BYTES = 10 * 1024 * 1024            # 10 MB per file
MAX_SIDE = 2560                              # sisi terpanjang; gambar lebih besar diperkecil agar proses cepat
ID_RE = re.compile(r"^[0-9a-f]{12}$")        # id hanya heksadesimal -> mencegah path traversal

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024   # batas total satu request


# ------------------------------------------------------------------ util
def err(msg: str, code: int = 400):
    return jsonify(ok=False, error=msg), code


def read_image(path: str):
    """Baca citra lewat imdecode (aman untuk path Windows ber-spasi/unicode)."""
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Gambar tidak dapat dibaca.")
    return img


def write_image(path: str, img, quality: int = 95) -> int:
    ext = os.path.splitext(path)[1].lower()
    params = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext in (".jpg", ".jpeg") else []
    ok, buf = cv2.imencode(ext, img, params)
    if not ok:
        raise ValueError("Gagal menyimpan gambar.")
    buf.tofile(path)
    return int(buf.size)


def detect_format(data: bytes):
    """Cek signature file (magic bytes), bukan hanya ekstensi."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return None


def static_url(folder: str, filename: str) -> str:
    return f"/static/{folder}/{filename}"


def public_upload(u: dict) -> dict:
    return {**u, "url": static_url("uploads", u["filename"])}


def parse_params(raw: dict) -> dict:
    """Validasi dan batasi parameter dari klien."""
    def num(key, lo, hi, cast=float):
        try:
            v = cast(raw.get(key, enhancement.DEFAULT_PARAMS[key]))
        except (TypeError, ValueError):
            raise ValueError(f"Parameter '{key}' harus berupa angka.")
        if not lo <= v <= hi:
            raise ValueError(f"Parameter '{key}' harus di antara {lo} dan {hi}.")
        return round(v, 2) if cast is float else v

    p = {
        "use_gamma": bool(raw.get("use_gamma")),
        "use_clahe": bool(raw.get("use_clahe")),
        "use_sharpen": bool(raw.get("use_sharpen")),
        "gamma": num("gamma", 0.2, 3.0),
        "clip_limit": num("clip_limit", 0.5, 10.0),
        "tile_grid": num("tile_grid", 2, 16, int),
        "amount": num("amount", 0.0, 3.0),
        "sigma": num("sigma", 0.3, 5.0),
        "threshold": num("threshold", 0, 30, int),
    }
    if not (p["use_gamma"] or p["use_clahe"] or p["use_sharpen"]):
        raise ValueError("Aktifkan minimal satu metode enhancement.")
    return p


def delete_files(folder: str, names):
    for n in names:
        try:
            os.remove(os.path.join(folder, n))
        except OSError:
            pass


# ------------------------------------------------------------------ halaman
@app.get("/")
def index():
    return render_template("index.html", page="index", defaults=enhancement.DEFAULT_PARAMS)


@app.get("/history")
def history():
    return render_template("history.html", page="history", items=storage.list_items("history"))


@app.get("/result/<rid>")
def result_page(rid):
    rec = storage.get_item("history", rid) if ID_RE.match(rid) else None
    if not rec:
        abort(404)
    return render_template("result.html", page="history", r=rec)


@app.get("/detect")
def detect_page():
    sources = [{"value": f"u:{u['id']}", "label": f"{u['name']} (asli)"} for u in storage.list_items("uploads")]
    sources += [{"value": f"r:{h['id']}", "label": f"{h['original_name']} (hasil enhancement {h['id'][:6]})"}
                for h in storage.list_items("history")]
    return render_template("detection.html", page="detect", sources=sources,
                           available=detection.is_available(), plate=detection.plate_model_available())


# ------------------------------------------------------------------ API upload
@app.get("/api/uploads")
def api_uploads():
    return jsonify(ok=True, uploads=[public_upload(u) for u in storage.list_items("uploads")])


def save_upload(f):
    name = os.path.basename(f.filename or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        raise ValueError("Format tidak didukung. Gunakan JPG, JPEG, atau PNG.")
    data = f.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Ukuran file melebihi 10 MB.")
    fmt = detect_format(data)
    if fmt is None:
        raise ValueError("Isi file bukan gambar JPG/PNG yang valid.")
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Gambar rusak dan tidak dapat dibaca.")

    resized = False
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:                       # perkecil proporsional (tanpa distorsi)
        s = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        resized = True
    uid = uuid.uuid4().hex[:12]
    filename = f"{uid}.{fmt}"
    path = os.path.join(UPLOAD_DIR, filename)
    if resized:
        size = write_image(path, img)
    else:
        with open(path, "wb") as out:
            out.write(data)
        size = len(data)
    h, w = img.shape[:2]
    rec = {"id": uid, "name": name, "filename": filename, "width": w, "height": h,
           "size": size, "resized": resized, "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    storage.add_item("uploads", rec)
    return public_upload(rec)


@app.post("/api/upload")
def api_upload():
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return err("Tidak ada file yang dipilih.")
    saved, errors = [], []
    for f in files:
        try:
            saved.append(save_upload(f))
        except ValueError as e:
            errors.append({"name": f.filename, "error": str(e)})
    return jsonify(ok=bool(saved), uploads=saved, errors=errors), (200 if saved else 400)


@app.delete("/api/upload/<uid>")
def api_delete_upload(uid):
    if not ID_RE.match(uid):
        return err("ID tidak valid.")
    rec = storage.remove_item("uploads", uid)
    if rec:
        delete_files(UPLOAD_DIR, [rec["filename"]])
    return jsonify(ok=True)


# ------------------------------------------------------------------ API proses
@app.post("/api/process")
def api_process():
    payload = request.get_json(silent=True) or {}
    uid = str(payload.get("image_id", ""))
    up = storage.get_item("uploads", uid) if ID_RE.match(uid) else None
    if not up:
        return err("Gambar tidak ditemukan. Unggah atau pilih gambar terlebih dahulu.", 404)
    try:
        params = parse_params(payload.get("params") or {})
        orig = read_image(os.path.join(UPLOAD_DIR, up["filename"]))
    except ValueError as e:
        return err(str(e))

    try:
        result, steps = enhancement.run_pipeline(orig, params)
        rid = uuid.uuid4().hex[:12]
        result_name = f"{rid}.png"
        result_size = write_image(os.path.join(RESULT_DIR, result_name), result)
        step_files = []
        for s in steps:
            fn = f"{rid}_{s['key']}.jpg"
            write_image(os.path.join(RESULT_DIR, fn), s["image"], 90)
            step_files.append({"key": s["key"], "label": s["label"], "filename": fn})
        evalr = evaluation.compare(orig, result, up["size"], result_size)
    except Exception as e:                       # kegagalan tak terduga saat pemrosesan
        app.logger.exception("Gagal memproses gambar")
        return err(f"Gagal memproses gambar: {e}", 500)

    rec = {"id": rid, "upload_id": uid, "original_name": up["name"], "original_file": up["filename"],
           "result_file": result_name, "steps": step_files, "params": params,
           "methods": enhancement.methods_used(params),
           "stats": {k: evalr[k] for k in ("original", "enhanced", "delta", "warnings")},
           "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    storage.add_item("history", rec)
    return jsonify(ok=True, id=rid, original_url=static_url("uploads", up["filename"]),
                   result_url=static_url("results", result_name), methods=rec["methods"], params=params,
                   steps=[{"label": s["label"], "url": static_url("results", s["filename"])} for s in step_files],
                   evaluation=evalr, width=orig.shape[1], height=orig.shape[0])


# ------------------------------------------------------------------ download & riwayat
@app.get("/download/<rid>")
def download(rid):
    rec = storage.get_item("history", rid) if ID_RE.match(rid) else None
    if not rec:
        abort(404)
    fmt = request.args.get("fmt", "png").lower()
    stem = os.path.splitext(rec["original_name"])[0] or "hasil"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)
    path = os.path.join(RESULT_DIR, rec["result_file"])
    if not os.path.exists(path):
        abort(404)
    if fmt in ("jpg", "jpeg"):
        ok, buf = cv2.imencode(".jpg", read_image(path), [cv2.IMWRITE_JPEG_QUALITY, 95])
        return send_file(io.BytesIO(buf.tobytes()), mimetype="image/jpeg",
                         as_attachment=True, download_name=f"{stem}_enhanced.jpg")
    return send_file(path, mimetype="image/png", as_attachment=True, download_name=f"{stem}_enhanced.png")


@app.delete("/api/history/<rid>")
def api_delete_history(rid):
    if not ID_RE.match(rid):
        return err("ID tidak valid.")
    rec = storage.remove_item("history", rid)
    if rec:
        delete_files(RESULT_DIR, [rec["result_file"]] + [s["filename"] for s in rec["steps"]])
    return jsonify(ok=True)


@app.post("/api/cleanup")
def api_cleanup():
    """Hapus semua unggahan, hasil, dan riwayat (file sementara)."""
    for h in storage.clear("history"):
        delete_files(RESULT_DIR, [h["result_file"]] + [s["filename"] for s in h["steps"]])
    for u in storage.clear("uploads"):
        delete_files(UPLOAD_DIR, [u["filename"]])
    for f in os.listdir(RESULT_DIR):             # sisa file hasil deteksi
        if f.startswith("det_"):
            delete_files(RESULT_DIR, [f])
    return jsonify(ok=True)


# ------------------------------------------------------------------ API deteksi (opsional)
@app.post("/api/detect")
def api_detect():
    if not detection.is_available():
        return err("Fitur deteksi belum aktif. Pasang dengan: pip install ultralytics", 503)
    payload = request.get_json(silent=True) or {}
    src = str(payload.get("source", ""))
    kind, _, sid = src.partition(":")
    if kind not in ("u", "r") or not ID_RE.match(sid):
        return err("Sumber gambar tidak valid.")
    if kind == "u":
        rec = storage.get_item("uploads", sid)
        path = os.path.join(UPLOAD_DIR, rec["filename"]) if rec else None
    else:
        rec = storage.get_item("history", sid)
        path = os.path.join(RESULT_DIR, rec["result_file"]) if rec else None
    if not path or not os.path.exists(path):
        return err("Gambar tidak ditemukan.", 404)
    try:
        conf = min(max(float(payload.get("conf", 0.25)), 0.05), 0.95)
        annotated, dets = detection.detect(read_image(path), conf)
        fn = f"det_{uuid.uuid4().hex[:12]}.jpg"
        write_image(os.path.join(RESULT_DIR, fn), annotated, 92)
    except Exception as e:
        app.logger.exception("Deteksi gagal")
        return err(f"Deteksi gagal: {e}", 500)
    counts = {}
    for d in dets:
        counts[d["label"]] = counts.get(d["label"], 0) + 1
    return jsonify(ok=True, url=static_url("results", fn), counts=counts, total=len(dets), detections=dets)


# ------------------------------------------------------------------ error handler
@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return err("Total ukuran unggahan terlalu besar (maksimal 60 MB per kirim).", 413)


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return err("Halaman atau data tidak ditemukan.", 404)
    return render_template("base.html", page="", not_found=True), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
