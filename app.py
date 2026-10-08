"""Zahir Coretax - versi web untuk Vercel (Flask).

Semua logika (query, normalisasi, export, lisensi) memakai core.py yang sama dengan aplikasi desktop.
Browser menyimpan token Zahir di sessionStorage dan mengirimnya di header `Authorization: Bearer <token>`;
password tidak pernah disimpan. Client OAuth Zahir (CLIENT_B64) hanya ada di server.
"""
import datetime as dt
import ipaddress
import os
import re

from flask import Flask, jsonify, request, send_file, send_from_directory, redirect, abort
from werkzeug.exceptions import HTTPException

import core

app = Flask(__name__)
PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024          # unggah template referensi maks 5 MB

# Server Zahir yang boleh dihubungi dari Vercel (mencegah fungsi dipakai untuk memanggil host sembarang).
# Isi env ALLOWED_SERVERS dengan akhiran domain dipisah koma, mis. "zahironline.com,zahirerp.com,erp.perusahaan.co.id".
ALLOWED = [s.strip().lower().lstrip(".") for s in
           os.environ.get("ALLOWED_SERVERS", "zahironline.com,zahirerp.com").split(",") if s.strip()]
if os.environ.get("FIREBASE_API_KEY"):
    core.FIREBASE_API_KEY = os.environ["FIREBASE_API_KEY"]
CLIENTS = {}                                                  # client khusus per host: env ZAHIR_CLIENT_<HOST>
for k, v in os.environ.items():
    if k.startswith("ZAHIR_CLIENT_") and k != "ZAHIR_CLIENT_B64":
        CLIENTS[k[len("ZAHIR_CLIENT_"):].lower().replace("_", ".")] = v


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg); self.code = code


@app.errorhandler(ApiError)
def _api_error(ex):
    return jsonify(error=str(ex)), ex.code


@app.errorhandler(Exception)
def _any_error(ex):
    if isinstance(ex, HTTPException):
        return jsonify(error=ex.description), ex.code
    msg = core.friendly(f"{type(ex).__name__}: {ex}")
    code = 401 if "HTTP 401" in msg else 403 if "HTTP 403" in msg else 502
    return jsonify(error=msg), code


def server_of(raw):
    """Validasi alamat server dari browser -> (protocol, host)."""
    proto, host = core.parse_server(raw)
    name = host.split(":")[0].lower()
    try:
        ipaddress.ip_address(name); raise ApiError("Alamat IP tidak diizinkan di versi web. Gunakan aplikasi desktop.")
    except ValueError:
        pass
    if name in ("localhost",) or not any(name == s or name.endswith("." + s) for s in ALLOWED):
        raise ApiError(f"Server {name} tidak ada di daftar yang diizinkan ({', '.join(ALLOWED)}). "
                       "Tambahkan lewat env ALLOWED_SERVERS di Vercel.")
    if proto != "https":
        raise ApiError("Versi web hanya mendukung server HTTPS.")
    return proto, host


def body():
    return request.get_json(silent=True) or {}


def conn(b):
    """Data koneksi zsql dari header token + body (server, slug)."""
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not tok: raise ApiError("Sesi berakhir. Silakan login ulang.", 401)
    slug = str(b.get("slug") or "").strip().lower()
    if not re.fullmatch(r"[\w.-]{3,120}", slug): raise ApiError("Database belum dipilih.")
    proto, host = server_of(b.get("server"))
    return {"token": tok, "slug": slug, "protocol": proto.upper(), "server": host, "url": f"{proto}://{host}/api/v2/zsql"}


def need_license(slug, code):
    ok, msg, exp = core.license_state(slug, code)
    if not ok: raise ApiError(f"Database ini {msg}. Masukkan kode registrasi dari admin.", 403)
    return exp


def job(b):
    """Parameter fetch() dari form web."""
    f = conn(b)
    need_license(f["slug"], b.get("license"))
    ids = [str(x) for x in (b.get("cust_ids") or [])][:2000]
    f.update(d1=str(b.get("d1") or ""), d2=str(b.get("d2") or ""), npwp=str(b.get("npwp") or ""),
             kode_a=str(b.get("kode_a") or ""), kode_b=str(b.get("kode_b") or ""),
             kode_trx=str(b.get("kode_trx") or "04"), ket_tambahan=str(b.get("ket") or ""),
             cap_fasilitas=str(b.get("cap") or ""), cust_ids=ids)
    return f


def clean(rows):
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


# ------------------------------------------------------------------ halaman
@app.get("/")
def home():
    path = os.path.join(PUBLIC, "index.html")
    if os.path.exists(path):
        return send_file(path)
    return redirect("/index.html")


