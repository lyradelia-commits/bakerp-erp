/* ==========================================================================
   BakeERP - Halaman modul (POS, produksi, pembelian, master, keuangan, laporan)
   ========================================================================== */

/* ============================ 1. PENJUALAN / POS ============================ */
let CART = [];

PAGES.penjualan = async (el) => {
  setTitle('Penjualan (POS)', 'Kasir — setiap transaksi otomatis mengurangi stok produk jadi & mencatat pendapatan');
  const [produk, riwayat] = await Promise.all([API.get('/api/produk'), API.get('/api/penjualan')]);
  CART = [];

  el.innerHTML = `
    <div class="pos">
      <div class="card">
        <div class="card-h">
          <h2>Pilih produk</h2>
          <div class="spacer"></div>
          <input id="cariProduk" placeholder="Cari produk…" style="max-width:230px" />
        </div>
        <div class="card-b">
          <div class="prodgrid" id="prodgrid">
            ${produk.filter(p => p.aktif).map(p => `
              <button class="prodcard" data-id="${p.id}" data-nama="${esc(p.nama)}"
                      data-harga="${p.harga_jual}" data-stok="${p.stok}" ${p.stok < 1 ? 'disabled' : ''}>
                <div class="nm">${esc(p.nama)}</div>
                <div class="pr">${Rp(p.harga_jual)}</div>
                <div class="st">Stok ${num(p.stok, 0)} pcs${p.stok < 1 ? ' · habis' : ''}</div>
              </button>`).join('')}
          </div>
        </div>
      </div>

      <div class="card cart">
        <div class="card-h"><h2>Keranjang</h2><div class="spacer"></div>
          <button class="btn sm" id="clearCart">Kosongkan</button></div>
        <div class="card-b" id="cartBody"></div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-h"><h2>Riwayat transaksi penjualan</h2><div class="spacer"></div>
        <span class="badge info">${riwayat.length} transaksi terakhir</span></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>Invoice</th><th>Tanggal</th><th>Item</th><th>Metode</th>
          <th class="num">Total</th><th class="num">HPP</th><th class="num">Laba kotor</th></tr></thead>
        <tbody>${riwayat.slice(0, 15).map(t => `<tr>
          <td class="t-strong mono">${esc(t.no_invoice)}</td>
          <td class="nowrap">${tgl(t.tanggal)}</td>
          <td class="t-sub">${t.items.map(i => `${esc(i.nama)} ×${num(i.qty, 0)}`).join(', ')}</td>
          <td><span class="badge neutral">${esc(t.metode)}</span></td>
          <td class="num">${Rp(t.total)}</td>
          <td class="num muted">${Rp(t.hpp)}</td>
          <td class="num" style="color:var(--ok);font-weight:650">${Rp(t.total - t.hpp)}</td>
        </tr>`).join('') || '<tr><td colspan="7" class="empty">Belum ada transaksi.</td></tr>'}</tbody>
      </table></div></div>
    </div>`;

  const drawCart = () => {
    const body = document.getElementById('cartBody');
    if (!CART.length) {
      body.innerHTML = `<div class="empty"><b>Keranjang kosong</b>Klik produk di sebelah kiri untuk menambahkan.</div>`;
      return;
    }
    const subtotal = CART.reduce((a, c) => a + c.harga * c.qty, 0);
    body.innerHTML = `
      ${CART.map((c, i) => `
        <div class="cart-line">
          <div class="nm">${esc(c.nama)}<div class="t-sub">${Rp(c.harga)}</div></div>
          <div class="qtybox">
            <button data-act="minus" data-i="${i}">−</button><span>${c.qty}</span>
            <button data-act="plus" data-i="${i}">+</button>
          </div>
          <div style="min-width:82px;text-align:right;font-weight:650">${Rp(c.harga * c.qty)}</div>
        </div>`).join('')}
      <label class="field" style="margin-top:14px"><span>Diskon (Rp)</span>
        <input id="diskon" type="number" min="0" value="0" /></label>
      <label class="field"><span>Metode pembayaran</span>
        <select id="metode"><option>Tunai</option><option>QRIS</option><option>Transfer</option></select></label>
      <div class="cart-total"><span>Total</span><b id="cartTotal">${Rp(subtotal)}</b></div>
      <button class="btn primary block" id="bayar" style="margin-top:10px;padding:11px">Proses Pembayaran</button>
      <p class="small muted" style="margin-top:8px">Stok produk jadi akan berkurang otomatis dan HPP dihitung dari resep.</p>`;

    body.querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', () => {
      const i = +b.dataset.i;
      if (b.dataset.act === 'plus') {
        if (CART[i].qty + 1 > CART[i].stok) return toast('Stok tidak mencukupi', 'err');
        CART[i].qty++;
      } else {
        CART[i].qty--;
        if (CART[i].qty <= 0) CART.splice(i, 1);
      }
      drawCart();
    }));

    const dsk = document.getElementById('diskon');
    dsk.addEventListener('input', () => {
      document.getElementById('cartTotal').textContent = Rp(Math.max(0, subtotal - (+dsk.value || 0)));
    });

    document.getElementById('bayar').addEventListener('click', async () => {
      try {
        const d = await API.post('/api/penjualan', {
          items: CART.map(c => ({ produk_id: c.id, qty: c.qty, harga: c.harga })),
          diskon: +document.getElementById('diskon').value || 0,
          metode: document.getElementById('metode').value
        });
        toast(`Transaksi ${d.no_invoice} berhasil — ${Rp(d.total)}`);
        router();
      } catch (e) { fail(e); }
    });
  };

  document.getElementById('prodgrid').addEventListener('click', (ev) => {
    const b = ev.target.closest('.prodcard');
    if (!b || b.disabled) return;
    const id = +b.dataset.id, nama = b.dataset.nama, harga = +b.dataset.harga, stok = +b.dataset.stok;
    const ada = CART.find(c => c.id === id);
    if (ada) {
      if (ada.qty + 1 > stok) return toast('Stok tidak mencukupi', 'err');
      ada.qty++;
    } else {
      CART.push({ id, nama, harga, stok, qty: 1 });
    }
    drawCart();
  });

  document.getElementById('clearCart').addEventListener('click', () => { CART = []; drawCart(); });
  document.getElementById('cariProduk').addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll('.prodcard').forEach(c => {
      c.style.display = c.dataset.nama.toLowerCase().includes(q) ? '' : 'none';
    });
  });
  drawCart();
};

