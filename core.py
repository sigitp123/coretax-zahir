"""Logika inti Coretax Faktur Keluaran dari Zahir Online (zsql).
Dipakai bersama oleh aplikasi desktop (coretax_faktur_gui.py) dan versi web Vercel (app.py).
Modul ini tidak bergantung pada GUI apa pun."""
import io, os, re, json, base64, datetime as dt
from html.parser import HTMLParser
from collections import defaultdict
from xml.etree import ElementTree as ET
import requests
from openpyxl import Workbook
from openpyxl.styles import Font


HEADER_CTE = """WITH header AS (
    SELECT j.id, j.tanggal, j.nojurnal, j.contact_id,
           ROW_NUMBER() OVER (ORDER BY j.tanggal, j.nojurnal, j.id) AS baris
    FROM public.g_jurnal j
    WHERE j.tanggal BETWEEN '{D1}' AND '{D2}'
      AND j.kelompok = 4{CUST}
      AND EXISTS (SELECT 1 FROM sales s WHERE s.transaction_id = j.id)
)"""

# Kolom pembeli opsional: tidak semua versi/server Zahir punya kolom ini. Bila tidak ada, pakai nilai pengganti.
#   kunci = (tabel, kolom) -> (ekspresi bila ada, ekspresi pengganti bila tidak ada)
_TKU_FALLBACK = ("NULLIF(CASE WHEN LENGTH(REGEXP_REPLACE(COALESCE(c.tax_id_number, ''), '[^0-9]', '', 'g')) = 15"
                 " THEN '0' ELSE '' END || REGEXP_REPLACE(COALESCE(c.tax_id_number, ''), '[^0-9]', '', 'g'), '')"
                 " || '000000'")                                     # NPWP 16 digit + 000000; tanpa NPWP -> NULL (diisi app)
OPTIONAL_COLS = {
    ("sales", "coretax_transaction_code"): ("s.coretax_transaction_code", "NULL"),   # kosong -> Kode Trx default dari form
    ("cardfile", "identity_type"): ("c.identity_type", "'TIN'"),
    ("cardfile", "country_code"):  ("c.country_code", "'IDN'"),
    ("emails", "value"):           ("e.value", "''"),
    ("cardfile", "tku_id"):        ("c.tku_id", _TKU_FALLBACK),
}
Q_COLCHECK = """SELECT table_name, column_name FROM information_schema.columns
WHERE table_name IN ('cardfile', 'emails')
  AND column_name IN ('identity_type', 'country_code', 'tku_id', 'value', 'data_id');"""

# Probe per kolom: COUNT(...) WHERE FALSE selalu menghasilkan tepat 1 baris bila kolom ada, dan error / 0 baris
# bila tidak ada. Tidak bergantung pada server mengirim error HTTP (sebagian server zsql membalas 200 + pesan error).
COL_PROBES = {
    ("sales", "coretax_transaction_code"): "SELECT COUNT(coretax_transaction_code) AS ok FROM sales WHERE FALSE;",
    ("cardfile", "identity_type"): "SELECT COUNT(identity_type) AS ok FROM cardfile WHERE FALSE;",
    ("cardfile", "country_code"):  "SELECT COUNT(country_code) AS ok FROM cardfile WHERE FALSE;",
    ("cardfile", "tku_id"):        "SELECT COUNT(tku_id) AS ok FROM cardfile WHERE FALSE;",
    ("emails", "value"):           "SELECT COUNT(value) AS ok, COUNT(data_id) AS ok2 FROM emails WHERE FALSE;",
}
_COL_CACHE = {}


def detect_cols(f):
    """Set (tabel, kolom) opsional yang tersedia di database ini (di-cache per server+slug)."""
    key = (f.get("url"), f.get("slug"))
    if key in _COL_CACHE: return _COL_CACHE[key]
    avail = set()
    for k, q in COL_PROBES.items():
        try:
            if run(q, f): avail.add(k)
        except Exception:
            pass
    if ("emails", "value") in avail: avail.add(("emails", "data_id"))
    _COL_CACHE[key] = avail
    return avail


def build_q_faktur(avail=None):
    """Susun query Faktur. avail = set (tabel, kolom) yang ada; None = anggap semua ada."""
    has = lambda k: avail is None or k in avail
    x = {k: (v[0] if has(k) else v[1]) for k, v in OPTIONAL_COLS.items()}
    email_join = has(("emails", "value")) and has(("emails", "data_id"))
    if not email_join: x[("emails", "value")] = "''"
    # LATERAL ... LIMIT 1 mencegah baris faktur dobel bila kontak punya >1 alamat billing / email
    return HEADER_CTE + f"""
SELECT h.baris AS "BARIS", TO_CHAR(h.tanggal, 'MM/DD/YYYY') AS "Tanggal Faktur",
    'Normal' AS "Jenis Faktur", {x[("sales", "coretax_transaction_code")]} AS "Kode Transaksi",
    '' AS "Keterangan Tambahan", '' AS "Dokumen Pendukung", '' AS "Period Dok Pendukung",
    h.nojurnal AS "Referensi", '' AS "Cap Fasilitas", '' AS "ID TKU Penjual",
    c.tax_id_number AS "NPWP/NIK Pembeli", {x[("cardfile", "identity_type")]} AS "Jenis ID Pembeli",
    {x[("cardfile", "country_code")]} AS "Negara Pembeli", '' AS "Nomor Dokumen", c.perusahaan AS "Nama Pembeli",
    a.complete_address AS "Alamat Pembeli", {x[("emails", "value")]} AS "Email Pembeli",
    {x[("cardfile", "tku_id")]} AS "ID TKU Pembeli"
FROM header h
JOIN sales s ON s.transaction_id = h.id
LEFT JOIN cardfile c ON c.contact_id = h.contact_id
LEFT JOIN LATERAL (SELECT complete_address FROM addresses
                   WHERE data_id = c.contact_id AND type = 'billing' LIMIT 1) a ON TRUE""" + ("""
LEFT JOIN LATERAL (SELECT value FROM emails WHERE data_id = c.contact_id LIMIT 1) e ON TRUE""" if email_join else "") + """
ORDER BY h.baris;"""


