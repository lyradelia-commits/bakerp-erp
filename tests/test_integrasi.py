"""
Uji integrasi end-to-end BakeERP (black box melalui HTTP API).

Menjalankan server pada database terpisah (tests/test_bakery.db) supaya data
demo tidak tercemar, lalu menguji alur bisnis lengkap:

    pembelian -> penerimaan barang -> produksi -> penjualan -> keuangan

Jalankan:  python tests/test_integrasi.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8099
DB = os.path.join(BASE_DIR, "tests", "test_bakery.db")
URL = f"http://127.0.0.1:{PORT}"

# Backend diuji: "sqlite" (default) atau "mysql"
BACKEND = (os.environ.get("BAKERP_TEST_BACKEND") or "sqlite").strip().lower()
MYSQL_DB = os.environ.get("BAKERP_TEST_MYSQL_DB", "bakerp_test")

HASIL = []


def call(method, path, body=None, token=None, expect=200):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, payload = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        status, payload = e.code, json.loads(e.read().decode() or "{}")
    return status, payload


def check(nama, kondisi, detail=""):
    HASIL.append((nama, bool(kondisi), detail))
    tanda = "LULUS" if kondisi else "GAGAL"
    print(f"  [{tanda:5}] {nama}" + (f"  -> {detail}" if detail else ""))


def tunggu_server(timeout=40):
    mulai = time.time()
    while time.time() - mulai < timeout:
        try:
            with urllib.request.urlopen(URL + "/", timeout=2):
                return True
        except Exception:
            time.sleep(0.4)
    return False


def siapkan_mysql():
    """Membuang database uji MySQL agar setiap eksekusi mulai dari kondisi bersih."""
    sys.path.insert(0, BASE_DIR)
    import dbmysql
    konek = dbmysql.connect_tanpa_db(
        host=os.environ.get("BAKERP_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("BAKERP_MYSQL_PORT", "3306")),
        user=os.environ.get("BAKERP_MYSQL_USER", "root"),
        password=os.environ.get("BAKERP_MYSQL_PASSWORD", ""),
    )
    with konek.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS `{MYSQL_DB}`")
    konek.close()


def main():
    if BACKEND == "mysql":
        siapkan_mysql()
        env = dict(os.environ, BAKERP_BACKEND="mysql", BAKERP_MYSQL_DB=MYSQL_DB,
                   PYTHONIOENCODING="utf-8")
    else:
        if os.path.exists(DB):
            os.remove(DB)
        env = dict(os.environ, BAKERP_DB=DB, PYTHONIOENCODING="utf-8")
    srv = subprocess.Popen([sys.executable, "app.py", "--port", str(PORT)], cwd=BASE_DIR,
                           env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not tunggu_server():
            print("Server gagal dijalankan.")
            return 1
        print("=" * 74)
        print("  UJI INTEGRASI SISTEM ERP BAKERY — alur bisnis end-to-end")
        print(f"  Backend basis data: {BACKEND.upper()}"
              + (f" (database {MYSQL_DB})" if BACKEND == "mysql" else ""))
        print("=" * 74)

        # ---------- 1. Autentikasi & otorisasi ----------
        print("\n1) Autentikasi & keamanan akses")
        st, r = call("POST", "/api/login", {"username": "admin", "password": "salah"})
        check("Login dengan password salah ditolak", st == 400, r.get("error", ""))
        st, r = call("POST", "/api/login", {"username": "admin", "password": "admin123"})
        token = r.get("data", {}).get("token")
        check("Login admin berhasil & token diterbitkan", st == 200 and token, "token aktif")
        st, r = call("GET", "/api/dashboard")
        check("Akses API tanpa token ditolak (401)", st == 401)

        # ---------- 2. Master data ----------
        print("\n2) Master data: bahan baku, produk, dan resep (BOM)")
        st, r = call("POST", "/api/bahan", {"nama": "Tepung Uji", "satuan": "kg",
                                            "stok_min": 2, "harga_beli": 10000}, token)
        bahan_id = r["data"]["id"]
        check("Tambah bahan baku baru", st == 200 and bahan_id, f"id={bahan_id}")
        st, r = call("POST", "/api/produk", {"nama": "Roti Uji", "kategori": "Roti",
                                             "harga_jual": 20000, "stok_min": 3}, token)
        produk_id = r["data"]["id"]
        check("Tambah produk baru", st == 200 and produk_id, f"id={produk_id}")
        st, r = call("POST", "/api/resep", {"produk_id": produk_id,
                                            "items": [{"bahan_id": bahan_id, "qty": 0.5}]}, token)
        check("Simpan resep: 0,5 kg bahan per unit produk", st == 200 and r["data"]["hpp"] == 5000,
              f"HPP/unit = Rp {r['data']['hpp']:,.0f}".replace(",", "."))

        # ---------- 3. Pembelian ----------
        print("\n3) Modul pembelian & penerimaan barang")
        st, r = call("POST", "/api/pembelian", {"supplier_id": 1, "tanggal": date.today().isoformat(),
                                                "items": [{"bahan_id": bahan_id, "qty": 10, "harga": 12000}]}, token)
        po_id, no_po = r["data"]["id"], r["data"]["no_po"]
        check("Buat purchase order (status draft)", st == 200 and r["data"]["total"] == 120000,
              f"{no_po} total Rp 120.000")

        st, r = call("GET", "/api/bahan", token=token)
        stok_sebelum = next(b["stok"] for b in r["data"] if b["id"] == bahan_id)
        check("PO draft belum mengubah stok gudang", stok_sebelum == 0, f"stok = {stok_sebelum}")

        st, r = call("POST", f"/api/pembelian/{po_id}/terima", token=token)
        check("Terima barang: PO berstatus diterima", st == 200 and r["data"]["status"] == "diterima")

        st, r = call("GET", "/api/bahan", token=token)
        b = next(x for x in r["data"] if x["id"] == bahan_id)
        check("Integrasi 1: penerimaan menambah stok bahan (0 -> 10 kg)", b["stok"] == 10, f"stok = {b['stok']}")
        check("Integrasi 2: harga beli rata-rata terbarui otomatis", b["harga_beli"] == 12000,
              f"harga = Rp {b['harga_beli']:,.0f}".replace(",", "."))

        st, r = call("GET", f"/api/keuangan/kas?dari={date.today()}&sampai={date.today()}", token=token)
        baris_po = [k for k in r["data"] if k["ref_tipe"] == "pembelian" and k["ref_id"] == po_id]
        check("Integrasi 3: penerimaan otomatis mencatat kas keluar", len(baris_po) == 1 and baris_po[0]["jumlah"] == 120000,
              f"kas keluar Rp {baris_po[0]['jumlah']:,.0f}".replace(",", ".") if baris_po else "tidak ada")

        st, r = call("POST", f"/api/pembelian/{po_id}/terima", token=token)
        check("PO tidak dapat diterima dua kali (validasi)", st == 400, r.get("error", ""))

        # ---------- 4. Produksi ----------
        print("\n4) Modul produksi berbasis resep")
        st, r = call("POST", "/api/produksi/cek", {"produk_id": produk_id, "qty": 10}, token)
        butuh = r["data"]["kebutuhan"][0]
        check("Simulasi kebutuhan bahan: 10 unit butuh 5 kg", st == 200 and butuh["butuh"] == 5,
              f"butuh {butuh['butuh']} kg, stok {butuh['stok']} kg")

        st, r = call("POST", "/api/produksi", {"produk_id": produk_id, "qty": 10,
                                               "tanggal": date.today().isoformat(),
                                               "catatan": "uji integrasi"}, token)
        biaya = r["data"]["biaya_bahan"]
        check("Jalankan produksi 10 unit", st == 200 and biaya == 60000,
              f"biaya bahan Rp {biaya:,.0f}".replace(",", "."))

        st, r = call("GET", "/api/bahan", token=token)
        b = next(x for x in r["data"] if x["id"] == bahan_id)
        check("Integrasi 4: produksi mengurangi stok bahan sesuai resep (10 -> 5 kg)", b["stok"] == 5,
              f"stok = {b['stok']} kg")
        st, r = call("GET", "/api/produk", token=token)
        p = next(x for x in r["data"] if x["id"] == produk_id)
        check("Integrasi 5: produksi menambah stok produk jadi (0 -> 10 pcs)", p["stok"] == 10,
              f"stok = {p['stok']} pcs")

        st, r = call("POST", "/api/produksi", {"produk_id": produk_id, "qty": 100,
                                               "tanggal": date.today().isoformat()}, token)
        check("Produksi ditolak bila stok bahan tidak mencukupi", st == 400,
              (r.get("error", "")[:64] + "…") if r.get("error") else "")

        # ---------- 5. Penjualan ----------
        print("\n5) Modul penjualan (POS)")
        st, r = call("POST", "/api/penjualan", {"items": [{"produk_id": produk_id, "qty": 3}],
                                                "metode": "QRIS",
                                                "tanggal": date.today().isoformat()}, token)
        inv, total, hpp = r["data"]["no_invoice"], r["data"]["total"], r["data"]["hpp"]
        jual_id = r["data"]["id"]
        check("Transaksi penjualan 3 unit berhasil", st == 200 and total == 60000, f"{inv} total Rp {total:,.0f}".replace(",", "."))
        check("Integrasi 6: HPP ikut berubah mengikuti harga beli terbaru (3 x Rp 6.000)", hpp == 18000,
              f"HPP = Rp {hpp:,.0f}".replace(",", "."))

        st, r = call("GET", "/api/produk", token=token)
        p = next(x for x in r["data"] if x["id"] == produk_id)
        check("Integrasi 7: penjualan mengurangi stok produk jadi (10 -> 7 pcs)", p["stok"] == 7,
              f"stok = {p['stok']} pcs")
        st, r = call("GET", f"/api/keuangan/kas?dari={date.today()}&sampai={date.today()}", token=token)
        baris_jual = [k for k in r["data"] if k["ref_tipe"] == "penjualan" and k["ref_id"] == jual_id]
        check("Integrasi 8: penjualan otomatis mencatat kas masuk",
              len(baris_jual) == 1 and baris_jual[0]["jumlah"] == 60000,
              f"kas masuk Rp {baris_jual[0]['jumlah']:,.0f}".replace(",", ".") if baris_jual else "tidak ada")

        st, r = call("POST", "/api/penjualan", {"items": [{"produk_id": produk_id, "qty": 999}]}, token)
        check("Penjualan ditolak bila stok produk tidak cukup", st == 400, r.get("error", "")[:60])

        # ---------- 6. Keuangan ----------
        print("\n6) Modul keuangan & pelaporan")
        st, r = call("POST", "/api/pengeluaran", {"tanggal": date.today().isoformat(),
                                                  "kategori": "Listrik & Gas",
                                                  "keterangan": "uji beban", "jumlah": 50000}, token)
        check("Catat pengeluaran operasional", st == 200)
        st, r = call("GET", f"/api/keuangan/labarugi?dari={date.today()}&sampai={date.today()}", token=token)
        lr = r["data"]
        check("Laba kotor = pendapatan - HPP", round(lr["pendapatan"] - lr["hpp"], 2) == lr["laba_kotor"],
              f"pendapatan {lr['pendapatan']:,.0f} - HPP {lr['hpp']:,.0f} = {lr['laba_kotor']:,.0f}".replace(",", "."))
        check("Laba bersih = laba kotor - total beban", round(lr["laba_kotor"] - lr["total_beban"], 2) == lr["laba_bersih"],
              f"laba bersih Rp {lr['laba_bersih']:,.0f}".replace(",", "."))
        check("Pengeluaran ikut mengurangi laba bersih", any(b["kategori"] == "Listrik & Gas" for b in lr["beban"]))

        st, r = call("GET", "/api/dashboard", token=token)
        d = r["data"]
        check("Dashboard menyajikan KPI & stok kritis", st == 200 and "tren" in d and "stok_kritis" in d,
              f"persediaan Rp {d['nilai_persediaan']:,.0f}".replace(",", "."))

        st, r = call("GET", "/api/audit", token=token)
        aksi = {a["aksi"] for a in r["data"]}
        check("Jejak audit merekam transaksi penting",
              {"TERIMA_PO", "PRODUKSI", "PENJUALAN"} <= aksi, f"{len(r['data'])} baris log")

        # ---------- ringkasan ----------
        lulus = sum(1 for _, ok, _ in HASIL if ok)
        total_tes = len(HASIL)
        print("\n" + "=" * 74)
        print(f"  HASIL: {lulus}/{total_tes} pengujian lulus "
              f"({lulus / total_tes * 100:.0f}%)")
        print("=" * 74)
        return 0 if lulus == total_tes else 1
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=8)
        except Exception:
            srv.kill()


if __name__ == "__main__":
    sys.exit(main())
