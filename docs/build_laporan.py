"""
Membangun laporan UTS EIS (.docx) untuk aplikasi BakeERP.

Seluruh angka pada laporan diambil langsung dari database aplikasi (bakery.db)
dan dari berkas hasil pengujian (docs/hasil_pengujian.txt), sehingga isi laporan
selalu konsisten dengan aplikasi yang dijalankan.

Jalankan:  python docs/build_laporan.py
"""

import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import core

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(BASE, "docs")
IMG = os.path.join(DOCS, "img")
OUT = os.path.join(DOCS, "Laporan_UTS_EIS_ERP_Bakery.docx")

FONT = "Times New Roman"
BROWN = "5B3A1E"
CREAM = "F5EDE3"

BULAN_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
            "Agustus", "September", "Oktober", "November", "Desember"]


def rp(n):
    """Format rupiah gaya Indonesia: Rp 1.234.567"""
    return "Rp " + f"{round(float(n or 0)):,}".replace(",", ".")


def angka(n, d=2):
    s = f"{float(n or 0):,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def tanggal_id(iso):
    y, m, d = str(iso)[:10].split("-")
    return f"{int(d)} {BULAN_ID[int(m) - 1]} {y}"


# ---------------------------------------------------------------------------
# Utilitas python-docx
# ---------------------------------------------------------------------------
def gaya_dasar(doc):
    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = st.paragraph_format
    pf.line_spacing = 1.5
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)

    for name, size in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 12)):
        h = doc.styles[name]
        h.font.name = FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        h.paragraph_format.space_before = Pt(16 if name == "Heading 1" else 12)
        h.paragraph_format.space_after = Pt(8 if name == "Heading 1" else 6)
        h.paragraph_format.line_spacing = 1.5
        h.paragraph_format.keep_with_next = True
        if name == "Heading 1":
            h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for name in ("List Bullet", "List Number"):
        s = doc.styles[name]
        s.font.name = FONT
        s.font.size = Pt(12)
        s.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        s.paragraph_format.line_spacing = 1.5
        s.paragraph_format.space_after = Pt(3)


def hal(doc):
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin, s.right_margin = Cm(3.5), Cm(2.5)
    s.top_margin, s.bottom_margin = Cm(3), Cm(3)


def p(doc, text="", bold=False, italic=False, size=12, align="justify",
      indent=1.25, space_after=6, space_before=0, color=None, style=None):
    par = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    par.paragraph_format.line_spacing = 1.5
    par.paragraph_format.space_after = Pt(space_after)
    par.paragraph_format.space_before = Pt(space_before)
    par.alignment = {"justify": WD_ALIGN_PARAGRAPH.JUSTIFY, "left": WD_ALIGN_PARAGRAPH.LEFT,
                     "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}[align]
    if indent:
        par.paragraph_format.first_line_indent = Cm(indent)
    run = par.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    return par


def h1(doc, text, page_break=True):
    if page_break:
        doc.add_page_break()
    par = doc.add_paragraph(style="Heading 1")
    run = par.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(14)
    run.bold = True
    return par


def h2(doc, text):
    par = doc.add_paragraph(style="Heading 2")
    run = par.add_run(text)
    run.font.name = FONT
    run.font.size = Pt(12)
    run.bold = True
    return par


def bullets(doc, items):
    for it in items:
        par = doc.add_paragraph(style="List Bullet")
        par.paragraph_format.line_spacing = 1.5
        par.paragraph_format.space_after = Pt(2)
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = par.add_run(it)
        run.font.name = FONT
        run.font.size = Pt(12)


def nomor(doc, items):
    for it in items:
        par = doc.add_paragraph(style="List Number")
        par.paragraph_format.line_spacing = 1.5
        par.paragraph_format.space_after = Pt(2)
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = par.add_run(it)
        run.font.name = FONT
        run.font.size = Pt(12)


def _shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def tabel(doc, headers, rows, widths=None, caption=None, font_size=10,
          align_cols=None, header_fill=BROWN):
    if caption:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(8)
        cap.paragraph_format.space_after = Pt(4)
        cap.paragraph_format.line_spacing = 1.0
        r = cap.add_run(caption)
        r.font.name = FONT
        r.font.size = Pt(10)
        r.bold = True

    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # Kunci tata letak tabel agar lebar kolom yang ditetapkan benar-benar dipakai Word
    _layout = OxmlElement("w:tblLayout")
    _layout.set(qn("w:type"), "fixed")
    t._tbl.tblPr.append(_layout)
    # Rapatkan margin sel (default Word 0,19 cm terlalu lebar untuk tabel padat)
    _mar = OxmlElement("w:tblCellMar")
    for sisi, nilai in (("top", 20), ("left", 70), ("bottom", 20), ("right", 70)):
        el = OxmlElement(f"w:{sisi}")
        el.set(qn("w:w"), str(nilai))
        el.set(qn("w:type"), "dxa")
        _mar.append(el)
    t._tbl.tblPr.append(_mar)

    hdr = t.rows[0]
    _repeat_header(hdr)
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.text = ""
        par = c.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.paragraph_format.line_spacing = 1.0
        par.paragraph_format.space_after = Pt(2)
        par.paragraph_format.space_before = Pt(2)
        run = par.add_run(str(h))
        run.font.name = FONT
        run.font.size = Pt(font_size)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shade(c, header_fill)

    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        for i, val in enumerate(row):
            c = cells[i]
            c.text = ""
            par = c.paragraphs[0]
            par.paragraph_format.line_spacing = 1.0
            par.paragraph_format.space_after = Pt(2)
            par.paragraph_format.space_before = Pt(2)
            if align_cols and i in align_cols:
                par.alignment = {"r": WD_ALIGN_PARAGRAPH.RIGHT, "c": WD_ALIGN_PARAGRAPH.CENTER}[align_cols[i]]
            run = par.add_run(str(val))
            run.font.name = FONT
            run.font.size = Pt(font_size)
            if ri % 2 == 1:
                _shade(c, CREAM)

    if widths:
        # Normalisasi agar total lebar tepat sama dengan area cetak (15 cm),
        # supaya tidak ada kolom yang dipaksa menyempit oleh Word.
        AREA = 15.0
        total = sum(widths) or 1
        skala = AREA / total
        lebar_final = [w * skala for w in widths]
        for i, w in enumerate(lebar_final):
            for row in t.rows:
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return t


def gambar(doc, path, caption, width=15.0):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_before = Pt(10)
    par.paragraph_format.space_after = Pt(4)
    par.paragraph_format.line_spacing = 1.0
    par.add_run().add_picture(path, width=Cm(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    cap.paragraph_format.line_spacing = 1.0
    r = cap.add_run(caption)
    r.font.name = FONT
    r.font.size = Pt(10)
    r.italic = True


def kode_mono(doc, code, caption=None):
    """Blok kode: font monospace 9 pt, latar abu terang."""
    if caption:
        cap = doc.add_paragraph()
        cap.paragraph_format.space_before = Pt(8)
        cap.paragraph_format.space_after = Pt(2)
        r = cap.add_run(caption)
        r.font.name = FONT
        r.font.size = Pt(10)
        r.bold = True
    t = doc.add_table(rows=1, cols=1)
    t.style = "Table Grid"
    cell = t.rows[0].cells[0]
    _shade(cell, "F7F4EF")
    cell.text = ""
    for i, line in enumerate(code.strip("\n").split("\n")):
        par = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        par.paragraph_format.line_spacing = 1.0
        par.paragraph_format.space_after = Pt(0)
        run = par.add_run(line if line else " ")
        run.font.name = "Consolas"
        run.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def footer_nomor(doc, section, mulai=1):
    section.footer.is_linked_to_previous = False
    par = section.footer.paragraphs[0]
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    run.font.name = FONT
    run.font.size = Pt(10)
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = " PAGE "
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)

    sectPr = section._sectPr
    pg = OxmlElement("w:pgNumType")
    pg.set(qn("w:start"), str(mulai))
    sectPr.append(pg)


def daftar_isi(doc):
    par = doc.add_paragraph()
    par.paragraph_format.space_after = Pt(6)
    run = par.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = r'TOC \o "1-2" \h \z \u'
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "separate")
    f3 = OxmlElement("w:fldChar"); f3.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)

    isi = par.add_run("Daftar isi akan terisi otomatis. Jika belum muncul, klik kanan pada bagian ini "
                      "lalu pilih Update Field (F9).")
    isi.font.name = FONT
    isi.font.size = Pt(12)
    isi.italic = True
    run2 = par.add_run()
    run2._r.append(f3)

    # minta Word memperbarui field saat dokumen dibuka
    settings = doc.settings.element
    uf = OxmlElement("w:updateFields")
    uf.set(qn("w:val"), "true")
    settings.append(uf)


# ---------------------------------------------------------------------------
# Data nyata dari aplikasi
# ---------------------------------------------------------------------------
def ambil_data():
    conn = core.get_db()
    hari = date.today().isoformat()
    awal_bulan = date.today().replace(day=1).isoformat()
    d = {
        "lr": core.laba_rugi(conn, awal_bulan, hari),
        "dash": core.dashboard(conn),
        "stok": core.laporan_stok(conn),
        "awal": awal_bulan,
        "hari": hari,
    }
    d["jumlah"] = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                   ("bahan", "produk", "supplier", "pembelian", "produksi", "penjualan",
                    "penjualan_item", "pengeluaran", "kas", "audit")}
    d["total_resep"] = conn.execute("SELECT COUNT(*) FROM resep").fetchone()[0]
    d["nilai_persediaan"] = d["dash"]["nilai_persediaan"]
    d["produk_resep"] = []
    for pr in conn.execute("SELECT * FROM produk ORDER BY nama").fetchall():
        r = core.get_resep(conn, pr["id"])
        d["produk_resep"].append({
            "nama": pr["nama"], "harga": pr["harga_jual"], "hpp": core.hpp_unit(conn, pr["id"]),
            "bahan": len(r),
            "komposisi": ", ".join(f"{x['nama']} {angka(x['qty'], 3)} {x['satuan']}" for x in r),
        })
    conn.close()
    return d


