/* ==========================================================================
   BakeERP — API lokal (mode demo statis)
   ==========================================================================
   Berkas ini menggantikan server Python ketika aplikasi dijalankan sebagai
   halaman statis (mis. GitHub Pages). Seluruh aturan bisnis dari core.py
   ditulis ulang di sini agar berjalan di browser:

     pembelian -> stok bahan naik + harga rata-rata + kas keluar
     produksi  -> bahan turun sesuai resep + produk jadi naik
     penjualan -> produk turun + pendapatan + HPP + kas masuk
     keuangan  -> laba kotor / laba bersih dihitung dari transaksi

   Data disimpan di localStorage peramban pengunjung, sehingga setiap orang
   mendapat salinan sendiri dan bisa mencoba tanpa merusak data orang lain.

   PENTING: ini hanya untuk DEMONSTRASI. Aplikasi sebenarnya memakai
   app.py + core.py dengan basis data SQLite/MySQL yang sesungguhnya.
   ========================================================================== */

(function () {
  'use strict';

  const STORE_KEY = 'bakerp_demo_db_v1';
  const TOKEN_KEY = 'bakerp_demo_token';
  const DATA_URL = 'data.json';

  let DB = null;
  let SIAP = null;

  /* ---------------- Utilitas ---------------- */
  const r2 = (x) => Math.round((Number(x) || 0) * 100) / 100;
  const pad = (n, w) => String(n).padStart(w, '0');

  function nowStr() {
    const d = new Date();
    const p = (n) => pad(n, 2);
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
           `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  }

  function todayISO() {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function firstOfMonthISO() {
    return todayISO().slice(0, 8) + '01';
  }

  function galat(pesan, status) {
    const e = new Error(pesan);
    e.status = status || 400;
    throw e;
  }

  /* ---------------- Penyimpanan ---------------- */
  function simpan() {
    try {
      localStorage.setItem(STORE_KEY, JSON.stringify(DB));
    } catch (e) {
      // Kuota penuh: tetap jalan di memori saja
      console.warn('Gagal menyimpan ke localStorage:', e);
    }
  }

  function muat() {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        const d = JSON.parse(raw);
        if (d && d.bahan && d.produk) return d;
      }
    } catch (e) {
      console.warn('Data tersimpan rusak, memuat ulang dari data.json', e);
    }
    return null;
  }

  function reset() {
    localStorage.removeItem(STORE_KEY);
    DB = null;
    SIAP = null;
    return muatData();
  }

  function muatData() {
    if (SIAP) return SIAP;
    const tersimpan = muat();
    if (tersimpan) {
      DB = tersimpan;
      SIAP = Promise.resolve(DB);
      return SIAP;
    }
    SIAP = fetch(DATA_URL, { cache: 'no-store' })
      .then((r) => {
        if (!r.ok) throw new Error('Gagal memuat data demo (' + r.status + ')');
        return r.json();
      })
      .then((d) => {
        // pastikan setiap tabel ada
        ['users', 'supplier', 'bahan', 'produk', 'resep', 'pembelian', 'pembelian_item',
         'produksi', 'produksi_item', 'penjualan', 'penjualan_item', 'pengeluaran',
         'kas', 'audit'].forEach((t) => { if (!Array.isArray(d[t])) d[t] = []; });
        DB = d;
        simpan();
        return DB;
      });
    return SIAP;
  }

  /* ---------------- Nomor dokumen ---------------- */
  function nextNumber(tabel, prefix) {
    const tahun = new Date().getFullYear();
    const awalan = `${prefix}-${tahun}-`;
    let maks = 0;
    DB[tabel].forEach((row) => {
      const no = row.no_po || row.no_batch || row.no_invoice || '';
      if (no.indexOf(awalan) === 0) {
        const n = parseInt(no.slice(awalan.length), 10);
        if (!isNaN(n) && n > maks) maks = n;
      }
    });
    return awalan + pad(maks + 1, 4);
  }

  function idBaru(tabel) {
    return DB[tabel].reduce((m, r) => Math.max(m, r.id || 0), 0) + 1;
  }

  function audit(user, aksi, detail) {
    DB.audit.push({
      id: idBaru('audit'), waktu: nowStr(), user: user || 'demo',
      aksi: aksi, detail: detail || ''
    });
  }

  /* ---------------- Autentikasi (PBKDF2, sama seperti server) ---------------- */
  async function hashPassword(password, salt) {
    if (!(window.crypto && window.crypto.subtle)) {
      // Peramban tanpa WebCrypto (mis. halaman file:// pada sebagian browser)
      return null;
    }
    const enc = new TextEncoder();
    const kunci = await crypto.subtle.importKey(
      'raw', enc.encode(password), { name: 'PBKDF2' }, false, ['deriveBits']);
    const bits = await crypto.subtle.deriveBits(
      { name: 'PBKDF2', salt: enc.encode(salt), iterations: 120000, hash: 'SHA-256' },
      kunci, 256);
    return Array.from(new Uint8Array(bits)).map((b) => pad(b.toString(16), 2)).join('');
  }

  async function authenticate(username, password) {
    const u = DB.users.find((x) => x.username === username && x.aktif !== 0);
    if (!u) galat('Username tidak ditemukan.');
    let cocok = false;
    const h = await hashPassword(password, u.salt);
    if (h) {
      cocok = h === u.password_hash;
    } else {
      // Cadangan bila WebCrypto tidak tersedia: cocokkan kata sandi demo
      const demo = { admin: 'admin123', gudang: 'gudang123', kasir: 'kasir123' };
      cocok = demo[username] === password;
    }
    if (!cocok) galat('Password salah.');
    audit(u.nama, 'LOGIN', 'role=' + u.role);
    simpan();
    return { id: u.id, username: u.username, nama: u.nama, role: u.role };
  }

  /* ---------------- Perhitungan ---------------- */
  function hppUnit(produkId) {
    return r2(DB.resep
      .filter((r) => r.produk_id === produkId)
      .reduce((a, r) => {
        const b = DB.bahan.find((x) => x.id === r.bahan_id);
        return a + (b ? r.qty * b.harga_beli : 0);
      }, 0));
  }

  function getResep(produkId) {
    return DB.resep
      .filter((r) => r.produk_id === produkId)
      .map((r) => {
        const b = DB.bahan.find((x) => x.id === r.bahan_id) || {};
        return {
          id: r.id, bahan_id: r.bahan_id, qty: r.qty,
          nama: b.nama, satuan: b.satuan, harga_beli: b.harga_beli, stok: b.stok,
          subtotal: r2(r.qty * (b.harga_beli || 0))
        };
      })
      .sort((a, b) => String(a.nama).localeCompare(String(b.nama)));
  }

  function cekKebutuhan(produkId, qty) {
    const resep = getResep(produkId);
    if (!resep.length) galat('Produk ini belum memiliki resep. Lengkapi resep terlebih dahulu.');
    return resep.map((r) => {
      const butuh = r2(r.qty * qty);
      return {
        bahan_id: r.bahan_id, nama: r.nama, satuan: r.satuan,
        butuh: butuh, stok: r2(r.stok), cukup: r.stok >= butuh,
        subtotal: r2(butuh * r.harga_beli)
      };
    });
  }

  function labaRugi(dari, sampai) {
    const dalam = (t) => t >= dari && t <= sampai;
    const pj = DB.penjualan.filter((p) => dalam(p.tanggal));
    const pendapatan = r2(pj.reduce((a, p) => a + p.total, 0));
    const hpp = r2(pj.reduce((a, p) => a + p.hpp, 0));

    const peta = {};
    DB.pengeluaran.filter((e) => dalam(e.tanggal)).forEach((e) => {
      peta[e.kategori] = (peta[e.kategori] || 0) + e.jumlah;
    });
    const beban = Object.keys(peta)
      .map((k) => ({ kategori: k, jumlah: r2(peta[k]) }))
      .sort((a, b) => b.jumlah - a.jumlah);
    const totalBeban = r2(beban.reduce((a, b) => a + b.jumlah, 0));

    const labaKotor = r2(pendapatan - hpp);
    const labaBersih = r2(labaKotor - totalBeban);
    const beli = DB.pembelian
      .filter((p) => p.status === 'diterima' && dalam(p.tanggal))
      .reduce((a, p) => a + p.total, 0);

    return {
      dari: dari, sampai: sampai,
      pendapatan: pendapatan, hpp: hpp,
      laba_kotor: labaKotor,
      margin_kotor: pendapatan ? r2((labaKotor / pendapatan) * 100) : 0,
      beban: beban, total_beban: totalBeban,
      laba_bersih: labaBersih,
      margin_bersih: pendapatan ? r2((labaBersih / pendapatan) * 100) : 0,
      jumlah_transaksi: pj.length,
      pembelian_bahan: r2(beli)
    };
  }

  function dashboard() {
    const hari = todayISO();
    const awal = firstOfMonthISO();
    const pjHari = DB.penjualan.filter((p) => p.tanggal === hari);
    const lr = labaRugi(awal, hari);

    const kritis = [];
    DB.bahan.forEach((b) => {
      if (b.stok <= b.stok_min) kritis.push({
        jenis: 'Bahan', kode: b.kode, nama: b.nama,
        stok: b.stok, stok_min: b.stok_min, satuan: b.satuan
      });
    });
    DB.produk.forEach((p) => {
      if (p.stok <= p.stok_min) kritis.push({
        jenis: 'Produk', kode: p.kode, nama: p.nama,
        stok: p.stok, stok_min: p.stok_min, satuan: 'pcs'
      });
    });

    const nilaiBahan = DB.bahan.reduce((a, b) => a + b.stok * b.harga_beli, 0);
    const nilaiProduk = DB.produk.reduce((a, p) => a + p.stok * hppUnit(p.id), 0);

    const tren = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const iso = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
      tren.push({
        tanggal: iso,
        total: r2(DB.penjualan.filter((p) => p.tanggal === iso).reduce((a, p) => a + p.total, 0))
      });
    }

    // Produk terlaris 30 hari
    const batas = new Date();
    batas.setDate(batas.getDate() - 30);
    const batasISO = new Date(batas.getTime() - batas.getTimezoneOffset() * 60000)
      .toISOString().slice(0, 10);
    const petaTop = {};
    DB.penjualan_item.forEach((it) => {
      const jual = DB.penjualan.find((s) => s.id === it.penjualan_id);
      if (!jual || jual.tanggal < batasISO) return;
      const p = DB.produk.find((x) => x.id === it.produk_id);
      if (!p) return;
      const k = p.id;
      if (!petaTop[k]) petaTop[k] = { nama: p.nama, qty: 0, omzet: 0 };
      petaTop[k].qty += it.qty;
      petaTop[k].omzet += it.subtotal;
    });
    const top = Object.values(petaTop)
      .sort((a, b) => b.qty - a.qty).slice(0, 5)
      .map((x) => ({ nama: x.nama, qty: r2(x.qty), omzet: r2(x.omzet) }));

    const terbaru = DB.penjualan.slice(-5).reverse()
      .map((p) => ({ no_invoice: p.no_invoice, tanggal: p.tanggal, total: p.total, metode: p.metode }));

    return {
      penjualan_hari_ini: r2(pjHari.reduce((a, p) => a + p.total, 0)),
      transaksi_hari_ini: pjHari.length,
      laba_bulan_ini: lr.laba_bersih,
      pendapatan_bulan_ini: lr.pendapatan,
      margin_bulan_ini: lr.margin_bersih,
      nilai_persediaan: r2(nilaiBahan + nilaiProduk),
      nilai_bahan: r2(nilaiBahan),
      nilai_produk: r2(nilaiProduk),
      stok_kritis: kritis,
      tren: tren,
      top_produk: top,
      transaksi_terbaru: terbaru,
      jumlah_po_draft: DB.pembelian.filter((p) => p.status === 'draft').length
    };
  }

  function laporanStok() {
    const bahan = DB.bahan.map((b) => ({
      kode: b.kode, nama: b.nama, satuan: b.satuan, stok: b.stok,
      stok_min: b.stok_min, harga_beli: b.harga_beli,
      nilai: r2(b.stok * b.harga_beli)
    })).sort((a, b) => String(a.nama).localeCompare(String(b.nama)));

    const produk = DB.produk.map((p) => {
      const hpp = hppUnit(p.id);
      return Object.assign({}, p, { hpp: hpp, margin: r2(p.harga_jual - hpp) });
    }).sort((a, b) => String(a.nama).localeCompare(String(b.nama)));

    return { bahan: bahan, produk: produk };
  }

  function laporanPenjualan(dari, sampai) {
    const pj = DB.penjualan.filter((p) => p.tanggal >= dari && p.tanggal <= sampai);
    const petaHari = {};
    pj.forEach((p) => {
      if (!petaHari[p.tanggal]) petaHari[p.tanggal] = { tanggal: p.tanggal, trx: 0, omzet: 0, hpp: 0 };
      petaHari[p.tanggal].trx += 1;
      petaHari[p.tanggal].omzet += p.total;
      petaHari[p.tanggal].hpp += p.hpp;
    });
    const harian = Object.values(petaHari).sort((a, b) => a.tanggal < b.tanggal ? -1 : 1)
      .map((h) => ({ tanggal: h.tanggal, trx: h.trx, omzet: r2(h.omzet), hpp: r2(h.hpp) }));

    const petaProduk = {};
    DB.penjualan_item.forEach((it) => {
      const jual = DB.penjualan.find((s) => s.id === it.penjualan_id);
      if (!jual || jual.tanggal < dari || jual.tanggal > sampai) return;
      const p = DB.produk.find((x) => x.id === it.produk_id);
      if (!p) return;
      if (!petaProduk[p.id]) petaProduk[p.id] = { nama: p.nama, qty: 0, omzet: 0, hpp: 0 };
      petaProduk[p.id].qty += it.qty;
      petaProduk[p.id].omzet += it.subtotal;
      petaProduk[p.id].hpp += it.hpp;
    });
    const perProduk = Object.values(petaProduk)
      .sort((a, b) => b.omzet - a.omzet)
      .map((x) => ({ nama: x.nama, qty: r2(x.qty), omzet: r2(x.omzet), hpp: r2(x.hpp) }));

    return { harian: harian, per_produk: perProduk };
  }

  function laporanProduksi(dari, sampai) {
    return DB.produksi
      .filter((p) => p.tanggal >= dari && p.tanggal <= sampai)
      .map((p) => {
        const pr = DB.produk.find((x) => x.id === p.produk_id) || {};
        return {
          no_batch: p.no_batch, tanggal: p.tanggal, produk: pr.nama,
          qty: p.qty, biaya_bahan: p.biaya_bahan,
          hpp_unit: r2(p.biaya_bahan / (p.qty || 1))
        };
      })
      .sort((a, b) => a.tanggal < b.tanggal ? 1 : -1);
  }

  function bukuKas(dari, sampai) {
    return DB.kas
      .filter((k) => k.tanggal >= dari && k.tanggal <= sampai)
      .sort((a, b) => b.id - a.id)
      .slice(0, 300);
  }

  /* ---------------- Aksi transaksi ---------------- */
  function buatPembelian(body, user) {
    const supplierId = Number(body.supplier_id || 0);
    if (!supplierId) galat('Supplier wajib dipilih.');
    const items = (body.items || []).filter((i) => Number(i.qty) > 0);
    if (!items.length) galat('Minimal satu bahan dengan jumlah > 0.');

    const id = idBaru('pembelian');
    const noPo = nextNumber('pembelian', 'PO');
    const tanggal = body.tanggal || todayISO();
    let total = 0;

    const rinci = items.map((it) => {
      const qty = Number(it.qty);
      const harga = Number(it.harga || 0);
      const sub = r2(qty * harga);
      total += sub;
      return {
        id: idBaru('pembelian_item') + items.indexOf(it), pembelian_id: id,
        bahan_id: Number(it.bahan_id), qty: qty, harga: harga, subtotal: sub
      };
    });

    DB.pembelian.push({
      id: id, no_po: noPo, tanggal: tanggal, supplier_id: supplierId,
      total: r2(total), status: 'draft', user_id: user ? user.id : null,
      created_at: nowStr()
    });
    rinci.forEach((r) => DB.pembelian_item.push(r));
    audit(user && user.nama, 'BUAT_PO', `${noPo} total=${r2(total)}`);
    simpan();
    return { id: id, no_po: noPo, total: r2(total) };
  }

  function terimaPembelian(id, user) {
    const head = DB.pembelian.find((p) => p.id === id);
    if (!head) galat('Purchase order tidak ditemukan.');
    if (head.status === 'diterima') galat('PO ini sudah diterima sebelumnya.');
    const items = DB.pembelian_item.filter((i) => i.pembelian_id === id);
    if (!items.length) galat('PO tidak memiliki item.');

    items.forEach((it) => {
      const b = DB.bahan.find((x) => x.id === it.bahan_id);
      if (!b) return;
      const stokLama = Number(b.stok);
      const qty = Number(it.qty);
      const stokBaru = stokLama + qty;
      const hargaBaru = stokBaru > 0
        ? ((stokLama * b.harga_beli) + (qty * it.harga)) / stokBaru
        : it.harga;
      b.stok = r2(stokBaru);
      b.harga_beli = r2(hargaBaru);
    });

    head.status = 'diterima';
    DB.kas.push({
      id: idBaru('kas'), tanggal: head.tanggal, tipe: 'keluar',
      kategori: 'Pembelian Bahan', ref_tipe: 'pembelian', ref_id: id,
      keterangan: 'Pembayaran ' + head.no_po, jumlah: head.total, created_at: nowStr()
    });
    audit(user && user.nama, 'TERIMA_PO',
      `${head.no_po} -> stok bertambah, kas keluar ${head.total}`);
    simpan();
    return { status: 'diterima', no_po: head.no_po };
  }

  function buatProduksi(body, user) {
    const produkId = Number(body.produk_id || 0);
    const qty = Number(body.qty || 0);
    if (!produkId || qty <= 0) galat('Produk dan jumlah produksi wajib diisi.');

    const kebutuhan = cekKebutuhan(produkId, qty);
    const kurang = kebutuhan.filter((k) => !k.cukup);
    if (kurang.length) {
      galat('Stok bahan baku tidak mencukupi: ' + kurang
        .map((k) => `${k.nama} butuh ${k.butuh} ${k.satuan} (stok ${k.stok})`).join(', '));
    }

    const id = idBaru('produksi');
    const noBatch = nextNumber('produksi', 'PRD');
    const biaya = r2(kebutuhan.reduce((a, k) => a + k.subtotal, 0));
    const tanggal = body.tanggal || todayISO();

    DB.produksi.push({
      id: id, no_batch: noBatch, tanggal: tanggal, produk_id: produkId,
      qty: qty, biaya_bahan: biaya, user_id: user ? user.id : null,
      catatan: body.catatan || '', created_at: nowStr()
    });

    kebutuhan.forEach((k) => {
      DB.produksi_item.push({
        id: idBaru('produksi_item'), produksi_id: id, bahan_id: k.bahan_id,
        qty: k.butuh, harga: k.butuh ? r2(k.subtotal / k.butuh) : 0, subtotal: k.subtotal
      });
      const b = DB.bahan.find((x) => x.id === k.bahan_id);
      if (b) b.stok = r2(b.stok - k.butuh);
    });

    const p = DB.produk.find((x) => x.id === produkId);
    if (p) p.stok = r2(p.stok + qty);

    audit(user && user.nama, 'PRODUKSI',
      `${noBatch} ${p ? p.nama : ''} ${qty} pcs, biaya bahan ${biaya}`);
    simpan();
    return { id: id, no_batch: noBatch, biaya_bahan: biaya, qty: qty };
  }

  function buatPenjualan(body, user) {
    const items = (body.items || []).filter((i) => Number(i.qty) > 0);
    if (!items.length) galat('Keranjang masih kosong.');

    let subtotal = 0;
    let totalHpp = 0;
    const siap = [];

    items.forEach((it) => {
      const pid = Number(it.produk_id);
      const qty = Number(it.qty);
      const p = DB.produk.find((x) => x.id === pid);
      if (!p) galat('Produk tidak ditemukan.');
      if (p.stok < qty) {
        galat(`Stok ${p.nama} tidak cukup (tersedia ${r2(p.stok)}). ` +
              'Lakukan produksi terlebih dahulu.');
      }
      const harga = Number(it.harga || p.harga_jual);
      const sub = r2(harga * qty);
      const hpp = r2(hppUnit(pid) * qty);
      subtotal += sub;
      totalHpp += hpp;
      siap.push({ pid: pid, qty: qty, harga: harga, sub: sub, hpp: hpp });
    });

    const diskon = Number(body.diskon || 0);
    const total = r2(Math.max(subtotal - diskon, 0));
    const metode = body.metode || 'Tunai';
    const id = idBaru('penjualan');
    const noInv = nextNumber('penjualan', 'INV');
    const tanggal = body.tanggal || todayISO();

    DB.penjualan.push({
      id: id, no_invoice: noInv, tanggal: tanggal,
      subtotal: r2(subtotal), diskon: r2(diskon), total: total,
      hpp: r2(totalHpp), metode: metode,
      user_id: user ? user.id : null, created_at: nowStr()
    });

    siap.forEach((s) => {
      DB.penjualan_item.push({
        id: idBaru('penjualan_item'), penjualan_id: id, produk_id: s.pid,
        qty: s.qty, harga: s.harga, subtotal: s.sub, hpp: s.hpp
      });
      const p = DB.produk.find((x) => x.id === s.pid);
      if (p) p.stok = r2(p.stok - s.qty);
    });

    DB.kas.push({
      id: idBaru('kas'), tanggal: tanggal, tipe: 'masuk', kategori: 'Penjualan',
      ref_tipe: 'penjualan', ref_id: id,
      keterangan: `Penjualan ${noInv} (${metode})`, jumlah: total, created_at: nowStr()
    });

    audit(user && user.nama, 'PENJUALAN', `${noInv} total=${total} hpp=${r2(totalHpp)}`);
    simpan();
    return { id: id, no_invoice: noInv, total: total, hpp: r2(totalHpp) };
  }

  function buatPengeluaran(body, user) {
    const jumlah = Number(body.jumlah || 0);
    if (jumlah <= 0) galat('Jumlah pengeluaran harus lebih dari 0.');
    const id = idBaru('pengeluaran');
    const tanggal = body.tanggal || todayISO();
    const kategori = body.kategori || 'Operasional';

    DB.pengeluaran.push({
      id: id, tanggal: tanggal, kategori: kategori,
      keterangan: body.keterangan || '', jumlah: r2(jumlah),
      user_id: user ? user.id : null
    });
    DB.kas.push({
      id: idBaru('kas'), tanggal: tanggal, tipe: 'keluar', kategori: kategori,
      ref_tipe: 'pengeluaran', ref_id: id,
      keterangan: body.keterangan || 'Pengeluaran operasional',
      jumlah: r2(jumlah), created_at: nowStr()
    });
    audit(user && user.nama, 'PENGELUARAN', `${kategori} ${r2(jumlah)}`);
    simpan();
    return { id: id };
  }

  /* ---------------- Master data ---------------- */
  function simpanBahan(body, user) {
    const nama = String(body.nama || '').trim();
    if (!nama) galat('Nama bahan baku wajib diisi.');
    if (body.id) {
      const b = DB.bahan.find((x) => x.id === Number(body.id));
      if (!b) galat('Bahan tidak ditemukan.');
      b.kode = body.kode || b.kode;
      b.nama = nama;
      b.satuan = body.satuan || 'kg';
      b.stok_min = Number(body.stok_min || 0);
      b.harga_beli = Number(body.harga_beli || 0);
      audit(user && user.nama, 'UBAH_BAHAN', `${b.kode} ${nama}`);
      simpan();
      return { id: b.id };
    }
    const id = idBaru('bahan');
    DB.bahan.push({
      id: id, kode: body.kode || ('BH-' + pad(id, 3)), nama: nama,
      satuan: body.satuan || 'kg', stok: Number(body.stok || 0),
      stok_min: Number(body.stok_min || 0), harga_beli: Number(body.harga_beli || 0),
      aktif: 1
    });
    audit(user && user.nama, 'TAMBAH_BAHAN', nama);
    simpan();
    return { id: id };
  }

  function simpanProduk(body, user) {
    const nama = String(body.nama || '').trim();
    if (!nama) galat('Nama produk wajib diisi.');
    if (body.id) {
      const p = DB.produk.find((x) => x.id === Number(body.id));
      if (!p) galat('Produk tidak ditemukan.');
      p.kode = body.kode || p.kode;
      p.nama = nama;
      p.kategori = body.kategori || 'Roti';
      p.harga_jual = Number(body.harga_jual || 0);
      p.stok_min = Number(body.stok_min || 0);
      audit(user && user.nama, 'UBAH_PRODUK', `${p.kode} ${nama}`);
      simpan();
      return { id: p.id };
    }
    const id = idBaru('produk');
    DB.produk.push({
      id: id, kode: body.kode || ('PR-' + pad(id, 3)), nama: nama,
      kategori: body.kategori || 'Roti', harga_jual: Number(body.harga_jual || 0),
      stok: Number(body.stok || 0), stok_min: Number(body.stok_min || 0), aktif: 1
    });
    audit(user && user.nama, 'TAMBAH_PRODUK', nama);
    simpan();
    return { id: id };
  }

  function simpanSupplier(body, user) {
    const nama = String(body.nama || '').trim();
    if (!nama) galat('Nama supplier wajib diisi.');
    if (body.id) {
      const s = DB.supplier.find((x) => x.id === Number(body.id));
      if (!s) galat('Supplier tidak ditemukan.');
      s.nama = nama;
      s.kontak = body.kontak || '';
      s.telepon = body.telepon || '';
      s.alamat = body.alamat || '';
      audit(user && user.nama, 'UBAH_SUPPLIER', nama);
      simpan();
      return { id: s.id };
    }
    const id = idBaru('supplier');
    DB.supplier.push({
      id: id, nama: nama, kontak: body.kontak || '',
      telepon: body.telepon || '', alamat: body.alamat || '', aktif: 1
    });
    audit(user && user.nama, 'TAMBAH_SUPPLIER', nama);
    simpan();
    return { id: id };
  }

  function hapusMaster(tabel, id, user) {
    const i = DB[tabel].findIndex((x) => x.id === id);
    if (i < 0) galat('Data tidak ditemukan.');
    // tolak bila sudah dipakai transaksi
    const dipakai = {
      bahan: () => DB.resep.some((r) => r.bahan_id === id) ||
                   DB.pembelian_item.some((r) => r.bahan_id === id),
      produk: () => DB.resep.some((r) => r.produk_id === id) ||
                    DB.penjualan_item.some((r) => r.produk_id === id),
      supplier: () => DB.pembelian.some((r) => r.supplier_id === id)
    };
    if (dipakai[tabel] && dipakai[tabel]()) {
      galat('Data tidak bisa dihapus karena sudah dipakai pada transaksi. ' +
            'Nonaktifkan saja datanya.');
    }
    DB[tabel].splice(i, 1);
    audit(user && user.nama, 'HAPUS_' + tabel.toUpperCase(), 'id=' + id);
    simpan();
    return {};
  }

  function simpanResep(body, user) {
    const produkId = Number(body.produk_id || 0);
    const items = (body.items || []).filter((i) => i.bahan_id && Number(i.qty) > 0);
    if (!items.length) galat('Resep minimal berisi satu bahan.');
    DB.resep = DB.resep.filter((r) => r.produk_id !== produkId);
    items.forEach((it) => {
      DB.resep.push({
        id: idBaru('resep'), produk_id: produkId,
        bahan_id: Number(it.bahan_id), qty: Number(it.qty)
      });
    });
    const p = DB.produk.find((x) => x.id === produkId);
    audit(user && user.nama, 'SIMPAN_RESEP', `${p ? p.nama : ''} (${items.length} bahan)`);
    simpan();
    return { hpp: hppUnit(produkId) };
  }

  /* ---------------- Router ---------------- */
  let SESI = {};

  function butuhLogin(token) {
    if (!token) galat('Sesi berakhir, silakan login kembali.', 401);
    const u = SESI[token];
    if (!u) galat('Sesi berakhir, silakan login kembali.', 401);
    return u;
  }

  async function handle(method, path, body, token) {
    await muatData();
    const url = new URL(path, location.origin + location.pathname);
    const bagian = url.pathname.replace(/^.*?\/api\//, '').split('/').filter(Boolean);
    const res = bagian[0] || '';
    const sub = bagian[1] || '';
    const sub2 = bagian[2] || '';
    const q = url.searchParams;
    body = body || {};

    // ---- tanpa autentikasi ----
    if (res === 'info') {
      return {
        aplikasi: 'BakeERP', versi: '1.0 (demo statis)',
        backend: 'demo-browser',
        database: 'localStorage — data contoh 31 hari',
        waktu: nowStr()
      };
    }

    if (res === 'login' && method === 'POST') {
      const user = await authenticate(String(body.username || '').trim(), body.password || '');
      const tok = 'demo-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      SESI[tok] = user;
      try { localStorage.setItem(TOKEN_KEY, tok); } catch (e) {}
      return { token: tok, user: user };
    }

    const user = butuhLogin(token);

    if (res === 'logout' && method === 'POST') {
      delete SESI[token];
      try { localStorage.removeItem(TOKEN_KEY); } catch (e) {}
      return {};
    }
    if (res === 'me') return user;

    // ---- dashboard ----
    if (res === 'dashboard') return dashboard();

    // ---- master ----
    if (res === 'bahan' || res === 'produk' || res === 'supplier') {
      if (method === 'GET') {
        if (res === 'produk') {
          return DB.produk.map((p) => {
            const hpp = hppUnit(p.id);
            return Object.assign({}, p, { hpp: hpp, margin: r2(p.harga_jual - hpp) });
          });
        }
        return DB[res].slice();
      }
      if (method === 'POST') {
        if (res === 'bahan') return simpanBahan(body, user);
        if (res === 'produk') return simpanProduk(body, user);
        return simpanSupplier(body, user);
      }
      if (method === 'DELETE' && sub) return hapusMaster(res, Number(sub), user);
    }

    // ---- resep ----
    if (res === 'resep') {
      if (method === 'GET') {
        const pid = Number(q.get('produk_id') || 0);
        return { items: getResep(pid), hpp: hppUnit(pid) };
      }
      if (method === 'POST') return simpanResep(body, user);
    }

    // ---- pembelian ----
    if (res === 'pembelian') {
      if (method === 'GET') {
        if (sub) {
          const head = DB.pembelian.find((p) => p.id === Number(sub));
          if (!head) galat('Purchase order tidak ditemukan.');
          const sup = DB.supplier.find((s) => s.id === head.supplier_id) || {};
          const items = DB.pembelian_item
            .filter((i) => i.pembelian_id === head.id)
            .map((i) => {
              const b = DB.bahan.find((x) => x.id === i.bahan_id) || {};
              return Object.assign({}, i, { nama: b.nama, satuan: b.satuan });
            });
          return Object.assign({}, head, { supplier: sup.nama, items: items });
        }
        return DB.pembelian.slice().reverse().map((p) => {
          const s = DB.supplier.find((x) => x.id === p.supplier_id) || {};
          return Object.assign({}, p, { supplier: s.nama });
        });
      }
      if (method === 'POST') {
        if (sub && sub2 === 'terima') return terimaPembelian(Number(sub), user);
        return buatPembelian(body, user);
      }
    }

    // ---- produksi ----
    if (res === 'produksi') {
      if (method === 'GET') {
        return DB.produksi.slice().reverse().map((p) => {
          const pr = DB.produk.find((x) => x.id === p.produk_id) || {};
          return Object.assign({}, p, {
            produk: pr.nama, produk_kode: pr.kode
          });
        });
      }
      if (method === 'POST') {
        if (sub === 'cek') {
          const kebutuhan = cekKebutuhan(Number(body.produk_id || 0), Number(body.qty || 0));
          return {
            kebutuhan: kebutuhan,
            total_biaya: r2(kebutuhan.reduce((a, k) => a + k.subtotal, 0))
          };
        }
        return buatProduksi(body, user);
      }
    }

    // ---- penjualan ----
    if (res === 'penjualan') {
      if (method === 'GET') {
        return DB.penjualan.slice().reverse().slice(0, 100).map((p) => {
          const items = DB.penjualan_item
            .filter((i) => i.penjualan_id === p.id)
            .map((i) => {
              const pr = DB.produk.find((x) => x.id === i.produk_id) || {};
              return Object.assign({}, i, { nama: pr.nama });
            });
          return Object.assign({}, p, { items: items });
        });
      }
      if (method === 'POST') return buatPenjualan(body, user);
    }

    // ---- pengeluaran ----
    if (res === 'pengeluaran') {
      if (method === 'GET') return DB.pengeluaran.slice().reverse();
      if (method === 'POST') return buatPengeluaran(body, user);
    }

    // ---- keuangan ----
    if (res === 'keuangan') {
      const dari = q.get('dari') || firstOfMonthISO();
      const sampai = q.get('sampai') || todayISO();
      if (sub === 'labarugi') return labaRugi(dari, sampai);
      if (sub === 'kas') return bukuKas(dari, sampai);
    }

    // ---- laporan ----
    if (res === 'laporan') {
      const dari = q.get('dari') || firstOfMonthISO();
      const sampai = q.get('sampai') || todayISO();
      if (sub === 'stok') return laporanStok();
      if (sub === 'penjualan') return laporanPenjualan(dari, sampai);
      if (sub === 'produksi') return laporanProduksi(dari, sampai);
    }

    if (res === 'audit') {
      return DB.audit.slice().reverse().slice(0, 100);
    }

    galat('Endpoint tidak ditemukan: ' + res, 404);
  }

  /* ---------------- Publikasi ---------------- */
  window.LOCAL_API = {
    handle: handle,
    reset: reset,
    siap: muatData,
    info: () => ({
      baris: DB ? Object.keys(DB).reduce((a, k) => {
        return a + (Array.isArray(DB[k]) ? DB[k].length : 0);
      }, 0) : 0
    })
  };

  // Muat lebih awal agar tombol "reset" langsung siap
  muatData().catch((e) => console.error('Gagal memuat data demo:', e));
})();
