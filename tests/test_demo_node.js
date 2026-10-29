/* Uji logika api-local.js memakai Node (tanpa browser).
   Memverifikasi bahwa demo statis berperilaku sama dengan aplikasi Python.

   Jalankan: node tests/test_demo_node.js
*/
const fs = require('fs');
const path = require('path');

const DEMO = path.join(__dirname, '..', 'site', 'demo');
const dataJson = JSON.parse(fs.readFileSync(path.join(DEMO, 'data.json'), 'utf8'));

// ---- Tiruan lingkungan browser ----
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
global.location = { origin: 'http://localhost:8081', pathname: '/demo/index.html', protocol: 'http:' };
global.crypto = require('crypto').webcrypto;
global.fetch = async (url) => {
  if (String(url).indexOf('data.json') >= 0) {
    return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(dataJson)) };
  }
  throw new Error('fetch tak terduga: ' + url);
};
global.window = global;
global.console.warn = () => {};

// Muat modul
const kode = fs.readFileSync(path.join(DEMO, 'api-local.js'), 'utf8');
eval(kode);

const L = global.LOCAL_API;
let lulus = 0, gagal = 0;

function cek(nama, kondisi, detail) {
  if (kondisi) { lulus++; console.log(`  [LULUS] ${nama}` + (detail ? `  -> ${detail}` : '')); }
  else { gagal++; console.log(`  [GAGAL] ${nama}` + (detail ? `  -> ${detail}` : '')); }
}

const rp = (n) => 'Rp ' + Math.round(n).toLocaleString('id-ID');

