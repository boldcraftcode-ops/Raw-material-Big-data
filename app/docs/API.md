# API · v0.2

Kontrak mesin lengkap: `GET /api/openapi.json`. Semua panggilan pemilik memakai `X-Workspace-Token` (32–160 karakter `[A-Za-z0-9_-]`); gunakan token acak kuat dan simpan secara privat. Token baru membuat scope pemilik baru, bukan akun terautentikasi. `demo` dan `external` dapat dibaca lintas token, bukan diubah menjadi data pengguna.

`dataset=live|external|demo` memilih scope data, tidak memberikan akses ke scope privat milik orang lain. Default beberapa endpoint legacy tetap `demo`; **client baru sebaiknya selalu menyertakan dataset eksplisit**. ID harus diambil dari respons list/get, bukan ditebak. Error validasi domain `400`, tidak ada/tidak berhak `404`, token invalid `401`, schema request `422`, envelope terlalu besar `413`. File melebihi cap yang ditemukan oleh service dapat menghasilkan `400`; tidak dipotong diam-diam.

## File raw

`POST /api/uploads`, multipart, respons `202`:

| Field | Makna |
|---|---|
| `file` | Satu original byte file, default maksimum 10 MiB |
| `consent=true` | Pernyataan terkait karet alam, hak unggah, batas preview |
| `intake_mode=archive` | Arsip umum semua format; bukan pemetaan harga |
| `intake_mode=purchase` | Default legacy: CSV/XLSX yang akan dipetakan pembelian |
| `category` | `general`, `price`, `production`, `supply_chain`, `weather`, `quality`, `traceability` |
| `context` | Maksimum 2.000 karakter; pernyataan hubungan dengan karet |
| `source_uri` | HTTP(S) opsional tanpa kredensial/fragmen; metadata saja, **tidak di-fetch** |

```bash
# TOKEN dibuat dan disimpan oleh client; contoh generasi, bukan token tetap:
TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
curl -f http://localhost:8000/api/uploads \
  -H "X-Workspace-Token: $TOKEN" \
  -F consent=true -F intake_mode=archive -F category=quality \
  -F 'context=Hasil ukur kualitas lateks; izin dimiliki pengirim' \
  -F 'file=@hasil_mutu.json'
```

Respons memuat `version` (id, document_id, version_no, sha256, size_bytes, status, intake_meta, job) dan `duplicate`. Byte identik tetap menambah receipt akuisisi, tidak menggandakan raw/observasi. Pada arsip umum, logical key nama file (case-fold) membentuk stream versi; byte sama pada stream berbeda dapat berbagi blob, tetapi manifest masing-masing dipertahankan. Intake pembelian legacy mendeteksi duplikat byte per pemilik.

`202` berarti raw dan pekerjaan telah diterima, bukan ekstraksi atau publikasi sudah berhasil. Poll `GET /api/versions/{id}`. Arsip umum selesai dengan status `archived` dan `parsed_meta.extraction_status`: `indexed`, `partial`, `raw_only`, atau `extraction_failed`. Parser gagal/unsupported tidak menghapus raw yang telah diterima. Pembelian menunggu `awaiting_mapping` sebelum publish.

## Event / batch API

`POST /api/intake/events?stream=…&category=…&scope_confirmed=true&rights_confirmed=true` menerima **body persis apa adanya**, maksimum 1 MiB. CSV/TSV didukung melalui Content-Type eksplisit `text/csv` / `text/tab-separated-values`. Satu request adalah satu artefak/version; endpoint ini bukan broker streaming tak terbatas. `stream`: 1–100 huruf/angka/`_.-`. `context` opsional hingga 2.000 karakter. `Content-Type` menentukan hint ekstensi dan indeks, bukan konversi byte.

```bash
curl -f 'http://localhost:8000/api/intake/events?stream=sensor-gudang&category=quality&scope_confirmed=true&rights_confirmed=true' \
  -H "X-Workspace-Token: $TOKEN" \
  -H 'Content-Type: application/x-ndjson' \
  -H 'Idempotency-Key: batch-2026-10-15-001' \
  --data-binary @sensor.ndjson
```

Opsional `Idempotency-Key` mengikat owner + logical stream + hash payload. Replay byte sama pada stream sama mengembalikan versi sebelumnya dan mencatat receipt; key sama dengan payload/stream berbeda ditolak (`409`). Key bukan kredensial; jangan menaruh secret di header ini. Body kosong ditolak.

## Membaca arsip dan bukti

