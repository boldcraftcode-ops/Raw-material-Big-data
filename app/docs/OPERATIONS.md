# Operasi dan migrasi · v0.2

## Arsitektur eksekusi yang didukung

Satu proses aplikasi: FastAPI/Uvicorn satu worker, satu loop job intake dan satu loop kolektor background; pekerjaan blocking berjalan di thread. Indexer **arsip umum** adalah subprocess dengan batas sumber daya, bukan sandbox malware penuh. Parser adapter eksternal memproses source allowlisted dalam worker kolektor; parser pembelian legacy memakai batas struktur file, bukan isolasi kontainer.

SQLite + filesystem sesuai development/satu node. PostgreSQL direkomendasikan untuk penggunaan bersama, indeks dan backup terkelola; raw lebih sesuai private S3-compatible. Tidak perlu PostGIS agar kedua requirement rilis ini bekerja. PostGIS/Neo4j/ClickHouse belum dipasang; koordinat cuaca adalah metadata sumber, bukan analisis geografis terverifikasi.

**Jangan menjalankan beberapa proses Uvicorn/replika pada runtime yang sama.** Lease/row lock kolektor mencegah klaim ganda, tetapi recovery job pembelian dan garbage collection startup masih mengasumsikan satu proses inti. Multiworker/HA memerlukan lifecycle dan queue terpisah, bukan sekadar `--workers 4`.

Alur data:

```
file / body event / HTTP source
       ↓ size / scope / rights / policy checks
raw byte → content-addressed storage → manifest + acquisition receipt
                                      ↓
                       index job / adapter parser / purchase mapping
                                      ↓
                    validated records + immutable evidence revisions
                                      ↓
                   search / CSV export / galaxy evidence projection
```

Blob tersimpan sebelum receipt/manifest database di-commit. Publikasi record dan switch versi aktif transaksional. DB/object store bukan distributed transaction: kegagalan di antara keduanya bisa menyisakan blob orphan; **tidak boleh menghapus raw yang masih direferensikan**. Integrity raw diverifikasi sebelum download. Simpan backup database dan object store yang konsisten; manifest saja tidak cukup.

## Konfigurasi

`run.sh` membaca `.env` tepercaya milik operator (format shell; quote nilai kompleks). Native CLI migrasi memakai environment proses; `.env` tidak otomatis di-load oleh `python -m backend.migrate`. Compose membaca `.env` dan memasukkannya ke aplikasi; environment URL DB internal Compose mengalahkan URL native.

| Variable | Default / fungsi |
|---|---|
| `RUBBER_DATA_DIR` | `app/runtime`; metadata SQLite/raw lokal atau cache S3 |
| `RUBBER_DATABASE_URL` | kosong → SQLite; PostgreSQL UTF-8 bila diset |
| `RUBBER_COLLECTORS_ENABLED` | `1`; `0` menonaktifkan loop scheduler/collector, bukan menghapus riwayat |
| `RUBBER_MAX_FILE_BYTES` | 10.485.760; file manual. Naikkan hanya setelah meninjau RAM, parser, proxy, dan storage |
| `RUBBER_OWNER_RAW_BYTES` | 268.435.456; byte unik per owner |
| `RUBBER_GLOBAL_RAW_BYTES` | 1.073.741.824; seluruh owner, termasuk global public dan demo |
| `RUBBER_MAX_DOCUMENTS` | 10.000/owner; duplikat receipt bukan dokumen baru |
| `RUBBER_S3_BUCKET` | kosong → filesystem; bukan otomatis membuat bucket |
| `RUBBER_S3_ENDPOINT` | endpoint HTTPS S3-compatible; kosong untuk AWS S3 standar |
| `RUBBER_S3_PREFIX` | `rubber-raw`; **prefix unik per deployment**, jangan berbagi prefix/manifest antar instalasi |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, opsional `AWS_SESSION_TOKEN` | credential chain SDK; gunakan IAM role/least privilege bila tersedia |
| `RUBBER_S3_SSE` | opsional `AES256` / `aws:kms`; konfigurasi key/policy provider terpisah |
| `PORT` | `8000` |

