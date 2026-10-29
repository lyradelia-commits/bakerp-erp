"""
BakeERP - Lapisan data & logika bisnis
=====================================
Aplikasi ERP untuk UMKM Bakery (studi kasus: "Roti Kita Bakery").

Modul yang terintegrasi:
  Master Data  -> bahan baku, produk, supplier, resep (BOM), pengguna
  Pembelian    -> purchase order, penerimaan barang (menambah stok + harga rata-rata)
  Produksi     -> eksekusi resep (mengurangi bahan baku, menambah stok produk jadi)
  Penjualan    -> kasir/POS (mengurangi stok produk jadi, mencatat pendapatan & HPP)
  Keuangan     -> buku kas, pengeluaran operasional, laba rugi
  Laporan      -> dashboard KPI, stok, penjualan, produksi, jejak audit

Hanya memakai standard library Python: sqlite3, hashlib, secrets, datetime, random.
"""

import hashlib
import os
import random
import secrets
from datetime import datetime, timedelta, date

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = db.DB_PATH


class BizError(Exception):
    """Kesalahan aturan bisnis -> dikembalikan sebagai HTTP 400."""


# ----------------------------------------------------------------------------
# Koneksi & skema
# ----------------------------------------------------------------------------
def get_db():
    conn = db.connect()
    if db.BACKEND != "mysql":
        conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    salt          VARCHAR(64) NOT NULL,
    nama          VARCHAR(120) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'staf',   -- admin | gudang | kasir
    aktif         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS supplier (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nama    VARCHAR(150) NOT NULL,
    kontak  VARCHAR(120),
    telepon VARCHAR(40),
    alamat  VARCHAR(255),
    aktif   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bahan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kode       VARCHAR(30) NOT NULL UNIQUE,
    nama       VARCHAR(150) NOT NULL,
    satuan     VARCHAR(20) NOT NULL,
    stok       REAL NOT NULL DEFAULT 0,
    stok_min   REAL NOT NULL DEFAULT 0,
    harga_beli REAL NOT NULL DEFAULT 0,   -- harga rata-rata bergerak per satuan
    aktif      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS produk (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kode       VARCHAR(30) NOT NULL UNIQUE,
    nama       VARCHAR(150) NOT NULL,
    kategori   VARCHAR(60),
    harga_jual REAL NOT NULL DEFAULT 0,
    stok       REAL NOT NULL DEFAULT 0,
    stok_min   REAL NOT NULL DEFAULT 0,
    aktif      INTEGER NOT NULL DEFAULT 1
);

-- Bill of Material: komposisi bahan untuk 1 unit produk
CREATE TABLE IF NOT EXISTS resep (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    produk_id INTEGER NOT NULL,
    bahan_id  INTEGER NOT NULL,
    qty       REAL NOT NULL,
    UNIQUE (produk_id, bahan_id),
    FOREIGN KEY (produk_id) REFERENCES produk(id) ON DELETE CASCADE,
    FOREIGN KEY (bahan_id)  REFERENCES bahan(id)  ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pembelian (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    no_po       VARCHAR(30) NOT NULL UNIQUE,
    tanggal     VARCHAR(10) NOT NULL,
    supplier_id INTEGER NOT NULL,
    total       REAL NOT NULL DEFAULT 0,
    status      VARCHAR(20) NOT NULL DEFAULT 'draft',   -- draft | diterima
    user_id     INTEGER,
    created_at  VARCHAR(19) NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (user_id)     REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS pembelian_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pembelian_id INTEGER NOT NULL,
    bahan_id     INTEGER NOT NULL,
    qty          REAL NOT NULL,
    harga        REAL NOT NULL,
    subtotal     REAL NOT NULL,
    FOREIGN KEY (pembelian_id) REFERENCES pembelian(id) ON DELETE CASCADE,
    FOREIGN KEY (bahan_id)     REFERENCES bahan(id)
);

CREATE TABLE IF NOT EXISTS produksi (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    no_batch    VARCHAR(30) NOT NULL UNIQUE,
    tanggal     VARCHAR(10) NOT NULL,
    produk_id   INTEGER NOT NULL,
    qty         REAL NOT NULL,
    biaya_bahan REAL NOT NULL DEFAULT 0,
    user_id     INTEGER,
    catatan     VARCHAR(255),
    created_at  VARCHAR(19) NOT NULL,
    FOREIGN KEY (produk_id) REFERENCES produk(id),
    FOREIGN KEY (user_id)   REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS produksi_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    produksi_id INTEGER NOT NULL,
    bahan_id    INTEGER NOT NULL,
    qty         REAL NOT NULL,
    harga       REAL NOT NULL,
    subtotal    REAL NOT NULL,
    FOREIGN KEY (produksi_id) REFERENCES produksi(id) ON DELETE CASCADE,
    FOREIGN KEY (bahan_id)    REFERENCES bahan(id)
);

CREATE TABLE IF NOT EXISTS penjualan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    no_invoice VARCHAR(30) NOT NULL UNIQUE,
    tanggal    VARCHAR(10) NOT NULL,
    subtotal   REAL NOT NULL DEFAULT 0,
    diskon     REAL NOT NULL DEFAULT 0,
    total      REAL NOT NULL DEFAULT 0,
    hpp        REAL NOT NULL DEFAULT 0,
    metode     VARCHAR(20) NOT NULL DEFAULT 'Tunai',
    user_id    INTEGER,
    created_at VARCHAR(19) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS penjualan_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    penjualan_id INTEGER NOT NULL,
    produk_id    INTEGER NOT NULL,
    qty          REAL NOT NULL,
    harga        REAL NOT NULL,
    subtotal     REAL NOT NULL,
    hpp          REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (penjualan_id) REFERENCES penjualan(id) ON DELETE CASCADE,
    FOREIGN KEY (produk_id)    REFERENCES produk(id)
);

CREATE TABLE IF NOT EXISTS pengeluaran (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal    VARCHAR(10) NOT NULL,
    kategori   VARCHAR(60) NOT NULL,
    keterangan VARCHAR(255),
    jumlah     REAL NOT NULL,
    user_id    INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Buku kas / jurnal: jantung integrasi antar modul (setiap transaksi menghasilkan 1 baris)
CREATE TABLE IF NOT EXISTS kas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal    VARCHAR(10) NOT NULL,
    tipe       VARCHAR(10) NOT NULL,        -- masuk | keluar
    kategori   VARCHAR(60) NOT NULL,
    ref_tipe   VARCHAR(20),                 -- penjualan | pembelian | pengeluaran
    ref_id     INTEGER,
    keterangan VARCHAR(255),
    jumlah     REAL NOT NULL,
    created_at VARCHAR(19) NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu  VARCHAR(19) NOT NULL,
    user   VARCHAR(120),
    aksi   VARCHAR(40) NOT NULL,
    detail VARCHAR(500)
);

CREATE INDEX IF NOT EXISTS ix_kas_tanggal ON kas(tanggal);
CREATE INDEX IF NOT EXISTS ix_penjualan_tanggal ON penjualan(tanggal);
CREATE INDEX IF NOT EXISTS ix_pembelian_tanggal ON pembelian(tanggal);
CREATE INDEX IF NOT EXISTS ix_produksi_tanggal ON produksi(tanggal);
"""


def init_db(force=False):
    if force:
        db.hapus_database()
    db.pastikan_database()
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Util
# ----------------------------------------------------------------------------
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def r2(x):
    return round(float(x or 0), 2)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return h.hex(), salt


def audit(conn, user, aksi, detail=""):
    conn.execute(
        "INSERT INTO audit (waktu, user, aksi, detail) VALUES (?,?,?,?)",
        (now_str(), user, aksi, detail),
    )


def next_number(conn, table, kolom, prefix, width=4):
    """Nomor dokumen berurutan, contoh: PO-2026-0007."""
    year = datetime.now().year
    like = f"{prefix}-{year}-%"
    row = conn.execute(
        f"SELECT {kolom} FROM {table} WHERE {kolom} LIKE ? ORDER BY id DESC LIMIT 1", (like,)
    ).fetchone()
    seq = 1
    if row and row[0]:
        try:
            seq = int(row[0].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}-{year}-{seq:0{width}d}"


# ----------------------------------------------------------------------------
# Autentikasi
# ----------------------------------------------------------------------------
def authenticate(conn, username, password):
    row = conn.execute("SELECT * FROM users WHERE username=? AND aktif=1", (username,)).fetchone()
    if not row:
        raise BizError("Username tidak ditemukan.")
    h, _ = hash_password(password, row["salt"])
    if h != row["password_hash"]:
        raise BizError("Password salah.")
    audit(conn, row["nama"], "LOGIN", f"role={row['role']}")
    conn.commit()
    return {"id": row["id"], "username": row["username"], "nama": row["nama"], "role": row["role"]}


# ----------------------------------------------------------------------------
# Master data
# ----------------------------------------------------------------------------
def list_master(conn, tabel, order="nama"):
    return [dict(r) for r in conn.execute(f"SELECT * FROM {tabel} ORDER BY {order}")]


def save_bahan(conn, data, user="sistem"):
    nama = (data.get("nama") or "").strip()
    if not nama:
        raise BizError("Nama bahan baku wajib diisi.")
    kode = (data.get("kode") or "").strip() or "BH-" + secrets.token_hex(2).upper()
    if data.get("id"):
        conn.execute(
            "UPDATE bahan SET kode=?, nama=?, satuan=?, stok_min=?, harga_beli=? WHERE id=?",
            (kode, nama, data.get("satuan") or "kg", float(data.get("stok_min") or 0),
             float(data.get("harga_beli") or 0), data["id"]),
        )
        audit(conn, user, "UBAH_BAHAN", f"{kode} {nama}")
        pid = data["id"]
    else:
        cur = conn.execute(
            "INSERT INTO bahan (kode, nama, satuan, stok, stok_min, harga_beli) VALUES (?,?,?,?,?,?)",
            (kode, nama, data.get("satuan") or "kg", float(data.get("stok") or 0),
             float(data.get("stok_min") or 0), float(data.get("harga_beli") or 0)),
        )
        audit(conn, user, "TAMBAH_BAHAN", f"{kode} {nama}")
        pid = cur.lastrowid
    conn.commit()
    return pid


def save_produk(conn, data, user="sistem"):
    nama = (data.get("nama") or "").strip()
    if not nama:
        raise BizError("Nama produk wajib diisi.")
    kode = (data.get("kode") or "").strip() or "PR-" + secrets.token_hex(2).upper()
    if data.get("id"):
        conn.execute(
            "UPDATE produk SET kode=?, nama=?, kategori=?, harga_jual=?, stok_min=? WHERE id=?",
            (kode, nama, data.get("kategori") or "Roti", float(data.get("harga_jual") or 0),
             float(data.get("stok_min") or 0), data["id"]),
        )
        audit(conn, user, "UBAH_PRODUK", f"{kode} {nama}")
        pid = data["id"]
    else:
        cur = conn.execute(
            "INSERT INTO produk (kode, nama, kategori, harga_jual, stok, stok_min) VALUES (?,?,?,?,?,?)",
            (kode, nama, data.get("kategori") or "Roti", float(data.get("harga_jual") or 0),
             float(data.get("stok") or 0), float(data.get("stok_min") or 0)),
        )
        audit(conn, user, "TAMBAH_PRODUK", f"{kode} {nama}")
        pid = cur.lastrowid
    conn.commit()
    return pid


def save_supplier(conn, data, user="sistem"):
    nama = (data.get("nama") or "").strip()
    if not nama:
        raise BizError("Nama supplier wajib diisi.")
    if data.get("id"):
        conn.execute(
            "UPDATE supplier SET nama=?, kontak=?, telepon=?, alamat=? WHERE id=?",
            (nama, data.get("kontak"), data.get("telepon"), data.get("alamat"), data["id"]),
        )
        sid = data["id"]
        audit(conn, user, "UBAH_SUPPLIER", nama)
    else:
        cur = conn.execute(
            "INSERT INTO supplier (nama, kontak, telepon, alamat) VALUES (?,?,?,?)",
            (nama, data.get("kontak"), data.get("telepon"), data.get("alamat")),
        )
        sid = cur.lastrowid
        audit(conn, user, "TAMBAH_SUPPLIER", nama)
    conn.commit()
    return sid


def hapus_master(conn, tabel, id_, user="sistem"):
    try:
        conn.execute(f"DELETE FROM {tabel} WHERE id=?", (id_,))
        conn.commit()
    except db.IntegrityError:
        conn.rollback()
        raise BizError("Data tidak bisa dihapus karena sudah dipakai pada transaksi. "
                       "Nonaktifkan saja datanya.")
    audit(conn, user, "HAPUS_" + tabel.upper(), f"id={id_}")
    conn.commit()


# ----------------------------------------------------------------------------
# Resep / Bill of Material
# ----------------------------------------------------------------------------
def get_resep(conn, produk_id):
    rows = conn.execute(
        """SELECT r.id, r.bahan_id, r.qty, b.nama, b.satuan, b.harga_beli, b.stok,
                  ROUND(r.qty * b.harga_beli, 2) AS subtotal
           FROM resep r JOIN bahan b ON b.id = r.bahan_id
           WHERE r.produk_id=? ORDER BY b.nama""",
        (produk_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def hpp_unit(conn, produk_id):
    """Harga pokok produksi per unit = total nilai bahan pada resep."""
    row = conn.execute(
        """SELECT COALESCE(SUM(r.qty * b.harga_beli), 0) AS hpp
           FROM resep r JOIN bahan b ON b.id = r.bahan_id WHERE r.produk_id=?""",
        (produk_id,),
    ).fetchone()
    return r2(row["hpp"])


def save_resep(conn, produk_id, items, user="sistem"):
    if not items:
        raise BizError("Resep minimal berisi satu bahan.")
    for it in items:
        if float(it.get("qty") or 0) <= 0:
            raise BizError("Jumlah bahan pada resep harus lebih dari 0.")
    conn.execute("DELETE FROM resep WHERE produk_id=?", (produk_id,))
    for it in items:
        conn.execute(
            "INSERT INTO resep (produk_id, bahan_id, qty) VALUES (?,?,?)",
            (produk_id, int(it["bahan_id"]), float(it["qty"])),
        )
    p = conn.execute("SELECT nama FROM produk WHERE id=?", (produk_id,)).fetchone()
    audit(conn, user, "SIMPAN_RESEP", f"{p['nama']} ({len(items)} bahan)")
    conn.commit()
    return True


# ----------------------------------------------------------------------------
# Modul Pembelian
# ----------------------------------------------------------------------------
def list_pembelian(conn, limit=100):
    rows = conn.execute(
        """SELECT p.*, s.nama AS supplier
           FROM pembelian p JOIN supplier s ON s.id = p.supplier_id
           ORDER BY p.tanggal DESC, p.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_pembelian(conn, id_):
    head = conn.execute(
        """SELECT p.*, s.nama AS supplier FROM pembelian p
           JOIN supplier s ON s.id = p.supplier_id WHERE p.id=?""", (id_,)
    ).fetchone()
    if not head:
        raise BizError("Purchase order tidak ditemukan.")
    items = conn.execute(
        """SELECT pi.*, b.nama, b.satuan FROM pembelian_item pi
           JOIN bahan b ON b.id = pi.bahan_id WHERE pi.pembelian_id=?""", (id_,)
    ).fetchall()
    out = dict(head)
    out["items"] = [dict(r) for r in items]
    return out


def create_pembelian(conn, data, user="sistem", user_id=None):
    supplier_id = int(data.get("supplier_id") or 0)
    if not supplier_id:
        raise BizError("Supplier wajib dipilih.")
    items = [i for i in (data.get("items") or []) if float(i.get("qty") or 0) > 0]
    if not items:
        raise BizError("Minimal satu bahan dengan jumlah > 0.")
    total = 0.0
    no_po = next_number(conn, "pembelian", "no_po", "PO")
    tanggal = data.get("tanggal") or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO pembelian (no_po, tanggal, supplier_id, total, status, user_id, created_at)"
        " VALUES (?,?,?,?, 'draft', ?, ?)",
        (no_po, tanggal, supplier_id, 0, user_id, now_str()),
    )
    pid = cur.lastrowid
    for it in items:
        qty = float(it["qty"])
        harga = float(it.get("harga") or 0)
        sub = r2(qty * harga)
        total += sub
        conn.execute(
            "INSERT INTO pembelian_item (pembelian_id, bahan_id, qty, harga, subtotal)"
            " VALUES (?,?,?,?,?)", (pid, int(it["bahan_id"]), qty, harga, sub),
        )
    conn.execute("UPDATE pembelian SET total=? WHERE id=?", (r2(total), pid))
    audit(conn, user, "BUAT_PO", f"{no_po} total={r2(total)}")
    conn.commit()
    return {"id": pid, "no_po": no_po, "total": r2(total)}