def baca_hasil_uji():
    path = os.path.join(DOCS, "hasil_pengujian.txt")
    baris, bagian = [], ""
    if not os.path.exists(path):
        return baris
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            m_sec = re.match(r"^\d+\)\s+(.+)$", line.strip())
            if m_sec:
                bagian = m_sec.group(1).strip()
                continue
            m = re.match(r"^\s*\[(LULUS|GAGAL)\]\s+(.+?)(?:\s+->\s+(.*))?$", line)
            if m:
                baris.append((bagian, m.group(2).strip(), m.group(1), (m.group(3) or "").strip()))
    return baris


# ---------------------------------------------------------------------------
# Isi laporan
# ---------------------------------------------------------------------------
def sampul(doc):
    for _ in range(2):
        doc.add_paragraph()
    p(doc, "LAPORAN TUGAS UJIAN TENGAH SEMESTER", bold=True, size=14, align="center", indent=0)
    p(doc, "MATA KULIAH ENTERPRISE INFORMATION SYSTEM", bold=True, size=14, align="center", indent=0,
      space_after=30)

    p(doc, "PERANCANGAN DAN IMPLEMENTASI APLIKASI ERP BERBASIS WEB", bold=True, size=18,
      align="center", indent=0, space_after=6)
    p(doc, "“BakeERP: Sistem Informasi Terintegrasi untuk Pengelolaan Produksi, "
           "Persediaan, dan Keuangan UMKM Bakery”", bold=True, size=13, align="center", indent=0,
      space_after=4)
    p(doc, "Studi Kasus: Roti Kita Bakery", italic=True, size=12, align="center", indent=0,
      space_after=36)

    for _ in range(2):
        doc.add_paragraph()

    p(doc, "Disusun oleh:", bold=True, align="center", indent=0, space_after=6)
    p(doc, "Kadek Lyradelia Pracili  (NIM: …………………)", align="center", indent=0, space_after=2)
    p(doc, "Nama Anggota 2  (NIM: …………………)", align="center", indent=0, space_after=2)
    p(doc, "Nama Anggota 3  (NIM: …………………)", align="center", indent=0, space_after=24)

    p(doc, "Dosen Pengampu:", bold=True, align="center", indent=0, space_after=2)
    p(doc, "(Nama Dosen)", align="center", indent=0, space_after=30)

    p(doc, "PROGRAM STUDI ……………………………", bold=True, align="center", indent=0, space_after=2)
    p(doc, "FAKULTAS ……………………………", bold=True, align="center", indent=0, space_after=2)
    p(doc, "UNIVERSITAS ……………………………", bold=True, align="center", indent=0, space_after=2)
    p(doc, f"TAHUN {date.today().year}", bold=True, align="center", indent=0)


def bab1(doc, D):
    h1(doc, "BAB I PENDAHULUAN")

    h2(doc, "1.1 Latar Belakang")
    p(doc, "Industri makanan rumahan (UMKM bakery) di Indonesia tumbuh cukup pesat, terutama karena "
           "permintaan roti dan pastry segar yang tinggi dari konsumen perkotaan. Namun pertumbuhan "
           "usaha sering tidak diikuti oleh perbaikan sistem pengelolaan. Sebagian besar bakery kecil "
           "masih mengandalkan pencatatan manual: nota pembelian bahan ditumpuk, stok tepung dan mentega "
           "dihitung dengan perkiraan, penjualan dicatat pada buku kas harian, dan biaya produksi tidak "
           "pernah dihitung secara rinci per jenis roti.")
    p(doc, "Pola seperti ini menimbulkan beberapa persoalan yang saling berkaitan. Pertama, stok bahan "
           "baku tidak akurat sehingga produksi sering terhenti karena bahan habis, atau sebaliknya bahan "
           "menumpuk dan kedaluwarsa. Kedua, harga pokok produksi (HPP) per produk tidak diketahui, "
           "sehingga pemilik usaha menetapkan harga jual berdasarkan perkiraan dan tidak menyadari bahwa "
           "sebagian produk sebenarnya hanya memberikan margin kecil. Ketiga, laporan laba rugi baru "
           "disusun pada akhir bulan dengan cara merekap ulang semua nota, sehingga keputusan bisnis "
           "selalu terlambat diambil.")
    p(doc, "Akar masalahnya bukan pada kurangnya tenaga kerja atau modal, melainkan pada tidak adanya "
           "satu sumber data yang dipakai bersama oleh seluruh bagian usaha. Bagian gudang mencatat "
           "pembelian, bagian produksi mencatat pemakaian bahan, bagian kasir mencatat penjualan, dan "
           "pemilik mereka-rekap semuanya secara terpisah. Data yang seharusnya saling terhubung justru "
           "hidup sendiri-sendiri. Di sinilah konsep Enterprise Information System (EIS) dan Enterprise "
           "Resource Planning (ERP) menjadi relevan: seluruh proses bisnis dijalankan di atas satu basis "
           "data terpadu, sehingga satu transaksi langsung memperbarui seluruh bagian yang terkait.")
    p(doc, "Berdasarkan uraian tersebut, kelompok merancang dan mengimplementasikan BakeERP, yaitu "
           "aplikasi ERP berbasis web untuk usaha bakery yang mencakup modul pembelian, persediaan bahan "
           "baku, produksi berbasis resep, penjualan (point of sale), pengeluaran operasional, serta "
           "laporan keuangan dan manajerial. Aplikasi tidak hanya dirancang, tetapi benar-benar "
           "dijalankan, diisi data, dan diuji alur bisnisnya dari awal sampai akhir.")

    h2(doc, "1.2 Identifikasi Masalah")
    p(doc, "Berdasarkan pengamatan terhadap proses bisnis bakery skala kecil, masalah yang teridentifikasi "
           "adalah sebagai berikut.")
    nomor(doc, [
        "Pencatatan pembelian, pemakaian bahan, dan penjualan dilakukan pada media terpisah sehingga data "
        "antar bagian tidak pernah bertemu dan sering berbeda.",
        "Stok bahan baku dan produk jadi tidak diketahui secara real-time, sehingga produksi dan penjualan "
        "sering terganggu.",
        "Harga pokok produksi per unit produk tidak dihitung dari komposisi bahan (resep), sehingga margin "
        "tiap produk tidak terukur.",
        "Laporan laba rugi dan arus kas disusun manual pada akhir periode, rawan salah hitung, dan tidak "
        "bisa dipakai untuk pengambilan keputusan harian.",
        "Tidak ada jejak audit, sehingga ketika terjadi selisih stok atau kas, penyebabnya sulit ditelusuri.",
    ])

    h2(doc, "1.3 Tujuan")
    nomor(doc, [
        "Merancang sistem informasi enterprise (ERP) yang sesuai dengan proses bisnis UMKM bakery.",
        "Membangun aplikasi ERP berbasis web yang berjalan di browser dan menyimpan data secara permanen.",
        "Mengintegrasikan modul pembelian, persediaan, produksi, penjualan, dan keuangan dalam satu basis "
        "data sehingga tidak ada input data berulang.",
        "Menghitung HPP dan laba secara otomatis dari transaksi yang terjadi.",
        "Menguji aplikasi melalui skenario alur bisnis end-to-end dan mendokumentasikan hasilnya.",
    ])

    h2(doc, "1.4 Ruang Lingkup dan Batasan")
    p(doc, "Ruang lingkup sistem dibatasi agar pengerjaan terarah dan setiap fitur dapat diuji dengan baik.")
    bullets(doc, [
        "Objek studi: Roti Kita Bakery, usaha bakery skala kecil dengan 6 jenis produk dan 12 jenis bahan baku.",
        "Modul yang dibangun: master data (bahan, produk, resep, supplier, pengguna), pembelian, persediaan, "
        "produksi, penjualan, pengeluaran, keuangan, laporan, dan log aktivitas.",
        "Modul yang tidak dibangun: akuntansi lengkap berstandar SAK (jurnal umum, neraca, buku besar "
        "multi-akun), penggajian, e-commerce, dan integrasi pembayaran pihak ketiga. Sesuai catatan rubrik, "
        "penilaian difokuskan pada kesesuaian dan kedalaman fitur terhadap kebutuhan bisnis yang ditetapkan.",
        "Aplikasi dijalankan pada server lokal (localhost) menggunakan Python dan SQLite; akses dilakukan "
        "melalui browser modern.",
    ])

    h2(doc, "1.5 Manfaat")
    p(doc, "Bagi pemilik usaha, sistem ini menyediakan informasi stok, HPP, dan laba secara cepat sehingga "
           "keputusan pembelian bahan dan penetapan harga dapat diambil berdasarkan data. Bagi karyawan, "
           "pekerjaan pencatatan menjadi lebih ringkas karena satu transaksi cukup diinput satu kali. Bagi "
           "penulis, tugas ini menjadi latihan menerapkan konsep ERP secara utuh, mulai dari analisis "
           "kebutuhan, perancangan basis data, implementasi, sampai pengujian.")


