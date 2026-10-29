"""
Mengekspor isi bakery.db menjadi berkas JSON untuk versi demo sisi-klien
(demo yang berjalan penuh di browser tanpa server Python).

Hasil: site/demo/data.json  -> dipakai oleh site/demo/api-local.js

Jalankan:  python docs/export_demo_data.py
"""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "site", "demo")
OUT = os.path.join(OUT_DIR, "data.json")

TABEL = ["users", "supplier", "bahan", "produk", "resep", "pembelian", "pembelian_item",
         "produksi", "produksi_item", "penjualan", "penjualan_item", "pengeluaran",
         "kas", "audit"]


def main():
    if not os.path.exists(core.DB_PATH):
        print("Berkas database tidak ditemukan:", core.DB_PATH)
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(core.DB_PATH)
    conn.row_factory = sqlite3.Row

    data = {}
    total = 0
    for t in TABEL:
        baris = [dict(r) for r in conn.execute(f"SELECT * FROM {t}")]
        data[t] = baris
        total += len(baris)
        print(f"  {t:<18} {len(baris):>6} baris")

    # Kata sandi untuk demo ditanam apa adanya (hash asli tetap dipakai di aplikasi
    # Python). Ini hanya berlaku pada demo statis, bukan aplikasi sebenarnya.
    data["_meta"] = {
        "dibuat": core.now_str(),
        "backend_asli": "SQLite",
        "keterangan": "Data contoh 31 hari untuk demo sisi-klien",
    }

    conn.close()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    ukuran = os.path.getsize(OUT)
    print("-" * 40)
    print(f"  TOTAL {total} baris -> {ukuran/1024:.0f} KB")
    print("Berkas:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
