# Rubber Intelligence · v0.2.0

**Karet alam · raw intake · automatic external collection · evidence-backed galaxy**

Implementasi kedua requirement:
- File/event raw berizin diterima utuh, dicatat dengan checksum, versi, akuisisi, scope dan konteks. Format belum dipahami tetap disimpan sebagai raw.
- World Bank, FAOSTAT, BMKG, dan RSS berita dikoleksi otomatis oleh worker server, dengan jadwal/riwayat/bukti/error/retry nyata. Bukti live dan batas interpretasi ada di dokumentasi.

## Status pengembangan

Paket source + build ini dibuat **atas permintaan eksplisit pengguna** untuk diunggah ke GitHub dan dideploy dengan Cloudflare. Ekstrak ZIP, lalu upload **isi folder** ke root repository—jangan hanya upload file ZIP. [Panduan cepat GitHub/Cloudflare](README.md). Data/runtime/credential pribadi tidak disertakan. ZIP berikutnya tetap hanya dibuat bila diminta.

## MVP pertama: breakdown dan klasifikasi intake

**Tambah data → Intake & klasifikasi** sekarang alur utama. XLSX/CSV/TSV otomatis diurai menjadi lembar, tabel, kolom, dan contoh baris; sistem menyarankan **kategori bisnis + tipe/peran kolom** dengan alasan serta koordinat sumber. Hasil tak jelas tetap campuran/belum terklasifikasi. Koreksi dan review disimpan terpisah, tanpa mengubah raw atau mempublikasikan transaksi.

Buka kembali melalui **Data saya → Pusat data → Breakdown**. Format lain tetap raw/indeks sesuai dukungan; bukan diklaim sudah dipahami. Aturan server lokal, tanpa model/AI eksternal. [Panduan, batas dan hasil uji](app/docs/INTAKE_BREAKDOWN.md).

## Asisten Excel lokal

Pada **Tambah data → Pemetaan pembelian**, asisten berbasis aturan mendeteksi header/preambule dan header dua baris, menjelaskan saran kolom, memeriksa sampel tanpa publikasi, dan menyimpan pola hanya setelah Anda menyetujuinya. **Belum memakai model AI, tidak mengirim unggahan ke layanan AI eksternal.** [Panduan dan batasnya](app/docs/EXCEL_ASSISTANT.md).

## Deployment Cloudflare — MVP lengkap

Jika build menampilkan `Could not detect a directory containing static files`, gunakan konfigurasi root yang baru: `wrangler.jsonc`, `package.json`, lockfile, dan Node 22. Custom build menghasilkan `app/frontend/dist`; Worker meneruskan `/api` ke backend Python, bukan menjalankan Python di runtime Workers.

**Backend HTTPS + storage persisten tetap diperlukan.** Atur `BACKEND_ORIGIN` sebagai runtime secret Worker. `render.yaml` adalah contoh backend berbayar opsional, bukan resource yang sudah dibuat. Tidak ada deploy cloud otomatis atau perpindahan data preview. [Langkah lengkap, biaya/batas, dan verifikasi](DEPLOY_CLOUDFLARE.md).

## Windows 11

Pasang **Python 3.13 64-bit**, ekstrak seluruh paket, lalu klik dua kali **`start.bat`** pada folder utama. Browser dibuka otomatis setelah server siap. Frontend sudah dibundel; **Node.js tidak diperlukan**. Panduan dan batas verifikasi: [WINDOWS_11.md](WINDOWS_11.md).

## Galaksi bergerak

Entitas data melayang acak-terkendali; garis relasi ikut bergerak dan pusat workspace tetap diam. Gunakan **Jeda gerak / Gerakkan**. Gerak hanya visual, **bukan perubahan data**; node berhenti saat disorot/dipilih dan pengaturan reduced motion dihormati. [Panduan dan hasil uji galaksi](app/docs/GALAXY_MOTION.md).

## Jalankan lokal

Python 3.13, Node 20/22 + npm:

```bash
cd app
bash prepare.sh
bash run.sh
# Buka http://localhost:8000
```

Paket ini menyertakan frontend hasil build. Gunakan `SKIP_FRONTEND_BUILD=1 bash prepare.sh` untuk menyiapkan Python tanpa Node sebelum `bash run.sh`. Build/deploy Cloudflare tetap memakai Node 22+ pada CI dan akan membangun frontend ulang dari source.

Default pengembangan: SQLite + filesystem privat. PostgreSQL dan private S3-compatible dapat dikonfigurasi; tidak otomatis memigrasi workspace lama atau membuat bucket/cloud hosting. Internet dibutuhkan oleh sumber eksternal. Server harus tetap berjalan untuk jadwal koleksi; menutup tab tidak menghentikannya.

- [Panduan aplikasi, fitur dan batas](app/README.md)
- [Catatan rilis & hasil uji](app/RELEASE_NOTES.md)
- [Verifikasi requirement](app/docs/VERIFICATION.md)
- [API intake/sumber/bukti](app/docs/API.md)
- [Operasi, PostgreSQL/S3, migrasi offline & backup](app/docs/OPERATIONS.md)
- [Sumber, atribusi dan hak penggunaan](app/docs/SOURCES.md)
- [Blueprint awal](blueprint.html)

Runtime/raw privat, database pengguna, dependency directories dan credential/token **tidak disertakan**. Instalasi baru memulai koleksi sendiri; verifikasi live pada dokumentasi bukan data simulasi yang otomatis diimpor. Jangan unggah informasi sensitif ke mode preview. Fondasi single-node ini bukan klaim HA, SSO produksi, throughput petabyte, exhaustive crawling atau SLA.