@app.get("/<path:name>")
def public_file(name):
    """Untuk jalan lokal (python app.py). Di Vercel, folder public/ dilayani CDN lebih dulu."""
    if name.startswith("api/") or not os.path.isfile(os.path.join(PUBLIC, name)): abort(404)
    return send_from_directory(PUBLIC, name)


# ------------------------------------------------------------------ API
@app.get("/api/config")
def config():
    return jsonify(default_server=core.SERVER, allowed=ALLOWED, kode_trx=core.KODE_TRX,
                   ket=core.KET_TAMBAHAN, cap=core.CAP_FASILITAS, fasilitas=list(core.KODE_FASILITAS),
                   faktur_cols=core.FAKTUR_COLS, detail_cols=core.DETAIL_COLS, num_cols=core.NUM_COLS)


@app.post("/api/login")
def login():
    b = body()
    email, pw = str(b.get("email") or "").strip(), str(b.get("password") or "")
    if not email or not pw: raise ApiError("Email dan password wajib diisi.")
    proto, host = server_of(b.get("server"))
    client = CLIENTS.get(host.split(":")[0].lower(), core.CLIENT_B64)
    tok, me = core.login(email, pw, f"{proto}://{host}", client)
    dbs, note = core.list_companies({"token": tok, "protocol": proto, "server": host}, me)
    return jsonify(token=tok, server=host, databases=[{"name": n, "slug": s} for n, s in dbs], note=note)


@app.post("/api/connect")
def connect():
    b = body(); f = conn(b)
    core.run("SELECT 1 AS ok", f)
    ok, msg, exp = core.license_state(f["slug"], b.get("license"))
    return jsonify(slug=f["slug"], license={"ok": ok, "message": msg, "expiry": exp.isoformat() if exp else None})


@app.post("/api/license")
def license_check():
    b = body()
    slug = str(b.get("slug") or "").strip().lower()
    ok, msg, exp = core.license_state(slug, b.get("code"))
    return jsonify(ok=ok, message=msg, expiry=exp.isoformat() if exp else None)


@app.post("/api/customers")
def customers():
    f = conn(body())
    seen, out = set(), []
    for r in core.run(core.Q_CUSTOMERS, f):
        n = str(r.get("nama") or "").strip()
        if n and n not in seen: seen.add(n); out.append({"id": str(r.get("id")), "name": n})
    return jsonify(customers=out)


@app.post("/api/diagnose")
def diagnose():
    return jsonify(results=[{"name": n, "ok": ok, "detail": d} for n, ok, d in core.diagnose(conn(body()))])


@app.post("/api/preview")
def preview():
    f = job(body())
    fak, det = core.fetch(f)
    num = lambda x: float(x) if isinstance(x, (int, float)) else 0.0
    return jsonify(faktur=clean(fak), detail=clean(det), warnings=core.validate(fak, det),
                   totals={"faktur": len(fak), "detail": len(det),
                           "dpp": sum(num(r.get("DPP")) for r in det), "ppn": sum(num(r.get("PPN")) for r in det)})


@app.post("/api/export/<fmt>")
def export(fmt):
    if fmt not in ("xlsx", "xml"): raise ApiError("Format tidak dikenal.", 404)
    b = body(); f = job(b)
    if not re.fullmatch(r"\d{16}", re.sub(r"\D", "", f["npwp"])): raise ApiError("Isi NPWP Penjual 16 digit.")
    fak, det = core.fetch(f)
    if not fak: raise ApiError("Tidak ada faktur pada periode ini, file tidak dibuat.")
    buf = core.build_xlsx(fak, det, f["npwp"]) if fmt == "xlsx" else core.build_xml(fak, det, f["npwp"])
    name = f"Faktur_Keluaran_Coretax_{f['d1']}_{f['d2']}.{fmt}"
    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "application/xml")
    return send_file(buf, mimetype=mime, as_attachment=True, download_name=name)


@app.post("/api/refs/parse")
def refs_parse():
    up = request.files.get("file")
    if not up: raise ApiError("Pilih file template .xlsx.")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        up.save(tmp.name)
        got = core.parse_ref_xlsx(tmp.name)
    if not got: raise ApiError("Tabel Kode Transaksi / Keterangan Tambahan / Cap Fasilitas tidak ditemukan di file ini.")
    return jsonify(refs={k: [list(x) for x in v] for k, v in got.items()})


@app.get("/api/health")
def health():
    return jsonify(ok=True, time=dt.datetime.utcnow().isoformat() + "Z")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
