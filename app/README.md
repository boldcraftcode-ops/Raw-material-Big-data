# Rubber Intelligence · v0.2.0

Aplikasi karet alam dengan **raw-first intake** dan **koleksi eksternal otomatis**. Dikembangkan dari MVP–01 tanpa menghilangkan alur pembelian, bukti, versi, atau pemisahan simulasi.

## Pengembangan saat ini

Tidak membuat ZIP baru sampai pengguna meminta download. Jalankan/lihat perubahan melalui workspace dan preview; arsip rilis lama sudah dihapus atas permintaan pengguna.

### MVP pertama: intake → breakdown → klasifikasi → review

**Tambah data → Intake & klasifikasi** adalah mode utama/default UI. XLSX/CSV/TSV otomatis diurai menjadi lembar, tabel, kolom, distribusi tipe/kosong dan sampel dengan koordinat sumber. Setiap tabel memiliki saran kategori bisnis (stok, produksi, mutu, harga/pembelian, logistik, dll.) serta tipe/peran kolom. Yang belum jelas tetap **campuran / belum terklasifikasi**, bukan dipaksa menjadi transaksi.

Anda dapat mengoreksi dan menyimpan review per tabel. Review terikat versi/hash, terpisah dari saran awal, **tanpa menimpa raw, melatih model, atau menerbitkan observasi**. Buka kembali dari **Pusat data → Breakdown**. Maksimum profil 5.000 baris/record logis total, 64 kolom, 10 lembar, 20 tabel (5/lembar); partial dan format yang belum didukung dilabeli eksplisit. [Panduan dan hasil uji aktual](docs/INTAKE_BREAKDOWN.md).

### Asisten Excel lokal, tanpa AI eksternal

Di **Tambah data → Pemetaan pembelian**, header tidak harus pada baris pertama. Ada deteksi 50 baris awal/header teks dua baris, saran kolom beserta alasan/konflik, petunjuk format yang harus diterapkan secara sadar, pemeriksaan sampel read-only, dan ingatan pemetaan setelah persetujuan eksplisit. Pola dipisahkan per workspace; default tidak dipakai diam-diam. Raw dan bukti revisi tetap utuh.

**Ini aturan deterministik, bukan model AI/LLM atau pemahaman semua jenis laporan.** Chat/analisis bebas, normalisasi stok/mutu, dan AI eksternal belum ditambahkan. [Panduan, API, pengujian dan batas](docs/EXCEL_ASSISTANT.md).

## Dua requirement yang diimplementasikan

1. **Menerima dan mencatat data mentah karet alam.** File dalam format apa pun dan payload event/API disimpan sebagai byte asli, checksum SHA-256, konteks, versi, dan catatan setiap penerimaan. Format yang belum dapat diindeks tetap menjadi arsip raw. Data tidak dipaksa menjadi skema harga pembelian.
2. **Melacak dan mengumpulkan sumber eksternal secara otomatis.** Ada registry sumber, jadwal persisten, worker, akuisisi HTTP, deduplikasi, revisi record, backoff retry, lease pemulihan, bukti raw, dan status kegagalan. Empat sumber publik aktif secara default—bukan kartu aktivasi dekoratif.

**“Semua data masuk” berarti seluruh byte dari setiap payload yang diterima dan diotorisasi dalam batas konfigurasi, bukan semua informasi dunia atau file berukuran tak terbatas.** Penolakan ukuran/kuota/izin dikembalikan secara eksplisit. Pencatatan raw tidak menjamin format telah dipahami, semua teks telah diekstrak, atau isi telah diverifikasi.

## Windows 11: klik dua kali

Gunakan `start.bat` pada folder utama paket, setelah memasang **Python 3.13 64-bit**. Launcher membuat venv, memasang dependensi, menunggu API siap, dan membuka browser. Tidak perlu Node.js untuk frontend yang sudah dibundel. [Panduan Windows 11](../WINDOWS_11.md). Eksekusi Windows CMD belum diuji langsung dari lingkungan Linux ini; batas OS dijelaskan pada panduan tersebut.

## Mulai

Python 3.13, Node.js 20/22, npm. Paket ZIP menyertakan frontend hasil build.

```bash
cd rubber-intelligence/app
bash prepare.sh
bash run.sh
# http://localhost:8000
```