/* ============================ 2. PRODUKSI ============================ */
PAGES.produksi = async (el) => {
  setTitle('Produksi', 'Eksekusi resep — bahan baku berkurang, stok produk jadi bertambah');
  const [produk, bahan, riwayat] = await Promise.all([
    API.get('/api/produk'), API.get('/api/bahan'), API.get('/api/produksi')]);

  el.innerHTML = `
    <div class="grid g32" style="align-items:start">
      <div class="card">
        <div class="card-h"><h2>Input produksi baru</h2></div>
        <div class="card-b">
          <form id="formProduksi">
            <label class="field"><span>Produk yang dibuat</span>
              <select id="fProduk" required>
                <option value="">— pilih produk —</option>
                ${produk.map(p => `<option value="${p.id}">${esc(p.nama)} (stok ${num(p.stok, 0)})</option>`).join('')}
              </select></label>
            <div class="row">
              <label class="field"><span>Jumlah produksi (pcs)</span>
                <input id="fQty" type="number" min="1" value="20" required /></label>
              <label class="field"><span>Tanggal</span>
                <input id="fTanggal" type="date" value="${todayISO()}" required /></label>
            </div>
            <label class="field"><span>Catatan (opsional)</span>
              <input id="fCatatan" placeholder="contoh: produksi pagi shift 1" /></label>
            <button class="btn primary block" type="submit" style="padding:11px">Jalankan Produksi</button>
          </form>
          <p class="small muted" style="margin-top:10px">Sistem memvalidasi ketersediaan bahan sesuai resep sebelum produksi dijalankan.</p>
        </div>
      </div>

      <div class="card">
        <div class="card-h"><h2>Kebutuhan bahan (otomatis dari resep)</h2></div>
        <div class="card-b flush" id="kebutuhanBox">
          <div class="empty"><b>Pilih produk & jumlah</b>Rincian kebutuhan bahan akan muncul di sini.</div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-h"><h2>Riwayat produksi</h2><div class="spacer"></div>
        <span class="badge info">${riwayat.length} batch</span></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>No. Batch</th><th>Tanggal</th><th>Produk</th><th class="num">Jumlah</th>
          <th class="num">Biaya bahan</th><th class="num">HPP/unit</th><th>Operator</th></tr></thead>
        <tbody>${riwayat.slice(0, 20).map(r => `<tr>
          <td class="t-strong mono">${esc(r.no_batch)}</td><td class="nowrap">${tgl(r.tanggal)}</td>
          <td>${esc(r.produk)}</td><td class="num">${num(r.qty, 0)} pcs</td>
          <td class="num">${Rp(r.biaya_bahan)}</td>
          <td class="num muted">${Rp(r.biaya_bahan / (r.qty || 1))}</td>
          <td class="t-sub">${esc(r.user_id ? 'gudang' : '-')}</td></tr>`).join('') ||
          '<tr><td colspan="7" class="empty">Belum ada produksi.</td></tr>'}</tbody>
      </table></div></div>
    </div>`;

  const cek = async () => {
    const pid = document.getElementById('fProduk').value;
    const qty = +document.getElementById('fQty').value || 0;
    const box = document.getElementById('kebutuhanBox');
    if (!pid || qty <= 0) {
      box.innerHTML = `<div class="empty"><b>Pilih produk & jumlah</b>Rincian kebutuhan bahan akan muncul di sini.</div>`;
      return;
    }
    try {
      const d = await API.post('/api/produksi/cek', { produk_id: +pid, qty });
      const kurang = d.kebutuhan.filter(k => !k.cukup);
      box.innerHTML = `<div class="tablewrap"><table>
        <thead><tr><th>Bahan</th><th class="num">Butuh</th><th class="num">Stok</th><th>Status</th></tr></thead>
        <tbody>${d.kebutuhan.map(k => `<tr>
          <td>${esc(k.nama)}</td>
          <td class="num">${num(k.butuh, 3)} ${esc(k.satuan)}</td>
          <td class="num">${num(k.stok, 2)}</td>
          <td>${k.cukup ? '<span class="badge ok">cukup</span>' : '<span class="badge bad">kurang</span>'}</td>
        </tr>`).join('')}</tbody>
        <tfoot><tr><td>Total biaya bahan</td><td colspan="3" class="num">${Rp(d.total_biaya)}</td></tr></tfoot>
      </table></div>
      ${kurang.length ? `<div class="card-b"><div class="badge bad">Bahan kurang</div>
        <p class="small" style="margin-top:8px;color:var(--bad)">Lakukan pembelian bahan terlebih dahulu agar produksi dapat dijalankan.</p></div>` : ''}`;
    } catch (e) {
      box.innerHTML = `<div class="card-b"><span class="badge bad">Gagal</span>
        <p class="small" style="margin-top:8px">${esc(e.message)}</p></div>`;
    }
  };
  document.getElementById('fProduk').addEventListener('change', cek);
  document.getElementById('fQty').addEventListener('input', cek);

  document.getElementById('formProduksi').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const d = await API.post('/api/produksi', {
        produk_id: +document.getElementById('fProduk').value,
        qty: +document.getElementById('fQty').value,
        tanggal: document.getElementById('fTanggal').value,
        catatan: document.getElementById('fCatatan').value
      });
      toast(`Produksi ${d.no_batch} berhasil — ${d.qty} pcs, biaya bahan ${Rp(d.biaya_bahan)}`);
      router();
    } catch (err) { fail(err); }
  });
};