Event tetap maksimum 1 MiB/request. Adapter mempunyai cap download sendiri; menaikkan file manual tidak menaikkan otomatis cap bulk/provider. Quota memeriksa byte raw unik yang aktif dalam manifest, bukan keseluruhan backup, WAL, cache, derived indices atau historical S3 object versions. Ledger akuisisi/revisi dapat bertumbuh walau raw dideduplikasi. Operator perlu memonitor kapasitas database dan retensi; tidak ada automatic purge historis pada rilis ini.

Gunakan filesystem privat/dedicated volume. S3: aktifkan block public access, private bucket policy, TLS, credential least privilege untuk prefix aplikasi, encryption dan versioning/lifecycle sesuai kebutuhan. SDK tidak mengirim public ACL, kredensial, atau presigned URL ke browser, tetapi **aplikasi tidak mengaudit seluruh bucket policy provider**. Pastikan provider mendukung conditional `PutObject If-None-Match`; lakukan smoke test terhadap bucket nyata sebelum memigrasi data penting. Local download cache `.cache/raw` sensitif; lindungi/bersihkan sesuai retensi. Jangan menjadikan raw volume sebagai static web root.

## Migrasi offline SQLite → PostgreSQL (opsional S3)

Mengganti `RUBBER_DATABASE_URL` saja membuka database lain; itu **bukan migrasi**. Utilitas yang disertakan mempertahankan ID pemilik/dokumen/versi/job, raw, receipt, mapping, data, revisi, sumber, dan riwayat. Sumber tidak dihapus. Target harus kosong dan tidak punya writer. Dilarang memakai script untuk menggabungkan dua workspace aktif.

1. Hentikan aplikasi sumber dan tujuan. Tunggu run penting selesai atau catat run terputus. Jangan menjalankan server lama bersamaan dengan server baru pada raw directory/prefix yang sama.
2. Backup SQLite menggunakan mekanisme SQLite backup atau copy konsisten **setelah server berhenti**; sertakan file WAL/SHM bila masih ada, seluruh folder `raw`, serta konfigurasi dan token pengguna secara privat. Uji restore backup, bukan hanya cek file ada.
3. Buat database PostgreSQL UTF-8 terisolasi. Server harus kosong dari data aplikasi; schema akan disiapkan idempotently. Sediakan root runtime tujuan **baru**, serta bucket/prefix privat baru bila memakai S3.
4. Set environment target. Jangan menaruh password dalam command history; gunakan environment/config secret terproteksi. Contoh struktur (ganti dengan konfigurasi organisasi):

```bash
# Dari folder app; .env harus file tepercaya buatan operator:
source .venv/bin/activate
set -a; source .env; set +a
# Pastikan RUBBER_DATABASE_URL menunjuk PostgreSQL target, bukan DB produksi berisi data.
# Optional S3 env di atas berlaku pada target; sumber migrasi ini harus raw lokal.
python -m backend.migrate \
  --sqlite runtime/workspace.sqlite3 \
  --raw-dir runtime/raw \
  --target-dir runtime-postgres
```

5. Script membaca snapshot read-only sumber, memverifikasi ukuran/SHA-256 **setiap objek**, menulis blob ke storage target, menyalin tabel dengan urutan/FK deferred dalam transaksi, dan memverifikasi jumlah baris. `migration_report.json` hanya memuat waktu/counts/bytes/storage-kind, bukan DSN/token. Job `running` menjadi `queued`; run kolektor yang terputus ditandai `interrupted` agar bisa dijadwalkan ulang.
6. Set `RUBBER_DATA_DIR` ke root target yang sama; jalankan satu server dengan URL PostgreSQL target dan konfigurasi object store yang sama. Periksa health, jumlah dokumen/record, ownership, raw download beberapa sampel, sumber, dan ekspor. Token browser lama masih diperlukan untuk scope privat; script tidak menciptakan akun/SSO baru.
7. Simpan sumber dan backup offline sampai verifikasi selesai. Jika proses gagal, sumber tidak dihapus; row target belum ter-publish bila transaksi gagal. Objek yang sudah diunggah dapat menjadi orphan dan digunakan ulang saat retry pada target kosong. Jangan melakukan purge object store secara buta.