(async () => {
  console.log('='.repeat(70));
  console.log('  UJI LOGIKA DEMO SISI-KLIEN (api-local.js) — Node');
  console.log('='.repeat(70));

  // ---------- 1. Autentikasi ----------
  console.log('\n1) Autentikasi');
  let err = null;
  try { await L.handle('POST', '/api/login', { username: 'admin', password: 'salah' }, ''); }
  catch (e) { err = e; }
  cek('Password salah ditolak', err && /Password salah/.test(err.message), err && err.message);

  const login = await L.handle('POST', '/api/login',
    { username: 'admin', password: 'admin123' }, '');
  const tok = login.token;
  cek('Login admin (PBKDF2) berhasil', !!tok && login.user.username === 'admin',
    'token diterbitkan');

  err = null;
  try { await L.handle('GET', '/api/dashboard', null, ''); } catch (e) { err = e; }
  cek('Tanpa token ditolak (401)', err && err.status === 401);

  // ---------- 2. Data awal ----------
  console.log('\n2) Data awal termuat');
  const info = await L.handle('GET', '/api/info', null, tok);
  cek('Info backend demo', info.backend === 'demo-browser', info.database);

  const dash0 = await L.handle('GET', '/api/dashboard', null, tok);
  cek('Dashboard punya tren 7 hari', dash0.tren.length === 7,
    dash0.tren.map((t) => Math.round(t.total / 1000) + 'rb').join(' '));
  cek('Produk terlaris terisi', dash0.top_produk.length > 0, dash0.top_produk[0].nama);

  // ---------- 3. Master data ----------
  console.log('\n3) Master data & resep');
  const bahanBaru = await L.handle('POST', '/api/bahan',
    { nama: 'Tepung Uji Demo', satuan: 'kg', stok_min: 2, harga_beli: 10000 }, tok);
  cek('Tambah bahan', !!bahanBaru.id, 'id=' + bahanBaru.id);

  const produkBaru = await L.handle('POST', '/api/produk',
    { nama: 'Roti Uji Demo', kategori: 'Roti', harga_jual: 20000, stok_min: 3 }, tok);
  cek('Tambah produk', !!produkBaru.id, 'id=' + produkBaru.id);

  const resep = await L.handle('POST', '/api/resep',
    { produk_id: produkBaru.id, items: [{ bahan_id: bahanBaru.id, qty: 0.5 }] }, tok);
  cek('Resep: 0,5 kg/unit -> HPP Rp 5.000', resep.hpp === 5000, rp(resep.hpp));

  // ---------- 4. Pembelian -> stok & kas ----------
  console.log('\n4) Pembelian -> penerimaan barang');
  const po = await L.handle('POST', '/api/pembelian', {
    supplier_id: 1, tanggal: new Date().toISOString().slice(0, 10),
    items: [{ bahan_id: bahanBaru.id, qty: 10, harga: 12000 }],
  }, tok);
  cek('Buat PO (draft)', po.total === 120000, `${po.no_po} total ${rp(po.total)}`);

  let daftarBahan = await L.handle('GET', '/api/bahan', null, tok);
  let b = daftarBahan.find((x) => x.id === bahanBaru.id);
  cek('PO draft belum mengubah stok', b.stok === 0, 'stok = ' + b.stok);

  await L.handle('POST', `/api/pembelian/${po.id}/terima`, {}, tok);
  daftarBahan = await L.handle('GET', '/api/bahan', null, tok);
  b = daftarBahan.find((x) => x.id === bahanBaru.id);
  cek('INTEGRASI: stok bahan naik 0 -> 10', b.stok === 10, 'stok = ' + b.stok);
  cek('INTEGRASI: harga rata-rata = Rp 12.000', b.harga_beli === 12000, rp(b.harga_beli));

  let kas = await L.handle('GET',
    `/api/keuangan/kas?dari=2000-01-01&sampai=2100-01-01`, null, tok);
  const kasPo = kas.filter((k) => k.ref_tipe === 'pembelian' && k.ref_id === po.id);
  cek('INTEGRASI: kas keluar tercatat', kasPo.length === 1 && kasPo[0].jumlah === 120000,
    kasPo.length ? rp(kasPo[0].jumlah) : 'tidak ada');

  err = null;
  try { await L.handle('POST', `/api/pembelian/${po.id}/terima`, {}, tok); } catch (e) { err = e; }
  cek('PO tidak bisa diterima 2x', err && /sudah diterima/.test(err.message));

  // ---------- 5. Produksi ----------
  console.log('\n5) Produksi berbasis resep');
  const cekK = await L.handle('POST', '/api/produksi/cek',
    { produk_id: produkBaru.id, qty: 10 }, tok);
  cek('Simulasi kebutuhan: 10 unit butuh 5 kg',
    cekK.kebutuhan[0].butuh === 5, `butuh ${cekK.kebutuhan[0].butuh} kg`);

  const prd = await L.handle('POST', '/api/produksi',
    { produk_id: produkBaru.id, qty: 10, tanggal: new Date().toISOString().slice(0, 10) }, tok);
  cek('Produksi 10 unit, biaya bahan Rp 60.000', prd.biaya_bahan === 60000, rp(prd.biaya_bahan));

  daftarBahan = await L.handle('GET', '/api/bahan', null, tok);
  b = daftarBahan.find((x) => x.id === bahanBaru.id);
  cek('INTEGRASI: bahan turun 10 -> 5 kg', b.stok === 5, 'stok = ' + b.stok);

  let daftarProduk = await L.handle('GET', '/api/produk', null, tok);
  let p = daftarProduk.find((x) => x.id === produkBaru.id);
  cek('INTEGRASI: produk jadi naik 0 -> 10', p.stok === 10, 'stok = ' + p.stok);

  err = null;
  try {
    await L.handle('POST', '/api/produksi',
      { produk_id: produkBaru.id, qty: 100, tanggal: '2026-10-29' }, tok);
  } catch (e) { err = e; }
  cek('Produksi ditolak bila bahan kurang', err && /tidak mencukupi/.test(err.message),
    err ? err.message.slice(0, 45) + '…' : '');

  // ---------- 6. Penjualan ----------
  console.log('\n6) Penjualan (POS)');
  const jual = await L.handle('POST', '/api/penjualan', {
    items: [{ produk_id: produkBaru.id, qty: 3 }], metode: 'QRIS',
    tanggal: new Date().toISOString().slice(0, 10),
  }, tok);
  cek('Penjualan 3 unit = Rp 60.000', jual.total === 60000, `${jual.no_invoice} ${rp(jual.total)}`);
  cek('HPP ikut harga beli terbaru (3 x 6.000)', jual.hpp === 18000, rp(jual.hpp));

  daftarProduk = await L.handle('GET', '/api/produk', null, tok);
  p = daftarProduk.find((x) => x.id === produkBaru.id);
  cek('INTEGRASI: produk turun 10 -> 7', p.stok === 7, 'stok = ' + p.stok);

  kas = await L.handle('GET', `/api/keuangan/kas?dari=2000-01-01&sampai=2100-01-01`, null, tok);
  const kasJual = kas.filter((k) => k.ref_tipe === 'penjualan' && k.ref_id === jual.id);
  cek('INTEGRASI: kas masuk tercatat', kasJual.length === 1 && kasJual[0].jumlah === 60000,
    kasJual.length ? rp(kasJual[0].jumlah) : 'tidak ada');

  err = null;
  try {
    await L.handle('POST', '/api/penjualan', { items: [{ produk_id: produkBaru.id, qty: 999 }] }, tok);
  } catch (e) { err = e; }
  cek('Penjualan ditolak bila stok kurang', err && /tidak cukup/.test(err.message),
    err ? err.message.slice(0, 45) + '…' : '');

  // ---------- 7. Keuangan ----------
  console.log('\n7) Keuangan & laporan');
  await L.handle('POST', '/api/pengeluaran', {
    tanggal: new Date().toISOString().slice(0, 10), kategori: 'Listrik & Gas',
    keterangan: 'uji beban', jumlah: 50000,
  }, tok);

  const lr = await L.handle('GET',
    '/api/keuangan/labarugi?dari=2000-01-01&sampai=2100-01-01', null, tok);
  const harapKotor = Math.round((lr.pendapatan - lr.hpp) * 100) / 100;
  cek('Laba kotor = pendapatan - HPP', harapKotor === lr.laba_kotor,
    `${rp(lr.pendapatan)} - ${rp(lr.hpp)} = ${rp(lr.laba_kotor)}`);
  const harapBersih = Math.round((lr.laba_kotor - lr.total_beban) * 100) / 100;
  cek('Laba bersih = laba kotor - beban', harapBersih === lr.laba_bersih, rp(lr.laba_bersih));
  cek('Beban pengeluaran ikut terhitung',
    lr.beban.some((x) => x.kategori === 'Listrik & Gas'));

  const stok = await L.handle('GET', '/api/laporan/stok', null, tok);
  cek('Laporan stok: bahan & produk', stok.bahan.length > 0 && stok.produk.length > 0,
    `${stok.bahan.length} bahan, ${stok.produk.length} produk`);

  const lapJual = await L.handle('GET',
    '/api/laporan/penjualan?dari=2000-01-01&sampai=2100-01-01', null, tok);
  cek('Laporan penjualan: rekap harian', lapJual.harian.length > 0,
    lapJual.harian.length + ' hari');

  const audit = await L.handle('GET', '/api/audit', null, tok);
  const aksi = new Set(audit.map((a) => a.aksi));
  cek('Jejak audit merekam transaksi',
    aksi.has('TERIMA_PO') && aksi.has('PRODUKSI') && aksi.has('PENJUALAN'),
    audit.length + ' baris');

  // ---------- 8. Reset ----------
  console.log('\n8) Reset data demo');
  await L.reset();
  const login2 = await L.handle('POST', '/api/login',
    { username: 'admin', password: 'admin123' }, '');
  const produkSetelahReset = await L.handle('GET', '/api/produk', null, login2.token);
  cek('Reset mengembalikan data awal', produkSetelahReset.length === 6,
    produkSetelahReset.length + ' produk (awal 6)');

  // ---------- Ringkasan ----------
  const total = lulus + gagal;
  console.log('\n' + '='.repeat(70));
  console.log(`  HASIL: ${lulus}/${total} pengujian lulus (${Math.round(lulus / total * 100)}%)`);
  console.log('='.repeat(70));
  process.exit(gagal === 0 ? 0 : 1);
})().catch((e) => {
  console.error('\nERROR TAK TERTANGANI:', e);
  process.exit(1);
});
