# Rubber Intelligence — MVP karet alam

**Intake → breakdown → klasifikasi → review**, raw/provenance tetap utuh, kolektor eksternal otomatis, dan galaksi berbukti. Source ini mencakup frontend, backend Python, konfigurasi Cloudflare, serta launcher Windows 11.

> **MVP lengkap memerlukan backend Python dengan disk persisten.** Cloudflare pada konfigurasi ini melayani frontend dan meneruskan API; bukan menjalankan Uvicorn/SQLite/kolektor Python di runtime Workers. URL backend produksi belum diisi dan tidak ada layanan cloud berbayar yang dibuat oleh paket ini.

## 1. Dari ZIP ke GitHub

1. **Ekstrak ZIP terlebih dahulu.** Buka folder `rubber-intelligence` hasil ekstrak.
2. Buat/pilih repository GitHub Anda; repository privat disarankan.
3. Upload **isi folder tersebut** ke root repository, atau push melalui Git/Git client. Jangan hanya mengunggah file `.zip`—GitHub/Cloudflare tidak mengekstraknya otomatis.
4. Pastikan file `wrangler.jsonc`, `package.json`, `package-lock.json`, dan folder `app/` berada pada level yang sama:

```text
<root repository>/
├── README.md
├── wrangler.jsonc
├── package.json
├── package-lock.json
├── .node-version
├── .gitignore
├── render.yaml                 # contoh backend persisten opsional/berbayar
├── DEPLOY_CLOUDFLARE.md
├── start.bat
├── deployment/                 # gateway Worker + pengujian/verifikasi
└── app/
    ├── backend/                # FastAPI, intake, klasifikasi, raw, collectors
    ├── frontend/               # source + build siap pakai di dist/
    ├── Dockerfile
    ├── compose.yaml
    ├── requirements-tested.txt
    ├── docs/
    ├── tests/
    └── scripts/
```

Sertakan dotfiles seperti `.gitignore` dan `.node-version`. Jika UI upload browser membatasi jumlah file, upload bertahap atau gunakan Git client. Jangan memasukkan `runtime`, `.env`, `.dev.vars`, `.venv`, atau `node_modules` Anda.

Jika terlanjur upload folder `rubber-intelligence/` sebagai subfolder repository, pilih folder itu sebagai root directory Cloudflare. **Folder yang dipilih harus memuat `wrangler.jsonc` dan `package.json`.**

## 2. Deploy backend Python

Backend harus berjalan dengan storage persisten, bukan filesystem sementara. Gunakan hosting Python/Docker Anda sendiri atau contoh **opsional** `render.yaml`:

- Dockerfile `app/Dockerfile`; build context `app`.
- Satu instance/proses Uvicorn; health check `/api/health`.
- Disk persisten `/data` dan `RUBBER_DATA_DIR=/data` untuk database **dan** raw.
- `render.yaml` akan membuat service/disk **berbayar hanya bila Anda menyetujuinya di akun provider**. Periksa biaya/kapasitas/region sebelum klik deploy. File tersebut tidak membuat resource dengan sendirinya.
- Ambil URL HTTPS backend aktual setelah sehat. Jangan gunakan URL preview Arena, localhost, atau URL frontend Worker sebagai backend produksi.

Langkah, batas SQLite/single-node, permission volume dan alternatif VPS: [DEPLOY_CLOUDFLARE.md](DEPLOY_CLOUDFLARE.md).

## 3. Deploy frontend + gateway di Cloudflare Workers

| Pengaturan | Nilai |
|---|---|
| Root directory | Root yang memuat `wrangler.jsonc` |
| Build command dashboard | Kosong; custom build ada di Wrangler |
| Deploy command | `npx wrangler deploy` |
| Build variable | `NODE_VERSION=22` |
| Worker runtime secret | `BACKEND_ORIGIN` = origin HTTPS backend Python milik Anda |

Cocokkan `name` di `wrangler.jsonc` dengan nama Worker/project Anda. Custom build memasang dependensi frontend lalu membuat `app/frontend/dist`; folder `dist` tidak perlu dikomit karena akan dibangun ulang di CI.

**`BACKEND_ORIGIN` harus tersedia saat runtime Worker, bukan hanya environment build.** Atur di Settings → Variables and Secrets Worker. Tidak perlu memasukkan password/token pada URL. Tanpa binding backend yang benar, API sengaja mengembalikan **503**, bukan pura-pura berhasil dengan HTML SPA.

Source, build dan dry-run sudah diuji lokal; **ZIP ini bukan bukti backend/Cloudflare Anda sudah live**. Backend tetap membutuhkan internet dan proses yang berjalan untuk kolektor otomatis.

## 4. Verifikasi setelah live

Dengan Node 22+ pada mesin pengembangan/CI:

```bash
npm ci
npm run verify:deployment -- --url https://HOST_WORKER_ANDA --intake
```

Ganti host dengan URL Anda. Flag `--intake` mengunggah CSV sintetis menggunakan token QA baru, memeriksa breakdown/review/raw/ownership, lalu menghapus dokumen QA miliknya. Tidak mencetak token. Tanpa flag tersebut, hanya frontend/health/config yang dicek. [Panduan lengkap](DEPLOY_CLOUDFLARE.md).

## Windows 11 lokal

Pasang Python **3.13 64-bit**, ekstrak seluruh ZIP, kemudian klik dua kali **`start.bat`**. Build frontend sudah disertakan sehingga **Node.js tidak dibutuhkan untuk menjalankan paket Windows lokal**. Instalasi Python dependencies pertama memerlukan internet. Jangan menjalankan launcher langsung dari dalam ZIP. Eksekusi Windows CMD/wheels belum diuji secara native di lingkungan ini. [WINDOWS_11.md](WINDOWS_11.md).

## Isi dan privasi paket

- Source lengkap, SQL/migrasi, template CSV, test, dokumentasi, bukti uji lokal, frontend hasil build, launcher, dan konfigurasi deploy.
- **Tidak menyertakan database/raw pengguna, `.env` nyata, `.dev.vars` nyata, credential/token nyata, dependency directories atau cache.** File `.env.example` / `.dev.vars.example` hanyalah contoh konfigurasi tanpa credential nyata.
- Data yang sudah ada di workspace tidak dihapus atau dipindahkan. Instalasi/hosting baru memulai runtime terpisah; migrasi data memerlukan backup/transfer privat, bukan commit ke GitHub.
- Token workspace berbasis browser/origin bukan SSO produksi. Untuk data sensitif, tambahkan kontrol akses, proteksi origin, backup dan monitoring yang sesuai. Bukan sertifikasi keamanan produksi, HA atau SLA.

Mulai fitur: [START_HERE.md](START_HERE.md) · [Panduan aplikasi](app/README.md) · [MVP breakdown](app/docs/INTAKE_BREAKDOWN.md) · [Sumber dan atribusi](app/docs/SOURCES.md).