Migrasi integrasi SQLite→PostgreSQL telah diuji langsung. Migrasi ke bucket S3 nyata belum diuji di sandbox; protokol adapter S3 diuji dengan stub. Migrasi dari storage S3 sumber, penggabungan workspace, online dual-write, dan rollback otomatis lintas storage tidak disediakan.

## Backup dan pemulihan

- PostgreSQL: gunakan `pg_dump`/PITR terkelola dan backup private bucket/volume yang konsisten, termasuk historical raw yang direferensikan revision. Backup DB dan raw harus pasangan yang cocok. Kredensial/token bukan bagian ZIP.
- SQLite: hentikan writer sebelum copy biasa, atau gunakan backup API; arsipkan bersama raw. Jangan hanya menyalin `workspace.sqlite3` saat WAL aktif.
- Recovery job lokal mengantrekan ulang job terputus saat startup. Collector memakai heartbeat dan lease 20 menit; lease kedaluwarsa menjadi interrupted, lalu retry. Tidak mengeksekusi satu run untuk setiap interval yang terlewat; hanya jadwal due berikutnya.
- Jika raw hilang/hash gagal, download ditolak; jangan menganggap hasil indeks sebagai pengganti original. Restore dari backup yang cocok. S3 historical versions/lifecycle bukan dikelola otomatis oleh aplikasi.
- Penghapusan dokumen/source membersihkan manifest/turunan dan blob aktif ketika tidak lagi dipakai; backup, snapshot, filesystem recovery dan historical object versions berada di luar penghapusan API. Sebelum retensi/GC massal, lakukan dry-run inventaris seluruh `raw_assets.object_key` dan reference chain.

## Monitoring dan troubleshooting

- `/api/health`: versi, mode single-node, DB/storage backend, jumlah sumber dijadwalkan/berhasil/gagal, worker task hidup. Status `ok` bukan pemeriksaan menyeluruh provider/IAM/backup.
- UI sumber: last status/success, next due, stale, run history, HTTP, checksum, resource receipts, coverage dan rejection sample. Source “aktif” tidak sama dengan “sukses”. RSS partial adalah coverage policy yang disengaja.
- Log Uvicorn mencatat source/run ID dan hasil atau alasan error tanpa body raw atau credentials. Jurnal aplikasi mempertahankan receipt/proses. Tidak ada dashboard SLO/alert delivery terkelola.
- PostgreSQL connection/encoding: database UTF-8; client diset UTF-8. URL socket/query harus percent-encode spasi (`%20`, bukan `+`, pada libpq options).
- HTTP 429: lihat Retry-After/backoff; jangan memencet refresh berulang. Hanya Retry-After numeric yang dipakai khusus; lainnya tetap backoff standar.
- Skema/provider berubah: raw yang sempat diterima tetap ada, publish baru gagal dengan alasan; snapshot terakhir tidak dihapus. Perbarui adapter dan fixture/kontrak, jangan isi angka hilang dengan nol.
- PDF/image: tidak ada OCR; encrypted/binary raw-only wajar. Timeout/extraction_failed bukan bukti raw tidak diterima; lihat manifest dan download checksum.
- HTTP 413 atau quota error: bagi payload event/batch; perubahan limit harus lewat operator dan tidak menjadi klaim throughput baru.

## Sebelum produksi / naik skala

Tambahkan autentikasi SSO, otorisasi organisasi/RLS, TLS/rate limit reverse proxy, secret manager, audit akses, malware quarantine/scanning, data governance/retensi, private network, backup + restore drill dan observability. Ukur query, acquisition bandwidth, concurrency, indeks, serta kebutuhan antrean/worker terpisah sebelum scale-out. Tidak ada migration/deployment cloud yang dilakukan tanpa konfigurasi/izin pemilik infrastruktur. Docker/Compose disertakan namun belum diuji menjalankan container di sandbox ini; jangan menyebutnya sudah deployed.
