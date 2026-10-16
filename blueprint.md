# Rubber Intelligence Platform

## Blueprint teknis · v1.0

**Tanggal:** 15 Oktober 2026 · **Fokus:** karet alam · **Tahap:** mulai dari nol  
**Status:** usulan desain untuk pengembangan; belum ada aplikasi, kolektor aktif, atau data perusahaan yang terhubung.

> **Visi:** menjadi memori industri karet alam yang terus bertambah—menerima data, mempertahankan bukti, mengenali hubungan, dan memperlihatkan perubahan melalui sebuah galaksi informasi.
>
> **Batas penting:** sistem merekam informasi yang berhasil diperoleh dari sumber yang diizinkan. Sistem tidak dapat menjamin mengetahui seluruh kejadian di dunia, dan tidak boleh memperlakukan setiap informasi yang masuk sebagai kebenaran.

## 01 · Tujuan dan keputusan awal

Tiga keputusan dari pengguna sudah ditetapkan: **mulai dari nol, fokus karet alam, dan mendahulukan rancangan teknis**. Nama produk di atas adalah nama kerja, bukan merek final.

### Pertanyaan yang harus mampu dijawab

1. Informasi baru apa yang relevan dengan karet alam, dan dari mana asalnya?
2. Pemasok, wilayah produksi, pabrik, produk, harga, dan kejadian mana yang saling berhubungan?
3. Bagaimana informasi tersebut berubah dari waktu ke waktu?
4. Risiko atau peluang apa yang perlu diperiksa manusia, beserta bukti dan keterbatasannya?
5. Data mana yang belum tersedia, terlambat, bertentangan, atau gagal diproses?

### Asumsi kerja—masih bisa diubah

- Pilot digunakan satu organisasi; pemisahan organisasi disiapkan sejak model data.
- Operasi awal berorientasi Indonesia, dengan informasi pasar global dari sumber terpilih. Sumatera Utara boleh menjadi wilayah pilot **jika sesuai kegiatan usaha**, bukan karena dianggap sebagai satu-satunya wilayah relevan.
- Pengguna awal: admin, pengelola data, analis/pengadaan, dan pembaca.
- Bahasa antarmuka Indonesia; dokumen Indonesia/Inggris didahulukan.
- Belum ada sampel data, anggaran, volume, daftar pemasok, akun API, atau hak penggunaan feed yang diberikan. Semua kapasitas dan jadwal di dokumen ini adalah sasaran perencanaan, bukan hasil pengujian.

**Keputusan arsitektur utama:** bangun sebuah **modular monolith dengan worker asinkron**, penyimpanan objek untuk data mentah, dan PostgreSQL untuk metadata, pencarian awal, serta relasi. Knowledge graph adalah model pengetahuan; pada MVP, ia tidak membutuhkan database graph terpisah.

## 02 · Ruang lingkup MVP

| Masuk MVP | Ditunda hingga kebutuhan dan akses jelas |
| --- | --- |
| Unggah CSV, XLSX, JSON, TXT, dan PDF berbasis teks | OCR massal, audio/video, sensor/IoT, integrasi ERP penuh |
| Arsip asli yang diizinkan, checksum, riwayat versi, dan katalog | Pengarsipan tanpa batas waktu dan tanpa kebijakan retensi |
| Pencarian teks, filter, halaman bukti, dan antrean review | Asisten percakapan generatif menyeluruh |
| Tiga adapter eksternal kandidat: World Bank, BMKG, penemuan berita GDELT/feed yang disetujui | BPS, UN Comtrade, feed bursa berlisensi, satelit, dan regulasi lintas negara |
| Entitas dasar, relasi berbukti, timeline, dan galaksi 2D | Galaksi 3D sebagai tampilan utama dan jutaan node sekaligus |
| Watchlist dan beberapa aturan peringatan yang transparan | Prediksi harga, keputusan pembelian otomatis, dan klaim sebab-akibat otomatis |
| Hak akses, log audit, pemantauan kolektor, backup dan uji pemulihan | Ketersediaan tinggi multi-region dan platform streaming kompleks |

**Catatan akses:** adapter kandidat baru boleh diaktifkan setelah uji koneksi, skema, kuota, izin pemrosesan/penyimpanan, dan atribusi lulus. Jika GDELT/feed tidak lolos, MVP memakai impor metadata berita yang berizin; tidak diganti dengan crawling bebas.

**Arti “menerima segala data”:** lapisan penerimaan dibuat dapat diperluas. File yang lolos pemeriksaan keamanan dan memiliki izin penyimpanan dapat diarsipkan meskipun parser-nya belum tersedia. Statusnya **arsip saja / belum dapat dibaca**, bukan dianggap sudah dipahami. File berbahaya, terlalu besar, terenkripsi tanpa mekanisme yang disetujui, atau tanpa dasar akses yang jelas ditolak/ditahan dengan alasan tercatat.

## 03 · Arsitektur sistem

<!-- ARCHITECTURE_DIAGRAM -->

```text
SUMBER INTERNAL                     SUMBER EKSTERNAL YANG DISETUJUI
unggah file / API internal           API / feed / penemuan sumber terbatas
             \                       /
              KATALOG SUMBER + PENERIMAAN AMAN
                         |
                ARSIP MENTAH + MANIFEST
                         |
             JOB DURABEL -> QUEUE -> WORKER
                         |
       parse -> normalisasi -> validasi -> pencocokan entitas
                         |
          BUKTI + KLAIM + OBSERVASI + KEJADIAN
                         |
               API DENGAN HAK AKSES
                         |
       pencarian | galaksi | timeline | watchlist | review
```

### Tiga lapisan data