Q_FAKTUR = build_q_faktur()

# ------------------------- referensi Coretax -------------------------
KODE_TRX = [
    ("01", "kepada selain Pemungut PPN"),
    ("02", "kepada Pemungut PPN Instansi Pemerintah"),
    ("03", "kepada Pemungut PPN selain Instansi Pemerintah"),
    ("04", "DPP Nilai Lain"),
    ("05", "Besaran tertentu"),
    ("06", "kepada orang pribadi pemegang paspor luar negeri (16E UU PPN)"),
    ("07", "penyerahan dengan fasilitas PPN atau PPN dan PPnBM tidak dipungut/ditanggung pemerintah"),
    ("08", "penyerahan dengan fasilitas dibebaskan PPN atau PPN dan PPnBM"),
    ("09", "penyerahan aktiva yang menurut tujuan semula tidak diperjualbelikan (16D UU PPN)"),
    ("10", "Penyerahan lainnya"),
]
KODE_FASILITAS = ("07", "08")      # Keterangan Tambahan & Cap Fasilitas hanya berlaku untuk kode ini
REF_HEADERS = {"trx": ("kode transaksi",)}
# Daftar dari tabel referensi template Faktur Coretax (screenshot user). Kode TD sama untuk 07 & 08; artinya tergantung kode transaksi.
KET_TAMBAHAN = {
    "07": [
        ("TD.00501", "untuk Kawasan Bebas"),
        ("TD.00502", "untuk Tempat Penimbunan Berikat"),
        ("TD.00503", "untuk Hibah dan Bantuan Luar Negeri"),
        ("TD.00504", "untuk Avtur"),
        ("TD.00505", "untuk Lainnya"),
        ("TD.00506", "untuk Kontraktor Perjanjian Karya Pengusahaan Pertambangan Batubara Generasi I"),
        ("TD.00507", "untuk Penyerahan bahan bakar minyak untuk Kapal Angkutan Laut"),
        ("TD.00508", "untuk Penyerahan jasa kena pajak terkait alat angkutan tertentu"),
        ("TD.00509", "untuk Penyerahan BKP Tertentu di KEK"),
        ("TD.00510", "untuk BKP tertentu yang bersifat strategis berupa anode slime"),
        ("TD.00511", "untuk Penyerahan alat angkutan tertentu dan/atau Jasa Kena Pajak terkait alat angkutan tertentu"),
        ("TD.00512", "untuk Penyerahan kepada Kontraktor Kerja Sama Migas yang mengikuti ketentuan Peraturan Pemerintah Nomor 27 Tahun 2017"),
        ("TD.00513", "Penyerahan Rumah Tapak dan Satuan Rumah Susun Rumah Susun Ditanggung Pemerintah Tahun Anggaran 2025"),
        ("TD.00514", "Penyerahan Jasa Sewa Ruangan atau Bangunan Kepada Pedagang Eceran yang Ditanggung Pemerintah Tahun Anggaran 2021"),
        ("TD.00515", "Penyerahan Barang dan Jasa Dalam Rangka Penanganan Pandemi COVID-19 (PMK 239/PMK. 03/2020)"),
        ("TD.00516", "Insentif PMK-103/PMK.010/2021 berupa PPN atas Penyerahan Rumah Tapak dan Unit Hunian Rumah Susun yang Ditanggung Pemerintah Tahun Anggaran 2021"),
        ("TD.00517", "Kawasan Ekonomi Khusus PP nomor 40 Tahun 2021"),
        ("TD.00518", "Kawasan Bebas PP nomor 41 Tahun 2021"),
        ("TD.00519", "Penyerahan Rumah Tapak dan Unit Hunian Rumah Susun yang Ditanggung Pemerintah Tahun Anggaran 2022"),
        ("TD.00520", "PPN Ditanggung Pemerintah dalam rangka Penanganan Pandemi Corona Virus"),
        ("TD.00521", "Penyerahan kepada Kontraktor Kerja Sama Migas yang mengikuti ketentuan Peraturan Pemerintah Nomor 53 Tahun 2017"),
        ("TD.00522", "BKP strategis tertentu dalam bentuk anode slime dan emas butiran"),
        ("TD.00523", "untuk penyerahan kertas koran dan/atau majalah"),
        ("TD.00524", "PPN Ditanggung Pemerintah"),
        ("TD.00525", "BKP dan JKP tertentu"),
        ("TD.00526", "Penyerahan BKP dan JKP di Ibu Kota Negara baru"),
        ("TD.00527", "Penyerahan kendaraan listrik berbasis baterai"),
        ("TD.00528", "Insentif Tambahan Penyerahan Rumah Tapak dan Satuan Rumah Susun Rumah Susun Ditanggung Pemerintah Tahun Anggaran 2025"),
        ("TD.00529", "PPN atas Penyerahan Hewan Khusus Tertentu Berupa Kuda serta Perlengkapan Pendukungnya Pemerintah Tahun Anggaran 2025"),
    ],
    "08": [
        ("TD.00501", "untuk BKP dan JKP Tertentu"),
        ("TD.00502", "untuk BKP Tertentu yang Bersifat Strategis"),
        ("TD.00503", "untuk Jasa Kebandarudaraan"),
        ("TD.00504", "untuk Lainnya"),
        ("TD.00505", "untuk BKP Tertentu yang Bersifat Strategis sesuai PP"),
        ("TD.00506", "untuk Penyerahan Jasa Kepelabuhan Tertentu untuk kegiatan angkutan laut Luar Negeri"),
        ("TD.00507", "untuk Penyerahan Air Bersih"),
        ("TD.00508", "Penyerahan BKP tertentu yang bersifat strategis"),
        ("TD.00509", "Penyerahan kepada Perwakilan Negara Asing dan Badan"),
        ("TD.00510", "BKP dan JKP tertentu"),
    ],
}
CAP_FASILITAS = {
    "07": [
        ("TD.01101", "Pajak Pertambahan Nilai Tidak Dipungut berdasarkan PP Nomor 10 Tahun 2012"),
        ("TD.01102", "Pajak Pertambahan Nilai atau Pajak Pertambahan Nilai dan Pajak Penjualan atas Barang Mewah tidak dipungut"),
        ("TD.01103", "Pajak Pertambahan Nilai dan Pajak Penjualan atas Barang Mewah Tidak Dipungut"),
        ("TD.01104", "Pajak Pertambahan Nilai Tidak Dipungut Sesuai PP Nomor 71 Tahun"),
        ("TD.01105", "(Tidak ada Cap)"),
        ("TD.01106", "PPN dan/atau PPnBM tidak dipungut berdasarkan PMK No. 194/PMK.03/2012"),
        ("TD.01107", "PPN Tidak Dipungut Berdasarkan PP Nomor 15 Tahun 2015"),
        ("TD.01108", "PPN Tidak Dipungut Berdasarkan PP Nomor 69 Tahun 2015"),
        ("TD.01109", "PPN Tidak Dipungut Berdasarkan PP Nomor 96 Tahun 2015"),
        ("TD.01110", "PPN Tidak Dipungut Berdasarkan PP Nomor 106 Tahun 2015"),
        ("TD.01111", "PPN Tidak Dipungut Sesuai PP Nomor 50 Tahun 2019"),
        ("TD.01112", "PPN atau PPN dan PPnBM Tidak Dipungut Sesuai Dengan PP Nomor 27 Tahun 2017"),
        ("TD.01113", "PPN DITANGGUNG PEMERINTAH EKSEKUSI PMK NOMOR 13 TAHUN 2025"),
        ("TD.01114", "PPN DITANGGUNG PEMERINTAH EKS PMK 102/PMK.010/2021"),
        ("TD.01115", "PPN DITANGGUNG PEMERINTAH EKS PMK 239/PMK.03/2020"),
        ("TD.01116", "Insentif PPN DITANGGUNG PEMERINTAH EKSEKUSI PMK NOMOR 103/PMK.010/2021"),
        ("TD.01117", "PAJAK PERTAMBAHAN NILAI TIDAK DIPUNGUT BERDASARKAN PP NOMOR 40 TAHUN 2021"),
        ("TD.01118", "PAJAK PERTAMBAHAN NILAI TIDAK DIPUNGUT BERDASARKAN PP NOMOR 41 TAHUN 2021"),
        ("TD.01119", "PPN DITANGGUNG PEMERINTAH EKS PMK 6/PMK.010/2022"),
        ("TD.01120", "PPN DITANGGUNG PEMERINTAH EKSEKUSI PMK NOMOR 226/PMK.03/2021"),
        ("TD.01121", "PPN ATAU PPN DAN PPnBM TIDAK DIPUNGUT SESUAI DENGAN PP NOMOR 53 TAHUN 2017"),
        ("TD.01122", "PPN tidak dipungut berdasarkan PP Nomor 70 Tahun 2021"),
        ("TD.01123", "PPN ditanggung Pemerintah Ex PMK-125/PMK.01/2020"),
        ("TD.01124", "(Tidak ada Cap)"),
        ("TD.01125", "PPN tidak dipungut berdasarkan PP Nomor 49 Tahun 2022"),
        ("TD.01126", "PPN tidak dipungut berdasarkan PP Nomor 12 Tahun 2023"),
        ("TD.01127", "PPN Ditanggung Pemerintah berdasarkan PMK Nomor 12 Tahun 2025"),
        ("TD.01128", "PPN DITANGGUNG PEMERINTAH EKSEKUSI PMK NOMOR 60 TAHUN 2025"),
    ],
    "08": [
        ("TD.01101", "PPN Dibebaskan Sesuai PP Nomor 146 Tahun 2000 Sebagaimana Telah Diubah Dengan PP Nomor 38 Tahun 2003"),
        ("TD.01102", "PPN Dibebaskan Sesuai PP Nomor 12 Tahun 2001 Sebagaimana Telah Beberapa Kali Diubah Terakhir Dengan PP Nomor 31 Tahun 2007"),
        ("TD.01103", "PPN dibebaskan berdasarkan Peraturan Pemerintah Nomor 28 Tahun 2009"),
        ("TD.01104", "(Tidak ada cap)"),
        ("TD.01105", "PPN Dibebaskan Sesuai Dengan PP Nomor 81 Tahun 2015"),
        ("TD.01106", "PPN Dibebaskan Berdasarkan PP Nomor 74 Tahun 2015"),
        ("TD.01107", "(tanpa cap)"),
        ("TD.01108", "PPN DIBEBASKAN SESUAI PP NOMOR 81 TAHUN 2015 SEBAGAIMANA TELAH DIUBAH DENGAN PP 48 TAHUN 2020"),
        ("TD.01109", "PPN DIBEBASKAN BERDASARKAN PP NOMOR 47 TAHUN 2020"),
        ("TD.01110", "PPN Dibebaskan berdasarkan PP Nomor 49 Tahun 2022"),
    ],
}
NONE_LABEL = "(Tidak ada)"