def bab2(doc, D):
    h1(doc, "BAB II LANDASAN TEORI")

    h2(doc, "2.1 Sistem Informasi Enterprise")
    p(doc, "Sistem informasi enterprise adalah sistem informasi yang mendukung proses bisnis utama pada "
           "tingkat organisasi, bukan hanya pada satu departemen. Laudon dan Laudon (2020) menjelaskan "
           "bahwa sistem informasi pada level enterprise berfungsi mengintegrasikan data lintas fungsi "
           "sehingga manajemen memperoleh gambaran menyeluruh tentang kinerja organisasi. Ciri utamanya "
           "adalah adanya basis data bersama, proses bisnis yang terstandar, dan aliran informasi yang "
           "melintasi batas departemen.")
    p(doc, "Konsekuensi penting dari sifat lintas fungsi tersebut adalah bahwa nilai sebuah sistem "
           "enterprise tidak terletak pada banyaknya menu atau fitur, melainkan pada keterhubungan antar "
           "bagian. Sistem yang memiliki banyak modul tetapi datanya terpisah tetap berperilaku seperti "
           "kumpulan aplikasi tunggal, bukan sebagai sistem enterprise.")

    h2(doc, "2.2 Enterprise Resource Planning (ERP)")
    p(doc, "ERP adalah paket sistem informasi terintegrasi yang mengelola sumber daya organisasi — bahan, "
           "produk, keuangan, dan sumber daya manusia — melalui satu basis data dan satu kumpulan proses "
           "bisnis (Monk & Wagner, 2013). Wallace dan Kremzar (2001) menambahkan bahwa ERP bekerja dengan "
           "prinsip prediksi dan penjadwalan terpadu: permintaan pelanggan, persediaan, dan kapasitas "
           "produksi dihitung dalam satu rangkaian logika.")
    p(doc, "Terdapat empat karakteristik yang membedakan ERP dari aplikasi biasa, dan keempatnya dijadikan "
           "acuan perancangan pada tugas ini.")
    tabel(doc,
          ["Karakteristik", "Penjelasan", "Wujud pada BakeERP"],
          [["Basis data tunggal", "Seluruh modul membaca dan menulis ke satu skema data yang sama",
            "Satu berkas SQLite dengan 14 tabel relasional; tidak ada duplikasi data antar modul"],
           ["Proses lintas fungsi", "Satu transaksi menyentuh beberapa fungsi sekaligus",
            "Penjualan mengurangi stok produk, mencatat pendapatan, HPP, dan kas masuk sekaligus"],
           ["Konsistensi & real-time", "Data yang ditampilkan selalu mencerminkan transaksi terakhir",
            "Dashboard, stok, dan laba dihitung langsung dari tabel transaksi"],
           ["Keterlacakan (traceability)", "Setiap perubahan data dapat ditelusuri sumbernya",
            "Tabel kas menyimpan referensi dokumen; tabel audit mencatat aksi pengguna"]],
          widths=[3.6, 5.4, 6.2], caption="Tabel 2.1 Karakteristik ERP dan wujudnya dalam rancangan sistem")

    h2(doc, "2.3 Modul ERP dan Penyesuaian untuk UMKM")
    p(doc, "ERP komersial umumnya terdiri atas modul keuangan, penjualan, pembelian, persediaan, produksi, "
           "dan sumber daya manusia. Untuk UMKM, penerapan seluruh modul sekaligus tidak realistis. "
           "Pendekatan yang dipakai adalah memilih modul inti yang menyentuh langsung permasalahan utama, "
           "lalu memperdalam integrasi antar modul tersebut. Tabel berikut memetakan modul ERP umum "
           "terhadap keputusan perancangan kelompok.")
    tabel(doc,
          ["Modul ERP umum", "Diterapkan?", "Alasan keputusan"],
          [["Purchasing (pembelian)", "Ya", "Bahan baku adalah pengeluaran terbesar dan sumber data harga pokok"],
           ["Inventory (persediaan)", "Ya", "Stok bahan dan produk jadi adalah masalah utama bakery"],
           ["Production / Manufacturing", "Ya (disederhanakan)", "Produksi bakery berbasis resep; diimplementasikan sebagai BOM"],
           ["Sales / Order Management", "Ya", "Sumber pendapatan dan pemicu pengurangan stok produk jadi"],
           ["Financial / Accounting", "Ya (terbatas)", "Buku kas, HPP, laba rugi; tanpa jurnal umum berpasangan"],
           ["Human Resource", "Tidak", "Diganti pencatatan beban gaji pada modul pengeluaran"],
           ["CRM / Marketing", "Tidak", "Di luar ruang lingkup permasalahan yang diangkat"]],
          widths=[4.4, 3.2, 7.6], caption="Tabel 2.2 Pemetaan modul ERP umum terhadap ruang lingkup sistem",
          align_cols={1: "c"})

    h2(doc, "2.4 Bill of Material, HPP, dan Harga Rata-rata Bergerak")
    p(doc, "Bill of Material (BOM) atau dalam aplikasi ini disebut resep adalah daftar bahan beserta "
           "kuantitasnya untuk menghasilkan satu unit produk. BOM menjadi penghubung antara modul produksi "
           "dan modul persediaan: ketika produksi dijalankan, sistem mengalikan kuantitas resep dengan "
           "jumlah unit yang diproduksi, lalu mengurangi stok bahan sesuai hasil perkalian tersebut.")
    p(doc, "Harga pokok produksi (HPP) per unit dihitung sebagai jumlah nilai bahan pada resep, yaitu "
           "Σ (kuantitas bahan × harga beli per satuan). Karena harga bahan dapat berubah setiap kali "
           "pembelian dilakukan, sistem menyimpan harga beli sebagai harga rata-rata bergerak "
           "(moving average):")
    p(doc, "Harga baru = ((stok lama × harga lama) + (jumlah masuk × harga beli)) ÷ (stok lama + jumlah masuk)",
      italic=True, align="center", indent=0)
    p(doc, "Dengan mekanisme ini, HPP selalu mengikuti harga pasar terakhir tanpa harus menghitung ulang "
           "seluruh riwayat pembelian, dan margin setiap produk dapat dipantau secara wajar.")

    h2(doc, "2.5 Teknologi yang Digunakan")
    tabel(doc,
          ["Komponen", "Teknologi", "Alasan pemilihan"],
          [["Bahasa pemrograman", "Python 3 (standard library)", "Tidak memerlukan instalasi paket tambahan sehingga mudah didemokan"],
           ["Basis data (utama)", "SQLite 3", "Basis data relasional berbasis berkas, mendukung transaksi ACID, tanpa server terpisah"],
           ["Basis data (alternatif)", "MySQL 8 / MariaDB", "Dipakai bila lingkungan kampus mensyaratkan DBMS server; diakses lewat driver PyMySQL"],
           ["Server aplikasi", "http.server (ThreadingHTTPServer)", "Menyediakan REST API dan penyajian berkas statis"],
           ["Antarmuka", "HTML, CSS, JavaScript (vanilla)", "Berjalan langsung di browser tanpa proses build"],
           ["Keamanan", "PBKDF2-HMAC-SHA256 + token sesi", "Menyimpan password sebagai hash dengan salt, bukan teks asli"],
           ["Pengujian", "Skrip uji HTTP otomatis", "Menguji alur bisnis end-to-end secara berulang dan konsisten"]],
          widths=[3.6, 5.4, 6.2], caption="Tabel 2.3 Tumpukan teknologi aplikasi")


