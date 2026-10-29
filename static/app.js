/* ==========================================================================
   BakeERP - Inti aplikasi: API client, utilitas, layout, router, dashboard
   ========================================================================== */

const API = {
  token: localStorage.getItem('bakerp_token') || '',
  async req(method, path, body) {
    // Mode demo: bila api-local.js dimuat, seluruh permintaan dilayani di browser
    // (tanpa server Python) memakai data yang ditanam di halaman.
    if (window.LOCAL_API) {
      try {
        return await window.LOCAL_API.handle(method, path, body, API.token);
      } catch (e) {
        if (e && e.status === 401) {
          localStorage.removeItem('bakerp_token');
          API.token = '';
          renderLogin('Sesi berakhir, silakan login kembali.');
          throw new Error('unauthorized');
        }
        throw new Error((e && e.message) || 'Terjadi kesalahan.');
      }
    }
    const opt = { method, headers: { 'Content-Type': 'application/json' } };
    if (API.token) opt.headers['Authorization'] = 'Bearer ' + API.token;
    if (body !== undefined) opt.body = JSON.stringify(body);
    const res = await fetch(path, opt);
    let json = null;
    try { json = await res.json(); } catch (e) { json = { ok: false, error: 'Respons server tidak valid.' }; }
    if (res.status === 401) {
      localStorage.removeItem('bakerp_token');
      API.token = '';
      renderLogin('Sesi berakhir, silakan login kembali.');
      throw new Error('unauthorized');
    }
    if (!res.ok || json.ok === false) throw new Error(json.error || 'Terjadi kesalahan.');
    return json.data;
  },
  get(p) { return API.req('GET', p); },
  post(p, b) { return API.req('POST', p, b || {}); },
  del(p) { return API.req('DELETE', p); }
};

/* ---------------- Utilitas tampilan ---------------- */
const Rp = (n) => 'Rp ' + Math.round(Number(n) || 0).toLocaleString('id-ID');
const RpShort = (n) => {
  n = Number(n) || 0;
  if (Math.abs(n) >= 1e9) return 'Rp ' + (n / 1e9).toFixed(1) + ' M';
  if (Math.abs(n) >= 1e6) return 'Rp ' + (n / 1e6).toFixed(1) + ' jt';
  if (Math.abs(n) >= 1e3) return 'Rp ' + (n / 1e3).toFixed(0) + ' rb';
  return Rp(n);
};
const num = (n, d = 2) => (Number(n) || 0).toLocaleString('id-ID', { maximumFractionDigits: d });
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
function todayISO() {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function firstOfMonthISO() { return todayISO().slice(0, 8) + '01'; }
function tgl(iso) {
  if (!iso) return '-';
  const p = String(iso).slice(0, 10).split('-');
  if (p.length !== 3) return iso;
  return `${+p[2]} ${BULAN[+p[1] - 1]} ${p[0]}`;
}
function tglWaktu(s) {
  if (!s) return '-';
  return tgl(s) + ' ' + String(s).slice(11, 16);
}

function toast(msg, type = 'ok') {
  const el = document.createElement('div');
  el.className = 'toast ' + (type === 'ok' ? '' : type);
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 3200);
  setTimeout(() => el.remove(), 3600);
}
const fail = (e) => { if (e && e.message !== 'unauthorized') toast(e.message || 'Gagal', 'err'); };