- **Raw / bronze:** byte atau respons sumber yang boleh disimpan, manifest pengambilan, checksum, dan hak penggunaannya. Tidak diubah diam-diam oleh hasil AI.
- **Normalized / silver:** teks/tabel hasil parsing, satuan dan waktu yang dinormalisasi, bukti per halaman/baris, serta hasil ekstraksi berversi. Data tidak valid tetap bisa dilacak ke raw dan masuk karantina.
- **Serving / gold:** indeks pencarian, entitas kanonis, tampilan graph, agregasi, dan sinyal risiko. Lapisan ini dapat dibangun ulang dari data serta versi pemrosesan yang masih tersedia sesuai retensi.

Pada MVP, bronze berada di object storage; silver dan gold terutama di PostgreSQL. Istilah tiga lapisan ini **tidak berarti** harus memasang tiga platform data terpisah.

### Stack yang direkomendasikan

| Komponen | Pilihan awal | Alasan / batas |
| --- | --- | --- |
| Antarmuka | Next.js + TypeScript | Dashboard, pencarian, detail bukti, dan panel galaksi |
| Visual graph | Sigma.js, WebGL 2D | Cluster dan eksplorasi bertahap; 3D opsional belakangan |
| Backend | FastAPI + Pydantic | Kontrak bertipe, adapter Python, API terstruktur |
| Data utama | PostgreSQL + JSONB + PostGIS + pg_trgm | Data relasional, lokasi, alias, dan graph adjacency |
| Pencarian awal | PostgreSQL full-text + indeks terstruktur | Uji tokenisasi Indonesia/Inggris; jangan mengasumsikan stemming Indonesia tersedia otomatis |
| Raw storage | Object storage kompatibel S3, bucket privat, versioning | File besar terpisah dari database; lifecycle mengikuti izin dan retensi |
| Pekerjaan asinkron | Celery + Redis, dengan tabel job/outbox durabel di PostgreSQL | Queue bukan satu-satunya catatan pekerjaan; pemulihan dan idempotensi wajib |
| Ekstraksi | Parser deterministik dahulu; LLM terkontrol untuk dokumen tidak terstruktur | Output harus terikat bukti dan skema; model bukan sumber kebenaran |
| Deployment awal | Container; PostgreSQL dan object storage terkelola bila memungkinkan | Docker Compose untuk pengembangan, bukan otomatis rancangan produksi aman |

**Jangan pasang semua teknologi sekaligus.** Tambahkan pgvector jika pencarian semantik terbukti membantu; OpenSearch jika pencarian teks menjadi bottleneck; Parquet/Iceberg dan mesin komputasi terdistribusi jika pengolahan historis memang melampaui kapasitas awal. Kafka untuk kebutuhan replay/streaming berkelanjutan yang terukur; ClickHouse untuk agregasi besar; Neo4j untuk traversal graph kompleks yang tidak memenuhi sasaran di PostgreSQL. Evaluasi satu bottleneck pada satu waktu.

## 04 · Penerimaan data dan alur pemrosesan

### Format awal

| Input | Perlakuan MVP |
| --- | --- |
| CSV / XLSX | Preview, pemetaan kolom, validasi tanggal/satuan, bukti sheet–baris–kolom; macro tidak dijalankan |
| JSON / respons API | Simpan respons yang diizinkan, validasi skema per adapter, pertahankan versi skema |
| TXT / PDF teks | Ekstraksi teks dan penanda halaman; tabel rumit yang tidak andal masuk review |
| PDF scan / gambar | Tandai membutuhkan OCR; tidak diam-diam dianggap kosong atau sukses |
| Format lain | Arsip saja bila aman dan diizinkan; parser tambahan melalui adapter |

Batas pilot usulan: **25 MB per file** dan **100 halaman per PDF**; diputuskan kembali setelah melihat sampel. Arsip ZIP tidak didukung pada MVP. Penerimaan mengembalikan `job_id` dan status, tidak menahan HTTP sampai seluruh pemrosesan selesai.

### Alur setiap data masuk

1. **Otorisasi dan hak sumber:** tentukan pemilik, ruang akses, penggunaan yang diizinkan, dan kebijakan retensi.
2. **Pemeriksaan aman:** verifikasi MIME dari isi file, ukuran, malware, dan batas waktu/memori parser. Parser berjalan terisolasi tanpa menjalankan macro/script sumber.
3. **Akuisisi tercatat:** simpan hasil pengambilan, URL/identitas sumber, waktu, HTTP status bila ada, dan manifest. Simpan raw hanya jika diperbolehkan.
4. **Hash dan versi:** hitung SHA-256. Byte identik tidak perlu disimpan ulang dalam tenant yang sama; setiap pengambilan tetap punya catatan. Perubahan isi membuat versi baru.
5. **Parsing dan bukti:** keluarkan teks/tabel dengan referensi halaman atau sel; simpan versi parser dan parameter.
6. **Normalisasi:** tipe angka, mata uang, unit, kode wilayah, bahasa, tanggal, dan identitas produk. Nilai asli selalu tetap tersedia.
7. **Ekstraksi:** hasilkan kandidat entitas, klaim, observasi, dan kejadian dengan bukti; data yang tidak jelas masuk review.
8. **Resolusi entitas:** cocokkan identifier yang andal, lalu alias dan konteks. Nama mirip saja tidak cukup untuk menggabungkan perusahaan.
9. **Publikasi terkontrol:** indeks dan graph diperbarui sesuai status validasi dan izin. Klaim belum tervalidasi tidak ditampilkan sebagai fakta terkonfirmasi.
10. **Aturan dan audit:** evaluasi watchlist, buat peringatan tanpa duplikasi, dan catat metode serta bukti yang digunakan.

**Ketahanan:** worker boleh menerima tugas lebih dari sekali. Efek bisnis harus idempoten melalui unique constraint, kunci pekerjaan, checkpoint, dan transaksi. Tidak ada janji “exactly once” hanya karena memakai queue. Gunakan outbox, retry dengan backoff dan jitter, `Retry-After`, timeout, circuit breaker, serta tabel `failed_jobs` sebagai antrean gagal logis. Scheduler tunggal atau terkoordinasi; pekerjaan tertinggal dapat direkonsiliasi dari database.