/* ============================ 3. PEMBELIAN ============================ */
PAGES.pembelian = async (el) => {
  setTitle('Pembelian', 'Purchase order ke supplier — penerimaan barang menambah stok & mencatat kas keluar');
  const [list, supplier, bahan] = await Promise.all([
    API.get('/api/pembelian'), API.get('/api/supplier'), API.get('/api/bahan')]);

  el.innerHTML = `
    <div class="card">
      <div class="card-h"><h2>Daftar purchase order</h2><div class="spacer"></div>
        <button class="btn primary" id="btnPO">${svg('plus', 16)} Buat PO</button></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>No. PO</th><th>Tanggal</th><th>Supplier</th><th class="num">Total</th>
          <th>Status</th><th class="right">Aksi</th></tr></thead>
        <tbody>${list.map(p => `<tr>
          <td class="t-strong mono">${esc(p.no_po)}</td>
          <td class="nowrap">${tgl(p.tanggal)}</td>
          <td>${esc(p.supplier)}</td>
          <td class="num">${Rp(p.total)}</td>
          <td>${p.status === 'diterima'
            ? '<span class="badge ok">diterima</span>'
            : '<span class="badge warn">draft</span>'}</td>
          <td class="right nowrap">
            <button class="btn sm" data-detail="${p.id}">Detail</button>
            ${p.status === 'draft' ? `<button class="btn sm ok" data-terima="${p.id}">Terima barang</button>` : ''}
          </td></tr>`).join('') || '<tr><td colspan="6" class="empty">Belum ada purchase order.</td></tr>'}</tbody>
      </table></div></div>
    </div>`;

  el.querySelectorAll('[data-detail]').forEach(b => b.addEventListener('click', async () => {
    try {
      const d = await API.get('/api/pembelian/' + b.dataset.detail);
      openModal({
        title: 'Detail ' + d.no_po, wide: true,
        body: `<div class="grid g2" style="margin-bottom:14px">
            <div><div class="small muted">Supplier</div><b>${esc(d.supplier)}</b></div>
            <div><div class="small muted">Tanggal</div><b>${tgl(d.tanggal)}</b></div>
          </div>
          <div class="tablewrap"><table>
            <thead><tr><th>Bahan</th><th class="num">Qty</th><th class="num">Harga</th><th class="num">Subtotal</th></tr></thead>
            <tbody>${d.items.map(i => `<tr><td>${esc(i.nama)}</td>
              <td class="num">${num(i.qty, 2)} ${esc(i.satuan)}</td>
              <td class="num">${Rp(i.harga)}</td><td class="num">${Rp(i.subtotal)}</td></tr>`).join('')}</tbody>
            <tfoot><tr><td colspan="3">Total</td><td class="num">${Rp(d.total)}</td></tr></tfoot>
          </table></div>
          <p class="small muted" style="margin-top:12px">Status: <b>${esc(d.status)}</b>${d.status === 'diterima'
            ? ' — stok bahan sudah diperbarui dan kas keluar tercatat otomatis.' : ' — belum memengaruhi stok maupun kas.'}</p>`,
        footer: `<button class="btn" onclick="closeModal()">Tutup</button>`
      });
    } catch (e) { fail(e); }
  }));

  el.querySelectorAll('[data-terima]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Terima barang untuk PO ini? Stok bahan akan bertambah dan kas keluar tercatat.')) return;
    try {
      const d = await API.post('/api/pembelian/' + b.dataset.terima + '/terima');
      toast('PO ' + d.no_po + ' diterima — stok bahan diperbarui');
      router();
    } catch (e) { fail(e); }
  }));

  document.getElementById('btnPO').addEventListener('click', () => {
    let rows = [{ bahan_id: '', qty: 10, harga: 0 }];
    const body = `
      <div class="row">
        <label class="field"><span>Supplier</span>
          <select id="poSupplier">${supplier.map(s => `<option value="${s.id}">${esc(s.nama)}</option>`).join('')}</select></label>
        <label class="field"><span>Tanggal PO</span><input id="poTanggal" type="date" value="${todayISO()}" /></label>
      </div>
      <div class="tablewrap" style="margin-bottom:10px"><table>
        <thead><tr><th>Bahan</th><th style="width:110px">Qty</th><th style="width:140px">Harga</th><th style="width:110px">Subtotal</th><th></th></tr></thead>
        <tbody id="poRows"></tbody>
      </table></div>
      <button class="btn sm" id="poAdd">+ Tambah baris</button>
      <div class="cart-total" style="border-top:1px solid var(--line);margin-top:12px">
        <span>Total PO</span><b id="poTotal">Rp 0</b></div>`;

    const m = openModal({
      title: 'Buat purchase order', wide: true, body,
      footer: `<button class="btn" onclick="closeModal()">Batal</button>
               <button class="btn primary" id="poSave">Simpan PO</button>`
    });

    const drawRows = () => {
      const tb = m.querySelector('#poRows');
      tb.innerHTML = rows.map((r, i) => `<tr>
        <td><select data-i="${i}" data-f="bahan_id">
          <option value="">— pilih bahan —</option>
          ${bahan.map(b => `<option value="${b.id}" ${+r.bahan_id === b.id ? 'selected' : ''}>
            ${esc(b.nama)} (${esc(b.satuan)})</option>`).join('')}
        </select></td>
        <td><input data-i="${i}" data-f="qty" type="number" min="0" step="0.01" value="${r.qty}" /></td>
        <td><input data-i="${i}" data-f="harga" type="number" min="0" value="${r.harga}" /></td>
        <td class="num">${Rp((+r.qty || 0) * (+r.harga || 0))}</td>
        <td><button class="x" data-del="${i}">&times;</button></td>
      </tr>`).join('');
      m.querySelector('#poTotal').textContent = Rp(rows.reduce((a, r) => a + (+r.qty || 0) * (+r.harga || 0), 0));

      tb.querySelectorAll('select,input').forEach(inp => {
        inp.addEventListener('input', () => {
          const i = +inp.dataset.i, f = inp.dataset.f;
          rows[i][f] = inp.value;
          if (f === 'bahan_id') {
            const b = bahan.find(x => x.id === +inp.value);
            if (b) rows[i].harga = Math.round(b.harga_beli);
          }
          drawRows();
        });
      });
      tb.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', () => {
        rows.splice(+b.dataset.del, 1);
        if (!rows.length) rows.push({ bahan_id: '', qty: 1, harga: 0 });
        drawRows();
      }));
    };
    drawRows();
    m.querySelector('#poAdd').addEventListener('click', () => {
      rows.push({ bahan_id: '', qty: 1, harga: 0 }); drawRows();
    });
    m.querySelector('#poSave').addEventListener('click', async () => {
      const items = rows.filter(r => r.bahan_id && +r.qty > 0)
        .map(r => ({ bahan_id: +r.bahan_id, qty: +r.qty, harga: +r.harga }));
      if (!items.length) return toast('Tambahkan minimal satu bahan', 'err');
      try {
        const d = await API.post('/api/pembelian', {
          supplier_id: +m.querySelector('#poSupplier').value,
          tanggal: m.querySelector('#poTanggal').value, items
        });
        closeModal();
        toast('PO ' + d.no_po + ' dibuat — status draft, terima barang untuk menambah stok');
        router();
      } catch (e) { fail(e); }
    });
  });
};

