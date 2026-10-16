# v0.2.0 · Raw intake + automatic external collection

**15 Oktober 2026** · Menuntaskan dua requirement implementasi karet alam, melanjutkan MVP–01.

## Yang selesai

### 1. Ingestion dan pencatatan raw

- File segala format serta endpoint event/batch; byte asli dipertahankan, SHA-256, manifest, versi, akuisisi dan metadata izin/konteks.
- Schema-on-read untuk teks, JSON/NDJSON, XML/RSS/Atom, HTML, PDF berteks, CSV/TSV/XLSX. Opaque/binary/encrypted/unsupported tetap raw-only; kegagalan/partial index dilabeli jujur, bukan kehilangan raw.
- Indexer arsip umum subprocess bounded; pencarian, manifest/raw download, history akuisisi dan versi dipaginasi. PostgreSQL full-text tersedia, SQLite fallback substring.
- Alur pembelian terpetakan tetap bekerja, termasuk CSV yang sebelumnya diarsipkan umum; satu blob dapat dipakai manifest berbeda tanpa saling menghapus.

### 2. Pelacakan dan koleksi eksternal otomatis

- Empat kolektor publik benar-benar aktif: **World Bank Pink Sheet**, **FAOSTAT QCL bulk**, **BMKG**, **Google News RSS**.
- Registry + jadwal database + server-side worker, conditional fetch, receipts HTTP/raw/checksum, dedup/revision semantik, last-known-good, retry/backoff, lease/heartbeat/recovery, dan batas laju host persisten.
- Pembuatan, konfigurasi, jeda/resume, history, one-shot refresh dan penghapusan sumber privat. Sumber baru enabled menjadi due otomatis, tidak menunggu tombol manual.
- Record harga/produksi/prakiraan/berita dengan unit, flag dan caveat masing-masing; filter/pencarian, evidence, revisi, CSV dan proyeksi galaksi berlandaskan raw.

### Fondasi penyimpanan dan delivery

- Repository/API diuji pada SQLite dan **PostgreSQL 17 UTF-8 nyata**.
- Adapter private filesystem atau S3-compatible; migrator offline SQLite→PostgreSQL yang memverifikasi byte/hash dan mempertahankan ID/ownership, tested direct.
- Compose PostgreSQL + aplikasi, Dockerfile multistage, konfigurasi/secret generator, venv setup, requirements versi teruji, API/operasi/sumber terdokumentasi.
- Build frontend lokal menyertakan font/icon; tidak memerlukan CDN. Runtime/private uploads/token/kredensial/dependencies tidak disertakan dalam ZIP.

## Verifikasi akhir

- **152 tes lulus**, termasuk matriks SQLite/PostgreSQL, adapter source fixtures, background scheduler tanpa manual-run, raw integritas/ownership, dedup/revisi/error/lease/control/delete, migration, dan stub protokol S3.
- Diulangi dalam **venv CPython 3.13 baru** dari `requirements-tested.txt`: **152 lulus dalam 19,15 detik**; `pip check` bersih.
- Satu deprecation warning dari Starlette TestClient/httpx; tidak ada tes gagal. Bukan alasan mengklaim dependency security audit sudah dilakukan.
- `tsc -b && vite build` lulus. Hasil build disertakan ZIP.
- ZIP diekstrak terpisah: setup aktual membuat venv baru dengan sukses; static frontend/blueprint, intake event, indeks, raw download dan cleanup dari isi paket diuji. Manifest SHA-256 setiap file diverifikasi; runtime/secret/dependency directories tidak dibundel.
- Browser end-to-end: raw upload, izin, search/index, original byte download, receipt duplikat, version/history, purchase mapping/valid/invalid evidence, public source ledger/filter/pagination, galaxy/fullscreen, drawer focus/Escape, cleanup.
- **BMKG privat di browser mengoleksi nyata secara scheduled tanpa tombol run**, lalu pause/edit/resume dan scheduled recollection berhasil. Data QA privat dibersihkan; data workspace lain tidak dihapus.
- Viewport 390/768/1024/1440: halaman galaksi dan sumber tidak overflow horizontal; navigasi mobile bekerja. **0 JavaScript page errors**.
- Raw source HTTP live telah diterima dan ditelusuri pada runtime utama. **2.440 record unik historis** tersimpan saat verifikasi: 1.134 harga, 1.256 produksi, 36 interval prakiraan historis dari dua snapshot 18 interval, 14 metadata berita. Angka terus dapat berubah mengikuti jadwal.
- WB/FAO/BMKG latest run sukses dengan 0 rejections; missing-source values dihitung terpisah. RSS sengaja partial/nonexhaustive. Detail checksum, URL, run coverage dan jumlah ada di `docs/LIVE_SOURCE_PROOF.json`.