`prepare.sh` membuat `.venv`, memasang versi Python yang diuji dan membangun frontend. ZIP sudah menyertakan build; untuk tanpa Node/npm gunakan `SKIP_FRONTEND_BUILD=1 bash prepare.sh`. `run.sh` memakai satu proses Uvicorn pada `0.0.0.0:${PORT:-8000}`. `.env`, bila dibuat operator, dibaca sebagai konfigurasi shell tepercaya. **Jangan masukkan file unggahan sebagai `.env`.** Nilai yang mengandung spasi atau karakter shell harus dikutip. Tanpa `RUBBER_DATABASE_URL`, mode pengembangan menggunakan SQLite + filesystem privat.

Default layar **Data eksternal** menampilkan hasil kolektor bersama. **Data saya** berisi unggahan dan sumber privat pemilik token browser. **Simulasi** adalah data fiktif, terpisah dan read-only. Saat instalasi baru, kolektor memerlukan internet dan waktu untuk akuisisi pertama; FAOSTAT mengunduh bulk sekitar 34 MB dan memindai jutaan baris secara streaming. Jangan mengartikan status dijadwalkan sebagai bukti sudah terkoneksi.

### PostgreSQL dan S3-compatible

Backend mendukung PostgreSQL dengan indeks dan pencarian full-text, serta object storage S3-compatible privat. Tanpa bucket S3, byte disimpan pada filesystem privat. Kredensial tidak dikirim ke browser dan tidak masuk manifest akuisisi HTTP.

```bash
python scripts/generate_env.py  # membuat .env baru, password acak, izin 0600; tidak mencetak secret
# opsional: isi bucket S3 privat / region / endpoint dan kredensial storage pada .env
# Docker + Compose harus sudah tersedia:
docker compose up --build -d
```

Compose menjalankan PostgreSQL 17 tanpa port database publik dan aplikasi pada port 8000. Ini **fondasi single-node**, bukan deployment produksi tersertifikasi. Image Compose/Docker belum dijalankan di sandbox ini; API/repository telah diuji langsung terhadap PostgreSQL 17. S3 diuji dengan stub protokol SDK, **bukan klaim koneksi ke bucket cloud nyata**. Sebelum produksi, pin image digest dan siapkan storage/backup/akses jaringan sesuai organisasi.

