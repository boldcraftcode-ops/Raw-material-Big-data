# Memperbaiki deploy Cloudflare untuk MVP lengkap

**16 Oktober 2026.** Pilihan pengguna: MVP lengkap, bukan frontend demo saja.

## Status dan langkah yang masih diperlukan

Konfigurasi/source di workspace sudah diperbaiki dan diuji **secara lokal**. **Belum ada deploy ke akun Cloudflare/hosting pengguna, belum ada URL backend produksi, dan tidak ada layanan berbayar yang dibuat.** Source yang diperbaiki harus Anda commit/push ke repository yang dipakai build cloud.

Arsitektur yang mempertahankan seluruh MVP:

```text
Browser
  └─ Cloudflare Worker
       ├─ frontend React + font/icon lokal (static assets)
       └─ /api/* dan /blueprint → HTTPS backend Python Anda
                                   ├─ FastAPI + worker intake/klasifikasi/review
                                   ├─ SQLite + raw pada disk persisten
                                   └─ kolektor eksternal otomatis
```

Worker ini **bukan port backend ke runtime Workers**. Tidak mengganti Python, SQLite/filesystem atau kolektor menjadi D1/R2/Queues. Tidak perlu mengubah kontrak API dan tidak ada AI eksternal baru.

## 1. Mengapa log Anda gagal

Build menjalankan `npx wrangler deploy` dari root tanpa hasil build/direktori assets. Frontend sebenarnya berada di `app/frontend`, dan `dist` sengaja tidak disimpan di Git.