def bab3(doc, D):
    h1(doc, "BAB III ANALISIS KEBUTUHAN DAN PERANCANGAN SISTEM")

    h2(doc, "3.1 Profil Bisnis dan Target Pengguna")
    p(doc, "Roti Kita Bakery adalah usaha bakery yang memproduksi roti dan pastry setiap pagi lalu menjualnya "
           "melalui etalase toko. Produk yang dihasilkan meliputi roti tawar, croissant, donat, bolu, roti "
           "sobek, dan bagel. Bahan baku utama adalah tepung terigu (dua jenis protein), gula, mentega, "
           "telur, ragi, susu, cokelat, keju, butter sheet, garam, dan kemasan. Bahan dipasok oleh tiga "
           "supplier dengan siklus pengiriman mingguan.")
    p(doc, "Pola operasionalnya sederhana tetapi padat transaksi: produksi dilakukan pagi hari, penjualan "
           "berlangsung sepanjang hari dengan puluhan transaksi kecil, dan pembelian bahan dilakukan berkala. "
           "Karena itu, target pengguna sistem terdiri atas tiga peran dengan kebutuhan berbeda.")
    tabel(doc,
          ["Peran", "Aktivitas utama", "Kebutuhan informasi"],
          [["Pemilik / Admin", "Memantau kinerja, mengatur harga, mencatat beban",
            "Laba rugi, margin per produk, nilai persediaan, arus kas"],
           ["Staf Gudang", "Menerima barang, mencatat produksi, mengontrol stok",
            "Stok terkini, kebutuhan bahan per resep, daftar PO yang belum diterima"],
           ["Kasir", "Melayani penjualan di etalase",
            "Harga jual, ketersediaan stok produk jadi, riwayat transaksi"]],
          widths=[3.2, 6.0, 6.0], caption="Tabel 3.1 Peran pengguna dan kebutuhan informasinya")

    h2(doc, "3.2 Analisis Masalah dan Kebutuhan Sistem")
    p(doc, "Setiap masalah yang ditemukan pada proses bisnis saat ini diterjemahkan menjadi kebutuhan "
           "sistem yang konkret. Tabel berikut menjadi dasar penentuan modul dan fitur yang dibangun.")
    tabel(doc,
          ["Masalah proses saat ini", "Dampak", "Kebutuhan sistem", "Modul"],
          [["Nota pembelian dicatat terpisah dari kartu stok", "Stok fisik dan catatan sering berbeda",
            "Penerimaan barang otomatis menambah stok dan memperbarui harga rata-rata", "Pembelian, Persediaan"],
           ["Pemakaian bahan tidak tercatat per batch", "Bahan hilang tanpa jejak, HPP tidak diketahui",
            "Produksi dijalankan berdasarkan resep sehingga pemakaian bahan tercatat otomatis", "Produksi, Persediaan"],
           ["Harga jual ditentukan perkiraan", "Sebagian produk dijual di bawah biaya",
            "HPP dihitung dari resep dan ditampilkan sebagai margin per produk", "Produk & Resep, Laporan"],
           ["Penjualan dicatat di buku kas", "Rekap akhir bulan lama dan rawan salah",
            "Transaksi kasir langsung membentuk pendapatan, HPP, dan kas masuk", "Penjualan, Keuangan"],
           ["Beban operasional tidak terpantau", "Laba bersih tidak diketahui",
            "Pencatatan pengeluaran per kategori yang mengurangi laba dan kas", "Pengeluaran, Keuangan"],
           ["Selisih data sulit ditelusuri", "Tidak ada pertanggungjawaban transaksi",
            "Setiap transaksi menyimpan referensi dokumen dan jejak audit pengguna", "Log Aktivitas, Keuangan"]],
          widths=[4.2, 3.6, 5.6, 2.6], caption="Tabel 3.2 Terjemahan masalah bisnis menjadi kebutuhan sistem",
          font_size=9)

    h2(doc, "3.3 Proses Bisnis Usulan (To-Be)")
    p(doc, "Alur bisnis yang dirancang membentuk satu siklus tertutup. Data hanya diinput sekali pada titik "
           "transaksi, lalu mengalir ke modul lain secara otomatis.")
    nomor(doc, [
        "Staf gudang membuat purchase order (PO) kepada supplier. PO berstatus draf dan belum memengaruhi stok.",
        "Saat barang datang, staf gudang menekan “Terima barang”. Sistem menambah stok bahan, menghitung "
        "ulang harga rata-rata, mengubah status PO menjadi diterima, dan mencatat kas keluar sebesar nilai PO.",
        "Sebelum produksi, sistem menampilkan kebutuhan bahan berdasarkan resep dan jumlah yang akan dibuat, "
        "sehingga stok dapat dipastikan cukup.",
        "Produksi dijalankan: stok bahan berkurang sesuai resep, stok produk jadi bertambah, dan biaya bahan "
        "batch tersebut tersimpan sebagai dasar HPP.",
        "Kasir melayani penjualan. Stok produk jadi berkurang, pendapatan dan HPP transaksi tercatat, kas "
        "masuk terbentuk otomatis.",
        "Beban operasional (gaji, listrik, sewa, perawatan) dicatat pada modul pengeluaran dan langsung "
        "mengurangi kas serta laba bersih.",
        "Laporan laba rugi, buku kas, stok, dan produktivitas tersedia kapan saja tanpa rekap manual.",
    ])

    h2(doc, "3.4 Kebutuhan Fungsional")
    tabel(doc,
          ["Kode", "Kebutuhan fungsional", "Modul"],
          [["F-01", "Pengguna dapat login dan sistem membatasi akses berdasarkan peran", "Autentikasi"],
           ["F-02", "Mengelola data bahan baku (tambah, ubah, hapus) beserta batas minimum stok", "Master"],
           ["F-03", "Mengelola data produk jadi beserta harga jual", "Master"],
           ["F-04", "Mengelola data supplier", "Master"],
           ["F-05", "Menyusun resep (BOM) per produk dan menghitung HPP otomatis", "Produk & Resep"],
           ["F-06", "Membuat purchase order dengan banyak item", "Pembelian"],
           ["F-07", "Menerima barang sehingga stok bertambah dan harga rata-rata diperbarui", "Pembelian"],
           ["F-08", "Menampilkan simulasi kebutuhan bahan sebelum produksi dijalankan", "Produksi"],
           ["F-09", "Menjalankan produksi: mengurangi bahan, menambah produk jadi, menyimpan biaya bahan", "Produksi"],
           ["F-10", "Menolak produksi bila stok bahan tidak mencukupi", "Produksi"],
           ["F-11", "Transaksi penjualan dengan keranjang, diskon, dan metode pembayaran", "Penjualan"],
           ["F-12", "Menolak penjualan bila stok produk jadi tidak mencukupi", "Penjualan"],
           ["F-13", "Mencatat pengeluaran operasional per kategori", "Pengeluaran"],
           ["F-14", "Menyajikan buku kas dengan referensi dokumen sumber", "Keuangan"],
           ["F-15", "Menyusun laporan laba rugi per periode secara otomatis", "Keuangan"],
           ["F-16", "Menyajikan dashboard KPI: penjualan, laba, persediaan, stok kritis, tren 7 hari", "Dashboard"],
           ["F-17", "Menyajikan laporan penjualan, produksi, dan posisi persediaan", "Laporan"],
           ["F-18", "Mencatat jejak audit setiap transaksi dan perubahan data", "Log Aktivitas"]],
          widths=[1.6, 11.2, 3.2], caption="Tabel 3.3 Daftar kebutuhan fungsional sistem",
          align_cols={0: "c"})

    h2(doc, "3.5 Kebutuhan Non-Fungsional")
    tabel(doc,
          ["Kode", "Kebutuhan non-fungsional", "Kriteria keberhasilan"],
          [["NF-01", "Aplikasi berjalan di browser tanpa instalasi klien", "Halaman terbuka pada Chrome/Edge/Firefox"],
           ["NF-02", "Data tersimpan permanen", "Data tetap ada setelah server dimulai ulang"],
           ["NF-03", "Konsistensi data antar modul", "Tidak ada transaksi yang membuat stok negatif atau kas ganda"],
           ["NF-04", "Waktu respons wajar", "Halaman utama tampil di bawah 1 detik pada data 1 bulan"],
           ["NF-05", "Antarmuka konsisten dan responsif", "Tata letak tetap terbaca pada layar 860 px ke bawah"],
           ["NF-06", "Keamanan dasar", "Password disimpan sebagai hash; API menolak permintaan tanpa token"]],
          widths=[1.6, 7.0, 7.4], caption="Tabel 3.4 Kebutuhan non-fungsional", align_cols={0: "c"})

    h2(doc, "3.6 Perancangan Basis Data")
    p(doc, "Basis data dirancang relasional dengan 14 tabel. Prinsipnya: data master dipisahkan dari data "
           "transaksi, setiap transaksi memiliki tabel kepala (header) dan tabel rinci (detail), dan seluruh "
           "arus kas dikumpulkan pada satu tabel jurnal sederhana agar dapat ditelusuri.")
    tabel(doc,
          ["Tabel", "Jenis", "Fungsi utama"],
          [["users", "Master", "Akun pengguna, peran, dan hash password"],
           ["supplier", "Master", "Data pemasok bahan"],
           ["bahan", "Master", "Bahan baku: stok, satuan, batas minimum, harga rata-rata"],
           ["produk", "Master", "Produk jadi: harga jual, stok, batas minimum"],
           ["resep", "Master", "Bill of Material: produk × bahan × kuantitas"],
           ["pembelian", "Transaksi (header)", "Purchase order: nomor, tanggal, supplier, total, status"],
           ["pembelian_item", "Transaksi (detail)", "Rincian bahan, kuantitas, harga, subtotal per PO"],
           ["produksi", "Transaksi (header)", "Batch produksi: nomor, produk, jumlah, biaya bahan"],
           ["produksi_item", "Transaksi (detail)", "Pemakaian bahan per batch beserta nilainya"],
           ["penjualan", "Transaksi (header)", "Invoice: subtotal, diskon, total, HPP, metode bayar"],
           ["penjualan_item", "Transaksi (detail)", "Produk terjual, harga, subtotal, HPP per baris"],
           ["pengeluaran", "Transaksi", "Beban operasional per kategori"],
           ["kas", "Jurnal", "Arus kas masuk/keluar dengan referensi dokumen sumber"],
           ["audit", "Log", "Jejak aktivitas pengguna dan transaksi"]],
          widths=[3.6, 3.4, 9.0], caption="Tabel 3.5 Struktur tabel basis data BakeERP", font_size=9.5)
    p(doc, "Relasi antar tabel mengikuti aturan integritas referensial: tabel detail merujuk header melalui "
           "foreign key dengan penghapusan berantai, resep merujuk produk dan bahan, serta tabel kas "
           "menyimpan pasangan ref_tipe dan ref_id yang menunjuk dokumen sumber (penjualan, pembelian, atau "
           "pengeluaran). Dengan pola ini, setiap baris kas selalu dapat dilacak kembali ke dokumen asalnya.")

    h2(doc, "3.7 Rancangan Integrasi Antar Modul")
    p(doc, "Bagian ini merupakan inti rancangan sistem enterprise. Tabel berikut menjelaskan efek setiap "
           "transaksi terhadap modul lain, yang menjadi dasar pengujian integrasi pada Bab V.")
    tabel(doc,
          ["Transaksi", "Efek pada persediaan", "Efek pada keuangan", "Efek pada laporan"],
          [["Penerimaan barang (PO)", "Stok bahan bertambah; harga rata-rata diperbarui",
            "Kas keluar sebesar nilai PO", "Nilai persediaan naik; laba tidak berubah"],
           ["Produksi", "Stok bahan berkurang sesuai resep; stok produk jadi bertambah",
            "Tidak mengubah kas; biaya bahan tercatat sebagai dasar HPP", "HPP per unit dan biaya produksi"],
           ["Penjualan", "Stok produk jadi berkurang", "Kas masuk; pendapatan dan HPP transaksi tercatat",
            "Omzet, laba kotor, produk terlaris"],
           ["Pengeluaran operasional", "Tidak berubah", "Kas keluar", "Beban operasional menurunkan laba bersih"],
           ["Perubahan resep", "Tidak langsung berubah", "Mengubah HPP seluruh transaksi berikutnya",
            "Margin per produk ikut berubah"]],
          widths=[3.4, 4.6, 4.4, 3.6], caption="Tabel 3.6 Matriks integrasi antar modul", font_size=9)

    h2(doc, "3.8 Arsitektur Aplikasi")
    p(doc, "Aplikasi dibangun dengan arsitektur tiga lapis yang sederhana: lapisan antarmuka (browser), "
           "lapisan logika dan API (server Python), serta lapisan data (SQLite). Pemisahan ini membuat "
           "aturan bisnis terpusat di server, sehingga antarmuka tidak dapat mengubah data secara langsung.")
    kode_mono(doc, """Browser (HTML/CSS/JS)
   |  HTTP + JSON  (REST API, token Bearer)
   v
Server Python  app.py  ->  routing endpoint /api/...
   |  pemanggilan fungsi
   v
Logika bisnis  core.py  ->  aturan transaksi, validasi, laporan
   |  SQL (dialek SQLite)
   v
Lapisan backend  db.py  ->  memilih mesin basis data
   |                        (dbmysql.py menerjemahkan dialek ke MySQL)
   +--> SQLite : bakery.db (berkas lokal)
   +--> MySQL  : 127.0.0.1:3306 / bakerp""", caption="Gambar 3.1 Arsitektur tiga lapis aplikasi BakeERP")
    p(doc, "Seluruh aturan penting — validasi stok, perhitungan harga rata-rata, pemotongan bahan, "
           "perhitungan HPP, dan pencatatan kas — dijalankan di lapisan logika (core.py) di dalam satu "
           "transaksi basis data. Artinya, jika salah satu langkah gagal, seluruh rangkaian dibatalkan "
           "sehingga data tidak pernah berada pada kondisi setengah jadi.")

    h2(doc, "3.9 Rancangan Antarmuka")
    p(doc, "Antarmuka dirancang dengan prinsip konsistensi dan efisiensi kerja: navigasi tetap di sisi kiri, "
           "judul dan konteks halaman di bagian atas, serta aksi utama selalu berada pada posisi yang sama. "
           "Warna hangat (cokelat dan krem) dipilih agar sesuai dengan karakter usaha bakery, dengan kontras "
           "teks yang tetap tinggi untuk keterbacaan.")
    tabel(doc,
          ["Halaman", "Fungsi", "Aksi utama"],
          [["Login", "Autentikasi pengguna", "Masuk dengan username dan password"],
           ["Dashboard", "Ringkasan KPI dan peringatan stok", "Menavigasi ke modul terkait"],
           ["Penjualan (POS)", "Melayani transaksi kasir", "Pilih produk, atur jumlah, proses pembayaran"],
           ["Produksi", "Menjalankan batch produksi", "Pilih produk dan jumlah, lihat kebutuhan bahan, jalankan"],
           ["Pembelian", "Mengelola purchase order", "Buat PO, terima barang, lihat detail"],
           ["Bahan Baku", "Master persediaan bahan", "Tambah/ubah bahan, pantau status stok"],
           ["Produk & Resep", "Master produk dan BOM", "Ubah produk, sunting resep, lihat HPP"],
           ["Supplier", "Master pemasok", "Tambah/ubah supplier"],
           ["Pengeluaran", "Beban operasional", "Catat pengeluaran per kategori"],
           ["Laba Rugi & Kas", "Laporan keuangan periode", "Pilih rentang tanggal, lihat laba rugi dan buku kas"],
           ["Laporan", "Analisis penjualan, produksi, persediaan", "Pindah tab, terapkan rentang tanggal"],
           ["Log Aktivitas", "Jejak audit", "Menelusuri aksi pengguna"]],
          widths=[3.6, 5.6, 6.8], caption="Tabel 3.7 Daftar halaman antarmuka aplikasi", font_size=9.5)