/* ---------------- Modal ---------------- */
let modalEl = null;
function openModal({ title, body, footer, wide }) {
  closeModal();
  const wrap = document.createElement('div');
  wrap.className = 'overlay';
  wrap.innerHTML = `
    <div class="modal ${wide ? 'wide' : ''}" role="dialog" aria-modal="true">
      <div class="modal-h"><h2>${esc(title)}</h2><button class="x" aria-label="Tutup">&times;</button></div>
      <div class="modal-b">${body}</div>
      ${footer ? `<div class="modal-f">${footer}</div>` : ''}
    </div>`;
  wrap.addEventListener('click', (e) => { if (e.target === wrap) closeModal(); });
  wrap.querySelector('.x').addEventListener('click', closeModal);
  document.body.appendChild(wrap);
  modalEl = wrap;
  const first = wrap.querySelector('input, select, textarea');
  if (first) setTimeout(() => first.focus(), 60);
  return wrap;
}
function closeModal() {
  if (modalEl) { modalEl.remove(); modalEl = null; }
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

/* ---------------- Ikon ---------------- */
const ICON = {
  grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  cart: '<circle cx="9" cy="20" r="1.6"/><circle cx="18" cy="20" r="1.6"/><path d="M2 3h3l2.6 12h11L21 7H6"/>',
  oven: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M8 14h8"/>',
  box: '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>',
  truck: '<rect x="1" y="6" width="13" height="10" rx="1"/><path d="M14 9h4l3 3v4h-7"/><circle cx="5" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
  factory: '<path d="M2 21V9l6 4V9l6 4V5l8 4v12z"/>',
  coin: '<circle cx="12" cy="12" r="9"/><path d="M12 7v10M9 9.5h4.5a2 2 0 010 4H9"/>',
  chart: '<path d="M3 21h18M7 17V9M12 17V5M17 17v-6"/>',
  doc: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  logout: '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>'
};
const svg = (name, size = 18) =>
  `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${ICON[name] || ''}</svg>`;

/* ---------------- Struktur navigasi ---------------- */
const NAV = [
  { group: 'Operasional', items: [
    { r: 'dashboard', label: 'Dashboard', icon: 'grid' },
    { r: 'penjualan', label: 'Penjualan (POS)', icon: 'cart' },
    { r: 'produksi', label: 'Produksi', icon: 'factory' }
  ]},
  { group: 'Pengadaan & Gudang', items: [
    { r: 'pembelian', label: 'Pembelian', icon: 'truck' },
    { r: 'bahan', label: 'Bahan Baku', icon: 'box' },
    { r: 'supplier', label: 'Supplier', icon: 'user' }
  ]},
  { group: 'Master Produk', items: [
    { r: 'produk', label: 'Produk & Resep', icon: 'oven' }
  ]},
  { group: 'Keuangan', items: [
    { r: 'pengeluaran', label: 'Pengeluaran', icon: 'coin' },
    { r: 'keuangan', label: 'Laba Rugi & Kas', icon: 'coin' }
  ]},
  { group: 'Analisis', items: [
    { r: 'laporan', label: 'Laporan', icon: 'doc' },
    { r: 'audit', label: 'Log Aktivitas', icon: 'clock' }
  ]}
];

let ME = null;

/* ---------------- Login ---------------- */
function renderLogin(msg) {
  const root = document.getElementById('root');
  root.innerHTML = `
  <div class="login-wrap">
    <div class="login-art">
      <div class="glow"></div>
      <div class="brand-mark" style="width:46px;height:46px;border-radius:13px;font-size:19px">B</div>
      <h1>Satu sistem untuk seluruh proses bisnis bakery.</h1>
      <p>BakeERP menghubungkan pembelian bahan, produksi berbasis resep, penjualan kasir,
         dan laporan keuangan dalam satu alur data yang konsisten.</p>
      <div class="badges">
        <span>Pembelian → Stok</span><span>Resep → Produksi</span>
        <span>Penjualan → HPP</span><span>Laba Rugi Otomatis</span>
      </div>
    </div>
    <div class="login-form">
      <div class="login-card">
        <div class="card">
          <div class="card-b">
            <h1 style="font-size:22px">Masuk ke BakeERP</h1>
            <p class="muted small" style="margin:6px 0 20px">Roti Kita Bakery — Sistem Informasi Enterprise</p>
            ${msg ? `<div class="hint" style="background:#fdecea;border-color:#f6c9c3;color:#b42318">${esc(msg)}</div>` : ''}
            <form id="loginForm">
              <label class="field"><span>Username</span>
                <input id="lgUser" value="admin" autocomplete="username" required /></label>
              <label class="field"><span>Password</span>
                <input id="lgPass" type="password" value="admin123" autocomplete="current-password" required /></label>
              <button class="btn primary block" type="submit" style="margin-top:6px;padding:11px">Masuk</button>
            </form>
            <div class="hint">Akun demo — admin/admin123 · gudang/gudang123 · kasir/kasir123</div>
          </div>
        </div>
      </div>
    </div>
  </div>`;
  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const d = await API.post('/api/login', {
        username: document.getElementById('lgUser').value.trim(),
        password: document.getElementById('lgPass').value
      });
      API.token = d.token;
      localStorage.setItem('bakerp_token', d.token);
      ME = d.user;
      toast('Selamat datang, ' + d.user.nama);
      location.hash = '#/dashboard';
      boot();
    } catch (err) { fail(err); }
  });
}

