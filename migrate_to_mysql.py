"""
Migrasi database BakeERP dari SQLite (bakery.db) ke MySQL/MariaDB.

Yang dilakukan:
  1. Membuat database MySQL (default: bakerp) beserta 14 tabelnya.
  2. Menyalin seluruh isi tabel dari bakery.db, mempertahankan nilai id
     agar relasi antar tabel tetap utuh.
  3. Memverifikasi jumlah baris setiap tabel di kedua sisi.

Jalankan:
    python migrate_to_mysql.py                 # SQLite -> MySQL
    python migrate_to_mysql.py --host 127.0.0.1 --port 3306 --user root --db bakerp

Setelah migrasi, jalankan aplikasi dengan backend MySQL:
    BAKERP_BACKEND=mysql python app.py
"""

import argparse
import os
import sqlite3
import sys

import db
import dbmysql
import core

# Urutan mengikuti dependensi foreign key (induk dulu, anak kemudian)
URUTAN = ["users", "supplier", "bahan", "produk", "resep", "pembelian", "pembelian_item",
          "produksi", "produksi_item", "penjualan", "penjualan_item", "pengeluaran",
          "kas", "audit"]

SQLITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bakery.db")


def main():
    ap = argparse.ArgumentParser(description="Migrasi BakeERP SQLite -> MySQL")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", default="root")
    ap.add_argument("--password", default="")
    ap.add_argument("--db", default="bakerp")
    ap.add_argument("--sqlite", default=SQLITE)
    ap.add_argument("--keep", action="store_true",
                    help="jangan hapus database MySQL yang sudah ada")
    args = ap.parse_args()

    if not os.path.exists(args.sqlite):
        print(f"[GAGAL] Berkas SQLite tidak ditemukan: {args.sqlite}")
        return 1

    # ---------- 1. Siapkan database MySQL ----------
    print("=" * 64)
    print("  MIGRASI BAKERP: SQLite -> MySQL")
    print("=" * 64)
    print(f"  Sumber : {args.sqlite}")
    print(f"  Tujuan : mysql://{args.user}@{args.host}:{args.port}/{args.db}")
    print()

    konek = dbmysql.connect_tanpa_db(host=args.host, port=args.port,
                                     user=args.user, password=args.password)
    with konek.cursor() as c:
        if not args.keep:
            c.execute(f"DROP DATABASE IF EXISTS `{args.db}`")
        c.execute(f"CREATE DATABASE IF NOT EXISTS `{args.db}` "
                  "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    konek.close()
    print("[1/3] Database MySQL siap.")

    # ---------- 2. Bangun skema ----------
    my = dbmysql.connect(host=args.host, port=args.port, user=args.user,
                         password=args.password, database=args.db)
    my.executescript(core.SCHEMA)
    my.commit()
    jumlah_tabel = len(my.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema=%s",
        (args.db,)).fetchall())
    print(f"[2/3] Skema dibuat: {jumlah_tabel} tabel.")

    # ---------- 3. Salin data ----------
    lite = sqlite3.connect(args.sqlite)
    lite.row_factory = sqlite3.Row
    my.execute("SET FOREIGN_KEY_CHECKS=0")

    print("[3/3] Menyalin data...")
    print()
    print(f"  {'Tabel':<18} {'SQLite':>8} {'MySQL':>8}  Status")
    print("  " + "-" * 48)

    total_ok = 0
    semua_cocok = True
    for t in URUTAN:
        baris = lite.execute(f"SELECT * FROM {t}").fetchall()
        n_src = len(baris)
        if baris:
            kolom = [d[0] for d in lite.execute(f"SELECT * FROM {t} LIMIT 1").description]
            kol_str = ", ".join(f"`{k}`" for k in kolom)
            ph = ", ".join(["%s"] * len(kolom))
            sql = f"INSERT INTO `{t}` ({kol_str}) VALUES ({ph})"
            data = [tuple(r) for r in baris]
            cur = my._conn.cursor()
            cur.executemany(sql, data)
            my.commit()

        n_dst = my.execute(f"SELECT COUNT(*) AS n FROM `{t}`").fetchone()["n"]
        cocok = (n_src == n_dst)
        semua_cocok = semua_cocok and cocok
        total_ok += n_dst
        print(f"  {t:<18} {n_src:>8} {n_dst:>8}  {'OK' if cocok else 'BEDA'}")

    my.execute("SET FOREIGN_KEY_CHECKS=1")
    my.commit()

    print("  " + "-" * 48)
    print(f"  {'TOTAL':<18} {'':>8} {total_ok:>8}")
    print()

    # ---------- Verifikasi integritas ----------
    print("Verifikasi relasi & konsistensi:")
    cek = []

    r = my.execute("""SELECT COUNT(*) AS n FROM resep r
                      LEFT JOIN produk p ON p.id=r.produk_id
                      LEFT JOIN bahan b ON b.id=r.bahan_id
                      WHERE p.id IS NULL OR b.id IS NULL""").fetchone()["n"]
    cek.append(("Resep tanpa produk/bahan (harus 0)", r, 0))

    r = my.execute("""SELECT COUNT(*) AS n FROM penjualan_item pi
                      LEFT JOIN penjualan p ON p.id=pi.penjualan_id
                      WHERE p.id IS NULL""").fetchone()["n"]
    cek.append(("Item penjualan tanpa invoice (harus 0)", r, 0))

    r = my.execute("""SELECT COUNT(*) AS n FROM pembelian_item pii
                      LEFT JOIN pembelian p ON p.id=pii.pembelian_id
                      WHERE p.id IS NULL""").fetchone()["n"]
    cek.append(("Item PO tanpa header (harus 0)", r, 0))

    r = my.execute("""SELECT COALESCE(SUM(total),0) AS v FROM penjualan""").fetchone()["v"]
    lite_val = lite.execute("SELECT COALESCE(SUM(total),0) FROM penjualan").fetchone()[0]
    cek.append(("Total nilai penjualan sama dengan SQLite", round(float(r), 2), round(float(lite_val), 2)))

    r = my.execute("""SELECT COUNT(*) AS n FROM kas WHERE tipe='masuk'""").fetchone()["n"]
    lite_val = lite.execute("SELECT COUNT(*) FROM kas WHERE tipe='masuk'").fetchone()[0]
    cek.append(("Jumlah kas masuk sama dengan SQLite", r, lite_val))

    for label, nilai, harap in cek:
        ok = (nilai == harap)
        semua_cocok = semua_cocok and ok
        tanda = "OK" if ok else "BEDA"
        print(f"  [{tanda}] {label}: {nilai} (harap {harap})")

    lite.close()
    my.close()

    print()
    print("=" * 64)
    if semua_cocok:
        print("  MIGRASI BERHASIL — seluruh data & relasi konsisten.")
        print()
        print("  Jalankan aplikasi dengan backend MySQL:")
        print("     BAKERP_BACKEND=mysql python app.py")
        print()
        print("  Buka di DBeaver / MySQL Workbench:")
        print(f"     host={args.host}  port={args.port}  database={args.db}")
    else:
        print("  MIGRASI SELESAI DENGAN PERBEDAAN — periksa tabel di atas.")
    print("=" * 64)
    return 0 if semua_cocok else 1


if __name__ == "__main__":
    sys.exit(main())