def ref_label(items, code):
    for c, d in items:
        if c == code: return f"{c} - {d}"
    return code or ""


def ref_labels(items):
    return [f"{c} - {d}" for c, d in items]


def ref_code(txt):
    """'TD.00501 - untuk ...' -> 'TD.00501'; teks ketik bebas tanpa ' - ' dipakai apa adanya."""
    if (txt or "").strip() == NONE_LABEL: return ""
    return (txt or "").split(" - ", 1)[0].strip()


def parse_ref_xlsx(path):
    """Baca referensi dari template Faktur Coretax DJP (.xlsx).
    - Kode Transaksi: blok berjudul 'Kode Transaksi' (kolom kode + uraian).
    - Keterangan Tambahan / Cap Fasilitas: kolom berjudul '... Kode Faktur 07' / '... 08'; kode TD diambil dari
      sel berpola TD.xxxxx di baris yang sama (satu kolom kode dipakai bersama oleh 07 dan 08).
    Kembalikan dict dengan kunci 'trx', 'ket07', 'ket08', 'cap07', 'cap08' (yang ditemukan saja)."""
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    out = {}
    td = re.compile(r"[A-Z]{2}\.\d{4,6}")
    pat = {"ket": re.compile(r"(?:keterangan|informasi)\s+tambahan.*\b(?P<k>07|08)\b", re.I),
           "cap": re.compile(r"cap\s+fasilitas.*\b(?P<k>07|08)\b", re.I)}

    def cell(row, c):
        return "" if c >= len(row) or row[c] is None else str(row[c]).strip()

    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        for ri, row in enumerate(grid):
            for ci in range(len(row)):
                v = cell(row, ci)
                if not v: continue
                if v.lower() == "kode transaksi" and "trx" not in out:          # blok Kode Transaksi
                    items = []
                    for r2 in grid[ri + 1:]:
                        a, b = cell(r2, ci), cell(r2, ci + 1)
                        if not a and not b:
                            if items: break
                            continue
                        if isinstance(r2[ci] if ci < len(r2) else None, (int, float)): a = f"{int(float(a)):02d}"
                        code = a or ref_code(b); desc = b or a
                        if desc.startswith(code): desc = desc[len(code):].lstrip(" -\t")
                        if re.fullmatch(r"\d{2}", code): items.append((code, desc))
                    if items: out["trx"] = items
                    continue
                for kind, rx in pat.items():                                     # kolom 07 / 08
                    m = rx.search(v)
                    if not m or f"{kind}{m.group('k')}" in out: continue
                    items, blank = [], 0
                    for r2 in grid[ri + 1:]:
                        desc = re.sub(r"^\d+\s*-\s*", "", cell(r2, ci)).strip()
                        code = next((cell(r2, c) for c in range(len(r2)) if td.fullmatch(cell(r2, c))), "")
                        if not desc:
                            blank += 1
                            if blank >= 3 and items: break
                            continue
                        blank = 0
                        if code: items.append((code, desc))                      # baris 'Tidak Ada' (tanpa kode) dilewati
                    if items: out[f"{kind}{m.group('k')}"] = items
    wb.close()
    return out