- `GET /api/documents?dataset=live&limit=100&offset=0`: array dokumen; maksimum 100/halaman dan 20 versi terbaru/dokumen. `version_count`, `active_version`, `latest` membantu navigasi. Total dokumen pada `/api/stats`.
- `GET /api/documents/{id}/versions?limit=20&offset=20`: `{items,total,limit,offset}` untuk versi lebih lama, owner/public-read diperiksa.
- `GET /api/versions/{id}`: manifest terotorisasi.
- `GET /api/versions/{id}/raw`: attachment byte original, hash diperiksa; tidak ada URL bucket publik.
- `GET /api/versions/{id}/acquisitions?limit=50&offset=0`: semua receipt termasuk duplikat, waktu, nama, metadata; maksimal 100/halaman.
- `GET /api/versions/{id}/content?offset=0&limit=12000`: indeks teks terpotong per halaman; `total_characters`, parser, status, warning; limit maksimal 20.000 karakter.
- `GET /api/archives?dataset=live&q=lateks&limit=20&offset=0`: pencarian indeks arsip umum dan metadata, **bukan** isi semua format yang belum berhasil diekstrak. PostgreSQL full-text kata (`simple`); SQLite fallback substring.
- `DELETE /api/documents/{id}`: dokumen privat non-kolektor, versi, turunan, receipt, dan blob tak terpakai. Dokumen kolektor dihapus melalui sumbernya agar tidak mematahkan provenance. Penghapusan logical aplikasi bukan penghapusan backup/provider version historis.

## MVP pertama: breakdown dan klasifikasi

Default **UI** sekarang Intake & klasifikasi; default **API legacy** tetap `intake_mode=purchase`. Client baru yang ingin intake umum harus menyertakan `intake_mode=archive`.

XLSX/CSV/TSV pada intake umum otomatis menyertakan `parsed_meta.breakdown` setelah pekerjaan selesai. Event dengan `text/csv` / `text/tab-separated-values` juga diurai. Hasil adalah **saran metadata**, bukan observasi terpublikasi atau normalisasi seluruh tabel. Format lain tetap raw/indeks sesuai dukungan, dengan status profil `unsupported`.

- `GET /api/versions/{id}/breakdown`: `available`, `profile`, `profile_hash`, `review` (revision, tables, created_at, stale), `can_edit`, `pending`, `job`, enum kategori/peran/tipe; `published:false`. Profil privat mengikuti ownership, demo/eksternal public-read only.
- Profil: schema_version, mode local_rules, external_ai_used:false, status ready/partial/unsupported/failed, struktur per lembar/tabel/kolom, classification/reasons, primitive type counts, empty counts, sampel, preview dan koordinat baris/kolom. `summary.data_records_scanned` adalah record per tabel, bukan jumlah transaksi atau total-file yang diekstrapolasi.
- `POST /api/versions/{id}/breakdown`: `202 {reused,queued}`. Untuk arsip lama/retry profil gagal; tidak menimpa raw atau status/pemetaan/observasi aktif. Worker yang sudah pending dipakai kembali.
- `POST /api/versions/{id}/breakdown/review`: body `profile_hash`, `confirmed:true`, `tables` (1–20). Setiap item memuat `table_id`, `category`, dan **seluruh** `columns` (`column_id`, `role`, `datatype`, maksimal 64). Ambil ID dan enum dari GET. Field tambahan/nilai sel ditolak. Hash bukan hash raw; hash profil disertakan GET dan terikat versi pada URL.
- Respons review: `revision`, `reused`, `published:false`, `raw_changed:false`. Snapshot revisi append-only, hanya pemilik; review tabel berikutnya menggabungkan keputusan untuk profil yang sama. Replay identik idempotent. Maksimum 200 revisi review/versi. Review stale tidak diterapkan; body hash lama ditolak `409`.

Batas profil 10 MiB file, 5.000 baris/record logis total, 64 kolom, 10 lembar terlihat, 20 tabel / 5 per lembar; preview 4 baris / 12 kolom. CSV multiline menyimpan baris fisik awal–akhir. Hidden sheets/anggaran scan dilabeli; sampel bukan seluruh isi. Tidak ada casting nilai, auto-publish, identitas digabung, pelatihan model, atau eksekusi formula/macro. [Metode dan batas lengkap](INTAKE_BREAKDOWN.md).

## Pemetaan pembelian (dipertahankan)

- `GET /api/versions/{id}/preview[?sheet=…]`: kolom, contoh baris, saran mapping; bukan konfirmasi otomatis.
- `POST /api/versions/{id}/mapping`: JSON `sheet`, `fields`, `options`, `scope_confirmed=true`; respons job `202`. Daftar field/opsi di `/api/config` dan kode domain. Tidak ada default mata uang/unit/basis berat implisit.
- `GET /api/observations?dataset=live&q=…&limit=20&offset=0`; maksimum 100/halaman.
- `GET /api/evidence/{observation_id}`: snapshot transformasi dan sel, versi, hash, mapping revision.
- `GET /api/observations/export.csv?dataset=live&q=…`: maksimal 10.000 baris, formula-safe.
- `/api/issues`, `/api/activity`, `/api/template.csv`, `/api/stats`, `/api/graph`, `/api/config`, `/api/health`.

