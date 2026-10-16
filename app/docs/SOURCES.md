# Sumber, arti data, dan hak penggunaan

Status aktual rilis di `VERIFICATION.md`. Katalog bukan bukti keberhasilan koneksi: status, HTTP, raw dan record pada setiap run adalah buktinya. Semua adapter hanya mengambil domain HTTPS yang diizinkan. URL pengguna tidak dijadikan open proxy. Pengumpulan mengikuti jadwal terbatas, conditional GET bila header tersedia, batas byte, batas laju per host, dan retry/backoff. Penyedia bisa mengubah skema, hak akses, atau ketentuan kapan saja.

## World Bank Commodity Price Data (Pink Sheet)

- Discovery: https://www.worldbank.org/en/research/commodity-markets
- Dataset terms: https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets
- License reference: https://datacatalog.worldbank.org/public-licenses#cc-by
- Adapter menemukan workbook **CMO-Historical-Data-Monthly.xlsx** dari halaman resmi, bukan mematok URL versi publikasi selamanya. Workbook asli beserta halaman discovery diarsipkan.
- Sheet **Monthly Prices**, seri rubber RSS3 dan TSR20, unit USD/kg diperiksa eksplisit. Data sumber nominal bulanan; tidak disamakan dengan spot intraday, harga pembelian lokal, SIR20 atau harga semua grade.
- Nilai unavailable seperti `..`/kosong dihitung sebagai source_missing_values; bukan nol atau penolakan kualitas harga. Sel rusak/unit tak dikenal dihentikan/ditahan dengan alasan.
- Bukti: workbook + sheet + row + column + raw period/value; periode historis dan jumlah per seri dicatat pada coverage.
- Attribution: **World Bank, Commodity Price Data (The Pink Sheet).** Lisensi dataset/CC BY tunduk pengecualian pihak ketiga. Periksa ketentuan sebelum redistribusi komersial luas; tidak ada endorsement World Bank.

## FAO/FAOSTAT QCL

- Katalog bulk: https://bulks-faostat.fao.org/production/datasets_E.xml
- Halaman data: https://www.fao.org/faostat/en/#data/QCL
- Terms: https://www.fao.org/contact-us/terms/db-terms-of-use/en/
- Dari katalog `QCL`, adapter mengambil ZIP normalized resmi. Seluruh ZIP dikonservasi; CSV dibaca streaming, bukan mengekstrak berkas/menjalankan kode di dalam ZIP. Raw memuat komoditas lain untuk mempertahankan original; record publik hanya **Natural rubber in primary forms / item 836**, elemen Production, unit ton metrik.
- Default sejak 2000, batas konfigurasi 1961–2100. Agregat wilayah tetap diberi label wilayah; jangan menjumlahkan negara dan agregat regional sebagai produksi dunia.
- Flag asli, deskripsi flag bila tersedia dalam auxiliary CSV, note, tanggal pembaruan dataset, area code, year, unit, value, dan raw CSV row dipertahankan. Estimasi/hasil imputasi sumber bukan pengukuran independen oleh aplikasi.
- Citation mengikuti metadata pembaruan, tanggal akuisisi dan URL. Contoh untuk snapshot yang diverifikasi: **FAO. 2025. FAOSTAT: Crops and livestock products (QCL). [Accessed on 15 October 2026]. https://www.fao.org/faostat/en/#data/QCL. Licence: CC-BY-4.0.** Tanggal capture/run dan attribution ikut bukti dan ekspor; sesuaikan tahun/tanggal pada akuisisi berikutnya.
- Dataset umumnya CC BY 4.0 sesuai ketentuan database FAO dan pengecualian metadata/pihak ketiga; jangan menyiratkan dukungan FAO.

## BMKG prakiraan adm4

- Dokumentasi resmi/atribusi dan pembatasan: https://data.bmkg.go.id/prakiraan-cuaca/
- Endpoint: `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=12.71.01.1001`
- Kode memakai **adm4 Kemendagri**, bukan kode BPS. Default: **Pasar Baru, Medan Kota, Kota Medan, Sumatera Utara**; label dipastikan dari respons, bukan diasumsikan koordinat kebun/pemasok pengguna.
- Data **prakiraan**, bukan pengamatan cuaca/kejadian bencana. Waktu analysis/issued dan valid disimpan terpisah. Temperature °C, humidity %, wind km/h dipertahankan; deskripsi cuaca bukan verifikasi banjir/gangguan pasok.
- Dokumentasi menyebut prakiraan 3 hari/interval 3 jam dan pembaruan dua kali sehari. Aplikasi menyimpan interval yang benar-benar dikembalikan API; capture 18 interval bukan klaim 72 jam lengkap. Coverage memperlihatkan interval count dan valid first/last.
- Batas resmi 60 request/menit/IP; collector aplikasi memakai minimum 1,1 detik/host secara persisten dalam DB. IP yang dipakai aplikasi lain juga harus diperhitungkan operator.
- Attribution **BMKG — Badan Meteorologi, Klimatologi, dan Geofisika** wajib ditampilkan. Jangan menyebut konten sebagai data milik aplikasi.

## Google News RSS / discovery rantai pasok

- Feed query karet: https://news.google.com/rss/search (parameter dibuat adapter).
- Terms: https://policies.google.com/terms
- Query tetap mengandung `natural rubber` / `karet alam` / `bokar`, kata tambahan terkait supply/exports/production/shipping/floods, jendela 7 hari. Ini membantu discovery, **tidak memverifikasi relevansi atau kelengkapan**.
- Yang disimpan terstruktur: metadata judul, publisher yang dilaporkan feed, timestamp bila tersedia, GUID/link, query, dan penanda belum direview. Raw response feed tetap utuh. Aplikasi tidak mengunjungi atau menyalin halaman artikel penerbit.
- Google News sering memberi URL redirect/aggregator; jangan menyebutnya URL publisher canonical yang sudah diverifikasi. Belum ada entity/event extraction yang membuktikan hubungan ke pemasok atau kontrak perusahaan.
- Seluruh run RSS sengaja berstatus **partial / terbatas** untuk menekankan sifat discovery dan cakupan nonexhaustive, bukan menyembunyikan kegagalan sebagai sukses penuh.
- Metadata feed dan tautan tidak memberikan lisensi CC atas isi artikel. Copyright publisher tetap berlaku. Pengguna harus membuka sumber dan memeriksa hak sebelum penggunaan lanjut.

## GDELT (opsional; bukan default live terverifikasi)

- Dokumentasi: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Terms/about: https://www.gdeltproject.org/about.html
- DOC API metadata, query natural rubber, 24 jam, maksimum 250 hasil. Minimum jarak request host 6,1 detik. Pemeriksaan live awal mendapat HTTP 429, sehingga bukan salah satu empat sumber default yang dinyatakan berhasil. Private source dapat dicoba dengan status/error/retry yang terlihat, tanpa janji akses.
- BPS, Comtrade, SGX, dan sumber key/licensing lain belum diintegrasikan. Tidak ada kredensial palsu, crawl bypass, isi artikel hasil generatif, atau feed demo yang diberi label sebagai data pasar nyata.
