# BakeERP — Sistem ERP Berbasis Web untuk UMKM Bakery

Studi kasus: **Roti Kita Bakery**. Aplikasi ERP yang mengintegrasikan pembelian bahan,
persediaan, produksi berbasis resep (BOM), penjualan (POS), dan keuangan dalam satu basis data.

> Tugas UTS Mata Kuliah Enterprise Information System (EIS)

**Halaman profil proyek:** https://lyradelia-commits.github.io/bakerp-erp/

> **Catatan:** GitHub Pages hanya menyajikan berkas statis, jadi halaman di atas berisi profil
> proyek, tangkapan layar, dan laporan PDF — bukan aplikasi interaktifnya. Aplikasi BakeERP
> memerlukan server Python yang berjalan; jalankan secara lokal dengan langkah di bawah, atau
> bagikan sesi sementara memakai tunnel (lihat bagian *Membagikan demo ke rekan*).

## Menjalankan aplikasi

Cara tercepat (Windows): klik dua kali **`Mulai BakeERP.bat`** — server dinyalakan dan
browser terbuka otomatis.

Atau lewat terminal:

```bash
cd erp-bakery
python app.py            # default http://localhost:8000
python app.py --port 8080
```

Tanpa dependensi eksternal untuk mode bawaan — hanya Python 3.10+ dan SQLite.
Saat pertama dijalankan, database `bakery.db` otomatis dibuat dan diisi data contoh
31 hari terakhir (pembelian, produksi, penjualan, beban operasional).

> **Penting:** buka lewat `http://localhost:8000`, jangan dobel-klik `static/index.html`.
> Berkas itu bukan halaman mandiri — ia butuh server untuk mengambil data dari API.

## Akun demo

| Username | Password    | Peran  |
|----------|-------------|--------|
| admin    | admin123    | Admin  |
| gudang   | gudang123   | Gudang |
| kasir    | kasir123    | Kasir  |

## Modul

1. **Dashboard** — KPI penjualan, laba, nilai persediaan, stok kritis, tren 7 hari.
2. **Penjualan (POS)** — keranjang, diskon, metode bayar; mengurangi stok produk & mencatat HPP.
3. **Produksi** — eksekusi resep: validasi ketersediaan bahan, mengurangi bahan baku, menambah produk jadi.
4. **Pembelian** — purchase order → penerimaan barang (stok naik, harga rata-rata bergerak, kas keluar).
5. **Bahan Baku / Produk & Resep / Supplier** — master data dan BOM penentu HPP.
6. **Pengeluaran** — beban operasional yang mengurangi kas dan laba bersih.
7. **Laba Rugi & Buku Kas** — laporan keuangan otomatis per periode.
8. **Laporan** — penjualan harian, kontribusi produk, rekap produksi, posisi persediaan.
9. **Log Aktivitas** — jejak audit setiap transaksi dan perubahan data.

## Alur integrasi

```
Pembelian → stok bahan naik (harga rata-rata) → kas keluar
Produksi  → stok bahan turun sesuai resep → stok produk jadi naik → biaya bahan tercatat
Penjualan → stok produk turun → pendapatan + HPP → kas masuk
Keuangan  → laba kotor = pendapatan − HPP; laba bersih = laba kotor − beban
```

## Dua pilihan basis data

Aplikasi berjalan di atas **SQLite** (bawaan) atau **MySQL/MariaDB**. Logika bisnis ditulis
sekali di `core.py`; pemilihan mesin diatur oleh `db.py` lewat variabel lingkungan.

| | SQLite (bawaan) | MySQL |
|---|---|---|
| Persiapan | tidak ada | server MySQL harus jalan di port 3306 |
| Penyimpanan | satu berkas `bakery.db` | database `bakerp` di server |
| Cocok untuk | demo cepat, laptop dosen | lingkungan yang mewajibkan DBMS server |
| Buka dengan | DB Browser for SQLite, DBeaver (driver SQLite) | DBeaver / MySQL Workbench (host `127.0.0.1`, port `3306`) |

### Menjalankan dengan MySQL

```bash
# 1. pastikan server MySQL hidup (Laragon: Start All, atau)
#    mysqld --defaults-file="C:\laragon\bin\mysql\mysql-8.0.30-winx64\my.ini" --standalone

# 2. migrasi skema + seluruh data dari SQLite ke MySQL
python migrate_to_mysql.py

# 3. jalankan aplikasi dengan backend MySQL
BAKERP_BACKEND=mysql python app.py
```

Di Windows bisa juga klik dua kali **`Mulai BakeERP (MySQL).bat`** — skrip itu menyalakan
MySQL bila belum jalan, lalu membuka aplikasi dalam mode MySQL.