/* ---------------- Layout ---------------- */
function layout(route) {
  const root = document.getElementById('root');
  root.innerHTML = `
  <div class="app">
    <aside class="sidebar" id="sidebar">
      <button class="nav-close" id="navClose" aria-label="Tutup menu">&times;</button>
      <div class="brand">
        <div class="brand-mark">B</div>
        <div>
          <div class="brand-name">BakeERP</div>
          <div class="brand-sub">Roti Kita Bakery</div>
        </div>
      </div>
      <nav class="nav">
        ${NAV.map(g => `
          <div class="nav-group">${g.group}</div>
          ${g.items.map(it => `<a href="#/${it.r}" data-r="${it.r}">${svg(it.icon)}<span>${it.label}</span>
            ${it.r === 'pembelian' ? '<span class="count hidden" id="poBadge"></span>' : ''}</a>`).join('')}
        `).join('')}
      </nav>
      <div class="side-foot">
        <div>${esc(ME ? ME.nama : '')} · <span style="text-transform:capitalize">${esc(ME ? ME.role : '')}</span></div>
        <div id="dbInfo" class="small" style="margin-top:6px;color:#8d7a68;font-size:11px"
             title="Basis data yang sedang dipakai aplikasi">&nbsp;</div>
        <a href="#" id="logoutBtn" style="color:#c9b8a6;display:inline-flex;gap:6px;align-items:center;margin-top:8px">${svg('logout', 15)} Keluar</a>
      </div>
    </aside>
    <div class="main">
      <div class="topbar">
        <button class="burger" id="burger">☰</button>
        <div>
          <div class="title" id="pgTitle"></div>
          <div class="crumb" id="pgCrumb"></div>
        </div>
        <div class="spacer"></div>
        <div class="userchip">
          <div class="avatar">${esc((ME ? ME.nama : '?').slice(0, 1).toUpperCase())}</div>
          <div class="small"><b>${esc(ME ? ME.nama : '')}</b><br><span class="muted">${esc(ME ? ME.role : '')}</span></div>
        </div>
      </div>
      <div class="page" id="page"></div>
    </div>
  </div>
  <div class="nav-backdrop" id="navBackdrop"></div>`;

  document.getElementById('logoutBtn').addEventListener('click', async (e) => {
    e.preventDefault();
    try { await API.post('/api/logout'); } catch (err) {}
    localStorage.removeItem('bakerp_token'); API.token = ''; ME = null;
    renderLogin();
  });

  // ---- Menu samping di layar kecil ----
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('navBackdrop');
  const burger = document.getElementById('burger');

  const tutupMenu = () => {
    sidebar.classList.remove('open');
    backdrop.classList.remove('show');
    document.body.classList.remove('nav-open');
  };
  const bukaMenu = () => {
    sidebar.classList.add('open');
    backdrop.classList.add('show');
    document.body.classList.add('nav-open');
  };
  const toggleMenu = () => {
    if (sidebar.classList.contains('open')) tutupMenu(); else bukaMenu();
  };

  burger.addEventListener('click', toggleMenu);
  document.getElementById('navClose').addEventListener('click', tutupMenu);
  backdrop.addEventListener('click', tutupMenu);

  // Menutup menu setiap kali sebuah halaman dipilih — ini yang sebelumnya
  // terlewat sehingga menu tetap menutupi layar setelah berpindah halaman.
  sidebar.querySelectorAll('.nav a[data-r]').forEach((a) => {
    a.addEventListener('click', tutupMenu);
  });

  // Tombol Esc & perubahan ukuran layar ditangani sekali di boot()
  markActive(route);
  refreshPOBadge();
  tampilkanDbInfo();
}

/* Menutup menu samping dengan tombol Esc (hanya berlaku saat menu terbuka). */
function onEscMenu(e) {
  if (e.key !== 'Escape') return;
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('navBackdrop');
  if (sidebar && sidebar.classList.contains('open')) {
    sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('show');
    document.body.classList.remove('nav-open');
  }
}

/* Bila layar dilebarkan melewati breakpoint, pastikan sisa status menu bersih. */
function onResizeMenu() {
  if (window.innerWidth > 860) {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('navBackdrop');
    if (sidebar) sidebar.classList.remove('open');
    if (backdrop) backdrop.classList.remove('show');
    document.body.classList.remove('nav-open');
  }
}

/* Menampilkan basis data yang sedang aktif di kaki sidebar,
   supaya jelas data ini tersimpan di mana (MySQL, SQLite, atau mode demo). */
