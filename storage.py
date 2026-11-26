"""
storage.py
==========
Penyimpanan metadata lokal (data/store.json) untuk daftar unggahan dan riwayat hasil.
Dilindungi lock agar aman saat Flask melayani beberapa request.
"""
import json
import os
import threading

_lock = threading.Lock()
_path = None


def init(path: str) -> None:
    global _path
    _path = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        _write({"uploads": [], "history": []})


def _read() -> dict:
    try:
        with open(_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("uploads", [])
        data.setdefault("history", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"uploads": [], "history": []}   # file rusak -> mulai kosong


def _write(data: dict) -> None:
    tmp = _path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path)


def list_items(kind: str) -> list:
    with _lock:
        return _read()[kind]


def get_item(kind: str, item_id: str):
    return next((x for x in list_items(kind) if x["id"] == item_id), None)


def add_item(kind: str, item: dict) -> None:
    with _lock:
        data = _read()
        data[kind].insert(0, item)          # terbaru di depan
        _write(data)


def remove_item(kind: str, item_id: str):
    with _lock:
        data = _read()
        removed = next((x for x in data[kind] if x["id"] == item_id), None)
        data[kind] = [x for x in data[kind] if x["id"] != item_id]
        _write(data)
        return removed


def clear(kind: str) -> list:
    with _lock:
        data = _read()
        old, data[kind] = data[kind], []
        _write(data)
        return old
