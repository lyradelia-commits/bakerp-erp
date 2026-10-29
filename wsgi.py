"""
BakeERP - Pintu masuk WSGI untuk hosting (PythonAnywhere, Render, dll.)
=======================================================================

Hosting gratis umumnya TIDAK menjalankan `http.server` mentah, melainkan
memanggil aplikasi lewat antarmuka WSGI. Berkas ini menjembatani keduanya:
semua permintaan diteruskan ke `app.handle()` yang sama dengan mode lokal,
sehingga tidak ada logika yang berbeda antara "di laptop" dan "di internet".

Cara pakai di PythonAnywhere:
  1. Upload/clone proyek ini ke  ~/bakerp-erp
  2. Web tab -> Add a new web app -> Manual configuration -> Python 3.10
  3. Isi "Source code" dengan  /home/<user>/bakerp-erp
  4. Klik berkas WSGI configuration file, ganti seluruh isinya dengan:

        import sys
        sys.path.insert(0, '/home/<user>/bakerp-erp')
        from wsgi import application

  5. Reload web app.

Uji lokal (tanpa hosting):
    python wsgi.py --port 8090
"""

import os
import sys
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app as bakerp          # noqa: E402
import core                   # noqa: E402

# Siapkan basis data sekali saat modul dimuat (bukan tiap permintaan).
core.ensure_seed()


def application(environ, start_response):
    """Entry point WSGI standar."""
    method = environ.get("REQUEST_METHOD", "GET").upper()

    # Path & query
    path = environ.get("PATH_INFO") or "/"
    script = environ.get("SCRIPT_NAME") or ""
    if script and path.startswith(script):
        path = path[len(script):] or "/"
    query = environ.get("QUERY_STRING") or ""

    # Header -> dict (Authorization yang kita perlukan)
    headers = {}
    for k, v in environ.items():
        if k.startswith("HTTP_"):
            nama = k[5:].replace("_", "-").title()
            headers[nama] = v
    if environ.get("CONTENT_TYPE"):
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if environ.get("CONTENT_LENGTH"):
        headers["Content-Length"] = environ["CONTENT_LENGTH"]

    # Body
    panjang = 0
    try:
        panjang = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        panjang = 0
    raw = environ["wsgi.input"].read(panjang) if panjang else b""

    status, payload, content_type = bakerp.handle(method, path, query, headers, raw)

    if isinstance(payload, (dict, list)):
        import json
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    elif isinstance(payload, str):
        body = payload.encode("utf-8")
    else:
        body = payload or b""

    # Kode status + keterangan standar
    alasan = {
        200: "OK", 201: "Created", 204: "No Content",
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
        404: "Not Found", 405: "Method Not Allowed", 500: "Internal Server Error",
    }.get(status, "OK")

    start_response(
        f"{status} {alasan}",
        [
            ("Content-Type", content_type),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ],
    )
    return [body]


def main():
    """Server WSGI sederhana untuk pengujian lokal."""
    from wsgiref.simple_server import make_server, WSGIRequestHandler

    port = 8090
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])

    class Sunyi(WSGIRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    print("=" * 62)
    print("  BakeERP (mode WSGI) - untuk meniru lingkungan hosting")
    print("  Buka: http://127.0.0.1:%d" % port)
    print("  Basis data: %s" % core.db.deskripsi())
    print("=" * 62)
    with make_server("127.0.0.1", port, application, handler_class=Sunyi) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer dihentikan.")


if __name__ == "__main__":
    main()