Perbaikan:
- `package.json` + `package-lock.json` di root agar dependensi deployment terdeteksi; Wrangler dipin ke **4.151.0** (Node **22+**).
- `wrangler.jsonc`: `main=deployment/worker.mjs`, `assets.directory=app/frontend/dist`, custom build `npm run build`.
- Build menginstal dependensi frontend dari lockfile lalu menjalankan TypeScript/Vite, **sebelum** Wrangler memproses assets.
- API dijalankan oleh Worker lebih dahulu, bukan jatuh ke `index.html` SPA. Konfigurasi assets/binding/routing ini mengikuti dokumentasi Cloudflare. [1](https://developers.cloudflare.com/workers/static-assets/binding/)
- Custom build dijalankan oleh Wrangler ketika `deploy`/`dev`, sehingga perintah deploy semula tetap dapat digunakan. [2](https://developers.cloudflare.com/workers/wrangler/custom-builds/)

## 2. Jalankan backend Python dengan penyimpanan persisten

### Jika sudah memiliki backend

Gunakan **origin HTTPS server yang Anda kendalikan**. `GET /api/health` pada server itu harus mengembalikan JSON `status:ok`, bukan halaman frontend/login.

Backend harus tetap menjalankan satu proses Uvicorn + worker bawaan, mempunyai internet untuk kolektor, dan menyimpan **seluruh `RUBBER_DATA_DIR`** pada storage persisten. Jangan hanya menyimpan database tetapi membuang `raw/` saat restart.

**Jangan gunakan `localhost`, URL Arena preview, atau URL Worker itu sendiri sebagai backend produksi.** Proxy meneruskan data unggahan dan token workspace ke origin ini, sehingga jangan memilih server yang tidak Anda kendalikan.

### Jika belum memiliki backend: contoh Render (opsional)

`render.yaml` adalah contoh Blueprint untuk backend Docker yang sudah ada, bukan kewajiban memakai provider ini. **Pembuatan service dan disk berbayar memerlukan persetujuan Anda di akun sendiri**; mempersiapkan file YAML ini tidak membuat resource atau mengenakan biaya.

1. Push source ke repository privat/berizin. Buat Blueprint dari `render.yaml` di akun Render Anda.
2. Periksa dan setujui biaya/paket/region terlebih dahulu. Template menggunakan satu instance, plan `0.5c-512mb`, region `singapore`, dan disk **5 GB**. Sesuaikan resource berdasarkan beban; 512 MB bukan jaminan cukup untuk semua XLSX/collectors. Jika terjadi OOM, ukur/tingkatkan RAM; jangan menghapus batas keamanan parser.
3. Dockerfile: `app/Dockerfile`; build context: `app`. Keduanya relatif **root repository**. Template tidak memakai `rootDir` agar tidak rancu soal path. Spesifikasi resmi mendefinisikan path Docker tersebut relatif root repo. [1](https://render.com/docs/blueprint-spec)
4. Disk harus terpasang di `/data`; `RUBBER_DATA_DIR=/data`. SQLite, raw, dan cache/runtime tetap di jalur itu. Aplikasi container memakai UID 10001; pastikan volume dapat ditulis UID tersebut. Jika deployment melaporkan permission denied, perbaiki ownership/mount, bukan membuat raw publik.
5. Health check `/api/health`. Jangan menambahkan proses cron/background worker kedua yang berebut database/disk. Kolektor sudah berjalan pada lifespan backend.
6. Tunggu service sehat. Ambil URL HTTPS aktual dari Dashboard, lalu periksa `/api/health` pada URL itu.

Render menyediakan disk persisten untuk service berbayar; filesystem default ephemeral. Disk terikat satu instance dan data hanya persisten di mount path. Redeploy dengan disk dapat memiliki jeda layanan—ini bukan HA atau zero-downtime. [4](https://render.com/docs/disks)

**Batas validasi:** YAML lolos JSON Schema resmi dan path Docker/context diperiksa. Image Docker dan deployment Render/permission disk **belum dieksekusi** di lingkungan ini karena Docker/account deployment tidak tersedia. Tidak ada resource Render yang dibuat.

Alternatif: hosting Python/Docker/VPS Anda sendiri. `app/Dockerfile` sudah membangun frontend dalam image dan menjalankan API pada `0.0.0.0:$PORT`. Di VPS, gunakan volume persisten `/data`, kepemilikan UID 10001, HTTPS/reverse proxy, backup dan monitoring. Compose PostgreSQL yang sudah ada tetap tersedia di `app/compose.yaml`; jangan mengganti SQLite ke PostgreSQL tanpa migrasi offline.

## 3. Pengaturan Cloudflare Workers Builds

| Pengaturan | Nilai |
|---|---|
| Root directory | Folder yang memuat `wrangler.jsonc`, `package.json`, `app/`, dan `deployment/`—**bukan** `app/frontend` |
| Build command dashboard | Boleh kosong; custom build sudah ada di `wrangler.jsonc` |
| Deploy command | `npx wrangler deploy` (atau `npm run deploy`) |
| Build variable | `NODE_VERSION=22` |
| Worker name | Cocokkan project Anda dengan `name` di `wrangler.jsonc`; ubah nama di file bila project Anda bernama lain |
| Runtime secret/binding | `BACKEND_ORIGIN` = origin HTTPS aktual backend Python Anda |

Jika repository Anda membungkus project ini dalam folder `rubber-intelligence/`, gunakan folder tersebut sebagai root directory. Jika `app/` langsung berada di root repository, gunakan root repository.

**Penting: build variables berbeda dari runtime bindings.** Menaruh URL hanya dalam environment build tidak membuat `env.BACKEND_ORIGIN` tersedia saat Worker melayani request. Cloudflare mendokumentasikan pemisahan build-time dan runtime ini. [3](https://developers.cloudflare.com/workers/static-assets/migration-guides/migrate-from-pages/)

Atur `BACKEND_ORIGIN` sebagai **Worker runtime secret** melalui Dashboard → Worker → Settings → Variables and Secrets. URL tidak perlu berisi password/token. Mode secret dipakai agar binding tidak perlu dikomit ke source. Jangan mengisi `ALLOW_LOCAL_BACKEND` pada produksi.

Bila memakai CLI yang sudah login ke akun Anda:

```bash
# Jalankan dari folder yang memuat wrangler.jsonc, menggunakan Node 22+.
npm ci
npx wrangler deploy
npx wrangler secret put BACKEND_ORIGIN
# Paste hanya origin HTTPS backend ANDA ketika diminta.
```

Deploy script sebelum binding ada hanya menampilkan frontend; API secara sengaja mengembalikan `503` sampai backend dikonfigurasi. Setelah binding benar, jalankan verifikasi di langkah 4. **Ini bukan klaim MVP sudah berfungsi hanya karena deploy assets sukses.** Jangan bagikan API token Cloudflare atau token workspace di chat/log.

## 4. Verifikasi MVP, bukan hanya halaman HTML

Setelah backend + Worker sudah live, jalankan dengan URL aktual milik Anda:

```bash
npm run verify:deployment -- --url https://WORKER_HOST_ANDA --intake
```

Ganti `WORKER_HOST_ANDA` dengan host Anda—tidak ada URL produksi yang di-hardcode. Skrip:
- memeriksa HTML dan JS/CSS;
- memastikan `/api/health` dan `/api/config` benar-benar JSON API Python;
- membuat workspace QA privat baru dengan token acak (tidak dicetak), mengunggah **CSV sintetis**, menunggu job nyata selesai;
- memeriksa breakdown/kategori inventory, raw identik dan SHA-256;
- menyimpan review terikat hash tanpa publikasi transaksi;
- memastikan token workspace lain ditolak;
- menghapus **hanya dokumen sintetis miliknya sendiri**.

Tanpa `--intake`, hanya frontend/health/config yang diperiksa. Dengan flag itu, skrip memang mengirim data uji kecil dan melakukan cleanup. Jangan menganggap hasil check lokal sebagai bukti Cloudflare/Render sudah live.

### Arti kegagalan umum

| Gejala | Makna / tindakan |
|---|---|
| Directory static files tidak terdeteksi | Root/config/build belum sesuai. Pastikan source perbaikan sudah di-push; custom build menghasilkan `app/frontend/dist`. |
| CLI meminta Node 22 | Atur `NODE_VERSION=22`; gunakan Node 22+ untuk CLI lokal. |
| `/api/health` mengembalikan 503 | `BACKEND_ORIGIN` runtime kosong/tidak valid/loopback, atau menunjuk Worker yang sama. |
| `/api/health` mengembalikan 502 | Origin salah/mati, HTML/login bukan API, atau redirect. Gunakan origin HTTPS backend langsung. |
| Data hilang setelah restart | Periksa mount persisten dan `RUBBER_DATA_DIR`. Jangan menjalankan database/raw pada filesystem sementara. |
| Health sehat tetapi intake pending | Periksa status job/worker, kapasitas RAM/disk dan log backend. Jangan mengatasi dengan publish otomatis. |

## Keamanan dan data lama

- API gateway hanya untuk `/api`, `/api/*`, `/blueprint`. Target hanya dari binding operator, bukan query/header pengunjung. Tidak ada open proxy.
- Multipart boundary, body unggahan, raw byte download dan header workspace/idempotency dipertahankan. Cookie/Authorization browser tidak dikirim ke server origin.
- API respons `no-store`; workspace lain tetap membutuhkan token yang benar. Redirect tidak diikuti, error API tidak diganti HTML SPA. JSON error 503/502 tidak mengekspos URL/kredensial/payload internal.
- CSP/nosniff/referrer policy untuk static assets ada di `app/frontend/public/_headers`; tidak melonggarkan CSP aplikasi.
- `runtime`, `.env`, `.dev.vars`, dependency directories, dan raw pengguna tidak boleh dikomit. `.gitignore` tidak menghapus file yang terlanjur tracked; periksa repository sebelum push.
- **Data preview tidak otomatis dipindahkan ke hosting baru.** Runtime baru mulai terpisah; kolektor mengisi datanya sendiri. Migrasi database/raw lama memerlukan backup/transfer privat yang konsisten, bukan memasukkannya ke Git. Data workspace yang ada tidak dihapus atau dipindahkan oleh perbaikan ini.
- Origin backend tetap memakai token kapabilitas yang sama dan dapat diakses langsung. Melindungi frontend dengan Access saja tidak otomatis melindungi origin; akses produksi memerlukan proteksi origin, rate limiting dan login yang sesuai.
- Token browser terikat origin/localStorage. Domain baru membuat token workspace baru; bukan login/SSO produksi. Jangan menyalin token melalui URL atau log. Pisahkan kontrol akses/backup/retensi sebelum data sensitif dipakai.
- Cloudflare tidak menjalankan kolektor Python di frontend Worker ini. Kolektor memerlukan backend yang tetap berjalan dan internet. Tidak ada managed hosting 24×7, backup terkelola baru, atau SLA yang dibuat otomatis.
- **ZIP kini disiapkan atas permintaan eksplisit pengguna**, berisi source dan frontend build, tanpa runtime/credential pribadi. Ekstrak sebelum upload isi folder ke GitHub. Windows `start.bat`, raw retention, pemetaan pembelian opsional dan fitur MVP tetap dipertahankan.

## Hasil uji lokal aktual

- Node **22.23.3** + Wrangler **4.151.0**; `wrangler deploy --dry-run` lulus, menemukan **15 file assets**; tidak mengunggah ke akun Cloudflare.
- **33 unit tests gateway** lulus: routing, origin validation, body/range download, no-store, token forwarding, redirection/error handling.
- **6 check integrasi lokal** lewat runtime Wrangler/Workerd sungguhan → backend Python, termasuk upload → breakdown → review → raw bytes → ownership; cleanup sukses.
- **174 tes backend** lulus, 1 optional PostgreSQL test skipped, 1 deprecation warning Starlette/httpx. **14 unit gerak frontend** dan build TypeScript/Vite lulus.
- `render.yaml` lolos JSON Schema resmi; Dockerfile/context dan mount path diperiksa. Tidak ada Docker build atau cloud deploy aktual.

Bukti: `deployment/LOCAL_GATEWAY_VERIFICATION.json` dan `deployment/DEPLOYMENT_VERIFICATION.json`. Data pengujian sintetis, bukan data perusahaan pengguna. Ini pemeriksaan deployment lokal, **bukan security audit atau sertifikasi produksi**.

Untuk QA lokal:

```bash
# Terminal 1, backend (Python deps + frontend build harus tersedia)
cd app
bash run.sh

# Terminal 2, dari root project dengan Node 22+
npm ci
cp .dev.vars.example .dev.vars
npm run preview:cloudflare

# Terminal 3
npm run verify:deployment -- --url http://127.0.0.1:8787 --allow-local --intake
```

`.dev.vars` hanya untuk localhost QA, diabaikan Git, dan bukan konfigurasi produksi.