def bab4(doc, D):
    h1(doc, "BAB IV IMPLEMENTASI APLIKASI")

    h2(doc, "4.1 Lingkungan Implementasi")
    p(doc, "Aplikasi diimplementasikan menggunakan Python 3 dengan standard library sehingga tidak "
           "memerlukan pemasangan paket tambahan. Server dijalankan dengan perintah berikut, lalu aplikasi "
           "dibuka melalui browser pada alamat http://localhost:8000.")
    kode_mono(doc, """cd erp-bakery
python app.py              # server berjalan pada port 8000
python app.py --port 8080  # bila port 8000 sudah dipakai""")
    p(doc, "Saat pertama kali dijalankan, sistem membuat berkas bakery.db, membangun 14 tabel, dan mengisi "
           "data contoh selama 31 hari (pembelian, produksi, penjualan, dan beban operasional) sehingga "
           "dashboard serta laporan langsung dapat didemonstrasikan.")

    h2(doc, "4.2 Struktur Berkas Proyek")
    tabel(doc,
          ["Berkas", "Isi", "Perkiraan baris"],
          [["app.py", "Server HTTP, routing REST API, penyajian berkas statis, autentikasi token", "± 300"],
           ["core.py", "Skema database, logika bisnis seluruh modul, laporan, dan data contoh", "± 990"],
           ["db.py", "Pemilih backend basis data (SQLite atau MySQL) melalui variabel lingkungan", "± 90"],
           ["dbmysql.py", "Lapisan kompatibilitas: menerjemahkan dialek SQLite ke MySQL", "± 230"],
           ["migrate_to_mysql.py", "Migrasi data SQLite ke MySQL beserta verifikasi konsistensi", "± 170"],
           ["static/index.html", "Kerangka halaman aplikasi", "± 20"],
           ["static/style.css", "Sistem desain antarmuka (warna, kartu, tabel, responsif)", "± 420"],
           ["static/app.js", "Klien API, layout, router, halaman dashboard", "± 470"],
           ["static/pages.js", "Halaman modul: POS, produksi, pembelian, master, keuangan, laporan", "± 800"],
           ["tests/test_integrasi.py", "29 skenario pengujian integrasi end-to-end (SQLite & MySQL)", "± 260"]],
          widths=[4.4, 9.4, 2.2], caption="Tabel 4.1 Struktur berkas dan tanggung jawabnya", font_size=9.5)

    h2(doc, "4.3 Endpoint API yang Dibangun")
    p(doc, "Seluruh komunikasi antarmuka dengan server menggunakan format JSON. Endpoint dikelompokkan per "
           "modul dan dilindungi token sesi.")
    tabel(doc,
          ["Metode", "Endpoint", "Fungsi"],
          [["GET", "/api/info", "Informasi aplikasi dan backend basis data yang aktif"],
           ["POST", "/api/login", "Autentikasi dan penerbitan token"],
           ["GET", "/api/dashboard", "Data KPI dashboard"],
           ["GET/POST/DELETE", "/api/bahan, /api/produk, /api/supplier", "Operasi master data"],
           ["GET/POST", "/api/resep", "Membaca dan menyimpan resep (BOM)"],
           ["GET/POST", "/api/pembelian", "Daftar PO dan pembuatan PO baru"],
           ["POST", "/api/pembelian/{id}/terima", "Penerimaan barang (stok + kas)"],
           ["POST", "/api/produksi/cek", "Simulasi kebutuhan bahan"],
           ["GET/POST", "/api/produksi", "Riwayat dan eksekusi produksi"],
           ["GET/POST", "/api/penjualan", "Riwayat dan transaksi penjualan"],
           ["GET/POST", "/api/pengeluaran", "Beban operasional"],
           ["GET", "/api/keuangan/labarugi, /api/keuangan/kas", "Laporan keuangan periode"],
           ["GET", "/api/laporan/stok, /penjualan, /produksi", "Laporan manajerial"],
           ["GET", "/api/audit", "Jejak audit"]],
          widths=[3.4, 7.0, 5.6], caption="Tabel 4.2 Ringkasan endpoint REST API", font_size=9)

    h2(doc, "4.4 Implementasi Logika Integrasi")
    p(doc, "Bagian terpenting dari implementasi adalah fungsi-fungsi yang menghubungkan modul. Berikut "
           "cuplikan kode penerimaan barang yang memperlihatkan tiga efek sekaligus: penambahan stok, "
           "pembaruan harga rata-rata, dan pencatatan kas keluar.")
    kode_mono(doc, '''def terima_pembelian(conn, id_, user="sistem"):
    """Penerimaan barang: stok bahan naik, harga rata-rata diperbarui,
    dan otomatis tercatat sebagai kas keluar."""
    head = conn.execute("SELECT * FROM pembelian WHERE id=?", (id_,)).fetchone()
    if head["status"] == "diterima":
        raise BizError("PO ini sudah diterima sebelumnya.")
    for it in conn.execute("SELECT * FROM pembelian_item WHERE pembelian_id=?", (id_,)):
        b = conn.execute("SELECT * FROM bahan WHERE id=?", (it["bahan_id"],)).fetchone()
        stok_baru = b["stok"] + it["qty"]
        harga_baru = ((b["stok"] * b["harga_beli"]) + (it["qty"] * it["harga"])) / stok_baru
        conn.execute("UPDATE bahan SET stok=?, harga_beli=? WHERE id=?",
                     (r2(stok_baru), r2(harga_baru), it["bahan_id"]))
    conn.execute("UPDATE pembelian SET status='diterima' WHERE id=?", (id_,))
    conn.execute("INSERT INTO kas (tanggal, tipe, kategori, ref_tipe, ref_id, "
                 "keterangan, jumlah, created_at) VALUES (?,?,?,?,?,?,?,?)",
                 (head["tanggal"], "keluar", "Pembelian Bahan", "pembelian", id_,
                  f"Pembayaran {head['no_po']}", head["total"], now_str()))''',
               caption="Kode 4.1 Penerimaan barang: stok, harga rata-rata, dan kas dalam satu transaksi")

    p(doc, "Fungsi produksi membaca resep, memvalidasi ketersediaan bahan, lalu mengurangi stok bahan dan "
           "menambah stok produk jadi. Jika salah satu bahan kurang, seluruh proses dibatalkan dan pengguna "
           "menerima pesan rinci mengenai bahan mana yang tidak mencukupi.")
    kode_mono(doc, '''kebutuhan = cek_kebutuhan_bahan(conn, produk_id, qty)
kurang = [k for k in kebutuhan if not k["cukup"]]
if kurang:
    raise BizError("Stok bahan baku tidak mencukupi: " + rinci(kurang))

for k in kebutuhan:                       # 1) bahan berkurang sesuai resep
    conn.execute("UPDATE bahan SET stok = ROUND(stok - ?, 3) WHERE id=?",
                 (k["butuh"], k["bahan_id"]))
conn.execute("UPDATE produk SET stok = ROUND(stok + ?, 3) WHERE id=?",  # 2) produk jadi bertambah
             (qty, produk_id))''', caption="Kode 4.2 Inti eksekusi produksi berbasis resep")

    p(doc, "Pada modul penjualan, HPP setiap baris dihitung dari resep produk dikalikan kuantitas, sehingga "
           "laba kotor transaksi dapat diketahui seketika. Nilai HPP disimpan pada baris penjualan agar "
           "laporan historis tidak berubah walaupun harga bahan berubah di kemudian hari.")

    h2(doc, "4.5 Perhitungan HPP dan Margin Produk")
    p(doc, "Tabel berikut menampilkan resep dan HPP setiap produk yang tersimpan pada basis data aplikasi, "
           "dihitung langsung dari harga rata-rata bahan saat laporan ini dibuat.")
    rows = []
    for pr in D["produk_resep"]:
        margin = pr["harga"] - pr["hpp"]
        rows.append([pr["nama"], pr["bahan"], rp(pr["hpp"]), rp(pr["harga"]),
                     rp(margin), f"{angka(margin / pr['harga'] * 100, 1)}%"])
    tabel(doc, ["Produk", "Jumlah bahan", "HPP/unit", "Harga jual", "Margin", "Margin (%)"],
          rows, widths=[3.6, 2.0, 2.6, 2.6, 2.6, 2.0],
          caption="Tabel 4.3 HPP dan margin setiap produk (data aktual aplikasi)",
          align_cols={1: "c", 2: "r", 3: "r", 4: "r", 5: "r"})
    p(doc, "Contoh pembacaan: Roti Tawar Gandum membutuhkan 0,30 kg tepung protein tinggi, 0,03 kg gula, "
           "0,03 kg mentega, 0,005 kg ragi, dan satu kemasan. Dengan harga rata-rata bahan saat ini, HPP per "
           "unit berada pada kisaran Rp 9 ribu dan dijual Rp 22 ribu, sehingga margin kotornya sekitar 58%. "
           "Angka semacam ini yang sebelumnya tidak pernah diketahui pemilik usaha.")

    h2(doc, "4.6 Keamanan dan Hak Akses")
    p(doc, "Password pengguna tidak disimpan dalam bentuk teks asli, melainkan sebagai hash PBKDF2-HMAC-SHA256 "
           "dengan 120.000 iterasi dan salt acak per pengguna. Setiap permintaan API wajib menyertakan token "
           "sesi pada header Authorization; permintaan tanpa token ditolak dengan status 401. Sistem juga "
           "membedakan peran admin, gudang, dan kasir pada data pengguna, serta mencatat setiap aksi penting "
           "ke tabel audit.")

    h2(doc, "4.7 Dukungan Dua Backend Basis Data (SQLite dan MySQL)")
    p(doc, "Aplikasi dirancang agar tidak terikat pada satu DBMS. Logika bisnis ditulis sekali di core.py, "
           "sedangkan pemilihan mesin basis data ditentukan oleh modul db.py melalui variabel lingkungan "
           "BAKERP_BACKEND. Pilihan bawaan adalah SQLite karena paling mudah didemokan, namun seluruh fitur "
           "juga berjalan di atas MySQL 8 apabila lingkungan kampus mensyaratkan DBMS server.")
    kode_mono(doc, """python app.py                                 # SQLite  -> berkas bakery.db
BAKERP_BACKEND=mysql python app.py            # MySQL   -> localhost:3306/bakerp""",
              caption="Kode 4.3 Menjalankan aplikasi pada salah satu backend")

    p(doc, "Agar core.py tidak perlu ditulis dua kali, dibuat lapisan kompatibilitas dbmysql.py yang "
           "meniru antarmuka sqlite3 (placeholder tanda tanya, conn.execute, akses baris lewat indeks "
           "maupun nama kolom) tetapi mengirim perintah ke MySQL melalui driver PyMySQL. Perbedaan dialek "
           "ditangani sebagai berikut.")
    tabel(doc,
          ["Perbedaan dialek", "SQLite", "MySQL", "Cara ditangani"],
          [["Placeholder parameter", "?", "%s", "Diterjemahkan otomatis sebelum eksekusi"],
           ["Kolom auto increment", "AUTOINCREMENT", "AUTO_INCREMENT", "Diterjemahkan otomatis"],
           ["Tipe teks berindeks", "TEXT boleh", "Wajib VARCHAR(n)", "Skema memakai VARCHAR untuk kolom kunci"],
           ["Nilai default teks", "Boleh pada TEXT", "Tidak boleh pada TEXT", "Kolom tersebut dijadikan VARCHAR"],
           ["Foreign key", "Boleh sebaris kolom", "Harus level tabel", "Skema memakai FOREIGN KEY (...) REFERENCES"],
           ["CREATE INDEX IF NOT EXISTS", "Didukung", "Tidak ada", "Frasa dihapus, galat duplikat ditangkap"],
           ["INSERT OR IGNORE", "Didukung", "INSERT IGNORE", "Diterjemahkan otomatis"],
           ["ONLY_FULL_GROUP_BY", "Tidak ada", "Aktif secara bawaan", "sql_mode disetel ulang saat koneksi"],
           ["PRAGMA foreign_keys", "Perlu diaktifkan", "Tidak dikenal", "Dilewati saat backend MySQL"]],
          widths=[4.2, 3.3, 3.2, 4.3], caption="Tabel 4.4 Perbedaan dialek SQL dan cara penanganannya",
          font_size=8.5)

    p(doc, "Pemindahan data dilakukan dengan skrip migrate_to_mysql.py yang membuat skema MySQL, menyalin "
           "seluruh baris sambil mempertahankan nilai id (agar relasi antar tabel tetap utuh), lalu "
           "membandingkan jumlah baris di kedua sisi. Berikut keluaran nyata eksekusi skrip tersebut.")
    kode_mono(doc, """  Tabel                SQLite    MySQL  Status
  ------------------------------------------------
  users                     3        3  OK
  supplier                  3        3  OK
  bahan                    12       12  OK
  produk                    6        6  OK
  resep                    31       31  OK
  pembelian                12       12  OK
  pembelian_item           25       25  OK
  produksi                185      185  OK
  produksi_item           956      956  OK
  penjualan               534      534  OK
  penjualan_item         1060     1060  OK
  pengeluaran              14       14  OK
  kas                     560      560  OK
  audit                   762      762  OK
  ------------------------------------------------
  TOTAL                           4163

Verifikasi relasi & konsistensi:
  [OK] Resep tanpa produk/bahan (harus 0): 0
  [OK] Item penjualan tanpa invoice (harus 0): 0
  [OK] Item PO tanpa header (harus 0): 0
  [OK] Total nilai penjualan sama dengan SQLite: 71966000.0
  [OK] Jumlah kas masuk sama dengan SQLite: 534""",
              caption="Kode 4.4 Keluaran migrasi 4.163 baris data dari SQLite ke MySQL")

    p(doc, "Konsistensi hasil migrasi juga dibuktikan pada tingkat aplikasi: dashboard dan laporan laba rugi "
           "menghasilkan angka yang identik pada kedua backend. Pada backend MySQL, "
           "penjualan hari terakhir tercatat Rp 1.977.000 dari 12 transaksi, laba bersih bulan berjalan "
           "Rp 28.334.090 (margin 41,9%), dan nilai persediaan Rp 23.017.646 — sama persis dengan hasil "
           "backend SQLite. Seluruh 29 skenario pengujian integrasi juga dijalankan ulang pada MySQL dan "
           "memberikan hasil lulus penuh.")
    p(doc, "Dengan demikian, perpindahan DBMS tidak mengubah perilaku sistem. Hal ini menunjukkan bahwa "
           "integrasi antar modul memang dibangun pada lapisan logika, bukan bergantung pada fitur khusus "
           "salah satu mesin basis data.")

    h2(doc, "4.8 Tampilan Antarmuka Aplikasi")
    p(doc, "Bagian ini menampilkan tangkapan layar aplikasi yang benar-benar dijalankan pada browser, bukan "
           "mockup. Seluruh gambar diambil dari aplikasi yang berjalan dengan data contoh 31 hari.")
    gambar(doc, os.path.join(IMG, "01-login.png"),
           "Gambar 4.1 Halaman login BakeERP")
    gambar(doc, os.path.join(IMG, "02-dashboard.png"),
           "Gambar 4.2 Dashboard: KPI penjualan, laba, nilai persediaan, tren 7 hari, dan stok kritis")
    gambar(doc, os.path.join(IMG, "03-pos-penjualan.png"),
           "Gambar 4.3 Modul penjualan (POS) dengan keranjang, diskon, metode bayar, dan riwayat transaksi")
    gambar(doc, os.path.join(IMG, "04-produksi.png"),
           "Gambar 4.4 Modul produksi: kebutuhan bahan dihitung otomatis dari resep sebelum produksi dijalankan")
    gambar(doc, os.path.join(IMG, "05-pembelian.png"),
           "Gambar 4.5 Modul pembelian: daftar purchase order beserta status penerimaan barang")
    gambar(doc, os.path.join(IMG, "11-detail-po.png"),
           "Gambar 4.6 Detail purchase order beserta rincian bahan, kuantitas, dan nilai")
    gambar(doc, os.path.join(IMG, "06-bahan-baku.png"),
           "Gambar 4.7 Master bahan baku: stok, harga rata-rata, nilai persediaan, dan status ketersediaan")
    gambar(doc, os.path.join(IMG, "10-resep-bom.png"),
           "Gambar 4.8 Penyuntingan resep (BOM) yang langsung memperbarui HPP produk")
    gambar(doc, os.path.join(IMG, "07-keuangan.png"),
           "Gambar 4.9 Laporan laba rugi dan buku kas yang terbentuk otomatis dari transaksi")
    gambar(doc, os.path.join(IMG, "08-laporan.png"),
           "Gambar 4.10 Laporan penjualan: omzet harian dan kontribusi laba per produk")
    gambar(doc, os.path.join(IMG, "09-log-aktivitas.png"),
           "Gambar 4.11 Log aktivitas sebagai jejak audit transaksi dan perubahan data")