Native PostgreSQL: set `RUBBER_DATABASE_URL='postgresql://…'` pada environment; gunakan database UTF-8. Jangan hanya mengganti URL jika ingin membawa workspace SQLite lama. Ikuti migrasi offline yang memverifikasi checksum dan tidak menghapus sumber di [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Sumber otomatis

| Adapter | Data yang dikumpulkan | Jadwal default | Batas interpretasi |
|---|---|---|---|
| World Bank Pink Sheet | Discovery workbook bulanan terbaru, raw XLSX, seri RSS3/TSR20 USD/kg | 1 hari | Benchmark bulanan, bukan harga spot lokal; tidak ada konversi FX atau penyamaan grade |
| FAOSTAT QCL bulk | Discovery katalog resmi, ZIP/CSV asli, produksi karet alam per wilayah/tahun; flag dan catatan dipertahankan | 7 hari | Normalisasi default sejak 2000; bisa diubah sejak 1961. Bulk raw juga berisi komoditas lain; hanya produksi karet dinormalisasi |
| BMKG | JSON prakiraan untuk satu adm4; waktu terbit dan berlaku disimpan terpisah | 6 jam | Lokasi referensi **Pasar Baru, Medan Kota (12.71.01.1001)**, bukan kebun/pemasok terverifikasi. Cakupan mengikuti interval respons API, tidak menjamin 72 jam penuh |
| Google News RSS | Metadata penemuan berita karet alam: judul, penerbit, tanggal, tautan, raw feed | 1 jam | Feed terbatas; query match belum direview. Tidak mengunduh halaman penerbit atau mengonfirmasi kejadian |

GDELT tersedia sebagai adapter pantauan privat, tidak diaktifkan sebagai feed default karena akses/rate limit dapat gagal. API FAOSTAT berotorisasi, BPS ber-key, serta SGX berlisensi **tidak dipresentasikan sebagai koneksi aktif**. Jalur produksi FAOSTAT yang bekerja memakai bulk resmi tanpa API key.

- Buka **Sumber eksternal** untuk akuisisi nyata, raw, checksum, run, coverage, HTTP error, dan retry.
- **Ambil sekarang** benar-benar memasukkan pekerjaan ke antrean, dengan cooldown. Pekerjaan yang sedang berjalan tidak digandakan.
- **Tambah pantauan** / ikon salin membuat sumber privat. Ubah kode adm4/konteks, tahun minimum, kata kunci tambahan, interval; jeda atau hapus sumber privat. Domain/URL bebas tidak diterima.
- Sumber publik bersama read-only untuk konfigurasi; hanya operator server yang mengelolanya. Pengguna dapat meminta refresh yang dibatasi dan membuat pantauan privat sendiri.
- Penjadwal berjalan di server, bukan tab browser. Menutup tab tidak menghentikan koleksi; mematikan server menghentikan eksekusi. Jadwal/queue tetap tersimpan dan dilanjutkan ketika server hidup kembali. Tidak ada layanan hosting 24/7 yang otomatis disediakan paket ini.
- Batas per-host tersimpan di database. BMKG diberi jarak minimal 1,1 detik per request dalam deployment ini; GDELT 6,1 detik. Batas IP penyedia juga dipengaruhi aplikasi lain pada IP yang sama.
- Gagal fetch/parse tidak menghapus data terakhir yang berhasil. Nilai hilang tidak dijadikan nol. Revisi record dapat mencakup perubahan metadata, tidak selalu perubahan angka.

## Intake raw dan pembelian

**Tambah data → Intake & klasifikasi** (mode arsip umum) menerima JSON/NDJSON, XML/RSS/Atom, TXT/Markdown/log, HTML, PDF, tabel, gambar, berkas biner, dan format lain. Original tidak diubah. Indeks aman tersedia sesuai kemampuan parser. PDF hasil pindai tidak otomatis diberi OCR; berkas terenkripsi tidak ditebak password-nya. Program/HTML tidak dijalankan; tautan dalam berkas tidak di-crawl.

Indexer umum berjalan dalam subprocess ber-timeout; Linux menerapkan limit 384 MB address space, 12 detik CPU, dan 18 detik wall-time. Ini **bukan sandbox malware penuh**. Jika ekstraksi gagal, statusnya terlihat, raw tetap tersedia. Full-text PostgreSQL mencari kata pada indeks; fallback SQLite memakai substring. Format biner tetap bisa ditemukan melalui nama dan metadata, bukan pencarian isi yang belum diekstrak.

**Tambah data → Pemetaan pembelian** mempertahankan alur CSV/XLSX MVP–01: pemetaan eksplisit, format angka/tanggal, mata uang, unit, basis berat, KKK, validasi, issue review, dan publikasi atomik. Baris invalid tidak menjadi observasi harga. Bukti mempertahankan lembar/baris, raw values, transformasi, hash, versi, dan mapping revision. Nama mirip tidak otomatis digabungkan menjadi pemasok yang sama.

API event dapat menerima byte JSON, NDJSON, CSV/TSV, teks atau biner apa adanya. CSV/TSV ber-Content-Type eksplisit mendapatkan breakdown; JSON/format non-tabular tetap raw/indeks sesuai dukungan. Lihat [docs/API.md](docs/API.md). Pencarian arsip, halaman manifest, history versi, akuisisi, history record, dan ekspor tidak menggantikan penyimpanan raw. Galaksi adalah proyeksi berbukti/konteks—**bukan inferensi kausal, jarak geografis, atau sertifikat asal kebun**. Proyeksi maksimal 60 record terbaru per jenis, 40 arsip raw, 160 node/400 relasi; pencarian/API tetap mencakup seluruh indeks dalam scope pemilik.

## Galaksi bergerak

Node data pada peta melayang **acak-terkendali dan halus**, dengan garis relasi yang mengikuti posisi aktual. Pusat workspace tetap diam; hover, fokus keyboard, dan pemilihan menahan target agar mudah ditelusuri. Tombol **Jeda gerak / Gerakkan** menyimpan preferensi pada browser. Reduced motion, tab tersembunyi, dan panggung di luar viewport menghentikan animasi tanpa menghentikan kolektor.

**Gerak adalah presentasi, bukan perubahan harga, perpindahan barang, atau hubungan sebab-akibat.** Tidak ada node/relasi fiktif baru. Batas proyeksi dan bukti tetap sama. [Detail, pengujian dan batas](docs/GALAXY_MOTION.md).

## Batas default pengembangan

- File manual: **10 MB**, envelope multipart 11 MB; event API: **1 MB** per request.
- Raw: **256 MB per pemilik**, **1 GB total**, **10.000 dokumen per pemilik**; dapat dikonfigurasi operator, bukan janji kapasitas teruji.
- Fetch eksternal: cap per-adapter, maksimum 64 MB untuk bulk FAOSTAT; dekompresi ZIP tidak diekstrak ke filesystem. CSV QCL dipindai streaming dengan batas baris/uncompressed size.
- Breakdown MVP umum: 5.000 baris/record logis total, 64 kolom, 10 visible sheets, 20 tabel / 5 per lembar. Review metadata bukan normalisasi; hasil parsial dan bagian tak terurai tetap terlihat.
- Tabel pembelian: 10.000 baris, 64 kolom, 10 visible sheets, 4.096 karakter/sel. Indeks arsip umum dapat terbatas 600.000 karakter, 10.000 baris tabel, atau 50 halaman PDF. Seluruh byte raw tetap disimpan bila penerimaan berhasil.
- Sumber privat: maksimum 12/workspace; satu run pending/sumber; backoff 60 detik hingga 24 jam. Lease 20 menit dengan heartbeat, recovery untuk lease kedaluwarsa.
- Respons record/arsip/versi/akuisisi dipaginasi. Ekspor CSV dibatasi 10.000 record per permintaan, formula-safe.

Ini implementasi fungsional fondasi data karet, **bukan klaim throughput petabyte, pencarian semantik, crawling seluruh internet, real-time intraday, atau jaminan semua sumber selalu tersedia**. Untuk beban besar nyata: gunakan PostgreSQL + object storage terkelola, ukur beban, atur kapasitas/retensi, dan pisahkan worker sesuai hasil pengukuran.

## Privasi, lisensi, dan operasi

Token kapabilitas browser di `localStorage`, header `X-Workspace-Token`, dan hash pemilik membatasi data privat. Token bukan login/SSO/RBAC/RLS produksi. Jika token hilang, akses workspace dapat hilang. Demo tidak boleh diubah; data eksternal publik terpisah dari data pengguna. Raw hanya diunduh sebagai attachment terautorisasi, tidak dipasang sebagai direktori publik. CSP, nosniff, parameterized SQL, HTTPS source allowlist, validasi DNS/redirect, dan batas request diterapkan.

**Jangan unggah informasi pribadi, kontrak rahasia, koordinat kebun sensitif, atau kredensial ke preview.** Tidak ada pengiriman ke AI. Tidak ada malware scanner penuh, enkripsi terkelola otomatis, backup terjadwal terkelola, SSO, HA, atau SLA. Produksi memerlukan kontrol tersebut dan peninjauan lisensi setiap sumber. S3 bucket harus privat; backup/retensi dan hardening cloud adalah tanggung jawab operator.

Attribution BMKG, World Bank, FAO/FAOSTAT, dan penerbit berita ditampilkan. Tidak ada endorsement penyedia. Berita tidak memberikan hak menyalin seluruh artikel. Lihat [docs/SOURCES.md](docs/SOURCES.md), ketentuan masing-masing sumber, dan `THIRD_PARTY_NOTICES.txt`.

Runtime berisi database/raw privat: **tidak disertakan ZIP dan jangan di-commit**. Penghapusan aplikasi menghapus referensi/turunan dan objek aktif terkait; bukan sertifikasi penghapusan forensik atau penghapusan backup/snapshot/object-version historis provider. SQLite/filesystem lokal bukan layanan backup. Blueprint awal tetap disertakan; kemampuan implementasi saat ini mengikuti README v0.2, bukan roadmap lama.

## Pengujian

```bash
source .venv/bin/activate
python -m pytest -q
# Tambahkan PostgreSQL nyata untuk matriks repository/API dan migrasi:
RUBBER_TEST_DATABASE_URL='postgresql://…' python -m pytest -q
npm test --prefix frontend
npm run build --prefix frontend
```

Animasi galaksi mempunyai 14 tes unit geometri dan QA browser opsional terpisah. Lihat [docs/GALAXY_MOTION.md](docs/GALAXY_MOTION.md) untuk cara menjalankan dan batas verifikasi.

`requirements-tested.txt`: versi yang diuji di CPython 3.13/Linux, bukan lock lintas OS. Tes source menggunakan fixture eksplisit terpisah dari pemeriksaan live. Jumlah dan hasil verifikasi aktual, keterbatasan, serta file release ada di `RELEASE_NOTES.md` dan `docs/VERIFICATION.md`.
