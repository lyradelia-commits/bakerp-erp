"""
Lapisan kompatibilitas MySQL untuk BakeERP.

Tujuan: `core.py` ditulis memakai gaya API `sqlite3` (placeholder `?`,
`conn.execute(...)`, `fetchone()["kolom"]`). Modul ini menyediakan objek
yang berperilaku sama tetapi berbicara ke MySQL melalui PyMySQL, sehingga
seluruh logika bisnis tidak perlu ditulis ulang.

Pemakaian:
    import dbmysql
    conn = dbmysql.connect(host=..., user=..., password=..., database=...)
    conn.execute("SELECT * FROM bahan WHERE id=?", (1,)).fetchone()["nama"]

Catatan teknis:
  * Placeholder `?` diterjemahkan menjadi `%s` (dialek PyMySQL).
  * Baris hasil (Row) mendukung akses indeks (row[0]) sekaligus nama (row["nama"]).
  * `sql_mode` disetel tanpa ONLY_FULL_GROUP_BY agar query agregat bergaya
    SQLite (mis. SELECT p.nama, SUM(qty) ... GROUP BY p.id) tetap valid.
"""

import re

import pymysql
import pymysql.cursors

# Kesalahan integritas (foreign key / unique) disamakan dengan sqlite3.IntegrityError
IntegrityError = pymysql.err.IntegrityError


# ---------------------------------------------------------------------------
# Baris hasil
# ---------------------------------------------------------------------------
class Row:
    """Baris hasil query: bisa diakses seperti tuple maupun seperti dict."""

    __slots__ = ("_kolom", "_nilai", "_peta")

    def __init__(self, kolom, nilai):
        self._kolom = tuple(kolom)
        self._nilai = tuple(nilai)
        self._peta = {k: i for i, k in enumerate(self._kolom)}

    def __getitem__(self, kunci):
        if isinstance(kunci, int):
            return self._nilai[kunci]
        try:
            return self._nilai[self._peta[kunci]]
        except KeyError:
            raise KeyError(kunci) from None

    def __iter__(self):
        return iter(self._nilai)

    def __len__(self):
        return len(self._nilai)

    def keys(self):
        return list(self._kolom)

    def values(self):
        return list(self._nilai)

    def items(self):
        return list(zip(self._kolom, self._nilai))

    def get(self, kunci, default=None):
        i = self._peta.get(kunci)
        return default if i is None else self._nilai[i]

    def __repr__(self):
        return "Row(" + ", ".join(f"{k}={v!r}" for k, v in self.items()) + ")"


# ---------------------------------------------------------------------------
# Terjemahan dialek SQLite -> MySQL
# ---------------------------------------------------------------------------
_RE_PRAGMA = re.compile(r"^\s*PRAGMA\b", re.I)
_RE_CREATE_INDEX_INE = re.compile(r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS", re.I)
_RE_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE", re.I)


def terjemahkan(sql: str) -> str:
    s = sql
    s = _RE_INSERT_OR_IGNORE.sub("INSERT IGNORE", s)
    s = re.sub(r"\bAUTOINCREMENT\b", "AUTO_INCREMENT", s, flags=re.I)
    # REAL -> DOUBLE (kecuali di dalam nama kolom/identifier)
    s = re.sub(r"\bREAL\b", "DOUBLE", s, flags=re.I)
    # Placeholder posisional
    s = s.replace("?", "%s")
    return s


def _pecah_skrip(skrip: str):
    """Memecah skrip DDL menjadi pernyataan tunggal (abaikan ';' di dalam string)."""
    hasil, buf, dalam_string = [], [], None
    for ch in skrip:
        if dalam_string:
            buf.append(ch)
            if ch == dalam_string:
                dalam_string = None
            continue
        if ch in ("'", '"'):
            dalam_string = ch
            buf.append(ch)
            continue
        if ch == ";":
            pernyataan = "".join(buf).strip()
            if pernyataan:
                hasil.append(pernyataan)
            buf = []
            continue
        buf.append(ch)
    sisa = "".join(buf).strip()
    if sisa:
        hasil.append(sisa)
    return hasil


# ---------------------------------------------------------------------------
# Kursor
# ---------------------------------------------------------------------------
class Cursor:
    def __init__(self, kursor):
        self._k = kursor

    def _bungkus(self, baris):
        if baris is None:
            return None
        kolom = [d[0] for d in self._k.description]
        return Row(kolom, baris)

    def fetchone(self):
        return self._bungkus(self._k.fetchone())

    def fetchall(self):
        return [self._bungkus(b) for b in self._k.fetchall()]

    def __iter__(self):
        for b in self._k.fetchall():
            yield self._bungkus(b)

    @property
    def lastrowid(self):
        return self._k.lastrowid

    @property
    def rowcount(self):
        return self._k.rowcount

    @property
    def description(self):
        return self._k.description


# ---------------------------------------------------------------------------
# Koneksi
# ---------------------------------------------------------------------------
class Connection:
    def __init__(self, **konfigurasi):
        self.row_factory = None          # diabaikan (kompatibilitas sqlite3)
        self._conn = pymysql.connect(
            cursorclass=pymysql.cursors.Cursor,
            charset="utf8mb4",
            autocommit=False,
            **konfigurasi,
        )
        # Longgarkan ONLY_FULL_GROUP_BY agar query agregat gaya SQLite tetap jalan
        with self._conn.cursor() as c:
            c.execute(
                "SET SESSION sql_mode = "
                "'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,"
                "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
            )

    # -- eksekusi ----------------------------------------------------------
    def execute(self, sql, params=()):
        if _RE_PRAGMA.match(sql):
            return Cursor(self._kosong())
        kursor = self._conn.cursor()
        kursor.execute(terjemahkan(sql), params or ())
        return Cursor(kursor)

    def executemany(self, sql, seq_params):
        if _RE_PRAGMA.match(sql):
            return Cursor(self._kosong())
        kursor = self._conn.cursor()
        kursor.executemany(terjemahkan(sql), seq_params)
        return Cursor(kursor)

    def _kosong(self):
        kursor = self._conn.cursor()
        kursor.execute("SELECT 1 WHERE 0")
        return kursor

    def executescript(self, skrip):
        for pernyataan in _pecah_skrip(skrip):
            if _RE_PRAGMA.match(pernyataan):
                continue
            # CREATE INDEX IF NOT EXISTS tidak dikenal MySQL 8
            bersih = _RE_CREATE_INDEX_INE.sub("CREATE INDEX", pernyataan)
            try:
                kursor = self._conn.cursor()
                kursor.execute(terjemahkan(bersih))
            except pymysql.err.OperationalError as e:
                kode = e.args[0] if e.args else 0
                if kode in (1050, 1061):     # tabel / indeks sudah ada
                    continue
                raise

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def cursor(self):
        return Cursor(self._conn.cursor())

    # konteks manajer (dipakai sebagian kode bila perlu)
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc and exc[0] is not None:
            self.rollback()
        else:
            self.commit()
        return False


def connect(host="127.0.0.1", port=3306, user="root", password="", database="bakerp", **kw):
    return Connection(host=host, port=port, user=user, password=password,
                      database=database, **kw)


def connect_tanpa_db(host="127.0.0.1", port=3306, user="root", password=""):
    """Koneksi tanpa memilih database (untuk CREATE DATABASE)."""
    return pymysql.connect(host=host, port=port, user=user, password=password,
                           charset="utf8mb4", autocommit=True)