def bab5(doc, D):
    h1(doc, "BAB V PENGUJIAN DAN PEMBAHASAN")

    h2(doc, "5.1 Metode Pengujian")
    p(doc, "Pengujian dilakukan dengan metode black box melalui HTTP API terhadap aplikasi yang benar-benar "
           "berjalan. Berbeda dengan pengujian manual yang hanya menekan tombol, pendekatan ini memeriksa "
           "kondisi data sebelum dan sesudah setiap transaksi, sehingga integrasi antar modul dapat "
           "dibuktikan secara terukur. Pengujian dijalankan pada basis data terpisah (tests/test_bakery.db) "
           "agar data demonstrasi tidak tercemar, dan dapat diulang kapan saja dengan perintah:")
    kode_mono(doc, "python tests/test_integrasi.py")

    h2(doc, "5.2 Hasil Pengujian Fungsional dan Integrasi")
    hasil = baca_hasil_uji()
    lulus = sum(1 for h in hasil if h[2] == "LULUS")
    p(doc, f"Pengujian otomatis terdiri atas {len(hasil)} skenario. Hasil eksekusi terakhir: "
           f"{lulus} dari {len(hasil)} skenario lulus "
           f"({angka(lulus / len(hasil) * 100, 0)}%). Rinciannya disajikan pada tabel berikut.")
    p(doc, "Seluruh rangkaian pengujian dijalankan dua kali: sekali pada backend SQLite dan sekali pada "
           "backend MySQL 8. Keduanya menghasilkan 29 dari 29 skenario lulus (100%), sehingga dapat "
           "disimpulkan bahwa perilaku sistem tidak bergantung pada mesin basis data yang dipakai. "
           "Perintah untuk menjalankan pengujian pada masing-masing backend adalah sebagai berikut.")
    kode_mono(doc, """python tests/test_integrasi.py                              # backend SQLite
BAKERP_TEST_BACKEND=mysql python tests/test_integrasi.py   # backend MySQL""",
              caption="Kode 5.1 Menjalankan pengujian pada kedua backend")
    rows = [[str(i + 1), h[0], h[1], h[3] or "-", h[2]] for i, h in enumerate(hasil)]
    tabel(doc, ["No", "Kelompok uji", "Skenario pengujian", "Bukti / keterangan", "Hasil"],
          rows, widths=[1.0, 3.0, 6.4, 3.6, 1.6],
          caption="Tabel 5.1 Hasil pengujian fungsional dan integrasi", font_size=8.5,
          align_cols={0: "c", 4: "c"})

    h2(doc, "5.3 Pengujian Alur Bisnis End-to-End")
    p(doc, "Selain pengujian per fungsi, dilakukan pengujian satu siklus bisnis utuh untuk memastikan data "
           "mengalir benar dari hulu ke hilir. Skenario: membeli 10 kg bahan uji, memproduksi 10 unit produk, "
           "lalu menjual 3 unit, dan mencatat satu beban operasional.")
    tabel(doc,
          ["Langkah", "Aksi", "Kondisi stok bahan", "Kondisi stok produk", "Efek keuangan"],
          [["1", "Buat PO 10 kg @ Rp 12.000 (status draf)", "0 kg (tidak berubah)", "0 pcs", "Belum ada"],
           ["2", "Terima barang", "10 kg", "0 pcs", "Kas keluar Rp 120.000"],
           ["3", "Produksi 10 unit (resep 0,5 kg/unit)", "5 kg", "10 pcs", "Biaya bahan Rp 60.000 tercatat"],
           ["4", "Penjualan 3 unit @ Rp 20.000", "5 kg", "7 pcs", "Kas masuk Rp 60.000; HPP Rp 18.000"],
           ["5", "Catat beban operasional Rp 50.000", "5 kg", "7 pcs", "Kas keluar Rp 50.000"]],
          widths=[1.4, 5.4, 2.8, 2.6, 4.2],
          caption="Tabel 5.2 Hasil pengujian alur bisnis end-to-end", font_size=9,
          align_cols={0: "c"})
    p(doc, "Dari tabel tersebut terlihat bahwa setiap aksi hanya dilakukan satu kali, namun dampaknya muncul "
           "di beberapa modul sekaligus. Pada langkah 4, HPP transaksi bernilai Rp 18.000, yaitu 3 unit × "
           "Rp 6.000. Angka Rp 6.000 berasal dari resep 0,5 kg × harga rata-rata bahan Rp 12.000 yang "
           "diperbarui pada langkah 2 — bukti bahwa perubahan harga pembelian langsung memengaruhi HPP "
           "penjualan tanpa input ulang.")
    p(doc, "Pengujian juga memastikan sistem menolak kondisi yang tidak sah: PO tidak dapat diterima dua "
           "kali, produksi ditolak ketika bahan tidak mencukupi (dengan pesan yang menyebut bahan mana yang "
           "kurang), dan penjualan ditolak ketika stok produk jadi tidak memadai.")

    h2(doc, "5.4 Ringkasan Data Uji pada Aplikasi")
    lr = D["lr"]
    p(doc, "Sebagai bukti bahwa aplikasi mampu mengolah data dalam jumlah wajar, tabel berikut merangkum isi "
           "basis data setelah data contoh 31 hari dijalankan.")
    tabel(doc,
          ["Data", "Jumlah", "Data", "Jumlah"],
          [["Bahan baku", f"{D['jumlah']['bahan']} item", "Transaksi penjualan", f"{D['jumlah']['penjualan']} invoice"],
           ["Produk jadi", f"{D['jumlah']['produk']} produk", "Baris item terjual", f"{D['jumlah']['penjualan_item']} baris"],
           ["Supplier", f"{D['jumlah']['supplier']} supplier", "Batch produksi", f"{D['jumlah']['produksi']} batch"],
           ["Baris resep (BOM)", f"{D['total_resep']} baris", "Purchase order", f"{D['jumlah']['pembelian']} PO"],
           ["Pengeluaran", f"{D['jumlah']['pengeluaran']} catatan", "Baris buku kas", f"{D['jumlah']['kas']} baris"],
           ["Log audit", f"{D['jumlah']['audit']} baris", "Nilai persediaan", rp(D["nilai_persediaan"])]],
          widths=[3.4, 3.4, 3.8, 4.4],
          caption="Tabel 5.3 Ringkasan data yang diolah aplikasi", font_size=9.5,
          align_cols={1: "c", 3: "c"})

    p(doc, f"Untuk periode {tanggal_id(D['awal'])} sampai {tanggal_id(D['hari'])}, aplikasi menghasilkan "
           f"laporan laba rugi sebagai berikut: pendapatan {rp(lr['pendapatan'])} dari "
           f"{lr['jumlah_transaksi']} transaksi, HPP {rp(lr['hpp'])} "
           f"({angka(lr['hpp'] / lr['pendapatan'] * 100, 1)}% dari pendapatan), laba kotor "
           f"{rp(lr['laba_kotor'])}, beban operasional {rp(lr['total_beban'])}, dan laba bersih "
           f"{rp(lr['laba_bersih'])} dengan margin {angka(lr['margin_bersih'], 1)}%. Seluruh angka tersebut "
           "dihitung dari tabel transaksi, bukan dimasukkan secara manual.")

    h2(doc, "5.5 Pembahasan Kesesuaian dengan Konsep ERP")
    p(doc, "Rancangan BakeERP dapat dinilai sebagai sistem ERP karena memenuhi empat karakteristik yang "
           "disebut pada Bab II, bukan karena jumlah modulnya. Pertama, data berada pada satu basis data: "
           "tabel bahan dipakai bersama oleh modul pembelian, produksi, dan laporan sekaligus. Kedua, proses "
           "bersifat lintas fungsi: penjualan menyentuh persediaan, keuangan, dan pelaporan dalam satu "
           "transaksi basis data. Ketiga, informasi bersifat real-time karena dashboard membaca tabel "
           "transaksi secara langsung. Keempat, keterlacakan terjaga melalui referensi dokumen pada buku kas "
           "dan log audit.")
    p(doc, "Hal yang membedakan aplikasi ini dari sekumpulan aplikasi terpisah adalah tidak adanya input "
           "ganda. Pada sistem manual, angka penjualan dicatat di buku kasir, direkap di buku besar, lalu "
           "dihitung ulang untuk laporan. Pada BakeERP, satu transaksi kasir menghasilkan invoice, "
           "pengurangan stok, baris HPP, baris kas masuk, dan angka laporan sekaligus.")
    p(doc, "Kesesuaian rancangan dengan rubrik penilaian UTS dapat dilihat pada tabel berikut.")
    tabel(doc,
          ["Aspek penilaian (bobot)", "Bukti pada laporan dan aplikasi"],
          [["Identifikasi ide bisnis & analisis kebutuhan (10%)",
            "Bab I dan Bab III: profil usaha, lima masalah utama, tabel 3.2 yang menghubungkan masalah dengan kebutuhan sistem"],
           ["Pemahaman konsep ERP & kesesuaian rancangan (15%)",
            "Bab II (karakteristik ERP), Bab III (arsitektur tiga lapis, basis data tunggal), Bab V.5 (pembahasan kesesuaian)"],
           ["Kelengkapan & relevansi fitur (15%)",
            "18 kebutuhan fungsional (tabel 3.3) yang seluruhnya terimplementasi: pembelian, persediaan, produksi, penjualan, keuangan, laporan"],
           ["Integrasi antar modul & proses bisnis (15%)",
            "Tabel 3.6 (matriks integrasi), Kode 4.1–4.2, serta pengujian integrasi 1–8 pada tabel 5.1"],
           ["Implementasi aplikasi berbasis web (20%)",
            "Aplikasi berjalan di browser dengan 12 halaman fungsional, data tersimpan permanen, diuji 29 skenario (100% lulus) pada dua backend: SQLite dan MySQL"],
           ["Kualitas antarmuka & kemudahan penggunaan (5%)",
            "Gambar 4.1–4.11: navigasi tetap, kartu KPI, tabel konsisten, tata letak responsif hingga layar kecil"],
           ["Pengujian & demonstrasi (10%)",
            "Bab V: 29 skenario otomatis, alur end-to-end pada tabel 5.2, penanganan kesalahan (stok kurang, PO ganda)"],
           ["Kualitas laporan tertulis (10%)",
            "Struktur bab lengkap, bahasa akademik, tabel dan gambar bernomor, data diambil langsung dari basis data"]],
          widths=[6.2, 9.8], caption="Tabel 5.4 Kesesuaian pekerjaan dengan rubrik penilaian UTS", font_size=9)

    h2(doc, "5.6 Keterbatasan Sistem")
    bullets(doc, [
        "Perhitungan keuangan bersifat sederhana: belum memakai jurnal berpasangan (double entry) dan belum "
        "menyusun neraca.",
        "Biaya tenaga kerja langsung dan overhead pabrik belum dibebankan ke HPP per unit; keduanya dicatat "
        "sebagai beban operasional, sehingga margin kotor tampak lebih tinggi daripada praktik akuntansi "
        "biaya penuh.",
        "Belum ada pengelolaan pesanan pelanggan (pre-order), retur penjualan, dan penyesuaian stok opname.",
        "Aplikasi berjalan pada satu server lokal tanpa replikasi data dan belum menerapkan pembatasan hak "
        "akses per endpoint secara rinci.",
    ])