ALL_CUST = "(Semua customer)"
Q_CUSTOMERS = """SELECT DISTINCT c.contact_id AS id, c.perusahaan AS nama
FROM public.g_jurnal j JOIN cardfile c ON c.contact_id = j.contact_id
WHERE j.kelompok = 4 AND COALESCE(c.perusahaan, '') <> ''
ORDER BY c.perusahaan LIMIT 5000;"""


def cust_filter(f):
    """Filter customer untuk CTE header: daftar contact_id terpilih; kosong = semua customer."""
    ids = [str(x) for x in (f.get("cust_ids") or []) if re.fullmatch(r"[\w-]{1,64}", str(x))]   # id angka / UUID
    if not ids: return ""
    return "\n      AND j.contact_id::text IN (" + ", ".join(f"'{x}'" for x in ids) + ")"

Q_DETAIL = HEADER_CTE + """
SELECT h.baris AS "Baris",
    CASE WHEN i.product_id IS NOT NULL THEN 'A' ELSE 'B' END AS "Barang/Jasa",
    '' AS "Kode Barang Jasa", inv.deskripsi AS "Nama Barang Jasa",
    'UM.0033' AS "Nama Satuan Ukur", i.harga AS "Harga Satuan", i.jumlah AS "Jumlah Barang Jasa",
    COALESCE(i.discount, 0) AS "Total Diskon",
    ROUND((i.jumlah * i.harga)::numeric, 2) AS "DPP",
    ROUND((i.jumlah * i.harga / 12 * 11)::numeric, 2) AS "DPP Nilai Lain",
    12 AS "Tarif PPN",
    ROUND((i.jumlah * i.harga / 12 * 11 * 0.12)::numeric, 2) AS "PPN",
    0 AS "Tarif PPnBM", 0 AS "PPnBM"
FROM header h
JOIN itemsale i ON i.transaction_id = h.id
LEFT JOIN inventor inv ON inv.id = i.product_id
ORDER BY h.baris, i.id;"""

FAKTUR_COLS = ["BARIS", "Tanggal Faktur", "Jenis Faktur", "Kode Transaksi", "Keterangan Tambahan",
    "Dokumen Pendukung", "Period Dok Pendukung", "Referensi", "Cap Fasilitas", "ID TKU Penjual",
    "NPWP/NIK Pembeli", "Jenis ID Pembeli", "Negara Pembeli", "Nomor Dokumen", "Nama Pembeli",
    "Alamat Pembeli", "Email Pembeli", "ID TKU Pembeli"]
DETAIL_COLS = ["Baris", "Barang/Jasa", "Kode Barang Jasa", "Nama Barang Jasa", "Nama Satuan Ukur",
    "Harga Satuan", "Jumlah Barang Jasa", "Total Diskon", "DPP", "DPP Nilai Lain", "Tarif PPN",
    "PPN", "Tarif PPnBM", "PPnBM"]


def rows_from(o):
    """Cari list-of-dict di respons zsql (bentuk respons dibuat toleran)."""
    if isinstance(o, list):
        return o if o and isinstance(o[0], dict) else []
    if isinstance(o, dict):
        cols, data = o.get("columns") or o.get("fields"), o.get("rows") or o.get("data")
        if cols and isinstance(data, list) and data and isinstance(data[0], (list, tuple)):
            names = [c if isinstance(c, str) else c.get("name") for c in cols]
            return [dict(zip(names, r)) for r in data]
        for v in o.values():
            r = rows_from(v)
            if r:
                return r
    return []


