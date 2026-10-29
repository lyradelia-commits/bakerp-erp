"""
Pemilih backend basis data untuk BakeERP.

Default: SQLite (berkas bakery.db) — tidak perlu server apa pun.
Alternatif: MySQL/MariaDB — aktifkan dengan variabel lingkungan BAKERP_BACKEND=mysql.

Contoh:
    python app.py                                   -> SQLite (bawaan)
    BAKERP_BACKEND=mysql python app.py              -> MySQL localhost:3306/bakerp

Konfigurasi MySQL dapat diubah lewat variabel lingkungan:
    BAKERP_MYSQL_HOST      (default 127.0.0.1)
    BAKERP_MYSQL_PORT      (default 3306)
    BAKERP_MYSQL_USER      (default root)
    BAKERP_MYSQL_PASSWORD  (default kosong)
    BAKERP_MYSQL_DB        (default bakerp)
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("BAKERP_DB") or os.path.join(BASE_DIR, "bakery.db")

BACKEND = (os.environ.get("BAKERP_BACKEND") or "sqlite").strip().lower()

MYSQL = {
    "host": os.environ.get("BAKERP_MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("BAKERP_MYSQL_PORT", "3306")),
    "user": os.environ.get("BAKERP_MYSQL_USER", "root"),
    "password": os.environ.get("BAKERP_MYSQL_PASSWORD", ""),
    "database": os.environ.get("BAKERP_MYSQL_DB", "bakerp"),
}

if BACKEND == "mysql":
    import dbmysql
    from dbmysql import IntegrityError, Row

    def connect():
        return dbmysql.connect(**MYSQL)

    def deskripsi():
        return f"MySQL {MYSQL['host']}:{MYSQL['port']}/{MYSQL['database']}"

    def hapus_database():
        """Menghapus seluruh isi database MySQL (untuk reset)."""
        konek = dbmysql.connect_tanpa_db(host=MYSQL["host"], port=MYSQL["port"],
                                         user=MYSQL["user"], password=MYSQL["password"])
        with konek.cursor() as c:
            c.execute(f"DROP DATABASE IF EXISTS `{MYSQL['database']}`")
        konek.close()

    def pastikan_database():
        """Membuat database bila belum ada."""
        konek = dbmysql.connect_tanpa_db(host=MYSQL["host"], port=MYSQL["port"],
                                         user=MYSQL["user"], password=MYSQL["password"])
        with konek.cursor() as c:
            c.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL['database']}` "
                      "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        konek.close()

else:
    from sqlite3 import IntegrityError  # noqa: F401

    def connect():
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def deskripsi():
        return f"SQLite {DB_PATH}"

    def hapus_database():
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def pastikan_database():
        return None

    Row = sqlite3.Row