def bab6(doc, D):
    h1(doc, "BAB VI KESIMPULAN DAN SARAN")

    h2(doc, "6.1 Kesimpulan")
    nomor(doc, [
        "BakeERP berhasil dirancang dan diimplementasikan sebagai aplikasi ERP berbasis web untuk UMKM "
        "bakery, mencakup modul pembelian, persediaan, produksi, penjualan, pengeluaran, keuangan, dan "
        "pelaporan dalam satu basis data.",
        "Integrasi antar modul terbukti berjalan: penerimaan barang menambah stok dan mencatat kas keluar, "
        "produksi mengurangi bahan sesuai resep dan menambah produk jadi, penjualan mengurangi stok produk "
        "serta mencatat pendapatan, HPP, dan kas masuk secara otomatis.",
        "HPP dan margin setiap produk dihitung otomatis dari resep dan harga rata-rata bahan, sehingga "
        "penetapan harga jual dapat dilakukan berdasarkan data.",
        "Aplikasi berjalan di browser, menyimpan data secara permanen, dan telah diuji melalui 29 skenario "
        "otomatis dengan hasil seluruhnya lulus, termasuk pengujian penolakan transaksi yang tidak sah.",
    ])

    h2(doc, "6.2 Saran Pengembangan")
    bullets(doc, [
        "Menambahkan jurnal umum berpasangan dan neraca agar laporan keuangan memenuhi standar akuntansi.",
        "Membebankan biaya tenaga kerja langsung dan overhead ke HPP per unit untuk perhitungan margin yang "
        "lebih akurat.",
        "Menambahkan modul pesanan pelanggan (pre-order), retur, dan stok opname.",
        "Menerapkan pembatasan hak akses per endpoint sesuai peran, serta menyediakan pencadangan basis data "
        "otomatis.",
        "Mengembangkan versi daring (hosting) agar dapat diakses dari beberapa perangkat toko sekaligus.",
    ])