class _T(HTMLParser):
    """Parser tabel HTML sederhana (untuk respons zsql dengan is_show_as_table)."""
    def __init__(self):
        super().__init__(); self.rows = []; self.row = None; self.cell = None
    def handle_starttag(self, tag, a):
        if tag == "tr": self.row = []
        elif tag in ("td", "th") and self.row is not None: self.cell = []
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip()); self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row = None
    def handle_data(self, d):
        if self.cell is not None: self.cell.append(d)


def parse_body(text):
    """Respons bisa JSON atau tabel HTML; dua-duanya didukung."""
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if data is not None:
        if isinstance(data, dict) and data.get("error"):
            e = data["error"]
            raise RuntimeError("zsql: " + str(e.get("message", e) if isinstance(e, dict) else e))
        rows = rows_from(data)
        if not rows and isinstance(data, dict):
            msg = data.get("message") or data.get("errors") or data.get("detail")
            if data.get("success") is False or data.get("status") in (False, "error", "failed") or (
                    msg and re.search(r"error|exist|syntax|invalid|gagal|failed", str(msg), re.I)):
                raise RuntimeError("zsql: " + str(msg or data)[:300])
        return rows
    p = _T(); p.feed(text)
    if p.rows:
        head = p.rows[0]
        return [dict(zip(head, r)) for r in p.rows[1:]]
    raise ValueError("Respons bukan JSON/tabel HTML: " + (text.strip()[:300] or "(kosong)"))


def run(query, f):
    h = {"Authorization": f"Bearer {f['token']}", "Slug": f["slug"]}
    last = None
    for u in (f["url"], f["url"] + "?is_show_as_table=true"):
        r = requests.post(u, headers=h, files={"query": (None, query)}, timeout=180)
        if r.status_code >= 400:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}"); continue
        r.encoding = r.encoding or "utf-8"
        try:
            return parse_body(r.text)
        except ValueError as ex:
            last = ex
    raise last


ID_TYPES = {"npwp": "TIN", "nik": "National ID", "paspor": "Passport", "passport": "Passport", "other": "Other ID", "other id": "Other ID"}
NUM_COLS = ["Harga Satuan", "Jumlah Barang Jasa", "Total Diskon", "DPP", "DPP Nilai Lain",
            "Tarif PPN", "PPN", "Tarif PPnBM", "PPnBM"]


def fix_types(rows, key, numeric=()):
    """Respons HTML berisi teks semua: kembalikan kolom baris & nominal ke angka."""
    for r in rows:
        for c in (key, *numeric):
            v = r.get(c)
            if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v.strip()):
                r[c] = int(v) if c == key else float(v)


def normalize_buyer(r):
    """Isi otomatis data pembeli yang kosong supaya sesuai format Coretax."""
    raw = str(r.get("NPWP/NIK Pembeli") or "").strip()
    jt = ID_TYPES.get(str(r.get("Jenis ID Pembeli") or "").strip().lower(), r.get("Jenis ID Pembeli")) or ""
    digits = re.sub(r"\D", "", raw)
    if jt in ("Passport", "Other ID") and raw:
        pass                                                   # dokumen non-NPWP: biarkan apa adanya
    else:
        if len(digits) == 15: digits = "0" + digits            # NPWP lama 15 digit -> 16 digit (awalan 0)
        if not digits or set(digits) == {"0"}:                 # tanpa NPWP
            raw, jt = "0" * 16, "Other ID"
        else:
            raw, jt = digits, jt or "TIN"
    r["NPWP/NIK Pembeli"], r["Jenis ID Pembeli"] = raw, jt
    if str(r.get("Negara Pembeli") or "").strip().upper() in ("", "ID"):
        r["Negara Pembeli"] = "IDN"
    r["Email Pembeli"] = r.get("Email Pembeli") or ""
    tku = re.sub(r"\D", "", str(r.get("ID TKU Pembeli") or ""))
    if len(tku) != 22 or set(tku) == {"0"}: r["ID TKU Pembeli"] = ""
    if not str(r.get("ID TKU Pembeli") or "").strip():         # ID TKU = TIN + 000000 (kantor pusat)
        r["ID TKU Pembeli"] = (raw if re.fullmatch(r"\d{16}", raw) else "0" * 16) + "000000"


