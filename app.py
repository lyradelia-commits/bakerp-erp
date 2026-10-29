"""
BakeERP - Server aplikasi (HTTP + REST API + penyajian file statis)
===================================================================
Jalankan lokal:   python app.py              -> http://localhost:8000
Port lain:        python app.py --port 8080
Di hosting:       otomatis memakai $PORT dan mendengarkan 0.0.0.0

Tidak memerlukan framework eksternal (hanya standard library).

Berkas ini menyediakan dua pintu masuk yang memakai inti logika yang sama:
  1. ThreadingHTTPServer (mode lokal, `python app.py`)
  2. WSGI (mode hosting, lihat wsgi.py)

Seluruh penanganan permintaan dipusatkan pada fungsi `handle()` sehingga
tidak ada logika yang terduplikasi antara kedua mode tersebut.
"""

import json
import mimetypes
import os
import sys
import threading
import traceback
import urllib.parse
from datetime import date  # noqa: F401  (dipertahankan untuk kompatibilitas tipe)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core
from core import BizError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

TOKENS = {}          # token -> user dict
TOKEN_LOCK = threading.Lock()

JSON_CT = "application/json; charset=utf-8"


# ---------------------------------------------------------------------------
# Pembungkus respons
# ---------------------------------------------------------------------------
def ok(data=None, **extra):
    body = {"ok": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return 200, body


def err(msg, code=400):
    return code, {"ok": False, "error": msg}


# ---------------------------------------------------------------------------
# Inti penanganan permintaan (dipakai http.server maupun WSGI)
# ---------------------------------------------------------------------------
def _load_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except Exception:
        raise BizError("Format data tidak valid (JSON).")


def _token_of(headers):
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    return auth.replace("Bearer ", "").strip()


def _user_of(headers):
    token = _token_of(headers)
    with TOKEN_LOCK:
        return TOKENS.get(token), token


def _baca_statis(path):
    """Mengembalikan (status, isi_bytes, content_type) untuk berkas statis."""
    if path in ("/", ""):
        path = "/index.html"
    safe = os.path.normpath(path.lstrip("/")).replace("\\", "/")
    if safe.startswith(".."):
        return 403, b"Forbidden", "text/plain; charset=utf-8"
    full = os.path.join(STATIC_DIR, safe)
    if not os.path.isfile(full):
        return 404, b"Not found", "text/plain; charset=utf-8"
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    with open(full, "rb") as f:
        return 200, f.read(), ctype


def handle(method, path, query_string="", headers=None, raw_body=b""):
    """Menangani satu permintaan.

    Mengembalikan (status:int, payload:dict|bytes, content_type:str).
    Dipakai oleh Handler (http.server) dan application (WSGI).
    """
    headers = headers or {}
    parsed = urllib.parse.urlparse(path)
    p = parsed.path
    qs = parsed.query or query_string or ""
    q = urllib.parse.parse_qs(qs)

    # ---- berkas statis ----
    if not p.startswith("/api/"):
        if method != "GET":
            return 405, b"Method not allowed", "text/plain; charset=utf-8"
        return _baca_statis(p)

    # ---- API ----
    try:
        code, payload = _api(method, p, q, headers, raw_body)
    except BizError as e:
        code, payload = err(str(e), 400)
    except Exception:
        traceback.print_exc()
        ringkas = traceback.format_exc(limit=1).splitlines()[-1]
        code, payload = err("Terjadi kesalahan pada server: " + ringkas, 500)
    return code, payload, JSON_CT


def _api(method, path, q, headers, raw_body):
    parts = [x for x in path.strip("/").split("/") if x]
    res = parts[1] if len(parts) > 1 else ""
    sub = parts[2] if len(parts) > 2 else ""
    sub2 = parts[3] if len(parts) > 3 else ""

    if res == "info":
        return ok({
            "aplikasi": "BakeERP",
            "versi": "1.0",
            "backend": core.db.BACKEND,
            "database": core.db.deskripsi(),
            "waktu": core.now_str(),
        })

    if res == "login" and method == "POST":
        data = _load_json(raw_body)
        conn = core.get_db()
        try:
            user = core.authenticate(conn, data.get("username", ""), data.get("password", ""))
        finally:
            conn.close()
        token = core.secrets.token_urlsafe(24)
        with TOKEN_LOCK:
            TOKENS[token] = user
        return ok({"token": token, "user": user})

    user, token = _user_of(headers)
    if not user:
        return err("Sesi berakhir, silakan login kembali.", 401)

    if res == "logout" and method == "POST":
        with TOKEN_LOCK:
            TOKENS.pop(token, None)
        return ok()

    if res == "me":
        return ok(user)

    conn = core.get_db()
    try:
        return _api_auth(method, res, sub, sub2, q, user, conn, raw_body)
    finally:
        conn.close()


def _api_auth(method, res, sub, sub2, q, user, conn, raw_body):
    nama = user["nama"]

    # ---------- Dashboard ----------
    if res == "dashboard":
        return ok(core.dashboard(conn))

    # ---------- Master: bahan / produk / supplier ----------
    if res in ("bahan", "produk", "supplier"):
        tabel = res
        if method == "GET":
            rows = core.list_master(conn, tabel)
            if tabel == "produk":
                for r in rows:
                    r["hpp"] = core.hpp_unit(conn, r["id"])
                    r["margin"] = core.r2(r["harga_jual"] - r["hpp"])
            return ok(rows)
        if method == "POST":
            data = _load_json(raw_body)
            fn = {"bahan": core.save_bahan, "produk": core.save_produk,
                  "supplier": core.save_supplier}[tabel]
            pid = fn(conn, data, user=nama)
            return ok({"id": pid})
        if method == "DELETE" and sub:
            core.hapus_master(conn, tabel, int(sub), user=nama)
            return ok()

    # ---------- Resep / BOM ----------
    if res == "resep":
        if method == "GET":
            pid = int(q.get("produk_id", ["0"])[0])
            return ok({"items": core.get_resep(conn, pid), "hpp": core.hpp_unit(conn, pid)})
        if method == "POST":
            data = _load_json(raw_body)
            core.save_resep(conn, int(data.get("produk_id") or 0),
                            data.get("items") or [], user=nama)
            return ok({"hpp": core.hpp_unit(conn, int(data.get("produk_id") or 0))})

    # ---------- Pembelian ----------
    if res == "pembelian":
        if method == "GET":
            if sub:
                return ok(core.get_pembelian(conn, int(sub)))
            return ok(core.list_pembelian(conn))
        if method == "POST":
            if sub and sub2 == "terima":
                return ok(core.terima_pembelian(conn, int(sub), user=nama))
            data = _load_json(raw_body)
            return ok(core.create_pembelian(conn, data, user=nama, user_id=user["id"]))

    # ---------- Produksi ----------
    if res == "produksi":
        if method == "GET":
            return ok(core.list_produksi(conn))
        if method == "POST":
            data = _load_json(raw_body)
            if sub == "cek":
                kebutuhan = core.cek_kebutuhan_bahan(
                    conn, int(data.get("produk_id") or 0), float(data.get("qty") or 0))
                return ok({"kebutuhan": kebutuhan,
                           "total_biaya": core.r2(sum(k["subtotal"] for k in kebutuhan))})
            return ok(core.create_produksi(conn, data, user=nama, user_id=user["id"]))

    # ---------- Penjualan ----------
    if res == "penjualan":
        if method == "GET":
            return ok(core.list_penjualan(conn))
        if method == "POST":
            data = _load_json(raw_body)
            return ok(core.create_penjualan(conn, data, user=nama, user_id=user["id"]))

    # ---------- Pengeluaran ----------
    if res == "pengeluaran":
        if method == "GET":
            return ok(core.list_pengeluaran(conn))
        if method == "POST":
            data = _load_json(raw_body)
            return ok(core.create_pengeluaran(conn, data, user=nama, user_id=user["id"]))

    # ---------- Keuangan ----------
    if res == "keuangan":
        dari = q.get("dari", [core.hari_ini().replace(day=1).isoformat()])[0]
        sampai = q.get("sampai", [core.hari_ini().isoformat()])[0]
        if sub == "labarugi":
            return ok(core.laba_rugi(conn, dari, sampai))
        if sub == "kas":
            return ok(core.buku_kas(conn, dari, sampai))

    # ---------- Laporan ----------
    if res == "laporan":
        dari = q.get("dari", [core.hari_ini().replace(day=1).isoformat()])[0]
        sampai = q.get("sampai", [core.hari_ini().isoformat()])[0]
        if sub == "stok":
            return ok(core.laporan_stok(conn))
        if sub == "penjualan":
            return ok(core.laporan_penjualan(conn, dari, sampai))
        if sub == "produksi":
            return ok(core.laporan_produksi(conn, dari, sampai))

    if res == "audit":
        return ok(core.list_audit(conn))

    return err("Endpoint tidak ditemukan: " + res, 404)


# ---------------------------------------------------------------------------
# Mode lokal: http.server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "BakeERP/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _kirim(self, code, payload, content_type=JSON_CT):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, str):
            payload = payload.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _route(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        headers = {k: v for k, v in self.headers.items()}
        code, payload, ctype = handle(method, self.path, "", headers, raw)
        self._kirim(code, payload, ctype)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")


def main():
    port = int(os.environ.get("PORT") or 8000)
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    if "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]

    core.ensure_seed()
    srv = ThreadingHTTPServer((host, port), Handler)
    print("=" * 62)
    print("  BakeERP siap dijalankan")
    print("  Mendengarkan di: http://%s:%d" % (host, port))
    print("  Login: admin / admin123  (gudang / gudang123, kasir / kasir123)")
    print("  Basis data: %s" % core.db.deskripsi())
    print("=" * 62)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")


if __name__ == "__main__":
    main()
