# MVP pertama — Intake → Breakdown → Klasifikasi → Review

**16 Oktober 2026 · aturan lokal, tanpa AI eksternal.** Prioritas pertama adalah memahami struktur data yang masuk, **bukan memaksa semua file menjadi transaksi pembelian**.

## Cara mencoba di preview

1. Klik **Tambah data**. **Intake & klasifikasi** sekarang mode utama/default di UI.
2. Konfirmasikan lingkup karet alam dan hak unggah, lalu masukkan XLSX, CSV, atau TSV.
3. Setelah raw tersimpan, **Breakdown & klasifikasi** tampil otomatis. Lihat jumlah lembar, tabel, record-tabel teramati, dan struktur/cakupan sumber.
4. Pilih **Dataset terdeteksi**. Masing-masing tabel memiliki saran kategori bisnis sendiri, alasan, koordinat sumber, serta tipe/peran kolom. Klik nama kolom untuk distribusi tipe, alasan, dan sampel; buka preview untuk contoh baris.
5. Periksa/koreksi kategori, peran, dan tipe metadata. Centang konfirmasi lalu **Simpan review tabel**. Konfirmasi direset saat saran diubah. Review hanya berlaku untuk tabel terpilih.
6. Buka kembali melalui **Data saya → Pusat data → Breakdown**, atau riwayat versi → **Breakdown & bukti raw**. Review tersimpan dan saran awal tetap dibedakan.

Tidak ada workbook riil pengguna yang dipakai untuk verifikasi tahap ini. Jangan mengunggah data sensitif ke preview. “Lokal” berarti aturan berjalan di server aplikasi; preview bukan otomatis komputer Windows pengguna.

## Dua lapis klasifikasi

### 1. Jenis dataset bisnis

| Kategori usulan | Contoh kombinasi indikator header |
|---|---|
| Pembelian | pemasok + harga + tanggal/material |
| Penjualan | pembeli + harga + tanggal/material |
| Harga / benchmark | harga + tanggal/material, tanpa indikator pemasok/pembeli |
| Stok / persediaan | saldo stok atau barang masuk+keluar, bersama tanggal/material/gudang |
| Produksi | hasil produksi + tanggal/material/lini produksi |
| Mutu / hasil uji | parameter mutu atau ID sampel+hasil uji, bersama tanggal/material/sampel |
| Logistik / pengiriman | ID pengiriman + tanggal/asal/tujuan |
| Cuaca | sedikitnya dua dari curah hujan, suhu, kelembapan |
| Ketertelusuran | lot/batch + asal/koordinat |
| Campuran | lebih dari satu kategori mendapat dukungan; agregat file juga dapat berisi beberapa kategori/hasil belum jelas |
| Belum terklasifikasi | indikator tidak cukup; tidak membuat pemasok/harga/tanggal yang tidak ada |

Ini aturan yang bisa dijelaskan, **bukan angka keyakinan model atau sertifikat bahwa isi tabel benar**. Header "Harga" saja tidak membuktikan benchmark atau transaksi; kategori perlu review. Satu workbook dapat memuat tabel stok dan produksi yang berbeda. Kategori deklarasi ketika upload disimpan sebagai konteks tersendiri, bukan dipaksakan sebagai hasil mesin.

### 2. Tipe teramati dan peran kolom

- Tipe asli XLSX: angka, boolean, tanggal, teks, kosong; campuran dan error dipisahkan.
- CSV/TSV mempertahankan teks: angka-dalam-teks, kode dengan nol awal, teks berpola tanggal ISO/tanggal ambigu, persen, nominal bermata uang, dan periode dibedakan. Pola tanggal **bukan validasi kalender**.
- Peran: tanggal, pemasok/pembeli, material/grade, harga/mata uang/unit/basis berat/KKK/kuantitas, stok/gudang, produksi, mutu, pengiriman, asal/tujuan/lot/koordinat, cuaca, atau belum dikenali.
- Peran berasal dari alias header terdaftar, tidak ditebak semata-mata dari besarnya angka atau isi sel. Peran konflik/tak dikenal memerlukan review.
- Distribusi tipe dan kosong dihitung pada **seluruh bagian yang dipindai**, bukan hanya empat baris preview. Nol dan `false` bukan kosong. Baris yang seluruh sel rentang tabelnya kosong bukan record tabel.
- Tidak mengonversi format angka/tanggal, mata uang, satuan, fraksi KKK, atau identitas. Koreksi tipe saat review adalah **metadata**, bukan casting/validasi nilai.