## Sumber dan run otomatis

1. `GET /api/sources/catalog`: adapter yang diizinkan, config/default interval/minimum/atribusi/lisensi.
2. `GET /api/sources`: sumber publik bersama + sumber privat pemilik dan ringkasan worker/status.
3. `POST /api/sources`: membuat sumber privat. Respons `201`; jadwal otomatis langsung due bila enabled. **Tidak perlu menekan “Ambil sekarang” agar sumber baru mulai dikoleksi.**

```json
{
  "adapter": "bmkg",
  "name": "Referensi cuaca Medan",
  "config": {
    "adm4": "12.71.01.1001",
    "context": "Referensi regional Medan; bukan lokasi kebun terverifikasi"
  },
  "interval_seconds": 21600,
  "enabled": true
}
```

4. `PATCH /api/sources/{id}`: owner privat saja, `name/config/interval_seconds/enabled`; tidak boleh ketika run pending. Mengaktifkan/menyimpan konfigurasi membuat jadwal kembali due. Run manual pada sumber yang dijeda adalah one-shot, bukan resume jadwal.
5. `POST /api/sources/{id}/run`: enqueue nyata, `202 {run_id,reused}`; run pending digunakan kembali, cooldown manual 60 detik, termasuk feed publik. Tidak menjanjikan fetch berhasil.
6. `GET /api/sources/{id}/runs?limit=30&offset=0`: history; maksimum 100/halaman.
7. `GET /api/runs/{id}`: hasil, coverage, fetch/HTTP/raw/checksum, error, dan maksimum 50 rejections pertama. Seluruh raw tetap tersedia; rejected_records bisa lebih dari sampel alasan.
8. `DELETE /api/sources/{id}`: sumber privat beserta record/revisi/arsip. Run kolektor/indexer yang sedang berjalan harus selesai lebih dahulu; UI menunggu pending run. API dapat membatalkan run yang masih queued lewat penghapusan sumber. Publik tidak boleh dihapus pengguna.

Jadwal disimpan pada database dan dieksekusi worker server. Run: `queued → running → succeeded|partial|failed`; lease hilang menjadi `interrupted` dan dijadwalkan retry. Shared source read-only pada konfigurasi; operator dapat menonaktifkan global worker melalui `RUBBER_COLLECTORS_ENABLED=0` lalu restart.

## Record eksternal dan galaksi

- `GET /api/knowledge?dataset=external&kind=market_price&q=RSS3&source_id=…&limit=20&offset=0`: `{items,total,limit,offset}`, filter opsional; `kind`: `market_price`, `production_stat`, `weather_forecast`, `news_report`. Limit maksimum 100.
- `GET /api/knowledge/{id}`: fields, source, pointer ke raw, current revision, dan 100 revision terbaru.
- `GET /api/knowledge/{id}/revisions?limit=50&offset=20`: history tambahan, batas 100/halaman.
- `GET /api/knowledge/export.csv?dataset=external&kind=…&q=…`: maksimum 10.000 record, formula-safe, fields_json memuat unit/konteks/atribusi, raw_version_id dan captured_at ikut diekspor.
- `GET /api/graph?dataset=external`: proyeksi berbatas beserta record_ids/evidence_ids dan archive_version_id yang bisa dibuka ke bukti. Konteks/relasi tidak sama dengan sebab-akibat atau validasi asal kebun.

Identitas record berasal dari adapter + source + identifier/period sumber; tidak ada fuzzy auto-merge pemasok atau penciptaan angka kosong. Metadata/angka yang berubah membuat revision; raw lama tetap tersedia. Data yang tidak muncul di akuisisi baru tidak otomatis dihapus sebagai “salah”—record adalah arsip historis. Gunakan period, updated_at (terakhir terlihat)/source last_success dan waktu capture sebelum menganggapnya kondisi terkini.


## Asisten Excel lokal (tanpa AI eksternal)

Preview mendukung `header_row` (1–50), `header_depth` (1–2), dan `sheet`, serta mengembalikan `assistant` dengan alasan saran, konflik, petunjuk format, dan pola milik workspace yang cocok. Endpoint berikut memakai header kapabilitas/ownership yang sama:

- `POST /api/versions/{id}/mapping/check`: body pemetaan; `scope_confirmed` boleh false. Sampel maksimal 50 baris, `published=false`, `full_validation=false`.
- `POST /api/versions/{id}/mapping/remember`, body `{"revision":1}`: menyimpan pola hanya setelah revisi selesai dengan baris valid dan persetujuan eksplisit.
- `DELETE /api/excel-templates/{template_id}`: melupakan pola pemilik, tidak menghapus raw/observasi.

Publikasi tetap di `POST /api/versions/{id}/mapping`, dengan `scope_confirmed=true`; `header_row`/`header_depth` opsional. [Penjelasan dan batas](EXCEL_ASSISTANT.md).