def terima_pembelian(conn, id_, user="sistem"):
    """Penerimaan barang: stok bahan naik, harga rata-rata diperbarui,
    dan otomatis tercatat sebagai kas keluar (integrasi pembelian -> gudang -> keuangan)."""
    head = conn.execute("SELECT * FROM pembelian WHERE id=?", (id_,)).fetchone()
    if not head:
        raise BizError("Purchase order tidak ditemukan.")
    if head["status"] == "diterima":
        raise BizError("PO ini sudah diterima sebelumnya.")
    items = conn.execute("SELECT * FROM pembelian_item WHERE pembelian_id=?", (id_,)).fetchall()
    if not items:
        raise BizError("PO tidak memiliki item.")
    for it in items:
        b = conn.execute("SELECT * FROM bahan WHERE id=?", (it["bahan_id"],)).fetchone()
        stok_lama = float(b["stok"])
        qty = float(it["qty"])
        harga_lama = float(b["harga_beli"])
        stok_baru = stok_lama + qty
        # harga rata-rata bergerak (moving average)
        harga_baru = ((stok_lama * harga_lama) + (qty * float(it["harga"]))) / stok_baru if stok_baru > 0 else float(it["harga"])
        conn.execute(
            "UPDATE bahan SET stok=?, harga_beli=? WHERE id=?",
            (r2(stok_baru), r2(harga_baru), it["bahan_id"]),
        )
    conn.execute("UPDATE pembelian SET status='diterima' WHERE id=?", (id_,))
    conn.execute(
        "INSERT INTO kas (tanggal, tipe, kategori, ref_tipe, ref_id, keterangan, jumlah, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (head["tanggal"], "keluar", "Pembelian Bahan", "pembelian", id_,
         f"Pembayaran {head['no_po']}", float(head["total"]), now_str()),
    )
    audit(conn, user, "TERIMA_PO", f"{head['no_po']} -> stok bertambah, kas keluar {head['total']}")
    conn.commit()
    return {"status": "diterima", "no_po": head["no_po"]}


