# Asisten Excel lokal — tahap pertama

**Mode: aturan deterministik, bukan model AI/LLM.** Pengguna memilih memulai tanpa AI eksternal. Tidak ada API model, pelatihan otomatis, atau pengiriman isi unggahan ke penyedia AI. Pada preview, pemrosesan berlangsung di server preview; pada instalasi PC, di mesin yang menjalankan aplikasi. Kolektor publik tetap berjalan seperti sebelumnya dan terpisah dari isi unggahan.

## Cara memakai

1. Pilih **Tambah data → Pemetaan pembelian**, konfirmasi hak unggah, lalu pilih CSV/XLSX terkait karet alam. File disimpan utuh sebelum parsing.
2. Asisten mencari header pada **50 baris awal**, termasuk judul/preambule, baris kosong, dan header teks **satu/dua baris**. Beberapa header bertingkat dapat digabungkan. Lembar dengan struktur pembelian yang lebih dikenali disarankan terlebih dahulu; satu lembar tetap dipilih secara eksplisit untuk publikasi.
3. Periksa **Baris awal header** dan **Jumlah baris header**. Koreksi dengan **Terapkan header** jika perlu. Mengubah pilihan preview tidak memublikasikan/mengubah observasi atau file asli.
4. Baca **Alasan saran & batas pembacaan**. Saran kolom berdasarkan alias yang terdaftar, atau pola dalam workspace yang pernah Anda setujui. Field tidak dikenal harus dipetakan sendiri; kecocokan ganda tidak dipilih diam-diam.
5. **Gunakan saran format** bila sesuai sumber. Indikasi tanggal/angka yang cukup jelas hanya merupakan usulan dari sampel. Tanggal ambigu, skala KKK, mata uang, unit dan basis berat tidak ditebak otomatis.
6. Pilih **Periksa sampel**. Maksimum **50 baris** diperiksa tanpa publikasi. Hasil menyebut jumlah yang diperiksa dan nomor baris sumber. Ini bukan jaminan seluruh file valid.
7. Periksa semua aturan, konfirmasi lingkup karet alam, lalu **Validasi & publikasikan**. Semua baris pada lembar pilihan divalidasi; yang bermasalah ditahan. Mengedit aturan menghapus hasil pemeriksaan lama dan mengharuskan konfirmasi kembali.
8. Setelah terdapat baris valid, Anda boleh menekan **Ingat pemetaan ini**. Tanpa tombol tersebut, tidak ada pola yang dipelajari/disimpan otomatis.

## Ingatan koreksi

- Hanya hubungan **header → field** dan opsi pembacaan yang disetujui disimpan, bukan salinan nilai sel, bobot model, atau data latihan AI.
- Pola dipisahkan menurut pemilik token workspace, maksimal **50 pola/workspace**. Struktur dikenali dari fingerprint label header, bukan nama file.
- Urutan kolom boleh berubah: pemetaan dikembalikan berdasarkan label, bukan indeks lama. Header duplikat/kosong/terlalu panjang tidak boleh menjadi pola agar tidak salah cocok.
- Pada file berikutnya dengan header cocok, field dapat diusulkan dari pola tersebut. **Aturan default lama belum diterapkan otomatis**; pengguna harus memilih **Gunakan aturan baca tersimpan** dan tetap mengonfirmasi publikasi.
- **Lupakan pola** menghapus ingatan tanpa mengubah raw atau observasi. Menghapus versi sumber lewat penghapusan dokumen juga menghapus pola yang masih merujuk versi itu.
- Kemiripan nama pemasok tidak otomatis menyatukan identitas. Mata uang, unit, grade, basis berat dan periode tidak digabungkan hanya demi menghasilkan satu angka.

## Bukti dan kompatibilitas

- Byte asli, checksum, versi, dan penerimaan tetap dipertahankan.
- `row_no`/`line_end` mempertahankan posisi fisik sumber, termasuk CSV dengan sel multiline. Pemetaan menyimpan snapshot label kolom per revisi sehingga mengganti header tidak mengubah label bukti revisi lama.
- Parser baru: `tabular-v2-local-assistant`. Versi/pemetaan lama tetap bisa ditelusuri; tidak dimigrasi diam-diam atau diterbitkan ulang otomatis.
- Tabel tambahan `excel_templates` dibuat secara non-destruktif saat startup. Migrator menyertakannya bila ada; sumber lama yang belum memiliki tabel ini tetap ditangani. Pengujian PostgreSQL historis bukan klaim bahwa perubahan ini sudah diuji ulang di PostgreSQL nyata.

## Batas yang tetap berlaku