/* ============================ 4. BAHAN BAKU ============================ */
PAGES.bahan = async (el) => {
  setTitle('Bahan Baku', 'Master data persediaan — stok, harga rata-rata, dan batas minimum');
  const rows = await API.get('/api/bahan');
  const kritis = rows.filter(r => r.stok <= r.stok_min).length;

  el.innerHTML = `
    <div class="card">
      <div class="card-h"><h2>Daftar bahan baku</h2><div class="spacer"></div>
        ${kritis ? `<span class="badge warn">${kritis} di bawah minimum</span>` : '<span class="badge ok">stok aman</span>'}
        <button class="btn primary" id="btnBahan">${svg('plus', 16)} Tambah bahan</button></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>Kode</th><th>Nama bahan</th><th class="num">Stok</th><th class="num">Minimum</th>
          <th class="num">Harga rata-rata</th><th class="num">Nilai persediaan</th><th>Status</th><th class="right">Aksi</th></tr></thead>
        <tbody>${rows.map(b => `<tr>
          <td class="mono t-sub">${esc(b.kode)}</td>
          <td class="t-strong">${esc(b.nama)}</td>
          <td class="num">${num(b.stok, 2)} <span class="t-sub">${esc(b.satuan)}</span></td>
          <td class="num muted">${num(b.stok_min, 2)}</td>
          <td class="num">${Rp(b.harga_beli)}</td>
          <td class="num">${Rp(b.stok * b.harga_beli)}</td>
          <td>${b.stok <= b.stok_min ? '<span class="badge bad">kritis</span>'
            : b.stok <= b.stok_min * 1.5 ? '<span class="badge warn">menipis</span>'
            : '<span class="badge ok">aman</span>'}</td>
          <td class="right nowrap">
            <button class="btn sm" data-edit="${b.id}">Ubah</button>
            <button class="btn sm danger" data-del="${b.id}">Hapus</button>
          </td></tr>`).join('')}</tbody>
      </table></div></div>
    </div>`;

  const form = (b = {}) => {
    const m = openModal({
      title: b.id ? 'Ubah bahan baku' : 'Tambah bahan baku',
      body: `<label class="field"><span>Nama bahan</span><input id="bNama" value="${esc(b.nama || '')}" /></label>
        <div class="row">
          <label class="field"><span>Kode</span><input id="bKode" value="${esc(b.kode || '')}" placeholder="otomatis" /></label>
          <label class="field"><span>Satuan</span><input id="bSatuan" value="${esc(b.satuan || 'kg')}" /></label>
        </div>
        <div class="row">
          <label class="field"><span>Batas minimum</span><input id="bMin" type="number" step="0.01" value="${b.stok_min ?? 5}" /></label>
          <label class="field"><span>Harga beli / satuan</span><input id="bHarga" type="number" value="${b.harga_beli ?? 0}" /></label>
        </div>
        ${b.id ? '' : `<label class="field"><span>Stok awal</span><input id="bStok" type="number" step="0.01" value="0" /></label>`}`,
      footer: `<button class="btn" onclick="closeModal()">Batal</button>
               <button class="btn primary" id="bSave">Simpan</button>`
    });
    m.querySelector('#bSave').addEventListener('click', async () => {
      try {
        await API.post('/api/bahan', {
          id: b.id, nama: m.querySelector('#bNama').value, kode: m.querySelector('#bKode').value,
          satuan: m.querySelector('#bSatuan').value, stok_min: +m.querySelector('#bMin').value,
          harga_beli: +m.querySelector('#bHarga').value,
          stok: b.id ? undefined : +m.querySelector('#bStok').value
        });
        closeModal(); toast('Bahan baku disimpan'); router();
      } catch (e) { fail(e); }
    });
  };

  document.getElementById('btnBahan').addEventListener('click', () => form({}));
  el.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () =>
    form(rows.find(r => r.id === +b.dataset.edit))));
  el.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Hapus bahan ini?')) return;
    try { await API.del('/api/bahan/' + b.dataset.del); toast('Bahan dihapus'); router(); } catch (e) { fail(e); }
  }));
};

/* ============================ 5. SUPPLIER ============================ */
PAGES.supplier = async (el) => {
  setTitle('Supplier', 'Master data pemasok bahan baku');
  const rows = await API.get('/api/supplier');
  el.innerHTML = `
    <div class="card">
      <div class="card-h"><h2>Daftar supplier</h2><div class="spacer"></div>
        <button class="btn primary" id="btnSup">${svg('plus', 16)} Tambah supplier</button></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>Nama supplier</th><th>Kontak</th><th>Telepon</th><th>Alamat</th><th class="right">Aksi</th></tr></thead>
        <tbody>${rows.map(s => `<tr>
          <td class="t-strong">${esc(s.nama)}</td><td>${esc(s.kontak || '-')}</td>
          <td class="mono">${esc(s.telepon || '-')}</td><td class="t-sub">${esc(s.alamat || '-')}</td>
          <td class="right nowrap"><button class="btn sm" data-edit="${s.id}">Ubah</button></td></tr>`).join('')}</tbody>
      </table></div></div>
    </div>`;

  const form = (s = {}) => {
    const m = openModal({
      title: s.id ? 'Ubah supplier' : 'Tambah supplier',
      body: `<label class="field"><span>Nama supplier</span><input id="sNama" value="${esc(s.nama || '')}" /></label>
        <div class="row">
          <label class="field"><span>Nama kontak</span><input id="sKontak" value="${esc(s.kontak || '')}" /></label>
          <label class="field"><span>Telepon</span><input id="sTelp" value="${esc(s.telepon || '')}" /></label>
        </div>
        <label class="field"><span>Alamat</span><input id="sAlamat" value="${esc(s.alamat || '')}" /></label>`,
      footer: `<button class="btn" onclick="closeModal()">Batal</button>
               <button class="btn primary" id="sSave">Simpan</button>`
    });
    m.querySelector('#sSave').addEventListener('click', async () => {
      try {
        await API.post('/api/supplier', {
          id: s.id, nama: m.querySelector('#sNama').value, kontak: m.querySelector('#sKontak').value,
          telepon: m.querySelector('#sTelp').value, alamat: m.querySelector('#sAlamat').value
        });
        closeModal(); toast('Supplier disimpan'); router();
      } catch (e) { fail(e); }
    });
  };
  document.getElementById('btnSup').addEventListener('click', () => form({}));
  el.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () =>
    form(rows.find(r => r.id === +b.dataset.edit))));
};