async function tampilkanDbInfo() {
  const el = document.getElementById('dbInfo');
  if (!el) return;
  try {
    const info = await API.get('/api/info');
    let teks, warna = '#8d7a68';
    if (info.backend === 'demo-browser') {
      teks = '⚠ Demo — data di browser ini saja';
      warna = '#fbbf24';
    } else if (info.backend === 'mysql') {
      teks = '🗄 MySQL · ' + (info.database.split('/').pop() || 'bakerp');
    } else {
      teks = '🗄 SQLite · bakery.db';
    }
    el.textContent = teks;
    el.style.color = warna;
    el.title = 'Basis data: ' + info.database;
  } catch (e) {
    el.textContent = '';
  }
}

function markActive(route) {
  document.querySelectorAll('.nav a[data-r]').forEach(a => {
    a.classList.toggle('active', a.dataset.r === route);
  });
}

async function refreshPOBadge() {
  try {
    const d = await API.get('/api/dashboard');
    const el = document.getElementById('poBadge');
    if (el && d.jumlah_po_draft > 0) { el.textContent = d.jumlah_po_draft; el.classList.remove('hidden'); }
  } catch (e) {}
}

function setTitle(title, crumb) {
  document.getElementById('pgTitle').textContent = title;
  document.getElementById('pgCrumb').textContent = crumb || '';
}

/* ---------------- Dashboard ---------------- */
const PAGES = {};

PAGES.dashboard = async (el) => {
  setTitle('Dashboard', 'Ringkasan operasional bakery hari ini');
  el.innerHTML = `<div class="card"><div class="card-b muted">Memuat data…</div></div>`;
  const d = await API.get('/api/dashboard');
  const maxTren = Math.max(...d.tren.map(t => t.total), 1);

  el.innerHTML = `
    <div class="grid g4" style="margin-bottom:16px">
      <div class="card kpi accent">
        <div class="label">Penjualan hari ini</div>
        <div class="value">${Rp(d.penjualan_hari_ini)}</div>
        <div class="sub">${d.transaksi_hari_ini} transaksi tercatat</div>
        <div class="spark"><i style="width:${Math.min(100, (d.penjualan_hari_ini / Math.max(...d.tren.map(t => t.total), 1)) * 100)}%"></i></div>
      </div>
      <div class="card kpi">
        <div class="label">Pendapatan bulan ini</div>
        <div class="value">${Rp(d.pendapatan_bulan_ini)}</div>
        <div class="sub">${d.transaksi_hari_ini ? '' : ''}akumulasi ${tgl(firstOfMonthISO())} – hari ini</div>
      </div>
      <div class="card kpi">
        <div class="label">Laba bersih bulan ini</div>
        <div class="value" style="color:${d.laba_bulan_ini >= 0 ? 'var(--ok)' : 'var(--bad)'}">${Rp(d.laba_bulan_ini)}</div>
        <div class="sub">margin bersih ${num(d.margin_bulan_ini, 1)}%</div>
      </div>
      <div class="card kpi">
        <div class="label">Nilai persediaan</div>
        <div class="value">${Rp(d.nilai_persediaan)}</div>
        <div class="sub">bahan ${RpShort(d.nilai_bahan)} · produk jadi ${RpShort(d.nilai_produk)}</div>
      </div>
    </div>

    <div class="grid g23" style="margin-bottom:16px">
      <div class="card">
        <div class="card-h"><h2>Tren penjualan 7 hari terakhir</h2><div class="spacer"></div>
          <span class="badge info">${RpShort(d.tren.reduce((a, b) => a + b.total, 0))} total</span></div>
        <div class="card-b">
          <div class="chart">
            ${d.tren.map(t => `
              <div class="bar" title="${tgl(t.tanggal)}: ${Rp(t.total)}">
                <div class="val">${t.total ? RpShort(t.total).replace('Rp ', '') : ''}</div>
                <div class="fill" style="height:${Math.max(3, (t.total / maxTren) * 100)}%"></div>
                <div class="cap">${tgl(t.tanggal).slice(0, 6)}</div>
              </div>`).join('')}
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-h"><h2>Perlu perhatian</h2><div class="spacer"></div>
          <span class="badge ${d.stok_kritis.length ? 'warn' : 'ok'}">${d.stok_kritis.length} item</span></div>
        <div class="card-b flush">
          ${d.stok_kritis.length ? `<div class="tablewrap"><table>
            <thead><tr><th>Item</th><th>Jenis</th><th class="num">Stok</th><th class="num">Minimum</th></tr></thead>
            <tbody>${d.stok_kritis.slice(0, 8).map(s => `
              <tr><td class="t-strong">${esc(s.nama)}</td><td><span class="badge neutral">${esc(s.jenis)}</span></td>
              <td class="num" style="color:var(--bad);font-weight:700">${num(s.stok)} ${esc(s.satuan)}</td>
              <td class="num muted">${num(s.stok_min)}</td></tr>`).join('')}
            </tbody></table></div>`
            : `<div class="empty"><b>Semua stok aman</b>Tidak ada item di bawah batas minimum.</div>`}
        </div>
      </div>
    </div>

    <div class="grid g2">
      <div class="card">
        <div class="card-h"><h2>Produk terlaris (30 hari)</h2></div>
        <div class="card-b flush"><div class="tablewrap"><table>
          <thead><tr><th>Produk</th><th class="num">Terjual</th><th class="num">Omzet</th></tr></thead>
          <tbody>${d.top_produk.map(p => `<tr><td class="t-strong">${esc(p.nama)}</td>
            <td class="num">${num(p.qty, 0)} pcs</td><td class="num">${Rp(p.omzet)}</td></tr>`).join('') ||
            '<tr><td colspan="3" class="empty">Belum ada penjualan.</td></tr>'}</tbody>
        </table></div></div>
      </div>
      <div class="card">
        <div class="card-h"><h2>Transaksi terakhir</h2><div class="spacer"></div>
          <a href="#/penjualan" class="btn sm">Buka POS</a></div>
        <div class="card-b flush"><div class="tablewrap"><table>
          <thead><tr><th>Invoice</th><th>Tanggal</th><th>Metode</th><th class="num">Total</th></tr></thead>
          <tbody>${d.transaksi_terbaru.map(t => `<tr>
            <td class="t-strong mono">${esc(t.no_invoice)}</td><td>${tgl(t.tanggal)}</td>
            <td><span class="badge neutral">${esc(t.metode)}</span></td>
            <td class="num">${Rp(t.total)}</td></tr>`).join('')}</tbody>
        </table></div></div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-h"><h2>Alur integrasi data antar modul</h2></div>
      <div class="card-b">
        <div class="flow">
          <span class="step">Pembelian bahan</span><span class="arrow">→</span>
          <span class="step">Stok bahan baku naik</span><span class="arrow">→</span>
          <span class="step">Produksi sesuai resep</span><span class="arrow">→</span>
          <span class="step">Stok produk jadi naik</span><span class="arrow">→</span>
          <span class="step">Penjualan (POS)</span><span class="arrow">→</span>
          <span class="step">HPP & pendapatan tercatat</span><span class="arrow">→</span>
          <span class="step">Buku kas & laba rugi</span>
        </div>
        <p class="small muted" style="margin-top:12px">Setiap transaksi pada satu modul otomatis memperbarui modul lain — tidak ada input ulang data.</p>
      </div>
    </div>`;
};

