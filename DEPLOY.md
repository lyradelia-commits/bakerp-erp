# Panduan Deploy BakeERP ke Hosting Gratis

Tujuan: aplikasi Python asli (server + database) berjalan di internet, sehingga
**semua orang melihat data yang sama** — persis seperti yang akan dinilai dosen.

> Catatan penting: aplikasi ini butuh **penyimpanan permanen** (ada database).
> Tidak semua hosting gratis menyediakannya. Pilihan di bawah sudah dipilih
> dengan pertimbangan itu.

---

## Perbandingan pilihan

| Hosting | Gratis | Data permanen | Perlu kartu kredit | Cocok? |
|---|---|---|---|---|
| **PythonAnywhere** | ya | **ya** (disk 512 MB) | tidak | **Paling cocok** |
| Render | ya | tidak (disk sementara) | tidak | Data hilang tiap restart |
| Railway / Fly.io | terbatas | ya | ya | Perlu kartu |
| Vercel / Netlify | ya | tidak | tidak | Tidak bisa simpan database |

**Kesimpulan: pakai PythonAnywhere.** Data tersimpan di disk, gratis, tanpa kartu kredit.

---

## Cara A — PythonAnywhere (disarankan)

### 1. Daftar

Buka https://www.pythonanywhere.com/registration/register/beginner/

- Pilih paket **Beginner (Free)**
- Tidak perlu kartu kredit
- Username akan menjadi alamat situsmu: `https://<username>.pythonanywhere.com`

### 2. Ambil kode proyek

Setelah masuk, buka menu **Consoles** → **Bash**, lalu jalankan:

```bash
git clone https://github.com/lyradelia-commits/bakerp-erp.git
cd bakerp-erp
ls
```

Pastikan terlihat `app.py`, `core.py`, `wsgi.py`, dan folder `static/`.

### 3. Buat web app

1. Buka tab **Web** → klik **Add a new web app**
2. Klik **Next** (domain: `<username>.pythonanywhere.com`)
3. Pilih **Manual configuration** (JANGAN pilih Flask/Django)
4. Pilih **Python 3.10** → **Next**

### 4. Arahkan ke proyek

Di halaman **Web**, isi:

| Kolom | Isi |
|---|---|
| **Source code** | `/home/<username>/bakerp-erp` |
| **Working directory** | `/home/<username>/bakerp-erp` |

Ganti `<username>` dengan username PythonAnywhere-mu.

### 5. Sunting berkas WSGI

Masih di tab **Web**, klik tautan **WSGI configuration file**
(biasanya `/var/www/<username>_pythonanywhere_com_wsgi.py`).

**Hapus seluruh isinya**, ganti dengan tiga baris ini (bisa langsung di-copy apa adanya):

```python
import os, sys
sys.path.insert(0, os.path.expanduser('~/bakerp-erp'))
from wsgi import application
```

`expanduser('~/bakerp-erp')` otomatis menunjuk `/home/<username>/bakerp-erp`, jadi tidak
perlu menyesuaikan username secara manual.

Simpan (Ctrl+S).

### 6. Reload

Klik tombol hijau **Reload** di atas halaman Web.

### 7. Buka situsnya

```
https://<username>.pythonanywhere.com
```

Login: `admin` / `admin123`

### Kalau muncul error

Lihat **Error log** di tab Web. Penyebab paling umum:

| Gejala | Penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'core'` | path salah | periksa baris `sys.path.insert` — harus folder yang berisi `core.py` |
| Halaman 502 / error 500 | `wsgi.py` belum tersentuh | pastikan 3 baris tadi tersimpan |
| Tampilan tanpa CSS | static belum termuat | pastikan folder `static/` ikut ter-clone |
| Data kembali ke awal | pakai Render, bukan PythonAnywhere | pindah ke PythonAnywhere |

### Batasan paket gratis PythonAnywhere

- Disk 512 MB (proyek ini ± 10 MB, aman)
- Satu web app
- Tidak bisa domain sendiri (pakai `<username>.pythonanywhere.com`)
- **Akun dihapus bila tidak login selama 3 bulan** — login sesekali
- Aplikasi "tidur" saat tidak dipakai, tapi data **tetap** tersimpan

---

## Cara B — Render (alternatif, data tidak permanen)

Lebih cepat dipasang, tapi **database kembali ke kondisi awal setiap restart**.
Hanya cocok untuk demo sekali jalan.

1. Daftar di https://render.com (tanpa kartu kredit)
2. **New** → **Web Service** → hubungkan repo GitHub `bakerp-erp`
3. Isi:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
4. **Create Web Service**

Aplikasi otomatis memakai `$PORT` dan mendengarkan `0.0.0.0` (sudah ditangani `app.py`).
Alamatnya: `https://<nama-service>.onrender.com`

Kekurangan: paket gratis "tidur" setelah 15 menit tanpa aktivitas (buka pertama lambat
± 50 detik), dan **perubahan data hilang saat layanan bangun ulang**.

---

## Cara C — Tunnel dari laptop (paling cepat, sementara)

Kalau hanya butuh link hidup beberapa jam untuk presentasi:

```bash
python app.py                                              # terminal 1
ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:8000 free@a.pinggy.io   # terminal 2
```

Pinggy mencetak URL `https://....pinggy.link`. Data benar-benar sama untuk semua
pengunjung karena memakai satu database di laptopmu.

Batasan: mati otomatis setelah **60 menit**, URL berubah setiap kali dijalankan ulang,
dan laptop harus tetap menyala.

---

## Setelah deploy: yang perlu diperiksa

1. Buka `https://<situs>/api/info` — harus muncul `"backend": "sqlite"` dan path database.
2. Login `admin` / `admin123` — dashboard harus terisi data contoh 31 hari.
3. Tambah satu bahan baku dari **dua perangkat berbeda** (mis. HP dan laptop).
   Kalau keduanya melihat bahan yang sama → **berhasil**, datanya sudah terpusat.
4. Cek tab **Web → Error log** kosong dari error.

### Zona waktu

Server hosting berjalan pada **UTC**, sedangkan usaha berada di WITA (UTC+8).
Tanpa penyesuaian, antara pukul 00:00–08:00 WITA tanggal "hari ini" di server masih
menunjuk hari sebelumnya, sehingga laporan harian tampak kosong.

Aplikasi sudah menangani ini: `wsgi.py` menyetel `BAKERP_TZ` (bawaan `Asia/Makassar`)
sebelum `core` diimpor. Untuk zona lain, ubah baris itu:

```python
os.environ.setdefault("BAKERP_TZ", "Asia/Jakarta")   # WIB (UTC+7)
```

Verifikasi: `https://<situs>/api/info` — kolom `waktu` harus sama dengan jam dindingmu,
bukan 8 jam lebih lambat.

---

## Catatan keamanan

Aplikasi ini dibuat untuk tugas kuliah, bukan produksi. Sebelum dipakai sungguhan:

- Ganti kata sandi akun demo (`admin`, `gudang`, `kasir`).
- Token sesi disimpan di memori server, jadi semua pengguna ter-logout saat server
  dimulai ulang — ini normal untuk demo.
- Jangan menyimpan data pelanggan asli.