# ----------------------------------------------------------------------------
# Modul Produksi
# ----------------------------------------------------------------------------
def list_produksi(conn, limit=100):
    rows = conn.execute(
        """SELECT pr.*, p.nama AS produk, p.kode AS produk_kode
           FROM produksi pr JOIN produk p ON p.id = pr.produk_id
           ORDER BY pr.tanggal DESC, pr.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def cek_kebutuhan_bahan(conn, produk_id, qty):
    """Simulasi kebutuhan bahan tanpa mengubah data (dipakai UI & validasi)."""
    resep = get_resep(conn, produk_id)
    if not resep:
        raise BizError("Produk ini belum memiliki resep. Lengkapi resep terlebih dahulu.")
    hasil = []
    for r in resep:
        butuh = r2(r["qty"] * qty)
        hasil.append({
            "bahan_id": r["bahan_id"], "nama": r["nama"], "satuan": r["satuan"],
            "butuh": butuh, "stok": r2(r["stok"]), "cukup": r["stok"] >= butuh,
            "subtotal": r2(butuh * r["harga_beli"]),
        })
    return hasil


def create_produksi(conn, data, user="sistem", user_id=None):
    produk_id = int(data.get("produk_id") or 0)
    qty = float(data.get("qty") or 0)
    if not produk_id or qty <= 0:
        raise BizError("Produk dan jumlah produksi wajib diisi.")
    kebutuhan = cek_kebutuhan_bahan(conn, produk_id, qty)
    kurang = [k for k in kebutuhan if not k["cukup"]]
    if kurang:
        rinci = ", ".join(f"{k['nama']} butuh {k['butuh']} {k['satuan']} (stok {k['stok']})" for k in kurang)
        raise BizError("Stok bahan baku tidak mencukupi: " + rinci)

    biaya = r2(sum(k["subtotal"] for k in kebutuhan))
    no_batch = next_number(conn, "produksi", "no_batch", "PRD")
    tanggal = data.get("tanggal") or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO produksi (no_batch, tanggal, produk_id, qty, biaya_bahan, user_id, catatan, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (no_batch, tanggal, produk_id, qty, biaya, user_id, data.get("catatan"), now_str()),
    )
    prid = cur.lastrowid
    for k in kebutuhan:
        conn.execute(
            "INSERT INTO produksi_item (produksi_id, bahan_id, qty, harga, subtotal) VALUES (?,?,?,?,?)",
            (prid, k["bahan_id"], k["butuh"], r2(k["subtotal"] / k["butuh"]) if k["butuh"] else 0, k["subtotal"]),
        )
        conn.execute("UPDATE bahan SET stok = ROUND(stok - ?, 3) WHERE id=?", (k["butuh"], k["bahan_id"]))
    conn.execute("UPDATE produk SET stok = ROUND(stok + ?, 3) WHERE id=?", (qty, produk_id))
    p = conn.execute("SELECT nama FROM produk WHERE id=?", (produk_id,)).fetchone()
    audit(conn, user, "PRODUKSI", f"{no_batch} {p['nama']} {qty} pcs, biaya bahan {biaya}")
    conn.commit()
    return {"id": prid, "no_batch": no_batch, "biaya_bahan": biaya, "qty": qty}


# ----------------------------------------------------------------------------
# Modul Penjualan (POS)
# ----------------------------------------------------------------------------
def list_penjualan(conn, limit=100):
    rows = conn.execute(
        "SELECT * FROM penjualan ORDER BY tanggal DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        items = conn.execute(
            """SELECT pi.*, p.nama FROM penjualan_item pi JOIN produk p ON p.id = pi.produk_id
               WHERE pi.penjualan_id=?""", (r["id"],)
        ).fetchall()
        d["items"] = [dict(i) for i in items]
        out.append(d)
    return out


def create_penjualan(conn, data, user="sistem", user_id=None):
    items = [i for i in (data.get("items") or []) if float(i.get("qty") or 0) > 0]
    if not items:
        raise BizError("Keranjang masih kosong.")
    subtotal = 0.0
    total_hpp = 0.0
    siap = []
    for it in items:
        pid = int(it["produk_id"])
        qty = float(it["qty"])
        p = conn.execute("SELECT * FROM produk WHERE id=?", (pid,)).fetchone()
        if not p:
            raise BizError("Produk tidak ditemukan.")
        if p["stok"] < qty:
            raise BizError(f"Stok {p['nama']} tidak cukup (tersedia {r2(p['stok'])}). "
                           "Lakukan produksi terlebih dahulu.")
        harga = float(it.get("harga") or p["harga_jual"])
        sub = r2(harga * qty)
        hpp = r2(hpp_unit(conn, pid) * qty)
        subtotal += sub
        total_hpp += hpp
        siap.append((pid, qty, harga, sub, hpp))

    diskon = float(data.get("diskon") or 0)
    total = r2(max(subtotal - diskon, 0))
    metode = data.get("metode") or "Tunai"
    no_inv = next_number(conn, "penjualan", "no_invoice", "INV")
    tanggal = data.get("tanggal") or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO penjualan (no_invoice, tanggal, subtotal, diskon, total, hpp, metode, user_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (no_inv, tanggal, r2(subtotal), r2(diskon), total, r2(total_hpp), metode, user_id, now_str()),
    )
    sid = cur.lastrowid
    for pid, qty, harga, sub, hpp in siap:
        conn.execute(
            "INSERT INTO penjualan_item (penjualan_id, produk_id, qty, harga, subtotal, hpp)"
            " VALUES (?,?,?,?,?,?)", (sid, pid, qty, harga, sub, hpp),
        )
        conn.execute("UPDATE produk SET stok = ROUND(stok - ?, 3) WHERE id=?", (qty, pid))
    conn.execute(
        "INSERT INTO kas (tanggal, tipe, kategori, ref_tipe, ref_id, keterangan, jumlah, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (tanggal, "masuk", "Penjualan", "penjualan", sid, f"Penjualan {no_inv} ({metode})", total, now_str()),
    )
    audit(conn, user, "PENJUALAN", f"{no_inv} total={total} hpp={r2(total_hpp)}")
    conn.commit()
    return {"id": sid, "no_invoice": no_inv, "total": total, "hpp": r2(total_hpp)}


# ----------------------------------------------------------------------------
# Modul Keuangan
# ----------------------------------------------------------------------------
def list_pengeluaran(conn, limit=100):
    rows = conn.execute("SELECT * FROM pengeluaran ORDER BY tanggal DESC, id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def create_pengeluaran(conn, data, user="sistem", user_id=None):
    jumlah = float(data.get("jumlah") or 0)
    if jumlah <= 0:
        raise BizError("Jumlah pengeluaran harus lebih dari 0.")
    kategori = data.get("kategori") or "Operasional"
    tanggal = data.get("tanggal") or date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO pengeluaran (tanggal, kategori, keterangan, jumlah, user_id) VALUES (?,?,?,?,?)",
        (tanggal, kategori, data.get("keterangan"), r2(jumlah), user_id),
    )
    eid = cur.lastrowid
    conn.execute(
        "INSERT INTO kas (tanggal, tipe, kategori, ref_tipe, ref_id, keterangan, jumlah, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (tanggal, "keluar", kategori, "pengeluaran", eid,
         data.get("keterangan") or "Pengeluaran operasional", r2(jumlah), now_str()),
    )
    audit(conn, user, "PENGELUARAN", f"{kategori} {r2(jumlah)}")
    conn.commit()
    return {"id": eid}


def buku_kas(conn, dari, sampai, limit=300):
    rows = conn.execute(
        """SELECT * FROM kas WHERE tanggal BETWEEN ? AND ?
           ORDER BY tanggal DESC, id DESC LIMIT ?""", (dari, sampai, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def laba_rugi(conn, dari, sampai):
    pj = conn.execute(
        "SELECT COALESCE(SUM(total),0) AS pendapatan, COALESCE(SUM(hpp),0) AS hpp, COUNT(*) AS trx "
        "FROM penjualan WHERE tanggal BETWEEN ? AND ?", (dari, sampai)
    ).fetchone()
    beban_rows = conn.execute(
        "SELECT kategori, COALESCE(SUM(jumlah),0) AS jumlah FROM pengeluaran "
        "WHERE tanggal BETWEEN ? AND ? GROUP BY kategori ORDER BY jumlah DESC", (dari, sampai)
    ).fetchall()
    beban = [dict(r) for r in beban_rows]
    total_beban = r2(sum(b["jumlah"] for b in beban))
    pendapatan = r2(pj["pendapatan"])
    hpp = r2(pj["hpp"])
    laba_kotor = r2(pendapatan - hpp)
    laba_bersih = r2(laba_kotor - total_beban)
    beli = conn.execute(
        "SELECT COALESCE(SUM(total),0) AS v FROM pembelian WHERE status='diterima' AND tanggal BETWEEN ? AND ?",
        (dari, sampai)
    ).fetchone()["v"]
    return {
        "dari": dari, "sampai": sampai,
        "pendapatan": pendapatan,
        "hpp": hpp,
        "laba_kotor": laba_kotor,
        "margin_kotor": r2(laba_kotor / pendapatan * 100) if pendapatan else 0,
        "beban": beban,
        "total_beban": total_beban,
        "laba_bersih": laba_bersih,
        "margin_bersih": r2(laba_bersih / pendapatan * 100) if pendapatan else 0,
        "jumlah_transaksi": pj["trx"],
        "pembelian_bahan": r2(beli),
    }


# ----------------------------------------------------------------------------
# Laporan & dashboard
# ----------------------------------------------------------------------------
def dashboard(conn):
    hari_ini = date.today().isoformat()
    awal_bulan = date.today().replace(day=1).isoformat()
    penjualan_hari = conn.execute(
        "SELECT COALESCE(SUM(total),0) AS v, COUNT(*) AS n FROM penjualan WHERE tanggal=?",
        (hari_ini,)).fetchone()
    lr = laba_rugi(conn, awal_bulan, hari_ini)
    stok_kritis = [dict(r) for r in conn.execute(
        """SELECT 'Bahan' AS jenis, kode, nama, stok, stok_min, satuan FROM bahan
           WHERE stok <= stok_min
           UNION ALL
           SELECT 'Produk' AS jenis, kode, nama, stok, stok_min, 'pcs' AS satuan FROM produk
           WHERE stok <= stok_min""").fetchall()]
    nilai_bahan = conn.execute("SELECT COALESCE(SUM(stok*harga_beli),0) AS v FROM bahan").fetchone()["v"]
    nilai_produk = conn.execute(
        "SELECT COALESCE(SUM(p.stok * (SELECT COALESCE(SUM(r.qty*b.harga_beli),0) FROM resep r "
        "JOIN bahan b ON b.id=r.bahan_id WHERE r.produk_id=p.id)),0) AS v FROM produk p").fetchone()["v"]

    tren = []
    for i in range(6, -1, -1):
        tgl = (date.today() - timedelta(days=i)).isoformat()
        row = conn.execute(
            "SELECT COALESCE(SUM(total),0) AS v FROM penjualan WHERE tanggal=?", (tgl,)).fetchone()
        tren.append({"tanggal": tgl, "total": r2(row["v"])})

    top = [dict(r) for r in conn.execute(
        """SELECT p.nama, SUM(pi.qty) AS qty, SUM(pi.subtotal) AS omzet
           FROM penjualan_item pi JOIN produk p ON p.id = pi.produk_id
           JOIN penjualan s ON s.id = pi.penjualan_id
           WHERE s.tanggal >= ? GROUP BY p.id ORDER BY qty DESC LIMIT 5""",
        ((date.today() - timedelta(days=30)).isoformat(),)).fetchall()]

    terbaru = [dict(r) for r in conn.execute(
        "SELECT no_invoice, tanggal, total, metode FROM penjualan ORDER BY id DESC LIMIT 5").fetchall()]

    return {
        "penjualan_hari_ini": r2(penjualan_hari["v"]),
        "transaksi_hari_ini": penjualan_hari["n"],
        "laba_bulan_ini": lr["laba_bersih"],
        "pendapatan_bulan_ini": lr["pendapatan"],
        "margin_bulan_ini": lr["margin_bersih"],
        "nilai_persediaan": r2(nilai_bahan + nilai_produk),
        "nilai_bahan": r2(nilai_bahan),
        "nilai_produk": r2(nilai_produk),
        "stok_kritis": stok_kritis,
        "tren": tren,
        "top_produk": top,
        "transaksi_terbaru": terbaru,
        "jumlah_po_draft": conn.execute(
            "SELECT COUNT(*) AS n FROM pembelian WHERE status='draft'").fetchone()["n"],
    }


def laporan_stok(conn):
    bahan = [dict(r) for r in conn.execute(
        """SELECT kode, nama, satuan, stok, stok_min, harga_beli,
                  ROUND(stok*harga_beli,2) AS nilai FROM bahan ORDER BY nama""").fetchall()]
    produk = []
    for p in conn.execute("SELECT * FROM produk ORDER BY nama").fetchall():
        d = dict(p)
        d["hpp"] = hpp_unit(conn, p["id"])
        d["margin"] = r2(p["harga_jual"] - d["hpp"])
        produk.append(d)
    return {"bahan": bahan, "produk": produk}


def laporan_penjualan(conn, dari, sampai):
    harian = [dict(r) for r in conn.execute(
        """SELECT tanggal, COUNT(*) AS trx, ROUND(SUM(total),2) AS omzet, ROUND(SUM(hpp),2) AS hpp
           FROM penjualan WHERE tanggal BETWEEN ? AND ? GROUP BY tanggal ORDER BY tanggal""",
        (dari, sampai)).fetchall()]
    per_produk = [dict(r) for r in conn.execute(
        """SELECT p.nama, SUM(pi.qty) AS qty, ROUND(SUM(pi.subtotal),2) AS omzet,
                  ROUND(SUM(pi.hpp),2) AS hpp
           FROM penjualan_item pi JOIN produk p ON p.id=pi.produk_id
           JOIN penjualan s ON s.id=pi.penjualan_id
           WHERE s.tanggal BETWEEN ? AND ? GROUP BY p.id ORDER BY omzet DESC""",
        (dari, sampai)).fetchall()]
    return {"harian": harian, "per_produk": per_produk}


def laporan_produksi(conn, dari, sampai):
    return [dict(r) for r in conn.execute(
        """SELECT pr.no_batch, pr.tanggal, p.nama AS produk, pr.qty, pr.biaya_bahan,
                  ROUND(pr.biaya_bahan / pr.qty, 2) AS hpp_unit
           FROM produksi pr JOIN produk p ON p.id=pr.produk_id
           WHERE pr.tanggal BETWEEN ? AND ? ORDER BY pr.tanggal DESC""", (dari, sampai)).fetchall()]


def list_audit(conn, limit=100):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]


# ----------------------------------------------------------------------------
# Seed data contoh (dipakai sekali saat instalasi)
# ----------------------------------------------------------------------------
def seed(conn, with_history=True):
    users = [
        ("admin", "admin123", "Kadek Lyradelia", "admin"),
        ("gudang", "gudang123", "Ni Luh Ari", "gudang"),
        ("kasir", "kasir123", "Bagus Prayoga", "kasir"),
    ]
    for u, p, n, role in users:
        h, salt = hash_password(p)
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, salt, nama, role) VALUES (?,?,?,?,?)",
            (u, h, salt, n, role),
        )

    suppliers = [
        ("CV Tepung Nusantara", "Pak Hendra", "0812-3456-7890", "Jl. Raya Sesetan 88, Denpasar"),
        ("UD Sumber Dairy", "Bu Sri", "0813-9988-7766", "Jl. Gatot Subroto 12, Denpasar"),
        ("Toko Bahan Kue Makmur", "Pak Wayan", "0877-1122-3344", "Jl. Kumbasari 5, Denpasar"),
    ]
    conn.executemany(
        "INSERT INTO supplier (nama, kontak, telepon, alamat) VALUES (?,?,?,?)", suppliers)

    bahan = [
        # kode, nama, satuan, stok_awal, stok_min, harga
        ("BH-001", "Tepung Terigu Protein Tinggi", "kg", 0, 25, 13_500),
        ("BH-002", "Tepung Terigu Protein Sedang", "kg", 0, 20, 12_000),
        ("BH-003", "Gula Pasir", "kg", 0, 15, 16_000),
        ("BH-004", "Mentega Tawar", "kg", 0, 8, 95_000),
        ("BH-005", "Telur Ayam", "kg", 0, 10, 28_000),
        ("BH-006", "Ragi Instan", "kg", 0, 2, 120_000),
        ("BH-007", "Susu UHT Full Cream", "liter", 0, 10, 19_000),
        ("BH-008", "Cokelat Batang", "kg", 0, 5, 145_000),
        ("BH-009", "Keju Cheddar", "kg", 0, 4, 130_000),
        ("BH-010", "Garam Halus", "kg", 0, 2, 8_000),
        ("BH-011", "Butter Sheet (korsvet)", "kg", 0, 3, 110_000),
        ("BH-012", "Kemasan Roti", "pcs", 0, 200, 850),
    ]
    conn.executemany(
        "INSERT INTO bahan (kode, nama, satuan, stok, stok_min, harga_beli) VALUES (?,?,?,?,?,?)", bahan)

    produk = [
        ("PR-001", "Roti Tawar Gandum", "Roti Tawar", 22_000, 0, 10),
        ("PR-002", "Croissant Butter", "Pastry", 15_000, 0, 12),
        ("PR-003", "Donat Gula", "Donat", 7_000, 0, 15),
        ("PR-004", "Bolu Cokelat", "Cake", 35_000, 0, 6),
        ("PR-005", "Roti Sobek Keju", "Roti Manis", 25_000, 0, 10),
        ("PR-006", "Bagel Plain", "Roti Keras", 13_000, 0, 10),
    ]
    conn.executemany(
        "INSERT INTO produk (kode, nama, kategori, harga_jual, stok, stok_min) VALUES (?,?,?,?,?,?)", produk)

    # Resep per 1 unit produk (BOM) - takaran realistis untuk skala UMKM bakery
    resep = {
        # Roti Tawar Gandum 500 g
        "PR-001": [("BH-001", 0.30), ("BH-003", 0.03), ("BH-004", 0.03), ("BH-006", 0.005), ("BH-012", 1)],
        # Croissant Butter (butter sheet dominan)
        "PR-002": [("BH-001", 0.06), ("BH-011", 0.05), ("BH-003", 0.008), ("BH-005", 0.02), ("BH-012", 1)],
        # Donat Gula
        "PR-003": [("BH-002", 0.07), ("BH-003", 0.02), ("BH-005", 0.02), ("BH-007", 0.02), ("BH-012", 1)],
        # Bolu Cokelat
        "PR-004": [("BH-002", 0.08), ("BH-003", 0.05), ("BH-005", 0.06), ("BH-008", 0.03), ("BH-012", 1)],
        # Roti Sobek Keju
        "PR-005": [("BH-001", 0.08), ("BH-003", 0.02), ("BH-009", 0.025), ("BH-005", 0.02), ("BH-012", 1)],
        # Bagel Plain
        "PR-006": [("BH-001", 0.09), ("BH-003", 0.005), ("BH-010", 0.003), ("BH-006", 0.002),
                   ("BH-004", 0.01), ("BH-012", 1)],
    }
    kode_ke_id = {r["kode"]: r["id"] for r in conn.execute("SELECT id, kode FROM bahan")}
    prod_ke_id = {r["kode"]: r["id"] for r in conn.execute("SELECT id, kode FROM produk")}
    for pk, items in resep.items():
        for bk, qty in items:
            conn.execute("INSERT INTO resep (produk_id, bahan_id, qty) VALUES (?,?,?)",
                         (prod_ke_id[pk], kode_ke_id[bk], qty))
    conn.commit()

    if not with_history:
        return

    # ---- Riwayat 31 hari terakhir: pembelian -> produksi -> penjualan -> keuangan ----
    rnd = random.Random(20261029)
    admin_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
    gudang_id = conn.execute("SELECT id FROM users WHERE username='gudang'").fetchone()["id"]
    kasir_id = conn.execute("SELECT id FROM users WHERE username='kasir'").fetchone()["id"]
    sup_ids = [r["id"] for r in conn.execute("SELECT id FROM supplier")]

    # Stok ideal gudang per bahan (satuan dasar) - dipakai untuk pola restock
    TARGET = {
        "BH-001": 180, "BH-002": 140, "BH-003": 90, "BH-004": 45, "BH-005": 70,
        "BH-006": 6, "BH-007": 90, "BH-008": 28, "BH-009": 22, "BH-010": 12,
        "BH-011": 30, "BH-012": 3500,
    }

    def supplier_untuk(kode):
        return sup_ids[(int(kode.split("-")[1]) - 1) % len(sup_ids)]

    def belanja(tgl, hanya_kurang=True):
        """PO + penerimaan barang untuk bahan yang stoknya menipis (restock otomatis)."""
        per_supplier = {}
        for kode, target in TARGET.items():
            b = conn.execute("SELECT * FROM bahan WHERE kode=?", (kode,)).fetchone()
            if hanya_kurang and b["stok"] >= target * 0.55:
                continue
            qty = round(target - b["stok"], 2)
            if qty <= 0:
                continue
            harga = round(b["harga_beli"] * rnd.uniform(0.98, 1.06))
            per_supplier.setdefault(supplier_untuk(kode), []).append(
                {"bahan_id": b["id"], "qty": qty, "harga": harga})
        for sup, items in per_supplier.items():
            res = create_pembelian(conn, {"supplier_id": sup, "items": items, "tanggal": tgl},
                                   user="gudang", user_id=gudang_id)
            terima_pembelian(conn, res["id"], user="gudang")

    produk_ids = [r["id"] for r in conn.execute("SELECT id FROM produk")]

    # stok awal gudang (PO pertama, tanggal 31 hari lalu)
    belanja((date.today() - timedelta(days=31)).isoformat(), hanya_kurang=False)

    def produksi_untuk(pid, qty, tgl):
        try:
            create_produksi(conn, {"produk_id": pid, "qty": qty, "tanggal": tgl},
                            user="gudang", user_id=gudang_id)
        except BizError:
            # bahan kurang -> restock lalu ulangi produksi
            belanja(tgl)
            create_produksi(conn, {"produk_id": pid, "qty": qty, "tanggal": tgl},
                            user="gudang", user_id=gudang_id)

    for d in range(30, -1, -1):
        tgl = (date.today() - timedelta(days=d)).isoformat()
        weekday = (date.today() - timedelta(days=d)).weekday()

        # 1) Produksi pagi: isi etalase sampai target stok
        for pid in produk_ids:
            target = rnd.randint(20, 30) + (12 if weekday >= 5 else 0)
            stok = conn.execute("SELECT stok FROM produk WHERE id=?", (pid,)).fetchone()["stok"]
            if stok < target:
                produksi_untuk(pid, int(target - stok), tgl)

        # 2) Penjualan sepanjang hari (60-82% stok etalase terjual)
        total_stok = sum(r["stok"] for r in conn.execute("SELECT stok FROM produk"))
        target_jual = int(total_stok * rnd.uniform(0.60, 0.82))
        terjual, percobaan = 0, 0
        while terjual < target_jual and percobaan < 60:
            percobaan += 1
            items = []
            for pid in rnd.sample(produk_ids, rnd.randint(1, 3)):
                stok = conn.execute("SELECT stok FROM produk WHERE id=?", (pid,)).fetchone()["stok"]
                if stok >= 1:
                    items.append({"produk_id": pid, "qty": rnd.randint(1, min(6, int(stok)))})
            if not items:
                break
            try:
                create_penjualan(conn, {"items": items,
                                        "metode": rnd.choice(["Tunai", "Tunai", "QRIS", "Transfer"]),
                                        "tanggal": tgl}, user="kasir", user_id=kasir_id)
                terjual += sum(i["qty"] for i in items)
            except BizError:
                break

        # 3) Restock mingguan (setiap Senin)
        if weekday == 0:
            belanja(tgl)

        # 4) Beban operasional
        if d % 7 == 0:
            create_pengeluaran(conn, {"tanggal": tgl, "kategori": "Gaji Karyawan",
                                      "keterangan": "Gaji mingguan 3 karyawan produksi & kasir",
                                      "jumlah": 1_850_000}, user="admin", user_id=admin_id)
            create_pengeluaran(conn, {"tanggal": tgl, "kategori": "Listrik & Gas",
                                      "keterangan": "Operasional oven, mixer, dan chiller",
                                      "jumlah": rnd.randint(480_000, 620_000)},
                               user="admin", user_id=admin_id)
        if d % 30 == 0:
            create_pengeluaran(conn, {"tanggal": tgl, "kategori": "Sewa Tempat",
                                      "keterangan": "Sewa ruko bulanan",
                                      "jumlah": 4_500_000}, user="admin", user_id=admin_id)
            create_pengeluaran(conn, {"tanggal": tgl, "kategori": "Perawatan Mesin",
                                      "keterangan": "Servis berkala oven & mixer",
                                      "jumlah": 750_000}, user="admin", user_id=admin_id)
    audit(conn, "sistem", "SEED", "Data contoh 30 hari dibuat")
    conn.commit()


def ensure_seed():
    init_db()
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if n == 0:
        seed(conn)
    conn.close()


if __name__ == "__main__":
    init_db(force=True)
    conn = get_db()
    seed(conn)
    conn.close()
    print("Database dibuat ulang di", DB_PATH)