/* ---------------- Router ---------------- */
const ROUTES = ['dashboard', 'penjualan', 'produksi', 'pembelian', 'bahan', 'supplier',
  'produk', 'pengeluaran', 'keuangan', 'laporan', 'audit'];

async function router() {
  if (!API.token) { renderLogin(); return; }
  const hash = location.hash.replace(/^#\/?/, '') || 'dashboard';
  const route = ROUTES.includes(hash) ? hash : 'dashboard';
  if (!document.querySelector('.app')) layout(route); else markActive(route);
  const el = document.getElementById('page');
  el.innerHTML = '<div class="card"><div class="card-b muted">Memuat…</div></div>';
  try {
    const fn = PAGES[route];
    if (!fn) { el.innerHTML = '<div class="card"><div class="card-b">Halaman tidak ditemukan.</div></div>'; return; }
    await fn(el);
  } catch (e) {
    if (e.message !== 'unauthorized')
      el.innerHTML = `<div class="card"><div class="card-b" style="color:var(--bad)">Gagal memuat halaman: ${esc(e.message)}</div></div>`;
  }
}

async function boot() {
  if (!API.token) { renderLogin(); return; }
  try {
    ME = await API.get('/api/me');
  } catch (e) { return; }
  if (!location.hash) location.hash = '#/dashboard';
  router();
}

window.addEventListener('hashchange', router);
window.addEventListener('DOMContentLoaded', boot);

// Ditambahkan sekali di sini (bukan di layout) agar tidak menumpuk
// setiap kali halaman di-render ulang.
document.addEventListener('keydown', onEscMenu);
window.addEventListener('resize', onResizeMenu);