def fetch(f):
    d1, d2 = f["d1"], f["d2"]
    for d in (d1, d2):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            raise ValueError("Tanggal harus YYYY-MM-DD")
    cf = cust_filter(f)
    sub = lambda q: q.replace("{D1}", d1).replace("{D2}", d2).replace("{CUST}", cf)
    avail = detect_cols(f)                                     # kolom opsional yang ada di database ini
    try: det = run(sub(Q_DETAIL), f)
    except Exception as ex: raise RuntimeError(f"Query DetailFaktur gagal: {ex}") from ex
    fak, err, cols = [], None, set(avail)
    for _ in range(len(OPTIONAL_COLS) + 2):
        try:
            fak = run(sub(build_q_faktur(cols)), f); err = None
        except Exception as ex:
            err = ex
            m = re.search(r'column\s+"?(?:\w+\.)?(\w+)"?\s+does not exist', str(ex), re.I)
            hit = {k for k in cols if m and k[1] == m.group(1).lower()}
            if hit:                                            # kolom yang disebut error -> pakai nilai pengganti
                cols -= hit; _COL_CACHE[(f.get("url"), f.get("slug"))] = set(cols); continue
            if cols: cols = set(); continue                    # error lain: coba versi tanpa kolom opsional
            break
        if fak or not det or not cols: break                   # header kosong padahal detail ada = gagal diam-diam
        cols = set()
    if not fak and det:
        raise RuntimeError("Query Faktur tidak menghasilkan data padahal DetailFaktur ada "
                           f"({len(det)} baris). Detail error: {err or 'server tidak mengirim pesan error'}")
    fix_types(fak, "BARIS"); fix_types(det, "Baris", NUM_COLS)
    tku = re.sub(r"\D", "", f["npwp"]) + "000000" if f["npwp"] else ""
    kd = re.sub(r"\D", "", f.get("kode_trx") or "") or "04"
    for r in fak:
        r["ID TKU Penjual"] = tku
        k = re.sub(r"\D", "", str(r.get("Kode Transaksi") or ""))
        r["Kode Transaksi"] = (k or kd).zfill(2)              # kosong -> default form; 4 -> 04
        if r["Kode Transaksi"] in KODE_FASILITAS:              # 07/08 wajib Keterangan Tambahan & Cap Fasilitas
            if not str(r.get("Keterangan Tambahan") or "").strip(): r["Keterangan Tambahan"] = f.get("ket_tambahan") or ""
            if not str(r.get("Cap Fasilitas") or "").strip(): r["Cap Fasilitas"] = f.get("cap_fasilitas") or ""
        else:                                                  # selain 07/08: kosongkan (Coretax menolak bila diisi)
            r["Keterangan Tambahan"] = r["Cap Fasilitas"] = ""
        normalize_buyer(r)
    for r in det:                                              # kode barang/jasa kosong -> kode default dari form
        if not str(r.get("Kode Barang Jasa") or "").strip():
            r["Kode Barang Jasa"] = (f.get("kode_a") if r.get("Barang/Jasa") == "A" else f.get("kode_b")) or ""
            r["_kode_default"] = bool(r["Kode Barang Jasa"])
    return fak, det


def validate(fak, det):
    w = []
    bad = [r["BARIS"] for r in fak if r.get("Jenis ID Pembeli") not in ("Passport", "Other ID")
           and len(re.sub(r"\D", "", str(r.get("NPWP/NIK Pembeli") or ""))) != 16]
    if bad: w.append(f"NPWP/NIK pembeli bukan 16 digit di baris: {bad[:15]}")
    nocode = [r["Baris"] for r in det if not r.get("Kode Barang Jasa")]
    if nocode: w.append(f"{len(nocode)} detail tanpa Kode Barang Jasa (wajib di Coretax)")
    notrx = [r["BARIS"] for r in fak if not r.get("Kode Transaksi")]
    if notrx: w.append(f"Kode Transaksi kosong di baris: {notrx[:15]}")
    fas = [r["BARIS"] for r in fak if r.get("Kode Transaksi") in KODE_FASILITAS
           and not (r.get("Keterangan Tambahan") and r.get("Cap Fasilitas"))]
    if fas: w.append(f"Kode transaksi 07/08 tanpa Keterangan Tambahan / Cap Fasilitas di baris: {fas[:15]}")
    n0 = sum(1 for r in fak if set(str(r.get("NPWP/NIK Pembeli") or "x")) == {"0"})
    if n0: w.append(f"{n0} faktur tanpa NPWP pembeli: diisi 0000000000000000 dan Jenis ID 'Other ID'")
    nd = sum(1 for r in det if r.get("_kode_default"))
    if nd: w.append(f"{nd} detail memakai Kode Barang/Jasa default - pastikan sesuai referensi Coretax")
    if not fak: w.append("Tidak ada faktur pada rentang tanggal ini")
    return w


def build_xlsx(fak, det, npwp):
    wb = Workbook()
    ws = wb.active; ws.title = "Faktur"
    ws.append(["NPWP Penjual", npwp]); ws.append([])
    ws.append(FAKTUR_COLS)
    for r in fak: ws.append([r.get(c) for c in FAKTUR_COLS])
    ws.append(["END"])
    wd = wb.create_sheet("DetailFaktur")
    wd.append(DETAIL_COLS)
    for r in det: wd.append([r.get(c) for c in DETAIL_COLS])
    wd.append(["END"])
    for s in (ws, wd):
        for c in s[3 if s is ws else 1]: c.font = Font(name="Arial", bold=True)
        for col in s.columns: s.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf


def num(x):
    try: return f"{float(x):.2f}".rstrip("0").rstrip(".") or "0"
    except (TypeError, ValueError): return "0"