## Breakdown dan provenance

Struktur: **file → lembar → tabel terdeteksi → kolom → contoh nilai/baris**. Deteksi header dibatasi satu/dua baris teks dan 50 record awal per bagian. Bagian tabel dapat dipisahkan oleh baris kosong, header berikutnya, atau kolom pemisah yang sepenuhnya kosong bila alias mendukung kedua kelompok. Ini heuristik; bukan segmentasi seluruh tata letak Excel.

Setiap tabel/kolom menyertakan nama lembar, nomor kolom, baris header/data, dan referensi seperti `Stok!C3`. CSV multiline mempertahankan rentang baris fisik awal–akhir. Bagian/sel yang belum tercakup tabel dilaporkan, bukan diam-diam dinyatakan sudah dipahami. `data_records_scanned` menghitung **record per tabel**, sehingga tabel berdampingan bisa memakai baris fisik yang sama.

Raw diunduh dari endpoint attachment terotorisasi dengan verifikasi checksum. Breakdown tidak mengubah raw, manifest akuisisi, snapshot pemetaan, bukti pembelian lama, atau record kolektor.

## Review, bukan publikasi

- Saran awal disimpan dalam `parsed_meta.breakdown`. Review disimpan pada tabel terpisah `intake_classification_reviews` sebagai snapshot revisi eksplisit.
- Review terikat **versi file + hash profil**; hash kedaluwarsa ditolak `409`. Riwayat sebelumnya tidak ditimpa; review pada hash lama dilabeli stale dan tidak diterapkan.
- Tabel lain tetap belum direview. Penyimpanan tabel berikutnya menggabungkan keputusan yang sudah disimpan untuk profil yang sama. Replay keputusan identik idempotent; maksimum 200 revisi review per versi file.
- Semua kolom dari tabel terpilih harus disertakan; ID, kategori, peran, dan tipe divalidasi. Nilai sel baru tidak diterima dalam request review.
- Review **tidak** menerbitkan observasi, mengaktifkan normalisasi stok/mutu, membuat relasi bisnis baru, mengingat alias otomatis, atau melatih model. Memori Asisten Excel pembelian tetap fitur terpisah dengan persetujuan sendiri.
- Pemilik privat dapat mereview; profil demo/eksternal publik read-only. Workspace lain tidak dapat membaca profil privat.

## Format dan batas MVP

- Otomatis: **XLSX/CSV/TSV**, termasuk event ber-Content-Type `text/csv` / `text/tab-separated-values`. API upload legacy yang tetap default `purchase` juga menyertakan profil umum setelah parse berhasil; tidak mengubah kontrak pemetaannya.
- Format lain, termasuk XLS legacy, JSON, PDF dan gambar: raw tetap diterima sesuai kebijakan; indeks mengikuti dukungan parser lama. **Belum ada klasifikasi struktur otomatis** untuk format tersebut. Tidak ada OCR atau eksekusi lampiran.
- Profil: maksimum **10 MiB file**, **5.000 baris/record logis total**, **64 kolom**, **10 lembar terlihat**, **20 tabel total / 5 per lembar**. Lembar tersembunyi dilewati dan dicatat. Ketika batas tercapai, hasil partial; jumlah teramati tidak diekstrapolasi menjadi total file.
- Workbook: batas aman ZIP internal 2.000 entry / 60 MiB uncompressed. Workbook terenkripsi/rusak/macro tidak dipaksakan agar terbaca. Formula tidak dijalankan; hanya nilai cache, yang bisa kosong/usang. Kosong bukan nol.
- Preview: 4 baris, 12 kolom, tampilan nilai dipotong. Sampel kolom: 2 nilai; bukan salinan seluruh tabel. Jika laporan terlalu besar, sampel/preview dapat dihapus dan cakupan dilabeli terbatas.
- Subprocess: timeout 18 detik; Linux 12 detik CPU / 384 MiB address space. Windows dapat tidak memiliki batas resource OS yang sama; timeout tetap berlaku. Ini bukan sandbox malware/antivirus penuh.
- Crosstab, pivot, header numerik, subtotal/footer, layout sangat tidak konsisten, atau tabel tanpa header bisa belum terurai dengan tepat. Tidak ada editor rentang/header manual generik pada tahap ini. Baca koordinat, preview, cakupan dan raw; ekspor tabel yang lebih sederhana bila perlu.
- Arsip lama tidak diubah diam-diam. Pemilik dapat menekan **Jalankan breakdown** untuk menghasilkan metadata dari raw yang sama tanpa mengubah status/pemetaan aktifnya.

