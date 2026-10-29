"""
Menyinkronkan seluruh salinan data BakeERP dari SATU sumber kebenaran.

Sumber kebenaran: MySQL (database `bakerp`), sesuai keputusan pemakaian.
Dari situ diturunkan dua artefak:

  1. bakery.db              -> berkas SQLite untuk hosting (PythonAnywhere)
  2. site/demo/data.json    -> data untuk demo statis di GitHub Pages

Dengan begitu tidak ada lagi salinan yang berbeda diam-diam.

Jalankan:
    python sync_db.py              # MySQL -> bakery.db + data.json
    python sync_db.py --cek        # hanya bandingkan jumlah baris, tanpa menulis
"""

import argparse
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import core          # noqa: E402
import dbmysql       # noqa: E402
import db as dbmod   # noqa: E402

SQLITE = os.path.join(BASE, "bakery.db")
DATA_JSON = os.path.join(BASE, "site", "demo", "data.json")

TABEL = ["users", "supplier", "bahan", "produk", "resep", "pembelian", "pembelian_item",
         "produksi", "produksi_item", "penjualan", "penjualan_item", "pengeluaran",
         "kas", "audit"]


def baca_mysql():
    """Membaca seluruh tabel dari MySQL sebagai list of dict."""
    if dbmod.BACKEND != "mysql":
        print("[GAGAL] Backend aktif bukan MySQL. Pastikan server MySQL berjalan.")
        print("        Backend terdeteksi:", dbmod.BACKEND)
        return None
    conn = dbmysql.connect(**dbmod.MYSQL)
    data = {}
    for t in TABEL:
        rows = conn.execute(f"SELECT * FROM `{t}` ORDER BY id").fetchall()
        data[t] = [dict(r) for r in rows]
    conn.close()
    return data


def tulis_sqlite(data):
    """Menulis ulang bakery.db dari data MySQL (skema dari core.SCHEMA)."""
    if os.path.exists(SQLITE):
        os.remove(SQLITE)

    conn = sqlite3.connect(SQLITE)
    conn.executescript(core.SCHEMA)

    for t in TABEL:
        rows = data[t]
        if not rows:
            continue
        kolom = list(rows[0].keys())
        kol_str = ", ".join(kolom)
        ph = ", ".join(["?"] * len(kolom))
        conn.executemany(
            f"INSERT INTO {t} ({kol_str}) VALUES ({ph})",
            [tuple(r[k] for k in kolom) for r in rows],
        )
    conn.commit()
    conn.close()
    return os.path.getsize(SQLITE)


def tulis_data_json(data):
    os.makedirs(os.path.dirname(DATA_JSON), exist_ok=True)
    keluaran = dict(data)
    keluaran["_meta"] = {
        "dibuat": core.now_str(),
        "sumber": "MySQL bakerp",
        "keterangan": "Data contoh untuk demo sisi-klien",
    }
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(keluaran, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(DATA_JSON)


def jumlah_sqlite():
    if not os.path.exists(SQLITE):
        return {}
    conn = sqlite3.connect(SQLITE)
    hasil = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABEL}
    conn.close()
    return hasil


def jumlah_json():
    if not os.path.exists(DATA_JSON):
        return {}
    with open(DATA_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return {t: len(d.get(t, [])) for t in TABEL}


def main():
    ap = argparse.ArgumentParser(description="Sinkronkan data dari MySQL ke SQLite & demo")
    ap.add_argument("--cek", action="store_true", help="hanya bandingkan, tidak menulis")
    args = ap.parse_args()

    print("=" * 68)
    print("  SINKRONISASI DATA BAKERP")
    print("=" * 68)
    print(f"  Sumber : {dbmod.deskripsi()}")
    print()

    data = baca_mysql()
    if data is None:
        return 1

    lama_sqlite = jumlah_sqlite()
    lama_json = jumlah_json()

    if args.cek:
        print(f"  {'Tabel':<18} {'MySQL':>8} {'SQLite':>8} {'data.json':>10}")
        print("  " + "-" * 48)
        beda = 0
        for t in TABEL:
            n = len(data[t])
            a, b = lama_sqlite.get(t, 0), lama_json.get(t, 0)
            tanda = "" if (n == a == b) else "  <-- BEDA"
            if tanda:
                beda += 1
            print(f"  {t:<18} {n:>8} {a:>8} {b:>10}{tanda}")
        print()
        print("  Semua sama." if beda == 0 else f"  {beda} tabel berbeda.")
        return 0 if beda == 0 else 2

    ukuran_db = tulis_sqlite(data)
    ukuran_json = tulis_data_json(data)

    print(f"  {'Tabel':<18} {'baris':>8}")
    print("  " + "-" * 30)
    total = 0
    for t in TABEL:
        n = len(data[t])
        total += n
        print(f"  {t:<18} {n:>8}")
    print("  " + "-" * 30)
    print(f"  {'TOTAL':<18} {total:>8}")
    print()
    print(f"  bakery.db          : {ukuran_db/1024:>8.0f} KB")
    print(f"  site/demo/data.json: {ukuran_json/1024:>8.0f} KB")
    print()

    # Verifikasi ulang
    akhir_sqlite = jumlah_sqlite()
    akhir_json = jumlah_json()
    cocok = all(len(data[t]) == akhir_sqlite.get(t, 0) == akhir_json.get(t, 0) for t in TABEL)
    print("=" * 68)
    print("  SINKRON BERHASIL — MySQL, bakery.db, dan data.json identik."
          if cocok else "  ADA SELISIH — periksa kembali.")
    print("=" * 68)
    return 0 if cocok else 1


if __name__ == "__main__":
    sys.exit(main())