def build_xml(fak, det, npwp):
    root = ET.Element("TaxInvoiceBulk", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:noNamespaceSchemaLocation": "TaxInvoice.xsd"})
    ET.SubElement(root, "TIN").text = re.sub(r"\D", "", npwp)
    lst = ET.SubElement(root, "ListOfTaxInvoice")
    items = defaultdict(list)
    for d in det: items[d["Baris"]].append(d)
    for r in fak:
        t = ET.SubElement(lst, "TaxInvoice")
        tgl = dt.datetime.strptime(r["Tanggal Faktur"], "%m/%d/%Y").strftime("%Y-%m-%d")
        for tag, val in [("TaxInvoiceDate", tgl), ("TaxInvoiceOpt", r["Jenis Faktur"]),
                ("TrxCode", r["Kode Transaksi"]), ("AddInfo", r["Keterangan Tambahan"]),
                ("CustomDoc", r["Dokumen Pendukung"]), ("CustomDocMonthYear", r["Period Dok Pendukung"]),
                ("RefDesc", r["Referensi"]), ("FacilityStamp", r["Cap Fasilitas"]),
                ("SellerIDTKU", r["ID TKU Penjual"]), ("BuyerTin", r["NPWP/NIK Pembeli"]),
                ("BuyerDocument", r["Jenis ID Pembeli"]), ("BuyerCountry", r["Negara Pembeli"]),
                ("BuyerDocumentNumber", r["Nomor Dokumen"]), ("BuyerName", r["Nama Pembeli"]),
                ("BuyerAdress", r["Alamat Pembeli"]), ("BuyerEmail", r["Email Pembeli"]),
                ("BuyerIDTKU", r["ID TKU Pembeli"])]:
            ET.SubElement(t, tag).text = "" if val is None else str(val)
        g = ET.SubElement(t, "ListOfGoodService")
        for d in items[r["BARIS"]]:
            x = ET.SubElement(g, "GoodService")
            for tag, val in [("Opt", d["Barang/Jasa"]), ("Code", d["Kode Barang Jasa"]),
                    ("Name", d["Nama Barang Jasa"]), ("Unit", d["Nama Satuan Ukur"]),
                    ("Price", num(d["Harga Satuan"])), ("Qty", num(d["Jumlah Barang Jasa"])),
                    ("TotalDiscount", num(d["Total Diskon"])), ("TaxBase", num(d["DPP"])),
                    ("OtherTaxBase", num(d["DPP Nilai Lain"])), ("VATRate", num(d["Tarif PPN"])),
                    ("VAT", num(d["PPN"])), ("STLGRate", num(d["Tarif PPnBM"])), ("STLG", num(d["PPnBM"]))]:
                ET.SubElement(x, tag).text = "" if val is None else str(val)
    ET.indent(root)
    return io.BytesIO(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def _base_domain(host):
    """'go.zahironline.com' -> 'zahironline.com'; 'erp.pt-abc.co.id' -> 'pt-abc.co.id'; IP/localhost apa adanya."""
    h = host.split(":")[0].lower()
    if "." not in h or re.fullmatch(r"[\d.]+", h): return h
    parts = h.split(".")
    return ".".join(parts[1:]) if len(parts) > 2 else h


def _find_slugs(x, host=None):
    """Cari slug database (subdomain dari domain server, mis. *.zahironline.com) di struktur JSON."""
    host = (host or "go.zahironline.com").split(":")[0].lower()
    doms = {_base_domain(host), "zahironline.com", "zahirerp.com"}
    pat = re.compile(r"[\w.-]+\.(?:" + "|".join(re.escape(d) for d in doms) + ")")
    def walk(o):
        if isinstance(o, str):
            s = o.strip().lower()
            return [s] if pat.fullmatch(s) and s != host and not s.startswith("go.") else []
        if isinstance(o, dict): return [z for v in o.values() for z in walk(v)]
        if isinstance(o, list): return [z for v in o for z in walk(v)]
        return []
    return walk(x)


# (endpoint, gaya parameter). v3 = go.zahironline.com; v2 = server ERP/on-premise (mis. demo.zahirerp.com)
COMPANY_ENDPOINTS = [("/api/v3/user_companies", "v3"), ("/api/v2/user_companies", "v2"),
                     ("/api/v2/companies", "v2"), ("/api/v1/user_companies", "v2")]
INACTIVE = "Not Active,Expired,Suspend"


def _company_params(style, page):
    if style == "v3":
        return {"$page": page, "$per_page": 20, "$sort": "company.name",
                "company.membership.status.$nin": INACTIVE,
                "company.membership.variant.id.$nin": "21,25,150,151"}
    return {"page": page, "per_page": 20, "company[membership][status][$nin]": INACTIVE,
            "isort[company.name]": 1}


def _companies_from(items, host, out, seen):
    for it in items:
        if not isinstance(it, dict): continue
        slugs = _find_slugs(it, host) or [s for s in [_find_key(it, "slug")] if s]
        if not slugs or slugs[0] in seen: continue
        co = it.get("company") if isinstance(it.get("company"), dict) else it
        seen.add(slugs[0]); out.append((str(co.get("name") or slugs[0]), slugs[0]))


def list_companies(f, me=None):
    """Ambil daftar database milik user. Tiap server bisa beda versi API, jadi beberapa endpoint dicoba berurutan;
    terakhir coba cari slug di respons login (/me). Kembalikan (daftar, catatan_error); daftar kosong = isi slug manual."""
    h = {"Authorization": f"Bearer {f['token']}", "Accept": "application/json", "Content-Language": "id"}
    root = f"{f['protocol'].lower()}://{f['server']}"
    out, seen, notes = [], set(), []
    for ep, style in COMPANY_ENDPOINTS:
        try:
            for page in range(1, 51):
                r = requests.get(root + ep, headers=h, timeout=60, params=_company_params(style, page))
                if r.status_code >= 400:
                    raise RuntimeError(f"HTTP {r.status_code}")
                try: data = r.json()
                except ValueError: raise RuntimeError("respons bukan JSON")
                items = rows_from(data) or (data if isinstance(data, list) else [data])
                n = len(out); _companies_from(items, f["server"], out, seen)
                if len(items) < 20 or len(out) == n: break
        except (RuntimeError, requests.RequestException) as ex:
            notes.append(f"{ep}: {_short(ex)}")
        if out: return out, ""
        if notes and not notes[-1].startswith(ep):                   # endpoint ada (bukan error) tapi slug tak dikenali
            notes.append(f"{ep}: respons terbaca, slug tidak dikenali: {r.text[:150]}")
    if me is not None:
        _companies_from([me] if isinstance(me, dict) else me, f["server"], out, seen)
        if out: return out, ""
    return out, "; ".join(notes) or "tidak ada database di respons"


SERVER = "go.zahironline.com"
BASE = "https://" + SERVER
# Header "client" = base64(client_id:client_secret) milik aplikasi web go.zahironline.com (ZahirOnline-GO).
# Ini rahasia aplikasi: jangan bagikan exe ke luar tim internal.
CLIENT_B64 = os.environ.get("ZAHIR_CLIENT_B64") or "NjljYjNlYTMxN2EzMmM0ZTYxNDNlNjY1ZmRiMjBiMTQ6MTAyNmQ1MWQyZTkwZjg="


def _find_key(o, key):
    if isinstance(o, dict):
        if isinstance(o.get(key), str): return o[key]
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            r = _find_key(v, key)
            if r: return r
    return None


def parse_server(txt):
    """'go.zahironline.com' / 'https://x.com/' -> ('https', 'x.com')"""
    t = (txt or "").strip() or SERVER
    proto = "http" if t.lower().startswith("http://") else "https"
    host = re.sub(r"^https?://", "", t, flags=re.I).split("/")[0].strip()
    return proto, host or SERVER


def login(email, password, base=BASE, client=CLIENT_B64):
    """Login = GET /api/v2/me dengan Basic auth (email:password) + header client; respons memuat token."""
    basic = base64.b64encode(f"{email}:{password}".encode()).decode()
    r = requests.get(base + "/api/v2/me", timeout=60, headers={
        "Authorization": "Basic " + basic, "client": client,
        "Accept": "application/json", "Content-Language": "id"})
    if r.status_code >= 400:
        raise RuntimeError(f"Login gagal (HTTP {r.status_code}): {r.text[:200]}")
    data = r.json()
    tok = _find_key(data, "access_token") or _find_key(data, "token")
    if not tok:
        raise ValueError("Token tidak ditemukan di respons login. Potongan respons: " + r.text[:200])
    return tok, data


def friendly(msg):
    msg = str(msg)
    if "403" in msg:
        msg += ("\n\nAkun yang dipakai login belum punya izin membaca data (zsql) di database ini."
                "\nKlik 'Tes Akses' untuk melihat tabel mana yang ditolak, atau login dengan akun yang punya izin.")
    elif "401" in msg:
        msg += "\n\nSesi/token ditolak. Klik Logout lalu login ulang."
    return msg


def _short(ex):
    t = str(ex); m = re.search(r'HTTP (\d+).*?"message":"([^"]+)"', t)
    return f"HTTP {m.group(1)} - {m.group(2)}" if m else t[:200]


DIAG_TABLES = ["g_jurnal", "sales", "itemsale", "cardfile", "addresses", "emails", "inventor"]


def diagnose(f):
    """Uji baca tiap tabel yang dipakai query faktur -> [(nama, ok, detail)]."""
    tests = [("koneksi dasar", "SELECT current_database() AS db")] + \
            [(t, f"SELECT 1 AS ok FROM {t} LIMIT 1") for t in DIAG_TABLES]
    out = []
    for name, q in tests:
        try: run(q, f); out.append((name, True, "OK"))
        except Exception as ex: out.append((name, False, _short(ex)))
    return out


# ----------------------------- REGISTRASI -----------------------------
# Kode registrasi = tanda tangan Ed25519 atas (slug database + tanggal kedaluwarsa), dibuat dengan license_tool.py.
# Aplikasi hanya menyimpan KUNCI PUBLIK, jadi kode tidak bisa dipalsukan dari isi exe.
PUBLIC_KEY_B64 = "TkW1khRetianMcfQ2DT1BlVzE1lu1zO6t6nwdlSxnXc="            # tempel hasil `python license_tool.py keygen`
FIREBASE_PROJECT = "zahir-plugin"
FIREBASE_API_KEY = ""          # Web API key project Firebase (isi untuk mengaktifkan cek online)
LICENSE_COLLECTION = "coretax_licenses"   # dokumen per slug: {expiry: "YYYY-MM-DD", revoked: false}
EPOCH = dt.date(2020, 1, 1)


def _sig_message(slug, expiry):
    return f"CORETAX1|{slug.strip().lower()}|{expiry.isoformat()}".encode()


def verify_code(code, slug):
    """Kembalikan tanggal kedaluwarsa bila kode sah untuk slug ini; ValueError bila tidak."""
    if not PUBLIC_KEY_B64:
        raise RuntimeError("PUBLIC_KEY_B64 belum diisi di coretax_faktur_gui.py")
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    raw = re.sub(r"[\s-]", "", code or "").upper()
    if raw.startswith("CTX1"): raw = raw[4:]
    try:
        blob = base64.b32decode(raw + "=" * (-len(raw) % 8))
    except Exception:
        raise ValueError("format kode salah")
    if len(blob) != 66: raise ValueError("format kode salah")
    expiry = EPOCH + dt.timedelta(days=int.from_bytes(blob[:2], "big"))
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64)).verify(blob[2:], _sig_message(slug, expiry))
    except InvalidSignature:
        raise ValueError("kode tidak cocok dengan database ini")
    return expiry