/* ============================ 6. PRODUK & RESEP ============================ */
PAGES.produk = async (el) => {
  setTitle('Produk & Resep', 'Master produk jadi beserta bill of material (BOM) penentu HPP');
  const [rows, bahan] = await Promise.all([API.get('/api/produk'), API.get('/api/bahan')]);

  el.innerHTML = `
    <div class="card">
      <div class="card-h"><h2>Daftar produk</h2><div class="spacer"></div>
        <button class="btn primary" id="btnProduk">${svg('plus', 16)} Tambah produk</button></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>Kode</th><th>Produk</th><th>Kategori</th><th class="num">Stok</th>
          <th class="num">Harga jual</th><th class="num">HPP</th><th class="num">Margin</th><th class="right">Aksi</th></tr></thead>
        <tbody>${rows.map(p => `<tr>
          <td class="mono t-sub">${esc(p.kode)}</td>
          <td class="t-strong">${esc(p.nama)}</td>
          <td><span class="badge neutral">${esc(p.kategori || '-')}</span></td>
          <td class="num">${num(p.stok, 0)} pcs</td>
          <td class="num">${Rp(p.harga_jual)}</td>
          <td class="num muted">${Rp(p.hpp)}</td>
          <td class="num" style="color:var(--ok);font-weight:650">${num(p.harga_jual ? (p.margin / p.harga_jual) * 100 : 0, 1)}%</td>
          <td class="right nowrap">
            <button class="btn sm" data-resep="${p.id}">Resep</button>
            <button class="btn sm" data-edit="${p.id}">Ubah</button>
          </td></tr>`).join('')}</tbody>
      </table></div></div>
    </div>
    <p class="small muted" style="margin-top:12px">HPP dihitung otomatis: Σ (jumlah bahan pada resep × harga rata-rata bahan). Perubahan harga beli langsung memperbarui HPP.</p>`;

  const formProduk = (p = {}) => {
    const m = openModal({
      title: p.id ? 'Ubah produk' : 'Tambah produk',
      body: `<label class="field"><span>Nama produk</span><input id="pNama" value="${esc(p.nama || '')}" /></label>
        <div class="row">
          <label class="field"><span>Kode</span><input id="pKode" value="${esc(p.kode || '')}" placeholder="otomatis" /></label>
          <label class="field"><span>Kategori</span><input id="pKat" value="${esc(p.kategori || 'Roti')}" /></label>
        </div>
        <div class="row">
          <label class="field"><span>Harga jual</span><input id="pHarga" type="number" value="${p.harga_jual ?? 0}" /></label>
          <label class="field"><span>Stok minimum</span><input id="pMin" type="number" value="${p.stok_min ?? 5}" /></label>
        </div>`,
      footer: `<button class="btn" onclick="closeModal()">Batal</button>
               <button class="btn primary" id="pSave">Simpan</button>`
    });
    m.querySelector('#pSave').addEventListener('click', async () => {
      try {
        await API.post('/api/produk', {
          id: p.id, nama: m.querySelector('#pNama').value, kode: m.querySelector('#pKode').value,
          kategori: m.querySelector('#pKat').value, harga_jual: +m.querySelector('#pHarga').value,
          stok_min: +m.querySelector('#pMin').value
        });
        closeModal(); toast('Produk disimpan'); router();
      } catch (e) { fail(e); }
    });
  };

  document.getElementById('btnProduk').addEventListener('click', () => formProduk({}));
  el.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () =>
    formProduk(rows.find(r => r.id === +b.dataset.edit))));

  el.querySelectorAll('[data-resep]').forEach(b => b.addEventListener('click', async () => {
    const pid = +b.dataset.resep;
    const p = rows.find(r => r.id === pid);
    const d = await API.get('/api/resep?produk_id=' + pid);
    let items = d.items.map(i => ({ bahan_id: i.bahan_id, qty: i.qty }));
    if (!items.length) items = [{ bahan_id: '', qty: 0.05 }];

    const body = `
      <p class="small muted" style="margin-bottom:12px">Resep untuk <b>1 unit ${esc(p.nama)}</b>.
        Perubahan resep langsung mengubah HPP produk.</p>
      <div class="tablewrap"><table>
        <thead><tr><th>Bahan</th><th style="width:130px">Jumlah</th><th class="num">Biaya</th><th></th></tr></thead>
        <tbody id="rsRows"></tbody>
        <tfoot><tr><td colspan="2">HPP per unit</td><td class="num" id="rsHpp">Rp 0</td><td></td></tr></tfoot>
      </table></div>
      <button class="btn sm" id="rsAdd" style="margin-top:10px">+ Tambah bahan</button>`;
    const m = openModal({
      title: 'Resep — ' + p.nama, wide: true, body,
      footer: `<button class="btn" onclick="closeModal()">Batal</button>
               <button class="btn primary" id="rsSave">Simpan resep</button>`
    });

    const draw = () => {
      const tb = m.querySelector('#rsRows');
      tb.innerHTML = items.map((it, i) => {
        const b = bahan.find(x => x.id === +it.bahan_id);
        const biaya = b ? b.harga_beli * (+it.qty || 0) : 0;
        return `<tr>
          <td><select data-i="${i}" data-f="bahan_id">
            <option value="">— pilih bahan —</option>
            ${bahan.map(x => `<option value="${x.id}" ${+it.bahan_id === x.id ? 'selected' : ''}>${esc(x.nama)} (${esc(x.satuan)})</option>`).join('')}
          </select></td>
          <td><input data-i="${i}" data-f="qty" type="number" step="0.001" min="0" value="${it.qty}" /></td>
          <td class="num">${Rp(biaya)}</td>
          <td><button class="x" data-del="${i}">&times;</button></td></tr>`;
      }).join('');
      m.querySelector('#rsHpp').textContent = Rp(items.reduce((a, it) => {
        const b = bahan.find(x => x.id === +it.bahan_id);
        return a + (b ? b.harga_beli * (+it.qty || 0) : 0);
      }, 0));
      tb.querySelectorAll('select,input').forEach(inp => inp.addEventListener('input', () => {
        items[+inp.dataset.i][inp.dataset.f] = inp.value; draw();
      }));
      tb.querySelectorAll('[data-del]').forEach(btn => btn.addEventListener('click', () => {
        items.splice(+btn.dataset.del, 1);
        if (!items.length) items.push({ bahan_id: '', qty: 0.01 });
        draw();
      }));
    };
    draw();
    m.querySelector('#rsAdd').addEventListener('click', () => { items.push({ bahan_id: '', qty: 0.01 }); draw(); });
    m.querySelector('#rsSave').addEventListener('click', async () => {
      const payload = items.filter(i => i.bahan_id && +i.qty > 0)
        .map(i => ({ bahan_id: +i.bahan_id, qty: +i.qty }));
      if (!payload.length) return toast('Isi minimal satu bahan', 'err');
      try {
        await API.post('/api/resep', { produk_id: pid, items: payload });
        closeModal(); toast('Resep disimpan — HPP diperbarui'); router();
      } catch (e) { fail(e); }
    });
  }));
};

