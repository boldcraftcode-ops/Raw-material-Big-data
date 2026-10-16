# Jalankan di Windows 11

## Tiga langkah

1. Pasang **Python 3.13 64-bit** dari https://www.python.org/downloads/windows/. Pada installer, aktifkan **Add python.exe to PATH** dan Python Launcher. Tidak perlu Node.js, Docker, PostgreSQL atau WSL untuk mode lokal default.
2. **Ekstrak seluruh ZIP** ke folder lokal yang dapat ditulis, misalnya `C:\Karet` atau folder `Karet` di Documents. Jangan menjalankan langsung dari dalam ZIP. Sebaiknya hindari folder bersarang terlalu panjang, network drive, atau folder yang sedang disinkronkan saat database aktif.
3. Klik dua kali **`start.bat`** di folder utama hasil ekstraksi. Browser dibuka otomatis setelah API siap: **http://127.0.0.1:8000**.

`start.bat` juga dapat diletakkan di dalam folder `app`; isinya mandiri, tidak memerlukan file helper atau PowerShell. File ini bukan installer Python: jika Python belum tersedia, ia menampilkan petunjuk lalu berhenti.

## Yang dilakukan launcher

- Memeriksa Python 3.13 64-bit dan membuat `app\.venv` bila belum ada.
- Memasang/memeriksa dependensi dari `requirements-tested.txt`. **Instalasi pertama membutuhkan internet**; wheel Windows dan dependensi platform dipilih pip.
- Memakai frontend hasil build yang sudah disertakan, tanpa Node/npm.
- Menjalankan satu server pada **127.0.0.1**, hanya untuk PC ini—bukan membuka aplikasi ke LAN/internet.
- Menunggu health API siap sebelum membuka browser. Jika aplikasi sudah berjalan, membuka aplikasi yang sama tanpa membuat server ganda. Jika port dipakai program lain, tidak mematikan proses tersebut.
- Membaca `.env` opsional sebagai nilai literal, bukan mengeksekusi perintah shell. Mendukung komentar baris, kutip sederhana, dan BOM UTF-8. Tidak mendukung ekspansi `${VAR}`/`$(command)`; environment Windows yang sudah diset lebih diprioritaskan.

Biarkan jendela terminal tetap terbuka. **Menutup tab browser tidak menghentikan server/kolektor.** Tekan **Ctrl+C** di terminal untuk menghentikan server. PC/server yang mati tidak menjalankan jadwal koleksi.

## Data dan koneksi

Mode default memakai SQLite + filesystem di **`app\runtime`**. Jangan hapus folder tersebut untuk memperbaiki masalah instalasi. Buat backup database dan raw secara konsisten saat server berhenti; `.venv` hanya dependensi dan bukan tempat data.

ZIP tidak membawa database/raw privat atau token browser dari preview. Instalasi lokal memulai workspace sendiri dan akan mengambil sumber publik dengan internet; koleksi pertama FAOSTAT memerlukan download bulk dan waktu pemrosesan. Token workspace tersimpan pada browser/origin, jadi gunakan alamat browser yang sama agar scope data privat tidak tampak berpindah.

## Galaksi bergerak dan pembaruan paket

Paket `rubber-intelligence-windows-11-galaxy.zip` menyertakan build dengan node melayang acak-terkendali, relasi yang mengikuti node, serta **Jeda gerak / Gerakkan**. Node berhenti saat disorot/dipilih. Animasi mengikuti pengaturan kurangi gerakan perangkat/browser; bila dibatasi, peta dan bukti tetap dapat digunakan. Detail: [panduan galaksi](app/docs/GALAXY_MOTION.md).

Untuk memperbarui instalasi Windows sebelumnya tanpa memulai workspace baru:

1. Hentikan server lama dengan Ctrl+C dan tunggu sampai keluar. Cadangkan folder aplikasi lama, terutama **`app\\runtime`** dan `.env` bila ada.
2. Ekstrak paket baru ke folder sementara. Salin **isi folder `rubber-intelligence`** dari paket baru ke folder aplikasi lama, gabungkan folder dan ganti file program yang sama. ZIP tidak membawa `runtime`, `.env`, atau `.venv`; jangan menghapus yang lama. Jangan membuat folder `app` bersarang di dalam `app`.
3. Jalankan `start.bat` dari folder aplikasi lama yang sudah diperbarui. Gunakan alamat browser, port, dan profil browser yang sama. Muat ulang dengan **Ctrl+F5** jika tampilan masih lama.

Menjalankan hasil ekstrak di folder yang berbeda memakai `app\\runtime` berbeda, sehingga data lama tidak otomatis terlihat. Jangan hapus runtime lama untuk mengatasi ini. Menjeda **animasi** tidak menjeda koleksi eksternal.

## Jika terjadi masalah

- **Python tidak ditemukan:** pastikan versi **3.13 64-bit**, lalu jalankan `start.bat` lagi. Launcher mencoba `py -3.13` dan `python`.
- **Folder .venv tidak cocok/rusak:** tutup server, rename/hapus **hanya `app\.venv`**, lalu jalankan ulang. Jangan menghapus `app\runtime`.
- **Pip gagal:** periksa internet/proxy dan pesan error. Tidak perlu menonaktifkan antivirus. Data runtime tidak dihapus oleh launcher.
- **Port 8000 dipakai aplikasi lain:** tutup program tersebut, atau dari Command Prompt jalankan `start.bat --port 8001`. Gunakan origin/port yang konsisten untuk token browser.
- **Browser tidak terbuka:** buka manual alamat yang ditampilkan terminal.
- **Frontend hilang:** gunakan ZIP Windows lengkap yang menyertakan `app\frontend\dist`.

## Batas verifikasi

Launcher ditujukan untuk Windows 11, tetapi lingkungan pengembangan ini **Linux, bukan mesin Windows**. Parsing/eksekusi bagian Python launcher, deteksi app/port, konfigurasi, dan regresi backend diuji di Linux; eksekusi batch melalui Windows CMD dan instalasi wheel Windows **belum diuji langsung pada Windows 11**.

Indexer menyertakan path OS Windows yang diperlukan tanpa meneruskan environment kredensial storage/database. Limit memori/CPU berbasis `resource` Linux tidak tersedia di Windows; timeout tetap diterapkan dan keterbatasan dilabeli. Ini bukan sandbox malware penuh. Tetap ikuti batas keamanan/lisensi/operasi pada `app/README.md` dan dokumentasi lainnya.