def online_status(slug):
    """Cek Firestore. None = tidak dikonfigurasi/tidak terjangkau; {} = tidak ada rekaman."""
    if not FIREBASE_API_KEY: return None
    url = (f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT}/databases/(default)"
           f"/documents/{LICENSE_COLLECTION}/{slug}")
    try: r = requests.get(url, params={"key": FIREBASE_API_KEY}, timeout=10)
    except requests.RequestException: return None
    if r.status_code == 404: return {}
    if r.status_code != 200: return None
    f = r.json().get("fields", {})
    return {"expiry": f.get("expiry", {}).get("stringValue"), "revoked": f.get("revoked", {}).get("booleanValue", False)}


def license_state(slug, code):
    """(ok, pesan, tanggal_kedaluwarsa). Sah bila kode offline ATAU rekaman online masih berlaku; admin bisa mencabut/memperpanjang online."""
    exp, bad = None, ""
    if code and code.strip():
        try: exp = verify_code(code, slug)
        except ValueError as ex: bad = f"kode tidak valid ({ex})"
    on = online_status(slug)
    if on and on.get("revoked"):
        return False, "dicabut oleh admin", None
    if on and on.get("expiry"):
        try:
            oe = dt.date.fromisoformat(on["expiry"])
            if exp is None or oe > exp: exp = oe
        except ValueError: pass
    if exp is None:
        return False, bad or "belum teregistrasi", None
    left = (exp - dt.date.today()).days
    if left < 0: return False, f"kedaluwarsa sejak {exp:%d-%m-%Y}", None
    return True, f"aktif s/d {exp:%d-%m-%Y}" + (f" (sisa {left} hari)" if left <= 14 else ""), exp