Konfigurasi MySQL dapat diubah lewat variabel lingkungan:
`BAKERP_MYSQL_HOST`, `BAKERP_MYSQL_PORT`, `BAKERP_MYSQL_USER`,
`BAKERP_MYSQL_PASSWORD`, `BAKERP_MYSQL_DB`.

Cek backend yang sedang aktif: `curl http://localhost:8000/api/info`

### Melihat isi database

- **Cara termudah:** buka `docs/Database_BakeERP.xlsx` (15 sheet, satu sheet per tabel).
- **DBeaver (SQLite):** New Connection → SQLite → Path → `C:\Users\<user>\Documents\erp-bakery\bakery.db`.
  Port dikosongkan — SQLite tidak memakai port.
- **DBeaver / MySQL Workbench (MySQL):** host `127.0.0.1`, port `3306`, user `root`,
  password kosong, database `bakerp`.
- **Dump SQL:** `python docs/export_db.py` menghasilkan `docs/bakery_dump.sql`.

> Jangan mengubah data lewat DBeaver selagi aplikasi berjalan — basis data mengunci
> baris dan perubahan bisa bentrok. Membaca (SELECT) aman.

## Struktur proyek

```
erp-bakery/
├── app.py                  # server HTTP + REST API + penyajian file statis
├── core.py                 # skema database, logika bisnis, laporan, data contoh
├── db.py                   # pemilih backend (SQLite / MySQL)
├── dbmysql.py              # lapisan kompatibilitas dialek SQLite -> MySQL
├── migrate_to_mysql.py     # migrasi data SQLite -> MySQL + verifikasi
├── bakery.db               # database SQLite (dibuat otomatis)
├── Mulai BakeERP.bat       # launcher mode SQLite
├── Mulai BakeERP (MySQL).bat  # launcher mode MySQL
├── static/
│   ├── index.html
│   ├── style.css
│   ├── app.js              # inti SPA: API client, layout, router, dashboard
│   └── pages.js            # halaman modul
├── tests/test_integrasi.py # 29 skenario uji integrasi end-to-end
└── docs/
    ├── img/                     # tangkapan layar untuk laporan
    ├── hasil_pengujian.txt      # keluaran uji backend SQLite
    ├── hasil_migrasi.txt        # keluaran migrasi ke MySQL
    ├── Database_BakeERP.xlsx    # seluruh tabel dalam satu workbook
    ├── bakery_dump.sql          # dump SQL
    ├── export_db.py             # pembuat xlsx + dump
    ├── build_laporan.py         # pembuat laporan .docx
    ├── to_pdf.ps1               # konversi .docx -> .pdf (via Word)
    ├── Laporan_UTS_EIS_ERP_Bakery.docx
    └── Laporan_UTS_EIS_ERP_Bakery.pdf
```

## Pengujian

```bash
python tests/test_integrasi.py                             # backend SQLite
BAKERP_TEST_BACKEND=mysql python tests/test_integrasi.py   # backend MySQL
```

Menguji 29 skenario: autentikasi, master data, pembelian, produksi, penjualan,
keuangan, dan konsistensi antar modul. Database uji terpisah
(`tests/test_bakery.db` atau database `bakerp_test`) sehingga data demo tidak tercemar.
Kedua backend lulus 29/29.

## Reset data contoh

```bash
python core.py     # membuat ulang database + seed 31 hari (backend sesuai BAKERP_BACKEND)
```

## Membagikan demo ke rekan

Aplikasi butuh server Python yang hidup, jadi tidak bisa di-host di GitHub Pages.
Untuk memberi akses sementara tanpa membuat mereka memasang Python, gunakan tunnel SSH
ke Pinggy (tanpa instalasi, cukup `ssh` bawaan Windows/Linux/macOS):

```bash
# 1. pastikan aplikasi lokal sudah jalan di port 8000
python app.py

# 2. buka tunnel (terminal terpisah)
ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:8000 free@a.pinggy.io
```

Pinggy mencetak URL `https://....pinggy.link` yang bisa dibuka siapa pun. Login aplikasi
tetap diperlukan, jadi data tidak terbuka bagi yang tidak punya akun.

Batasan free tier: tunnel mati otomatis setelah **60 menit**, dan URL berubah setiap kali
dinyalakan ulang. Cocok untuk demo presentasi, bukan untuk penggunaan permanen.

## Membangun ulang laporan

```bash
python docs/build_laporan.py
powershell -ExecutionPolicy Bypass -File docs/to_pdf.ps1   # butuh Microsoft Word
```

Angka pada laporan diambil langsung dari basis data saat skrip dijalankan, sehingga isi
laporan selalu konsisten dengan aplikasi.
