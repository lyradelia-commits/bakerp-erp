"""
BakeERP - Server aplikasi (HTTP + REST API + penyajian file statis)
===================================================================
Jalankan:  python app.py            -> http://localhost:8000
Opsi:      python app.py --port 8080

Tidak memerlukan framework eksternal (hanya standard library).
"""

import json
import mimetypes
import os
import sys
import threading
import traceback
import urllib.parse
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import core
from core import BizError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

TOKENS = {}          # token -> user dict
TOKEN_LOCK = threading.Lock()


def ok(data=None, **extra):
    body = {"ok": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return 200, body


def err(msg, code=400):
    return code, {"ok": False, "error": msg}


class Handler(BaseHTTPRequestHandler):
    server_version = "BakeERP/1.0"

    # ---------------- util ----------------
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise BizError("Format data tidak valid (JSON).")

    def _send(self, code, payload, content_type="application/json; charset=utf-8"):
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

    def _user(self):
        auth = self.headers.get("Authorization") or ""
        token = auth.replace("Bearer ", "").strip()
        with TOKEN_LOCK:
            return TOKENS.get(token), token

    def _static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        safe = os.path.normpath(path.lstrip("/")).replace("\\", "/")
        if safe.startswith(".."):
            return self._send(403, "Forbidden", "text/plain")
        full = os.path.join(STATIC_DIR, safe)
        if not os.path.isfile(full):
            return self._send(404, "Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)

    # ---------------- HTTP verbs ----------------
    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")

    def do_DELETE(self):
        self._route("DELETE")

    def _route(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        q = urllib.parse.parse_qs(parsed.query)

        if not path.startswith("/api/"):
            if method != "GET":
                return self._send(405, "Method not allowed", "text/plain")
            return self._static(path)

        try:
            code, payload = self._api(method, path, q)
        except BizError as e:
            code, payload = err(str(e), 400)
        except Exception:
            traceback.print_exc()
            code, payload = err("Terjadi kesalahan pada server: " + traceback.format_exc(limit=1).splitlines()[-1], 500)
        self._send(code, payload)

    # ---------------- API ----------------
    def _api(self, method, path, q):
        parts = [p for p in path.strip("/").split("/") if p]
        # parts[0] == 'api'
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
            data = self._json_body()
            conn = core.get_db()
            try:
                user = core.authenticate(conn, data.get("username", ""), data.get("password", ""))
            finally:
                conn.close()
            token = core.secrets.token_urlsafe(24)
            with TOKEN_LOCK:
                TOKENS[token] = user
            return ok({"token": token, "user": user})

        user, token = self._user()
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
            return self._api_auth(method, res, sub, sub2, q, user, conn)
        finally:
            conn.close()

    def _api_auth(self, method, res, sub, sub2, q, user, conn):
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
                data = self._json_body()
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
                data = self._json_body()
                core.save_resep(conn, int(data.get("produk_id") or 0), data.get("items") or [], user=nama)
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
                data = self._json_body()
                return ok(core.create_pembelian(conn, data, user=nama, user_id=user["id"]))

        # ---------- Produksi ----------
        if res == "produksi":
            if method == "GET":
                return ok(core.list_produksi(conn))
            if method == "POST":
                data = self._json_body()
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
                data = self._json_body()
                return ok(core.create_penjualan(conn, data, user=nama, user_id=user["id"]))

        # ---------- Pengeluaran ----------
        if res == "pengeluaran":
            if method == "GET":
                return ok(core.list_pengeluaran(conn))
            if method == "POST":
                data = self._json_body()
                return ok(core.create_pengeluaran(conn, data, user=nama, user_id=user["id"]))

        # ---------- Keuangan ----------
        if res == "keuangan":
            dari = q.get("dari", [date.today().replace(day=1).isoformat()])[0]
            sampai = q.get("sampai", [date.today().isoformat()])[0]
            if sub == "labarugi":
                return ok(core.laba_rugi(conn, dari, sampai))
            if sub == "kas":
                return ok(core.buku_kas(conn, dari, sampai))

        # ---------- Laporan ----------
        if res == "laporan":
            dari = q.get("dari", [date.today().replace(day=1).isoformat()])[0]
            sampai = q.get("sampai", [date.today().isoformat()])[0]
            if sub == "stok":
                return ok(core.laporan_stok(conn))
            if sub == "penjualan":
                return ok(core.laporan_penjualan(conn, dari, sampai))
            if sub == "produksi":
                return ok(core.laporan_produksi(conn, dari, sampai))

        if res == "audit":
            return ok(core.list_audit(conn))

        return err("Endpoint tidak ditemukan: " + res, 404)


def main():
    port = 8000
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    core.ensure_seed()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("=" * 62)
    print("  BakeERP siap dijalankan")
    print("  Buka browser: http://localhost:%d" % port)
    print("  Login: admin / admin123  (gudang / gudang123, kasir / kasir123)")
    print("=" * 62)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")


if __name__ == "__main__":
    main()
