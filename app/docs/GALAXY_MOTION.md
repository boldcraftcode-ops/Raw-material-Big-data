# Galaksi hidup — gerak entitas data

Pembaruan presentasi untuk Rubber Intelligence v0.2.0. Tidak mengubah API, nilai observasi, bukti, raw, scheduler, atau database.

## Perilaku

- Entitas yang memang ada pada proyeksi graph bergerak **acak-terkendali dan halus** di sekitar posisi dasarnya. Tidak ada node atau relasi fiktif yang ditambahkan untuk efek animasi.
- Masing-masing ID mempunyai lintasan pseudo-random dan tempo sendiri. Interpolasi halus menggantikan jitter/lompatan posisi. Pusat **Karet alam / workspace** tetap diam sebagai acuan.
- Gerak dibatasi oleh ukuran viewport dan jarak antarnode pada layout awal. Peta padat memperoleh simpangan lebih kecil; hubungan utama tetap terbaca. Ini bukan simulasi fisika, clustering semantik baru, atau jaminan label tidak pernah saling bertumpuk.
- Kurva relasi dan area kliknya selalu memakai koordinat node yang sama, termasuk ketika zoom, pan, atau layar penuh.
- Node berhenti pada pose saat ini ketika disorot pointer, menerima fokus keyboard, atau dipilih. Node lain tetap bergerak. Klik / Enter / Space tetap membuka detail/bukti yang sama seperti sebelumnya.
- Tombol **Jeda gerak / Gerakkan** menghentikan/melanjutkan seluruh galaksi. Preferensi jeda disimpan pada browser jika localStorage tersedia. Menjeda animasi **tidak menghentikan kolektor atau server**.
- **Kurangi gerakan / prefers-reduced-motion** pada perangkat/browser mematikan gerak. Tombol dilabeli “Gerak dibatasi”; tidak memaksa menimpa preferensi aksesibilitas.
- Animasi berhenti ketika dokumen tersembunyi atau panggung galaksi tidak terlihat, dan menahan gerak saat peta sedang digeser. Waktu yang terlewat tidak dikejar dengan lompatan.
- Polling graph mempertahankan jam animasi ID yang masih ada. ID baru mulai dari layout dasar; ID hilang dilepas. Perubahan layout/ukuran/cakupan data sendiri dapat menggeser susunan node.

**Gerak hanya efek visual, bukan perubahan harga, perpindahan barang, aliran transaksi, lokasi geografis, prediksi, atau hubungan sebab-akibat.** Hubungan tetap harus ditelusuri ke arsip sumber. Informasi ini juga tertulis di footer peta.

## Cara melihat

1. Buka aplikasi dan pilih **Galaksi pengetahuan**.
2. Pilih **Data eksternal**, **Simulasi**, atau **Data saya**. Animasi tersedia jika ada entitas selain pusat workspace; instalasi baru menunggu koleksi/unggahan pertama.
3. Jika sebelumnya dijeda, tekan **Gerakkan**. Untuk membaca peta statis, tekan **Jeda gerak**.
4. Sorot/pilih node untuk menahan target, atau tekan Tab lalu Enter/Space untuk membuka detail.
5. Gunakan kontrol zoom/reset dan ikon layar penuh seperti sebelumnya.

Setelah mengganti build, muat ulang browser; **Ctrl+F5** jika tab masih menampilkan tampilan lama. Bila pengaturan perangkat meminta reduced motion, galaksi sengaja tetap statis dan alur data tetap berfungsi.

## Implementasi dan batas performa

- `frontend/src/components/galaxyMotion.ts`: fungsi geometri murni, seeded waypoints, batas simpangan, pemeliharaan clock, serta kurva/transform.
- `frontend/src/components/useGalaxyMotion.ts`: lifecycle requestAnimationFrame, ref SVG, jeda, aksesibilitas dan visibility.
- `Galaxy.tsx`: interaksi, kontrol dan layout d3 yang sudah ada.
- Target sekitar **30 pembaruan geometri/detik**, tanpa render React per frame. Angka nyata bergantung perangkat/browser, bukan jaminan benchmark pada semua PC.
- Batas proyeksi tetap **160 node / 400 relasi**; animasi bukan perluasan kapasitas data. Ingestion dan kolektor tidak diubah.

## Verifikasi pembaruan

Lingkungan pengujian: **Linux, Node 20, CPython 3.13, Chromium melalui Playwright**.

- **14 tes unit geometri lulus**: awal tanpa lompatan, lintasan per-ID, input tidak berubah, bounded/crowd-aware, freeze/resume, refresh/resize/lifecycle ID, kasus kosong/invalid time, dan endpoint kurva.
- **16 pemeriksaan browser lulus**, **0 JavaScript page errors**: node nyata bergerak/pusat diam, koneksi kurva dan area klik, pause/filter/reload/resume, hover/pilih/keyboard, zoom/pan/fullscreen, reduced motion, event dokumen tersembunyi, offscreen, pergantian dataset dan kondisi kosong.
- Responsif tanpa overflow horizontal pada lebar **340, 390, 768, 1024, dan 1440 px**. Geometri relasi tetap terhubung pada semua ukuran tersebut.
- Regresi backend/launcher: **108 lulus, 1 dilewati**, dengan satu deprecation warning Starlette/httpx. PostgreSQL tidak dijalankan ulang untuk perubahan presentasi ini.
- `tsc -b && vite build` lulus. Build siap pakai disertakan ZIP Windows; tidak perlu Node pada PC untuk menjalankannya.
- Laporan browser: [GALAXY_MOTION_VERIFICATION.json](GALAXY_MOTION_VERIFICATION.json). Screenshot adalah contoh tampilan statis, bukan satu-satunya bukti gerak; tes browser membandingkan transform antarwaktu dan endpoint kurva aktual.
- **Windows CMD / wheel Windows tetap belum diuji pada mesin Windows nyata**. Hasil Chromium/Linux bukan klaim verifikasi native Windows 11.

Untuk pengembang (bukan syarat pengguna paket prebuilt):

```bash
cd frontend
npm ci
npm test
npm run build
# Kembali ke app; aplikasi harus sedang berjalan:
cd ..
# Playwright + browser Chromium adalah dependency QA opsional, bukan requirement runtime.
python -m pip install playwright
python -m playwright install chromium
# Linux mungkin memerlukan: python -m playwright install-deps chromium
python scripts/verify_galaxy_motion.py --base-url http://127.0.0.1:8000 --output-dir .cache/galaxy-qa
```

QA memakai browser context baru, tidak menyimpan token workspace, dan tidak mengunggah, menghapus, atau mengonfigurasi sumber. Pemeriksaan kondisi Data saya kosong memerlukan context baru tanpa data privat sebelumnya.