- Alur normalisasi ini untuk **pembelian karet**, bukan mesin pemahaman semua jenis laporan. Stok, produksi, mutu dan laporan lainnya dapat tetap menjadi arsip raw; logika analisis khususnya belum ditambahkan.
- Tidak ada chat bahasa alami, ekstraksi semantik LLM, prediksi, atau publikasi otomatis. Tidak ada klaim akurasi 100% pada format Excel arbitrer.
- Header di luar 50 baris pertama, crosstab kompleks, lebih dari dua lapis header, banyak tabel pada satu sheet, struktur tak dikenal, atau workbook terenkripsi membutuhkan penanganan/ekspor tambahan. Baris total/footer yang tidak sesuai aturan dapat ditahan, bukan dihapus diam-diam.
- Formula **tidak dihitung ulang**. Hanya nilai cache yang dibaca; cache kosong memerlukan review. Macro ditolak pada jalur pemetaan.
- Batas tabular: 10 MB/file, 10.000 baris data total, 64 kolom, 10 sheet terlihat, 4.096 karakter/sel; rentang sheet dan ukuran dekompresi juga dibatasi. Raw yang sudah diterima tetap ada jika parsing gagal. File melebihi batas penerimaan ditolak, bukan diterima sebagian.
- Saran format dari sampel dapat tidak mewakili semua baris. Pengguna tetap perlu memastikan definisi bisnis dan meninjau hasil seluruh validasi.
- Token browser bukan login/SSO/backup produksi. Jangan unggah informasi sensitif ke preview.

## API

Semua endpoint memerlukan `X-Workspace-Token`; pembacaan mengikuti scope dokumen, perubahan pola hanya untuk pemilik privat.

- `GET /api/versions/{id}/preview?sheet=...&header_row=4&header_depth=2`: preview plus `assistant` (alasan, konflik, header, petunjuk format, pola yang cocok). Opsi header tidak wajib.
- `POST /api/versions/{id}/mapping/check`: body pemetaan seperti publikasi, tetapi `scope_confirmed` boleh false. Tidak menulis observasi/mapping/template; maksimum 50 baris. Hasil `published=false`, `full_validation=false`.
- `POST /api/versions/{id}/mapping`: tetap perlu `scope_confirmed=true`; tambahan `header_row` dan `header_depth` bersifat opsional untuk kompatibilitas.
- `POST /api/versions/{id}/mapping/remember` dengan `{"revision":1}`: hanya setelah revisi validasi selesai dan ada baris valid. Persetujuan eksplisit menyimpan/memperbarui satu pola yang cocok.
- `DELETE /api/excel-templates/{template_id}`: lupakan pola milik workspace itu saja.

## Verifikasi aktual

- **131 tes backend lulus, 1 dilewati**, satu deprecation warning Starlette/httpx pada Linux/SQLite. Termasuk **22 tes baru** untuk judul/blank/header dua baris, pemilihan sheet, CSV multiline/delimiter, konflik dan ambiguitas, dry-run read-only, header override/bukti lama, ingatan/kolom diurut ulang/ownership/forget/cascade/reopen, formula dan parameter invalid.
- Satu tes tambahan memastikan packager menolak membuat ZIP tanpa flag konfirmasi rilis eksplisit.
- **14 tes unit geometri galaksi lulus**, build TypeScript/Vite lulus.
- **12 pemeriksaan browser Asisten Excel lulus**, **0 JavaScript page errors**, modal cocok pada 390/768/1440 px. Memakai workbook sintetis, bukan klaim sudah diuji terhadap file bisnis pengguna yang belum diberikan.
- Regresi browser galaksi **16 pemeriksaan lulus**, 0 JavaScript page errors.
- Raw XLSX byte-identik dan pointer baris bukti diperiksa. Dokumen/pola QA privat dibersihkan; data pengguna dan sumber publik tidak dihapus.
- SQLite integrity `ok`, 0 pelanggaran foreign key. Bukti browser: [EXCEL_ASSISTANT_VERIFICATION.json](EXCEL_ASSISTANT_VERIFICATION.json).
- Belum diuji langsung melalui Windows CMD atau pada PostgreSQL nyata untuk pembaruan ini. Tidak membuat ZIP; pengembangan dilanjutkan langsung pada workspace/preview sesuai permintaan pengguna.

Pengembang dapat mengulang:

```bash
python -m pytest -q
npm test --prefix frontend
npm run build --prefix frontend
# Dengan Playwright/Chromium QA opsional, server sudah berjalan:
python scripts/verify_excel_assistant.py --output-dir .cache/excel-qa
```