## Batas yang tetap eksplisit

- Preview masih **SQLite + filesystem, single-node**, bukan migrasi otomatis ke cloud atau layanan 24/7. Menutup tab tidak menghentikan kolektor; mematikan server menghentikan eksekusi.
- **S3 menggunakan SDK stub tests, bukan live bucket terverifikasi. Docker/Compose belum dieksekusi di sandbox.** PostgreSQL dan migrasi database telah diuji langsung, bukan asumsi konfigurasi.
- Tidak ada klaim skala tak terbatas/petabyte, exhaustive crawl, intraday real-time, SSO/RLS produksi, multi-replica, malware sandbox penuh, OCR, forecasting, AI, managed backup, HA atau SLA.
- BMKG adalah lokasi referensi kota/kelurahan, bukan asal kebun/pemasok; prakiraan bukan observed event. News metadata belum diverifikasi; tidak ada page/article crawl. World Bank benchmark bukan harga spot lokal.
- Revisi FAO pada penyempurnaan adapter dapat menambah metadata flag/citation tanpa perubahan nilai produksi. Record lama tidak dihapus hanya karena tidak muncul lagi pada satu snapshot.
- Review keamanan, lisensi/redistribusi, backup/restore, kapasitas, auth dan provider S3 tetap wajib sebelum produksi. Lihat `docs/OPERATIONS.md`, `docs/SOURCES.md`, `docs/VERIFICATION.md`.

MVP–01 asli dan blueprint awal tetap menjadi histori pengembangan; deskripsi “zero collectors” pada paket lama tidak lagi menggambarkan implementasi v0.2 ini.


## Tambahan distribusi Windows 11

- `start.bat` mandiri: deteksi Python 3.13 64-bit, setup venv/dependensi, localhost-only single worker, cek port/app lama, dan browser dibuka sesudah health siap. Tidak menghapus runtime atau mematikan proses lain.
- Frontend prebuilt; Node.js/Docker/WSL tidak diperlukan pada jalur native ini. Python tetap harus dipasang.
- Environment indexer mempertahankan path OS Windows yang diperlukan tanpa mewariskan secret database/S3.
- Bagian Python launcher serta regresi SQLite diuji pada Linux; eksekusi batch di Windows CMD dan wheel Windows belum diuji langsung. Matriks PostgreSQL 152 tes pada rilis awal tetap merupakan hasil uji historis, bukan klaim pengujian native Windows.
- Paket `rubber-intelligence-windows-11.zip` tetap tidak berisi database, raw pengguna, atau kredensial.

## Pembaruan presentasi: galaksi bergerak

- Entitas nyata pada graph bergerak halus di lintasan acak-terkendali; pusat workspace tetap diam, kurva dan area klik relasi mengikuti endpoint node.
- Node ditahan ketika hover/fokus/dipilih; zoom/pan/reset/fullscreen dan pembukaan bukti tetap berfungsi. Tombol **Jeda gerak / Gerakkan** menyimpan preferensi browser.
- Reduced motion dihormati; animasi berhenti saat dokumen tersembunyi/peta di luar viewport. Pembaruan geometri memakai ref SVG, bukan render React per frame.
- Tidak mengubah nilai, raw, API, jadwal kolektor, kapasitas proyeksi atau pemisahan dataset. Gerak dilabeli sebagai efek visual, bukan perubahan data atau sebab-akibat.
- **14 tes unit gerak, 16 pemeriksaan browser, 0 JavaScript page errors**. Lebar 340/390/768/1024/1440 px tanpa overflow horizontal, relasi tetap terhubung. Regresi Linux/SQLite **108 lulus, 1 dilewati, 1 deprecation warning**; `tsc -b && vite build` lulus. Bukan pengulangan matriks PostgreSQL historis atau uji Windows native.
- Paket baru **`rubber-intelligence-windows-11-galaxy.zip`** menyertakan `start.bat`, source, tes, dokumentasi dan frontend prebuilt; paket lama tidak ditimpa. Petunjuk memperbarui instalasi tanpa menghapus `app/runtime` ada di `WINDOWS_11.md`.
- Detail: [GALAXY_MOTION.md](docs/GALAXY_MOTION.md) dan [laporan browser](docs/GALAXY_MOTION_VERIFICATION.json). Batas native Windows yang disebut sebelumnya tetap berlaku.