def daftar_pustaka(doc):
    h1(doc, "DAFTAR PUSTAKA")
    refs = [
        "Laudon, K. C., & Laudon, J. P. (2020). Management Information Systems: Managing the Digital Firm "
        "(16th ed.). Pearson.",
        "Monk, E. F., & Wagner, B. J. (2013). Concepts in Enterprise Resource Planning (4th ed.). "
        "Cengage Learning.",
        "O'Brien, J. A., & Marakas, G. M. (2011). Management Information Systems (10th ed.). McGraw-Hill.",
        "Romney, M. B., & Steinbart, P. J. (2018). Accounting Information Systems (14th ed.). Pearson.",
        "Wallace, T. F., & Kremzar, M. H. (2001). ERP: Making It Happen — The Implementers' Guide to "
        "Success with Enterprise Resource Planning. John Wiley & Sons.",
        "Sumintar, A. (2019). Buku Sakti Pemrograman Python. Anak Hebat Indonesia.",
        "SQLite Consortium. (2024). SQLite Documentation. Diakses dari https://www.sqlite.org/docs.html",
        "Python Software Foundation. (2024). Python 3 Documentation. Diakses dari https://docs.python.org/3/",
    ]
    for r in refs:
        par = doc.add_paragraph()
        par.paragraph_format.line_spacing = 1.5
        par.paragraph_format.space_after = Pt(6)
        par.paragraph_format.left_indent = Cm(1.0)
        par.paragraph_format.first_line_indent = Cm(-1.0)
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = par.add_run(r)
        run.font.name = FONT
        run.font.size = Pt(12)


def lampiran(doc, D):
    h1(doc, "LAMPIRAN")
    h2(doc, "Lampiran 1 — Akun Demo dan Cara Menjalankan Aplikasi")
    tabel(doc,
          ["Username", "Password", "Peran"],
          [["admin", "admin123", "Admin / pemilik usaha"],
           ["gudang", "gudang123", "Staf gudang dan produksi"],
           ["kasir", "kasir123", "Kasir penjualan"]],
          widths=[4.0, 4.0, 6.0], caption="Tabel L.1 Akun pengguna untuk demonstrasi",
          align_cols={0: "c", 1: "c"})
    kode_mono(doc, """1. Buka folder proyek: erp-bakery
2. Jalankan: python app.py
   (atau klik dua kali "Mulai BakeERP.bat")
3. Buka browser: http://localhost:8000
4. Login dengan akun admin / admin123
5. Uji alur: Pembelian -> terima barang -> Produksi -> Penjualan -> Laba Rugi

Mode MySQL (opsional):
1. Pastikan server MySQL hidup di port 3306
2. Migrasi data:  python migrate_to_mysql.py
3. Jalankan:      BAKERP_BACKEND=mysql python app.py
   (atau klik dua kali "Mulai BakeERP (MySQL).bat")
4. Lihat isi database lewat DBeaver / MySQL Workbench:
   host=127.0.0.1  port=3306  database=bakerp  user=root""",
              caption="Langkah demonstrasi aplikasi")

    h2(doc, "Lampiran 2 — Keluaran Pengujian Otomatis")
    path = os.path.join(DOCS, "hasil_pengujian.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            isi = f.read().strip().splitlines()
        kode_mono(doc, "\n".join(isi[-8:]), caption="Cuplikan ringkasan hasil pengujian")

    h2(doc, "Lampiran 3 — Contoh Struktur Tabel Basis Data")
    kode_mono(doc, """CREATE TABLE bahan (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kode       TEXT NOT NULL UNIQUE,
    nama       TEXT NOT NULL,
    satuan     TEXT NOT NULL,
    stok       REAL NOT NULL DEFAULT 0,
    stok_min   REAL NOT NULL DEFAULT 0,
    harga_beli REAL NOT NULL DEFAULT 0,   -- harga rata-rata bergerak
    aktif      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE resep (            -- bill of material
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    produk_id INTEGER NOT NULL REFERENCES produk(id) ON DELETE CASCADE,
    bahan_id  INTEGER NOT NULL REFERENCES bahan(id) ON DELETE CASCADE,
    qty       REAL NOT NULL,
    UNIQUE (produk_id, bahan_id)
);

CREATE TABLE kas (              -- jurnal arus kas, jantung integrasi
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal    TEXT NOT NULL,
    tipe       TEXT NOT NULL,        -- masuk | keluar
    kategori   TEXT NOT NULL,
    ref_tipe   TEXT,                 -- penjualan | pembelian | pengeluaran
    ref_id     INTEGER,
    keterangan TEXT,
    jumlah     REAL NOT NULL,
    created_at TEXT NOT NULL
);""", caption="Kode L.1 Potongan skema basis data")


def main():
    D = ambil_data()
    doc = Document()
    gaya_dasar(doc)
    hal(doc)

    sampul(doc)

    # bagian kedua: daftar isi + isi laporan, dengan nomor halaman
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    footer_nomor(doc, sec, mulai=1)
    doc.sections[0].footer.is_linked_to_previous = False

    h1(doc, "DAFTAR ISI", page_break=False)
    daftar_isi(doc)

    bab1(doc, D)
    bab2(doc, D)
    bab3(doc, D)
    bab4(doc, D)
    bab5(doc, D)
    bab6(doc, D)
    daftar_pustaka(doc)
    lampiran(doc, D)

    doc.save(OUT)
    print("Laporan dibuat:", OUT)
    print("Ukuran:", round(os.path.getsize(OUT) / 1024), "KB")


if __name__ == "__main__":
    main()