/* ============================ 7. PENGELUARAN ============================ */
PAGES.pengeluaran = async (el) => {
  setTitle('Pengeluaran', 'Beban operasional — otomatis mengurangi kas dan laba bersih');
  const rows = await API.get('/api/pengeluaran');
  const total = rows.reduce((a, r) => a + r.jumlah, 0);

  el.innerHTML = `
    <div class="grid g32" style="align-items:start">
      <div class="card">
        <div class="card-h"><h2>Catat pengeluaran</h2></div>
        <div class="card-b">
          <form id="formKeluar">
            <div class="row">
              <label class="field"><span>Tanggal</span><input id="kTanggal" type="date" value="${todayISO()}" /></label>
              <label class="field"><span>Kategori</span>
                <select id="kKategori">
                  <option>Gaji Karyawan</option><option>Listrik & Gas</option>
                  <option>Sewa Tempat</option><option>Perawatan Mesin</option>
                  <option>Pemasaran</option><option>Operasional</option>
                </select></label>
            </div>
            <label class="field"><span>Keterangan</span><input id="kKet" placeholder="contoh: servis mixer" /></label>
            <label class="field"><span>Jumlah (Rp)</span><input id="kJumlah" type="number" min="1" required /></label>
            <button class="btn primary block" type="submit" style="padding:11px">Simpan pengeluaran</button>
          </form>
        </div>
      </div>
      <div class="card">
        <div class="card-h"><h2>Riwayat pengeluaran</h2><div class="spacer"></div>
          <span class="badge info">${Rp(total)}</span></div>
        <div class="card-b flush"><div class="tablewrap"><table>
          <thead><tr><th>Tanggal</th><th>Kategori</th><th>Keterangan</th><th class="num">Jumlah</th></tr></thead>
          <tbody>${rows.slice(0, 20).map(r => `<tr>
            <td class="nowrap">${tgl(r.tanggal)}</td>
            <td><span class="badge neutral">${esc(r.kategori)}</span></td>
            <td class="t-sub">${esc(r.keterangan || '-')}</td>
            <td class="num">${Rp(r.jumlah)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Belum ada pengeluaran.</td></tr>'}</tbody>
        </table></div></div>
      </div>
    </div>`;

  document.getElementById('formKeluar').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await API.post('/api/pengeluaran', {
        tanggal: document.getElementById('kTanggal').value,
        kategori: document.getElementById('kKategori').value,
        keterangan: document.getElementById('kKet').value,
        jumlah: +document.getElementById('kJumlah').value
      });
      toast('Pengeluaran tercatat — kas berkurang otomatis');
      router();
    } catch (err) { fail(err); }
  });
};

/* ============================ 8. LABA RUGI & KAS ============================ */
PAGES.keuangan = async (el) => {
  setTitle('Laba Rugi & Buku Kas', 'Laporan keuangan otomatis dari transaksi seluruh modul');
  const dari = sessionStorage.getItem('keu_dari') || firstOfMonthISO();
  const sampai = sessionStorage.getItem('keu_sampai') || todayISO();

  el.innerHTML = `
    <div class="card" style="margin-bottom:16px"><div class="card-b">
      <div class="inline" style="gap:12px;flex-wrap:wrap">
        <label class="field" style="margin:0"><span>Dari tanggal</span><input id="kDari" type="date" value="${dari}" /></label>
        <label class="field" style="margin:0"><span>Sampai tanggal</span><input id="kSampai" type="date" value="${sampai}" /></label>
        <button class="btn primary" id="kFilter" style="margin-top:18px">Tampilkan</button>
      </div>
    </div></div>
    <div id="keuBody"><div class="card"><div class="card-b muted">Memuat…</div></div></div>`;

  const load = async () => {
    const d1 = document.getElementById('kDari').value;
    const d2 = document.getElementById('kSampai').value;
    sessionStorage.setItem('keu_dari', d1); sessionStorage.setItem('keu_sampai', d2);
    const [lr, kas] = await Promise.all([
      API.get(`/api/keuangan/labarugi?dari=${d1}&sampai=${d2}`),
      API.get(`/api/keuangan/kas?dari=${d1}&sampai=${d2}`)]);

    const masuk = kas.filter(k => k.tipe === 'masuk').reduce((a, k) => a + k.jumlah, 0);
    const keluar = kas.filter(k => k.tipe === 'keluar').reduce((a, k) => a + k.jumlah, 0);

    document.getElementById('keuBody').innerHTML = `
      <div class="grid g4" style="margin-bottom:16px">
        <div class="card kpi"><div class="label">Pendapatan</div><div class="value">${Rp(lr.pendapatan)}</div>
          <div class="sub">${lr.jumlah_transaksi} transaksi</div></div>
        <div class="card kpi"><div class="label">HPP</div><div class="value">${Rp(lr.hpp)}</div>
          <div class="sub">${num(lr.pendapatan ? (lr.hpp / lr.pendapatan) * 100 : 0, 1)}% dari pendapatan</div></div>
        <div class="card kpi"><div class="label">Laba kotor</div><div class="value">${Rp(lr.laba_kotor)}</div>
          <div class="sub">margin ${num(lr.margin_kotor, 1)}%</div></div>
        <div class="card kpi accent"><div class="label">Laba bersih</div>
          <div class="value" style="color:${lr.laba_bersih >= 0 ? 'var(--ok)' : 'var(--bad)'}">${Rp(lr.laba_bersih)}</div>
          <div class="sub">margin ${num(lr.margin_bersih, 1)}%</div></div>
      </div>

      <div class="grid g2" style="align-items:start">
        <div class="card">
          <div class="card-h"><h2>Laporan laba rugi</h2><div class="spacer"></div>
            <span class="badge neutral">${tgl(d1)} – ${tgl(d2)}</span></div>
          <div class="card-b flush"><table>
            <tbody>
              <tr><td class="t-strong">Pendapatan penjualan</td><td class="num">${Rp(lr.pendapatan)}</td></tr>
              <tr><td>Harga pokok produksi (HPP)</td><td class="num" style="color:var(--bad)">(${Rp(lr.hpp)})</td></tr>
              <tr style="background:#fbf9f6"><td class="t-strong">Laba kotor</td><td class="num t-strong">${Rp(lr.laba_kotor)}</td></tr>
              ${lr.beban.map(b => `<tr><td class="t-sub" style="padding-left:26px">${esc(b.kategori)}</td>
                <td class="num" style="color:var(--bad)">(${Rp(b.jumlah)})</td></tr>`).join('')}
              <tr><td class="t-strong">Total beban operasional</td><td class="num" style="color:var(--bad)">(${Rp(lr.total_beban)})</td></tr>
            </tbody>
            <tfoot><tr><td>Laba bersih</td>
              <td class="num" style="color:${lr.laba_bersih >= 0 ? 'var(--ok)' : 'var(--bad)'}">${Rp(lr.laba_bersih)}</td></tr></tfoot>
          </table></div>
        </div>

        <div class="card">
          <div class="card-h"><h2>Ringkasan arus kas</h2></div>
          <div class="card-b">
            <div class="cart-total"><span>Kas masuk</span><b style="color:var(--ok)">${Rp(masuk)}</b></div>
            <div class="cart-total"><span>Kas keluar</span><b style="color:var(--bad)">${Rp(keluar)}</b></div>
            <div class="cart-total" style="border-top:1px solid var(--line);margin-top:8px">
              <span>Arus kas bersih</span><b>${Rp(masuk - keluar)}</b></div>
            <p class="small muted" style="margin-top:14px">Pembelian bahan dicatat sebagai kas keluar sekaligus menambah nilai persediaan;
              biayanya baru diakui sebagai HPP saat produk terjual.</p>
          </div>
        </div>
      </div>

      <div class="card" style="margin-top:16px">
        <div class="card-h"><h2>Buku kas (jurnal transaksi)</h2><div class="spacer"></div>
          <span class="badge info">${kas.length} baris</span></div>
        <div class="card-b flush"><div class="tablewrap"><table>
          <thead><tr><th>Tanggal</th><th>Tipe</th><th>Kategori</th><th>Keterangan</th><th>Referensi</th><th class="num">Jumlah</th></tr></thead>
          <tbody>${kas.slice(0, 80).map(k => `<tr>
            <td class="nowrap">${tgl(k.tanggal)}</td>
            <td>${k.tipe === 'masuk' ? '<span class="badge ok">masuk</span>' : '<span class="badge bad">keluar</span>'}</td>
            <td>${esc(k.kategori)}</td><td class="t-sub">${esc(k.keterangan || '-')}</td>
            <td class="mono t-sub">${esc(k.ref_tipe || '-')} #${k.ref_id || '-'}</td>
            <td class="num" style="color:${k.tipe === 'masuk' ? 'var(--ok)' : 'var(--bad)'}">
              ${k.tipe === 'masuk' ? '+' : '−'} ${Rp(k.jumlah)}</td></tr>`).join('')}</tbody>
        </table></div></div>
      </div>`;
  };

  document.getElementById('kFilter').addEventListener('click', load);
  await load();
};

/* ============================ 9. LAPORAN ============================ */
let LAP_TAB = 'penjualan';
PAGES.laporan = async (el) => {
  setTitle('Laporan', 'Analisis penjualan, produksi, dan posisi persediaan');
  const dari = sessionStorage.getItem('lap_dari') || firstOfMonthISO();
  const sampai = sessionStorage.getItem('lap_sampai') || todayISO();

  el.innerHTML = `
    <div class="card" style="margin-bottom:16px"><div class="card-b">
      <div class="inline" style="gap:10px;flex-wrap:wrap">
        <button class="btn ${LAP_TAB === 'penjualan' ? 'dark' : ''}" data-tab="penjualan">Penjualan</button>
        <button class="btn ${LAP_TAB === 'produksi' ? 'dark' : ''}" data-tab="produksi">Produksi</button>
        <button class="btn ${LAP_TAB === 'stok' ? 'dark' : ''}" data-tab="stok">Persediaan</button>
        <div style="flex:1"></div>
        <label class="field" style="margin:0"><span>Dari</span><input id="lDari" type="date" value="${dari}" /></label>
        <label class="field" style="margin:0"><span>Sampai</span><input id="lSampai" type="date" value="${sampai}" /></label>
        <button class="btn primary" id="lFilter" style="margin-top:18px">Terapkan</button>
      </div>
    </div></div>
    <div id="lapBody"><div class="card"><div class="card-b muted">Memuat…</div></div></div>`;

  const load = async () => {
    const d1 = document.getElementById('lDari').value, d2 = document.getElementById('lSampai').value;
    sessionStorage.setItem('lap_dari', d1); sessionStorage.setItem('lap_sampai', d2);
    const body = document.getElementById('lapBody');

    if (LAP_TAB === 'penjualan') {
      const d = await API.get(`/api/laporan/penjualan?dari=${d1}&sampai=${d2}`);
      const omzet = d.harian.reduce((a, h) => a + h.omzet, 0);
      const hpp = d.harian.reduce((a, h) => a + h.hpp, 0);
      const max = Math.max(...d.harian.map(h => h.omzet), 1);
      body.innerHTML = `
        <div class="grid g3" style="margin-bottom:16px">
          <div class="card kpi"><div class="label">Total omzet</div><div class="value">${Rp(omzet)}</div></div>
          <div class="card kpi"><div class="label">Total HPP</div><div class="value">${Rp(hpp)}</div></div>
          <div class="card kpi"><div class="label">Laba kotor</div><div class="value" style="color:var(--ok)">${Rp(omzet - hpp)}</div></div>
        </div>
        <div class="card" style="margin-bottom:16px">
          <div class="card-h"><h2>Omzet harian</h2></div>
          <div class="card-b"><div class="chart">
            ${d.harian.map(h => `<div class="bar" title="${tgl(h.tanggal)}: ${Rp(h.omzet)}">
              <div class="fill" style="height:${Math.max(3, (h.omzet / max) * 100)}%"></div>
              <div class="cap">${tgl(h.tanggal).slice(0, 6)}</div></div>`).join('') ||
              '<div class="empty">Tidak ada data pada periode ini.</div>'}
          </div></div>
        </div>
        <div class="grid g2">
          <div class="card"><div class="card-h"><h2>Rekap harian</h2></div>
            <div class="card-b flush"><div class="tablewrap" style="max-height:420px;overflow:auto"><table>
              <thead><tr><th>Tanggal</th><th class="num">Transaksi</th><th class="num">Omzet</th><th class="num">HPP</th></tr></thead>
              <tbody>${d.harian.map(h => `<tr><td>${tgl(h.tanggal)}</td>
                <td class="num">${h.trx}</td><td class="num">${Rp(h.omzet)}</td>
                <td class="num muted">${Rp(h.hpp)}</td></tr>`).join('')}</tbody>
            </table></div></div></div>
          <div class="card"><div class="card-h"><h2>Kontribusi per produk</h2></div>
            <div class="card-b flush"><div class="tablewrap"><table>
              <thead><tr><th>Produk</th><th class="num">Terjual</th><th class="num">Omzet</th><th class="num">Laba kotor</th></tr></thead>
              <tbody>${d.per_produk.map(p => `<tr><td class="t-strong">${esc(p.nama)}</td>
                <td class="num">${num(p.qty, 0)}</td><td class="num">${Rp(p.omzet)}</td>
                <td class="num" style="color:var(--ok)">${Rp(p.omzet - p.hpp)}</td></tr>`).join('')}</tbody>
            </table></div></div></div>
        </div>`;
    } else if (LAP_TAB === 'produksi') {
      const d = await API.get(`/api/laporan/produksi?dari=${d1}&sampai=${d2}`);
      const total = d.reduce((a, r) => a + r.biaya_bahan, 0);
      body.innerHTML = `
        <div class="card"><div class="card-h"><h2>Rekap produksi</h2><div class="spacer"></div>
          <span class="badge info">${d.length} batch · ${Rp(total)} biaya bahan</span></div>
          <div class="card-b flush"><div class="tablewrap"><table>
            <thead><tr><th>Batch</th><th>Tanggal</th><th>Produk</th><th class="num">Jumlah</th>
              <th class="num">Biaya bahan</th><th class="num">HPP/unit</th></tr></thead>
            <tbody>${d.map(r => `<tr><td class="mono t-sub">${esc(r.no_batch)}</td>
              <td>${tgl(r.tanggal)}</td><td class="t-strong">${esc(r.produk)}</td>
              <td class="num">${num(r.qty, 0)} pcs</td><td class="num">${Rp(r.biaya_bahan)}</td>
              <td class="num muted">${Rp(r.hpp_unit)}</td></tr>`).join('') ||
              '<tr><td colspan="6" class="empty">Tidak ada produksi pada periode ini.</td></tr>'}</tbody>
          </table></div></div></div>`;
    } else {
      const d = await API.get('/api/laporan/stok');
      const nilaiBahan = d.bahan.reduce((a, b) => a + b.nilai, 0);
      const nilaiProduk = d.produk.reduce((a, p) => a + p.stok * p.hpp, 0);
      body.innerHTML = `
        <div class="grid g3" style="margin-bottom:16px">
          <div class="card kpi"><div class="label">Nilai bahan baku</div><div class="value">${Rp(nilaiBahan)}</div></div>
          <div class="card kpi"><div class="label">Nilai produk jadi</div><div class="value">${Rp(nilaiProduk)}</div></div>
          <div class="card kpi accent"><div class="label">Total persediaan</div><div class="value">${Rp(nilaiBahan + nilaiProduk)}</div></div>
        </div>
        <div class="grid g2">
          <div class="card"><div class="card-h"><h2>Persediaan bahan baku</h2></div>
            <div class="card-b flush"><div class="tablewrap"><table>
              <thead><tr><th>Bahan</th><th class="num">Stok</th><th class="num">Nilai</th></tr></thead>
              <tbody>${d.bahan.map(b => `<tr><td>${esc(b.nama)}</td>
                <td class="num">${num(b.stok, 2)} ${esc(b.satuan)}</td><td class="num">${Rp(b.nilai)}</td></tr>`).join('')}</tbody>
            </table></div></div></div>
          <div class="card"><div class="card-h"><h2>Stok produk jadi & margin</h2></div>
            <div class="card-b flush"><div class="tablewrap"><table>
              <thead><tr><th>Produk</th><th class="num">Stok</th><th class="num">HPP</th><th class="num">Margin</th></tr></thead>
              <tbody>${d.produk.map(p => `<tr><td class="t-strong">${esc(p.nama)}</td>
                <td class="num">${num(p.stok, 0)}</td><td class="num muted">${Rp(p.hpp)}</td>
                <td class="num" style="color:var(--ok)">${Rp(p.margin)}</td></tr>`).join('')}</tbody>
            </table></div></div></div>
        </div>`;
    }
  };

  el.querySelectorAll('[data-tab]').forEach(b => b.addEventListener('click', () => {
    LAP_TAB = b.dataset.tab; router();
  }));
  document.getElementById('lFilter').addEventListener('click', load);
  await load();
};

/* ============================ 10. LOG AKTIVITAS ============================ */
PAGES.audit = async (el) => {
  setTitle('Log Aktivitas', 'Jejak audit setiap transaksi dan perubahan data');
  const rows = await API.get('/api/audit');
  el.innerHTML = `
    <div class="card">
      <div class="card-h"><h2>Jejak audit sistem</h2><div class="spacer"></div>
        <span class="badge info">${rows.length} aktivitas terakhir</span></div>
      <div class="card-b flush"><div class="tablewrap"><table>
        <thead><tr><th>Waktu</th><th>Pengguna</th><th>Aksi</th><th>Detail</th></tr></thead>
        <tbody>${rows.map(r => `<tr>
          <td class="nowrap t-sub">${tglWaktu(r.waktu)}</td>
          <td class="t-strong">${esc(r.user || '-')}</td>
          <td><span class="badge neutral">${esc(r.aksi)}</span></td>
          <td class="t-sub">${esc(r.detail || '-')}</td></tr>`).join('')}</tbody>
      </table></div></div>
    </div>`;
};
