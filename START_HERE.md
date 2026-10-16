# Rubber Intelligence · v0.2.0

**Karet alam · raw intake · automatic external collection · evidence-backed galaxy**

Implementasi kedua requirement:
- File/event raw berizin diterima utuh, dicatat dengan checksum, versi, akuisisi, scope dan konteks. Format belum dipahami tetap disimpan sebagai raw.
- World Bank, FAOSTAT, BMKG, dan RSS berita dikoleksi otomatis oleh worker server, dengan jadwal/riwayat/bukti/error/retry nyata. Bukti live dan batas interpretasi ada di dokumentasi.

## Status pengembangan

Pengembangan dilanjutkan langsung di workspace/preview. **Jangan membuat ZIP baru kecuali pengguna memintanya secara eksplisit.** Paket ZIP lama telah dihapus atas permintaan pengguna; petunjuk distribusi Windows di bawah tetap disimpan untuk pemakaian nanti.

## MVP pertama: breakdown dan klasifikasi intake

**Tambah data → Intake & klasifikasi** sekarang alur utama. XLSX/CSV/TSV otomatis diurai menjadi lembar, tabel, kolom, dan contoh baris; sistem menyarankan **kategori bisnis + tipe/peran kolom** dengan alasan serta koordinat sumber. Hasil tak jelas tetap campuran/belum terklasifikasi. Koreksi dan review disimpan terpisah, tanpa mengubah raw atau mempublikasikan transaksi.

Buka kembali melalui **Data saya → Pusat data → Breakdown**. Format lain tetap raw/indeks sesuai dukungan; bukan diklaim sudah dipahami. Aturan server lokal, tanpa model/AI eksternal. [Panduan, batas dan hasil uji](app/docs/INTAKE_BREAKDOWN.md).

## Asisten Excel lokal

Pada **Tambah data → Pemetaan pembelian**, asisten berbasis aturan mendeteksi header/preambule dan header dua baris, menjelaskan saran kolom, memeriksa sampel tanpa publikasi, dan menyimpan pola hanya setelah Anda menyetujuinya. **Belum memakai model AI, tidak mengirim unggahan ke layanan AI eksternal.** [Panduan dan batasnya](app/docs/EXCEL_ASSISTANT.md).

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

Source workspace perlu satu kali build frontend. Paket distribusi nanti dapat menyertakan hasil build; jika hasil build sudah tersedia, `SKIP_FRONTEND_BUILD=1 bash prepare.sh` dapat melewati build sebelum `bash run.sh`. Tidak ada ZIP baru yang dibuat saat ini.

Default pengembangan: SQLite + filesystem privat. PostgreSQL dan private S3-compatible dapat dikonfigurasi; tidak otomatis memigrasi workspace lama atau membuat bucket/cloud hosting. Internet dibutuhkan oleh sumber eksternal. Server harus tetap berjalan untuk jadwal koleksi; menutup tab tidak menghentikannya.

- [Panduan aplikasi, fitur dan batas](app/README.md)
- [Catatan rilis & hasil uji](app/RELEASE_NOTES.md)
- [Verifikasi requirement](app/docs/VERIFICATION.md)
- [API intake/sumber/bukti](app/docs/API.md)
- [Operasi, PostgreSQL/S3, migrasi offline & backup](app/docs/OPERATIONS.md)
- [Sumber, atribusi dan hak penggunaan](app/docs/SOURCES.md)
- [Blueprint awal](blueprint.html)

Runtime/raw privat, database pengguna, dependency directories dan credential/token **tidak disertakan**. Instalasi baru memulai koleksi sendiri; verifikasi live pada dokumentasi bukan data simulasi yang otomatis diimpor. Jangan unggah informasi sensitif ke mode preview. Fondasi single-node ini bukan klaim HA, SSO produksi, throughput petabyte, exhaustive crawling atau SLA.