## API

- `GET /api/versions/{id}/breakdown`: availability, profile/hash, review/stale, can_edit, pending/job, kategori/peran/tipe yang diizinkan; `published:false`.
- `POST /api/versions/{id}/breakdown`: antrekan analisis arsip lama/retry kegagalan; `202`, idempotent, owner-only. Tidak mempublikasikan apa pun.
- `POST /api/versions/{id}/breakdown/review`: `profile_hash`, `confirmed:true`, dan `tables` (table_id, category, seluruh columns: column_id/role/datatype). Ambil ID dan enum dari GET, bukan ditebak. Respons revision/reused, `published:false`, `raw_changed:false`.
- `GET /api/versions/{id}/raw` dan `/acquisitions`: byte asli dan ledger penerimaan tetap kontrak lama.

Lihat [API.md](API.md) dan OpenAPI lokal. API legacy upload tetap default `purchase` untuk kompatibilitas; client baru gunakan eksplisit `intake_mode=archive`.

## Hasil uji aktual

**Linux / CPython 3.13 / SQLite**:
- **174 backend tests lulus**, 1 dilewati (integrasi PostgreSQL opsional), 1 warning deprecation Starlette/httpx; termasuk **43 tes khusus breakdown/klasifikasi/review**.
- **14 unit tests gerak**, TypeScript + build Vite lulus.
- **17 pemeriksaan browser MVP lulus**, desktop/mobile 390/768/1440, raw identik, review terpisah, cakupan partial, ownership, dukungan format jujur; **0 JavaScript page errors**, private QA dibersihkan.
- **12 browser regression Asisten Excel** dan **16 browser regression galaksi** lulus; 0 page errors.
- Integrity database utama: SQLite `ok`, 0 foreign-key issues; **13 aset raw** diverifikasi ukuran dan SHA-256, **0 dokumen QA** tersisa. Knowledge records pada pemeriksaan akhir **2.463** (sebelumnya 2.440; kolektor tetap berjalan). Angka dapat berubah mengikuti jadwal.

Bukti build/integrity: [INTAKE_BUILD_VERIFICATION.json](INTAKE_BUILD_VERIFICATION.json). Bukti browser: [INTAKE_BREAKDOWN_VERIFICATION.json](INTAKE_BREAKDOWN_VERIFICATION.json), [INTAKE_EXCEL_REGRESSION.json](INTAKE_EXCEL_REGRESSION.json), [INTAKE_GALAXY_REGRESSION.json](INTAKE_GALAXY_REGRESSION.json), dan `screenshots/intake-breakdown-desktop.png` / `intake-breakdown-mobile.png`.

Pengujian ini memakai data sintetis, **bukan pengukuran akurasi pada file pengguna**. Windows CMD/wheel native dan PostgreSQL nyata tidak diuji ulang untuk perubahan ini. `start.bat` dipertahankan. Tidak membuat ZIP.

Untuk mengulang:

```bash
.venv/bin/python -m pytest -q tests/test_intake_breakdown.py
npm test --prefix frontend
npm run build --prefix frontend
# Playwright + Chromium adalah dependensi QA opsional, bukan dependensi runtime:
PYTHONPATH=/path/to/optional-playwright PLAYWRIGHT_BROWSERS_PATH=/path/to/chromium \
  .venv/bin/python scripts/verify_intake_breakdown.py --output-dir /path/to/qa-output
```