## Pengembangan lanjutan — Asisten Excel lokal

Pengguna memilih **Asisten Excel** lalu **tanpa AI eksternal dahulu**. Tahap ini menambah deteksi header/preambule/dua baris, alias yang dijelaskan beserta konflik, usulan format yang harus diterapkan secara sadar, pemeriksaan sampel read-only (maks. 50 baris), serta ingatan koreksi yang eksplisit dan terpisah per workspace. Snapshot kolom per revisi menjaga bukti historis ketika header diubah. Raw tetap byte-identik; format tak dikenal tidak dipaksa menjadi pembelian.

Belum ada model AI/LLM, chat umum, analisis semua jenis laporan, atau pelatihan dengan unggahan. Struktur/header yang belum dikenali masih memerlukan pemetaan dan konfirmasi. Memori menyimpan aturan, bukan nilai sel. Rincian: [EXCEL_ASSISTANT.md](docs/EXCEL_ASSISTANT.md).

Verifikasi Linux/SQLite: **131 tes backend lulus, 1 dilewati, 1 deprecation warning** (termasuk 22 tes Asisten Excel dan 1 guard tanpa ZIP). **14 tes unit gerak**, build TypeScript/Vite, **12 pemeriksaan browser Excel**, dan **16 regresi browser galaksi** lulus; 0 JavaScript page errors. Fixture sintetis, bukan klaim format pengguna yang belum diuji. PostgreSQL nyata dan Windows native tidak diuji ulang untuk pembaruan ini.

**Tidak membuat ZIP**, sesuai permintaan pengguna. Paket-paket lama telah dihapus. Packager memerlukan `--confirm-release` dan hanya boleh dijalankan bila pengguna meminta download secara eksplisit. Manifest workspace ditandai sebagai pengembangan, bukan rilis immutable.


## Koreksi prioritas MVP — 16 Oktober 2026

MVP pertama kini **Intake → Breakdown → Klasifikasi → Review**, bukan kewajiban pemetaan pembelian. Mode utama UI berubah menjadi Intake & klasifikasi; API legacy tetap kompatibel.

- Profil XLSX/CSV/TSV otomatis, file → lembar → tabel → kolom/baris, dengan sample, type/empty counts dan koordinat sumber.
- Dua klasifikasi: jenis dataset bisnis dan tipe/peran kolom. Alasan dari aturan/header, bukan LLM; unknown/mixed tidak dipaksa menjadi purchase.
- Review per tabel, kategori/peran/tipe dapat dikoreksi; konfirmasi eksplisit, snapshot revisi terikat versi/hash, stale ditolak. Saran mesin, raw, dan observasi tidak ditimpa. Tidak ada publikasi atau pembelajaran pola otomatis.
- Surface selesai unggah + Pusat data + bukti raw; arsip lama bisa meminta breakdown. CSV/TSV event dengan Content-Type eksplisit juga didukung.
- Hasil parsial/unsupported/failed, hidden sheets, batas 5.000 record logis/64 kolom/10 lembar/20 tabel (5 per lembar), sel/bagian tak tercakup dan cache formula dijelaskan. Format lain tetap raw/indeks, bukan diklaim diklasifikasikan.

Verifikasi saat ini Linux/SQLite: **174 backend lulus, 1 skipped, 1 deprecation warning**, termasuk **43 tes baru**. **14 unit gerak + build TypeScript/Vite** lulus. **17 browser MVP**, **12 regresi Asisten Excel**, **16 regresi galaksi** lulus, 0 JavaScript errors; fixture sintetis, private QA dibersihkan. Bukan benchmark akurasi file pengguna. Native Windows/PostgreSQL nyata tidak diuji ulang.

Rincian dan bukti: [INTAKE_BREAKDOWN.md](docs/INTAKE_BREAKDOWN.md). `start.bat`, runtime/raw lama, dan kolektor dipertahankan. **Tidak ada ZIP baru**.