Penyimpanan objek dan transaksi database tidak atomik bersama: unggah ke objek sementara, verifikasi hash, finalisasi manifest melalui transaksi, lalu rekonsiliasi objek yatim dan status tertunda. Reproses membuat versi hasil baru; tidak menghilangkan hasil lama yang masih berlaku menurut retensi.

## 05 · Katalog sumber eksternal

**Hasil pemeriksaan dokumentasi, bukan integrasi yang sudah berjalan.** Jadwal di bawah adalah usulan polling kita, bukan jaminan kecepatan pembaruan penerbit. Ketentuan dan akses perlu diverifikasi lagi ketika adapter diaktifkan.

| Prioritas / sumber | Data dan akses yang diketahui | Rencana penggunaan / batas |
| --- | --- | --- |
| MVP · World Bank Pink Sheet | Portal menyediakan data harga bulanan dalam spreadsheet; publikasi memuat seri Rubber RSS3 dan TSR20. [3](https://www.worldbank.org/en/research/commodity-markets) [1](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Pink-Sheet-June-2026.pdf) | Cek pembaruan harian secara ringan; impor hanya saat versi berubah. Simpan periode dan definisi seri. **Bukan harga spot lokal atau feed intraday.** Periksa ketentuan dataset dan atribusi. |
| MVP · BMKG Data Terbuka | API JSON prakiraan desa/kelurahan: horizon 3 hari, interval 3 jam, pembaruan 2 kali sehari. Dokumentasi menyebut 60 permintaan/menit/IP dan kewajiban atribusi BMKG. [1](https://data.bmkg.go.id/prakiraan-cuaca/) | Poll misalnya tiap 12 jam untuk daftar lokasi pilot, memakai batas lebih konservatif dari kuota. Simpan waktu terbit dan waktu berlaku. **Prakiraan bukan bukti kejadian banjir atau kerusakan kebun.** |
| MVP · GDELT + feed berita yang disetujui | DOC API mendukung penemuan berita. Dokumentasi historis menunjukkan perubahan horizon dan perbedaan perilaku mode pencarian. [1](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) [3](https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/) | Poll usulan 30–60 menit; simpan metadata/tautan yang diizinkan. Uji jendela pencarian, batas hasil dan kemampuan bahasa pada layanan saat ini. Penemuan URL **tidak memberikan hak mengarsipkan seluruh artikel**. |
| Fase 2 · BPS | WebAPI menyediakan JSON untuk berbagai data/tabel/publikasi dan menggunakan key token. [1](https://webapi.bps.go.id/documentation/) | Pilih dataset karet/produksi/perdagangan melalui katalog resmi; petakan ID tabel, variabel, satuan dan periode yang benar. Jangan menganggap seluruh isi PDF tersedia sebagai tabel API. |
| Fase 2 · UN Comtrade | Tersedia preview terbatas dan API dengan subscription key; akses endpoint bergantung tingkat langganan. [2](https://uncomtrade.org/docs/un-comtrade-api/) | Data perdagangan menurut reporter, partner, arus, periode, dan versi HS. Pilih subkode yang sesuai untuk karet alam. Sinkronisasi berdasarkan ketersediaan rilis, kuota, dan revisi; data kosong tidak otomatis nol. |
| Fase 2 · SGX / vendor berizin | Dokumen kebijakan SGX 2020 mengatur pemakaian non-display dan redistribusi data pasar. Ini referensi kewaspadaan lisensi, **bukan konfirmasi tarif atau ketentuan terbaru**. [2](https://www.datadirect.sgx.com/Portals/0/Documents/Market-Data-Policy/SGX%20Market%20Data%20Policy_1%20July%202020.pdf?ver=3VcRAqOoXvJSKwL8glUf_w%3D%3D) | Feed harga hanya setelah hak display, penyimpanan, analitik/AI dan redistribusi dikonfirmasi dengan penyedia. Tidak mengganti lisensi dengan scraping halaman. |
| Kandidat fase 2 · kurs, regulasi, dan laporan industri | Belum ditetapkan adapter maupun kontrak datanya dalam blueprint ini. | Pilih sumber resmi/berizin. Sementara gunakan impor manual yang sah. Tanggal penerbitan, tanggal berlaku, versi, dan hak penggunaan harus dipetakan terpisah. |

### Isi minimal satu entri sumber

`source_id`, pemilik/penerbit, tipe adapter, domain/endpoint yang diizinkan, cakupan topik/wilayah, metode autentikasi, referensi secret, jadwal, kuota, cursor, versi skema, atribusi, URL/dokumen syarat penggunaan, tanggal review, dan penanggung jawab.

Hak dipisah menjadi **boleh mengambil, menyimpan raw, mengekstrak, mengirim ke penyedia model, menampilkan, dan mendistribusikan ulang**. Semua ditolak secara default sampai kebijakan sumber menyetujui. Sumber “hanya metadata” tetap bermanfaat di galaksi; jangan mengarsipkan body artikel secara diam-diam.

## 06 · Cara sistem melacak sendiri data eksternal

Otomatisasi dibagi dua, agar tidak berubah menjadi crawler tanpa batas.

### A. Koleksi terjadwal dari sumber yang disetujui

- Scheduler menjalankan adapter sesuai katalog sumber dan daftar lokasi/topik yang aktif.
- Gunakan cursor/watermark dengan overlap untuk dokumen terlambat; deduplikasi menangani pengulangan.
- Gunakan ETag/Last-Modified jika didukung; deteksi perubahan berdasarkan hash.
- Pecah rentang waktu/query jika hasil mencapai batas layanan; catat jika hasil berpotensi terpotong. Jangan menyebutnya arsip lengkap jika provider membatasi hasil.
- Jika gagal, indikator menampilkan **sumber terlambat/gagal**, bukan “tidak ada kejadian”.

### B. Penemuan sumber dan topik baru yang dibatasi

1. Mulai dari kosakata kurasi: karet alam, natural rubber, Hevea, latex, bokar, RSS, TSR, SIR, dan nama entitas yang telah disetujui.
2. Susun query berkonteks. “Rubber” atau “latex” sendirian terlalu luas; gabungkan dengan istilah komoditas, wilayah atau rantai pasok dan uji precision/recall.
3. Panggil layanan pencarian/feed melalui adapter dan anggaran harian yang ditetapkan. Tool pencarian dalam percakapan ini **bukan** infrastruktur kolektor produksi.
4. Nilai relevansi, bahasa, penerbit, kebaruan, dan duplikasi; simpan kandidat beserta alasan penemuannya.
5. Domain baru masuk **antrean persetujuan**: verifikasi penerbit, ketentuan, akses, keamanan, serta cara penyimpanan. Relevansi tinggi tidak sama dengan izin akses.
6. Setelah disetujui, lakukan dry-run adapter, aktifkan jadwal, lalu pantau kualitas dan kegagalannya.

Entitas baru dapat diusulkan sebagai watchlist, tetapi tidak otomatis memperluas crawling tanpa batas. Terapkan batas domain, kedalaman, ukuran respons, jumlah query, biaya, dan waktu. Patuhi ketentuan layanan dan robots bila relevan; robots bukan pengganti hak penggunaan. Tidak menembus login, CAPTCHA, paywall, atau pembatasan akses.

## 07 · Ontologi karet alam dan aturan normalisasi

### Entitas inti

- **Organisasi:** pemasok, koperasi, pengolah, eksportir, pembeli, asosiasi, dan penerbit. “Pemasok” adalah peran organisasi, bukan identitas yang berbeda untuk perusahaan yang sama.
- **Fasilitas dan lahan:** kebun/plot, titik pengumpulan, pabrik, gudang, dan simpul logistik.
- **Lokasi:** negara, wilayah administratif, titik/poligon; setiap kode memiliki namespace dan versi. Kode BPS dan kode administrasi sumber lain tidak boleh diasumsikan sama.
- **Material/produk:** lateks, bahan olah karet rakyat, sheet, dan karet spesifikasi teknis. Bentuk, grade, standar, serta versi standar dipisahkan; label SIR/TSR tidak diperlakukan sebagai satu grade tunggal.
- **Dokumen, observasi, dan kejadian:** dokumen adalah bukti; observasi adalah nilai/pernyataan terukur atau dilaporkan; kejadian adalah sesuatu yang dinyatakan terjadi. Sinyal risiko adalah hasil analisis terpisah.

Relasi awal: `located_in`, `operates`, `supplies_to`, `produces`, `mentions`, `reported_by`, dan `potentially_exposed_to`. Relasi pasokan hanya diterbitkan bila ada bukti yang memadai; sekadar disebut dalam berita yang sama tidak membuktikan transaksi.

### Harga dan kuantitas tidak boleh disamakan begitu saja

Setiap observasi harga memerlukan nilai decimal, mata uang, unit, material/bentuk/grade, basis berat basah/kering/produk, jenis harga, pasar/lokasi, periode/waktu, sumber, dan versi. Tambahkan spot/futures/benchmark/transaksi internal, bulan kontrak, incoterm, pajak dan ongkos jika relevan. Field yang tidak diketahui adalah `null` dengan alasan, bukan ditebak AI.

- Bedakan IDR/kg bahan basah, IDR/kg karet kering, USD/kg produk, dan US cents/kg.
- Bedakan harga rata-rata bulanan, settlement kontrak tertentu, penawaran pemasok, dan transaksi aktual.
- Konversi mata uang harus menunjuk observasi kurs bertanggal beserta kebijakan tanggal yang dipakai; jangan mengubah nilai asli.
- Kadar Karet Kering (**KKK/DRC**) harus memiliki metode, waktu, sumber, dan unit persentase/fraksi yang jelas.

**Contoh simulasi, bukan harga pasar:** 1.000 kg bahan pada KKK 60% setara 600 kg kandungan karet kering. Harga Rp15.000/kg basah setara Rp25.000/kg kandungan karet kering melalui `15.000 / 0,60`. Ini hanya konversi basis sederhana; bukan biaya produksi akhir dan bukan otomatis setara mutu atau harga kontrak TSR20. Jika KKK tidak diketahui atau tidak valid, konversi ditahan.

Untuk perdagangan, simpan versi klasifikasi dan subkode komoditas yang relevan; jangan mengambil seluruh Bab 40 sebagai bahan baku karet alam. Nilai perdagangan dibagi berat menghasilkan **unit value**, bukan otomatis harga pasar yang sebanding.

## 08 · Model data logis

Nama berikut adalah rancangan tabel/domain, **belum migration produksi**. Seluruh objek bisnis berada dalam lingkup organisasi; foreign key dan unique constraint harus menjaga lingkup yang sama.

| Kelompok / tabel | Isi penting |
| --- | --- |
| `tenants`, `users`, `memberships` | Organisasi, identitas, peran, status keanggotaan |
| `sources`, `source_policies` | Adapter, cakupan, jadwal, hak per penggunaan, atribusi, versi kebijakan |
| `collection_runs`, `jobs`, `outbox`, `failed_jobs` | Percobaan koleksi, cursor, idempotency key, antrean durabel, hasil dan kegagalan |
| `acquisitions`, `raw_assets` | Setiap pengambilan/unggahan, status, hash, lokasi objek privat, MIME, ukuran, dasar retensi |
| `documents`, `document_versions`, `extraction_runs` | Identitas dokumen, versi isi, bahasa, hasil/versi parser atau model |
| `evidence_fragments` | Potongan bukti: halaman/offset/bounding box atau sheet–baris–kolom, versi dokumen dan hak akses |
| `entities`, `entity_identifiers`, `entity_aliases` | Identitas kanonis, ID eksternal beserta namespace, alias berkonteks |
| `entity_merge_log` | Riwayat penggabungan/pemisahan; dapat ditinjau dan dibatalkan |
| `claims`, `claim_evidence` | Subjek–predikat–objek atau nilai bertipe, status review, atribusi, waktu berlaku dan waktu pencatatan; bukti many-to-many |
| `material_specs`, `price_observations` | Bentuk/grade/standar, nilai harga, basis berat, mata uang, kontrak, periode dan bukti |
| `weather_observations` | Lokasi, jenis forecast/observed, waktu terbit, waktu berlaku, variabel dan bukti |
| `trade_observations` | Fase 2: reporter, partner, arus, HS/version, periode, berat, nilai dan revisi |
| `events`, `event_entities`, `event_evidence` | Kejadian, status, rentang waktu, peran entitas, bukti lintas dokumen |
| `risk_signals` | Kesimpulan turunan yang masih bersifat potensi; rule/model version, input, alasan, keterbatasan |
| `watchlists`, `alert_rules`, `alerts`, `alert_deliveries` | Ruang pantau, versi aturan, deduplikasi, acknowledge, tujuan pengiriman |
| `review_tasks`, `audit_log` | Masalah kualitas, keputusan manusia, perubahan kebijakan, akses dan tindakan penting |
| `lots`, `movements`, `quality_tests` | Fase 2: lot fisik, asal-usul, pergerakan, hasil uji; terpisah dari observasi berita/harga |

```text
Source -> CollectionRun -> Acquisition -> RawAsset
                                      -> DocumentVersion -> EvidenceFragment
Entity <- Claim -> Entity / TypedValue       ^                 |
              \-----------------------------+-----------------+
Event <-> EventEntity <-> Entity ; Event <-> EventEvidence
RiskSignal -> input observasi/klaim + versi aturan -> Alert
```

Graph bukan tabel bayangan tanpa bukti: edge adalah proyeksi klaim yang memenuhi aturan status dan hak akses. Satu klaim/kejadian dapat memiliki banyak bukti, termasuk bukti yang bertentangan. Tabel khusus observasi menyimpan nilai bertipe, sementara klaim menjadi penghubung pengetahuan; hindari menaruh semua angka penting dalam JSON bebas.

Kunci deduplikasi dibedakan: hash byte untuk aset, identitas sumber+versi untuk dokumen, key bisnis+periode+versi rilis untuk observasi, dan tanda tangan aturan+entitas+rentang kejadian untuk alert. Koreksi sumber menghasilkan revisi, bukan data baru yang tanpa sengaja dihitung dua kali.

## 09 · Waktu, kualitas, dan kebenaran

### Empat waktu yang berbeda

- **Waktu kejadian/periode observasi:** kapan hal terjadi atau periode nilai itu berlaku.
- **Waktu publikasi/terbit:** kapan penerbit mengeluarkan dokumen; untuk prakiraan, simpan `issued_at` dan `valid_at` secara terpisah.
- **Waktu akuisisi:** kapan sistem benar-benar memperoleh data.
- **Waktu sistem/riwayat:** kapan klaim/revisi direkam, digantikan, disetujui atau ditarik. Simpan interval waktu berlaku dan interval waktu pencatatan agar dapat menjawab “apa yang kita ketahui saat itu?”.

Simpan timestamp berzona/UTC dan zona asli bila tersedia; UI dapat memakai Asia/Jakarta. Tanggal tanpa jam tetap bertipe tanggal dengan presisi yang diketahui—jangan menciptakan jam kejadian. Data terlambat tidak dipindahkan ke tanggal pengambilan hanya agar terlihat baru.

### Pisahkan status yang sering tercampur

- **Relevansi:** seberapa terkait dengan topik karet.
- **Keandalan ekstraksi:** seberapa baik teks/nilai dibaca, bila metriknya tersedia dan telah diuji.
- **Status klaim:** diekstrak, tervalidasi aturan, ditinjau manusia, diperselisihkan, digantikan, atau ditarik.
- **Jenis informasi:** prakiraan, pengukuran, laporan sumber, atau hasil turunan.

Skor model tidak boleh diberi label “persentase kebenaran”. Tiga media yang menyalin siaran pers yang sama bukan tiga konfirmasi independen. Sistem mempertahankan klaim yang berbeda dengan sumbernya; tidak memilih nilai yang paling sering disalin secara otomatis.

Antrean review memprioritaskan harga tanpa unit, KKK tidak valid, tanggal ambigu, konflik identifier, perubahan skema, dan klaim berisiko tinggi. Koreksi manusia berversi dan diaudit. Bila bukti tidak cukup, keluaran yang sah adalah **belum diketahui**.

## 10 · Galaksi sebagai antarmuka pengetahuan

<!-- GALAXY_DIAGRAM -->

**Galaksi adalah tampilan dari pengetahuan yang boleh dilihat pengguna, bukan pengganti arsip dan database.** Ilustrasi di dokumen ini bersifat skematis; tidak memuat pemasok atau kejadian nyata.

| Metafora | Makna dalam aplikasi |
| --- | --- |
| Bintang | Entitas atau kejadian; dokumen menjadi node saat mode bukti dibuka |
| Gugus | Kelompok topik, wilayah, atau rantai pasok yang dapat dijelaskan |
| Garis | Relasi bertipe dengan bukti; klik untuk melihat sumber dan status |
| Cahaya/penanda baru | Kebaruan informasi, bukan jaminan kebenaran atau tingkat bahaya |
| Garis waktu | Filter waktu kejadian dan pilihan “diketahui sistem sampai tanggal…” |

### Interaksi utama

1. **Overview:** lihat gugus harga, pasokan, cuaca, perdagangan, logistik dan regulasi; tidak memuat setiap dokumen sekaligus.
2. **Zoom:** buka satu gugus/entitas, tampilkan tetangga satu atau dua hop yang relevan.
3. **Filter:** wilayah, jenis entitas, sumber, grade, rentang waktu, jenis informasi dan status review.
4. **Evidence drawer:** lihat relasi, kutipan/sel bukti yang diizinkan, penerbit, versi dokumen, waktu terbit dan waktu akuisisi.
5. **Timeline dan watchlist:** simpan ruang pantau; hubungkan perubahan dengan peringatan.
6. **Tampilan alternatif:** tabel, hasil pencarian dan peta. Semua informasi penting tetap dapat diakses tanpa harus menavigasi animasi.

Untuk pilot, respons subgraph dibatasi misalnya **500 node / 1.000 edge**. Gunakan pengelompokan dan pemuatan bertahap di server; bukan mengirim jutaan node ke browser. Node/relasi yang disembunyikan karena batas jumlah diberi indikator, tanpa membocorkan objek yang pengguna tidak berhak lihat.

Warna tidak menjadi satu-satunya pembeda; gunakan bentuk, label, legenda dan status. Gerakan dapat dimatikan. Ukuran node mengikuti metrik yang disebutkan, misalnya jumlah hubungan **dalam hasil terfilter**, bukan klaim “paling berpengaruh”. Jarak layout bukan jarak geografis atau bukti sebab-akibat. Cluster buatan algoritma ditandai sebagai hasil pengelompokan, bukan klasifikasi resmi.

## 11 · Intelligence dan peringatan

Mulai dengan aturan transparan, bukan agen yang bebas membuat kesimpulan.

### Tiga aturan awal

1. **Perubahan harga sebanding:** bandingkan seri, grade, unit, jenis harga dan frekuensi yang sama. Ambang perubahan ditentukan pengguna. Harga bulanan tidak dievaluasi seolah-olah tick harian.
2. **Paparan cuaca pada lokasi pemasok:** hubungkan prakiraan yang relevan dengan lokasi yang telah diverifikasi. Keluaran: potensi paparan yang perlu diperiksa; bukan bukti penurunan produksi.
3. **Perubahan dokumen/topik watchlist:** deteksi dokumen baru atau versi berubah yang menyebut entitas/topik pantauan, dengan sumber dan ringkasan berbukti.

Setiap alert mencantumkan alasan, input, waktu, versi aturan, status, tautan bukti, keterbatasan dan penanggung jawab. Deduplikasi, cooldown, tingkat prioritas, acknowledge dan penutupan mencegah banjir notifikasi. MVP cukup memiliki inbox dalam aplikasi; email/webhook ditambahkan setelah tujuan serta izin disetujui.

### Contoh keluaran—sepenuhnya simulasi

```json
{
  "record_type": "risk_signal",
  "example_only": true,
  "category": "weather_supply_exposure",
  "status": "potential",
  "evidence_ids": ["forecast_demo_01", "supplier_location_demo_01"],
  "rule_version": "weather_exposure_v1",
  "reason": "Prakiraan cuaca relevan dengan lokasi pemasok terdaftar.",
  "limitations": [
    "Prakiraan bukan bukti banjir.",
    "Lokasi pemasok bukan bukti lokasi seluruh kebun asal.",
    "Tidak membuktikan produksi turun atau pengiriman terlambat."
  ]
}
```

Jika asisten tanya-jawab ditambahkan nanti, gunakan retrieval dengan hak akses yang sama, jawaban bersumber, tanggal snapshot dan penolakan untuk menyimpulkan tanpa bukti. Angka/perhitungan dikerjakan oleh fungsi deterministik. Konten dokumen dianggap data tidak tepercaya: tidak dapat mengubah instruksi sistem, menjalankan tool, membuka URL arbitrer, atau memerintahkan pengiriman data.

## 12 · Kontrak API awal

API berversi; `tenant_id` diturunkan dari sesi dan keanggotaan yang terverifikasi, bukan dipercaya dari input klien. Pagination berbasis cursor, format error konsisten, audit, pembatasan permintaan, dan `Idempotency-Key` untuk mutasi yang dapat diulang.

| Endpoint usulan | Fungsi |
| --- | --- |
| `POST /v1/uploads` | Buat sesi unggah privat dan URL sementara yang dibatasi ukuran/tipe |
| `POST /v1/uploads/{id}/complete` | Verifikasi objek, hash dan hak, lalu buat job; URL unggah tidak otomatis berarti data diterima |
| `GET /v1/jobs/{id}` | Status, tahap, error terstruktur, dan tindakan yang tersedia |
| `GET /v1/documents/{id}/versions` | Riwayat dokumen yang diizinkan |
| `GET /v1/evidence/{id}` | Bukti dan lokasi asal; raw download bila hak mengizinkan |
| `GET /v1/search` | Teks + filter periode/sumber/entitas/status |
| `GET /v1/entities/{id}` | Profil dan identifier berbukti |
| `GET /v1/galaxy` | Subgraph terfilter, agregasi, batas jumlah dan status pemotongan |
| `GET /v1/events` | Timeline dengan pilihan waktu kejadian atau waktu diketahui |
| `GET /v1/alerts` | Inbox peringatan; acknowledge melalui mutasi terpisah |
| `POST /v1/sources/{id}/dry-run` | Uji adapter oleh admin tanpa langsung mengaktifkan jadwal |
| `POST /v1/review-tasks/{id}/decision` | Keputusan pengelola data, alasan dan versi; diaudit |

Frontend mengakses API melalui origin aplikasi atau reverse proxy. Browser tidak diarahkan ke `localhost` untuk menghubungi layanan yang berjalan di server. Kredensial feed/model hanya berada di backend; parser dan collector memiliki izin minimum.

## 13 · Keamanan, deployment, dan operasi

### Kontrol yang wajib sejak MVP

- **RBAC:** admin mengelola sumber/akses; data steward meninjau kualitas; analyst memakai pencarian dan watchlist; viewer hanya membaca. Hak sensitif seperti ekspor massal dipisahkan.
- **Pemisahan data:** `tenant_id`, constraint lintas tabel dan PostgreSQL row-level security. Hak akses diterapkan juga pada indeks, graph, cache, embedding, ekspor dan raw asset. Signed URL berumur pendek; bucket tidak publik.
- **Perlindungan:** TLS, enkripsi penyimpanan dan backup, secret di pengelola secret/environment yang aman, rotasi, serta pemisahan development/production.
- **Collector aman:** allowlist domain dan protokol; cegah SSRF ke jaringan privat, loopback dan metadata cloud, termasuk redirect serta perubahan DNS. Batasi respons, redirect, waktu dan bandwidth. HTML eksternal disanitasi dan tidak dieksekusi.
- **Privasi:** koordinat kebun, identitas petani, kontrak dan harga internal dapat sensitif. Kumpulkan seperlunya, batasi akses, dan tetapkan dasar pemrosesan serta kewajiban perlindungan data yang berlaku.
- **AI:** tidak mengirim data privat ke penyedia model/embedding tanpa persetujuan dan kebijakan yang sesuai. Model akses baca-terbatas; output terstruktur divalidasi.
- **Retensi:** tetapkan per kelas data dan sumber sebelum aktivasi. Append-only mencegah penimpaan diam-diam, **bukan janji menyimpan selamanya**. Penghapusan sah mencakup raw, turunan, indeks/cache/embedding; backup mengikuti jadwal kedaluwarsa dan proses pencegahan pemulihan ulang data terhapus. Audit menyimpan metadata minimal yang dibenarkan.

### Bentuk deployment pilot

Reverse proxy/TLS → frontend + API → PostgreSQL dan bucket privat. Scheduler/outbox dispatcher dan worker berjalan sebagai proses terpisah; Redis internal, tidak diekspos publik. Tambahkan worker horizontal bila antrean membesar. Produksi memerlukan hosting yang terus aktif; percakapan ini sendiri tidak menjalankan pemantauan 24/7.

### Observabilitas dan pemulihan

Pantau keberhasilan per sumber, keterlambatan jadwal, usia data, perubahan skema, panjang/usia antrean, error parsing, ukuran arsip, biaya API/model, dan antrean review. Bedakan status **belum aktif, sehat, tidak ada pembaruan, terlambat, dibatasi, dan gagal**.

Target pilot usulan: backup terenkripsi harian dengan retensi 30 hari, **RPO ≤24 jam** dan **RTO ≤8 jam**. Ini target yang harus dibuktikan lewat uji restore database, objek, konfigurasi dan kunci—bukan jaminan sebelum diuji. Pertimbangkan PITR dan layanan ber-redundansi saat kebutuhan bisnis menuntutnya. Backup berada di domain kegagalan terpisah dari server utama.

## 14 · Roadmap pengembangan

Estimasi kerja awal **10–12 minggu**, dengan dua engineer dan keterlibatan rutin pemilik domain/data. Bukan penawaran biaya atau janji tanggal rilis; akses sumber, kerumitan data dan hasil UAT dapat mengubahnya.

| Tahap | Waktu usulan | Hasil dan gerbang kelulusan |
| --- | --- | --- |
| Fondasi | Minggu 1 | 100–200 sampel berizin, kamus data, daftar sumber, kebijakan akses/retensi, repository dan keputusan arsitektur disepakati |
| Ingestion | Minggu 2–3 | Unggah, manifest/hash, parser, karantina, job/outbox, versi dokumen dan bukti sel/halaman; replay tidak menggandakan observasi |
| Adapter publik | Minggu 4–5 | World Bank dan BMKG lolos dry-run, atribusi, uji revisi/skema, retry dan dashboard kesehatan |
| Pengetahuan & discovery | Minggu 6–7 | Metadata berita berizin, resolusi entitas dasar, klaim berbukti, review dan tiga aturan awal; domain baru tetap melalui persetujuan |
| Pengalaman pengguna | Minggu 8–9 | Pencarian, profil entitas, galaksi, timeline, watchlist, inbox alert dan tampilan tabel alternatif |
| Hardening & pilot | Minggu 10–12 | Uji beban, keamanan, isolasi tenant, restore, UAT domain, runbook dan deployment yang terus aktif |

**Di luar jalur kritis MVP:** chatbot generatif, database graph terpisah, OCR massal, stream bursa, forecasting harga, dan ketertelusuran lot fisik end-to-end.

## 15 · Kriteria penerimaan dan biaya

### Sasaran uji pilot—belum benchmark

| Area | Kriteria kelulusan usulan |
| --- | --- |
| Provenance | 100% klaim/observasi yang dipublikasikan dapat ditelusuri ke bukti, sumber, versi dan waktu; jika bukti tidak boleh disimpan, batas tersebut terlihat |
| Idempotensi | Replay file, retry job, pengambilan berulang dan revisi sumber tidak menggandakan nilai aktif/agregasi |
| Kualitas | Pada set evaluasi berlabel yang disepakati, target precision ≥90% dan recall ≥80% untuk field/relasi terpilih; laporkan per kelas, bukan satu angka “akurasi AI” |
| Resolusi entitas | Penggabungan ambigu masuk review; merge/split dapat dibatalkan tanpa kehilangan bukti |
| Keamanan | Uji negatif lintas tenant untuk API, raw URL, search, graph, cache dan ekspor semuanya lulus |
| Pencarian | Sasaran p95 ≤2 detik pada corpus pilot hingga 100.000 dokumen dengan teks terindeks rata-rata ≤5.000 karakter, 10 sesi uji serentak dan konfigurasi server yang dicatat; beban lebih besar diuji ulang |
| Galaksi | Maksimum awal 500 node/1.000 edge per tampilan; target respons API p95 ≤2 detik, lalu uji render/interaksi pada laptop pilot yang disebutkan spesifikasinya |
| Kesegaran | Untuk sumber sehat, target 95% job mulai dalam 15 menit dari jadwal. Ukur terpisah dari jeda publikasi penerbit, waktu unduh dan waktu pemrosesan |
| Pemulihan | Uji restore memenuhi RPO/RTO yang disepakati; catat durasi serta kehilangan data aktual |
| Operasi | Sumber gagal atau terpotong terlihat, alert memiliki alasan/bukti, ada runbook retry dan pemilik setiap sumber |

Set evaluasi dipisahkan dari contoh untuk menyusun prompt/aturan. Pengukuran precision/recall dilakukan per field dan relasi, dengan definisi label yang jelas. Target yang gagal menjadi pekerjaan perbaikan atau pengurangan cakupan; tidak disembunyikan di balik visualisasi.

### Mengukur cakupan dengan jujur

Tampilkan jumlah sumber disetujui/aktif/sehat, wilayah dan topik yang dipantau, rentang arsip, usia data terakhir, jumlah dokumen tersimpan, serta celah koleksi. Jangan menampilkan “cakupan seluruh dunia 100%”. Tidak adanya dokumen di arsip tidak membuktikan tidak adanya kejadian.

### Model biaya sebelum menentukan anggaran

Biaya bulanan = compute frontend/API/worker + database + object storage dan backup + bandwidth + lisensi sumber/search + token model/embedding + observabilitas serta operasi. Pisahkan biaya pembangunan dari biaya berjalan.

**Ilustrasi kapasitas, bukan proyeksi penggunaan:** 2.000 objek/hari × 300 KB × 365 hari ≈ **219 GB/tahun** raw, sebelum versi tambahan, teks hasil ekstraksi, indeks, replika dan backup. Jumlah node graph saja tidak cukup untuk menghitung biaya.

Jalankan benchmark dengan sampel nyata sebelum memilih paket cloud. Tetapkan kuota per sumber, batas token/dokumen dan anggaran reproses; hindari membaca ulang seluruh arsip dengan model setiap hari. Tidak ada harga cloud/feed yang diasumsikan sudah disetujui dalam blueprint ini.

## 16 · Keputusan yang dibekukan dan langkah berikutnya

### Catatan keputusan arsitektur

- **ADR-01:** simpan raw yang diizinkan dan provenance sebelum menambahkan intelligence.
- **ADR-02:** PostgreSQL + object storage menjadi fondasi awal; graph adalah model pengetahuan, bukan alasan memasang stack terdistribusi sejak hari pertama.
- **ADR-03:** kolektor terjadwal dan discovery dipisahkan; domain baru tidak otomatis memperoleh izin crawling.
- **ADR-04:** klaim, prakiraan, pengukuran dan inferensi dibedakan; tidak ada klaim sebab-akibat dari kedekatan node.
- **ADR-05:** galaksi 2D dengan bukti dan tampilan alternatif lebih dahulu; efek visual tidak mengalahkan keterbacaan.
- **ADR-06:** pemrosesan at-least-once dengan idempotensi; revisi dan koreksi berversi, bukan ditimpa diam-diam.

### Input yang dibutuhkan sebelum sprint pertama

1. Satu pemilik keputusan bisnis dan satu penanggung jawab data/review.
2. Tiga contoh pertanyaan bisnis paling penting, misalnya perubahan harga pembelian atau paparan pasokan.
3. Sampel berizin: file pembelian, daftar pemasok/lokasi, spesifikasi produk, dan beberapa dokumen karet; data sintetis dipakai bila data asli belum aman dibagikan.
4. Pilihan wilayah, grade/material dan sumber pilot; lokasi pemasok tidak otomatis mewakili seluruh kebun asal.
5. Batas akses, retensi, hosting, anggaran berjalan, dan proses persetujuan akun/lisensi. Tidak perlu memberikan password/API key melalui chat; gunakan secret manager saat implementasi.

### Paket implementasi pertama yang direkomendasikan

Mulai dengan **unggah satu file pembelian → arsip asli → mapping kolom → observasi bertipe dan bukti sel → pencarian → beberapa node/relasi berbukti**. Lalu tambahkan satu adapter World Bank untuk menguji versi, periode dan perbandingan seri yang benar. Setelah alur ini lulus, perluas ke cuaca dan berita. Galaksi tumbuh dari data yang dapat dipercaya, bukan dari banyaknya titik yang dibuat.

## Referensi dan status verifikasi

Dokumentasi diperiksa pada 15 Oktober 2026. Pemeriksaan ini tidak sama dengan pengujian SLA, ketersediaan seluruh histori, autentikasi, ketentuan kontrak terbaru, atau kelengkapan cakupan sumber.

- **BMKG:** format, horizon, frekuensi, atribusi dan batas akses—[1](https://data.bmkg.go.id/prakiraan-cuaca/).
- **BPS:** WebAPI, token dan jenis sumber—[1](https://webapi.bps.go.id/documentation/).
- **World Bank:** portal data dan berkas bulanan—[3](https://www.worldbank.org/en/research/commodity-markets); definisi seri karet dalam publikasi—[1](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Pink-Sheet-June-2026.pdf).
- **UN Comtrade:** preview dan subscription API—[2](https://uncomtrade.org/docs/un-comtrade-api/).
- **GDELT:** DOC API dan perubahan perilaku historis—[1](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/), [3](https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/). Perilaku layanan aktual wajib diuji ketika implementasi.
- **SGX:** referensi kebijakan 2020 untuk risiko lisensi, bukan tarif terkini—[2](https://www.datadirect.sgx.com/Portals/0/Documents/Market-Data-Policy/SGX%20Market%20Data%20Policy_1%20July%202020.pdf?ver=3VcRAqOoXvJSKwL8glUf_w%3D%3D).

---

**Ringkasan akhir:** bangun memori data yang berbukti lebih dahulu, kolektor yang terkendali berikutnya, lalu intelligence dan galaksi yang dapat ditelusuri. Besar dan otomatis tidak harus berarti tanpa batas, tanpa sumber, atau tanpa pengawasan.
