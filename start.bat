@echo off
rem = r"""
setlocal EnableExtensions DisableDelayedExpansion
title Rubber Intelligence - Windows 11
chcp 65001 >nul
cd /d "%~dp0"
if exist "backend\app.py" goto APP_FOUND
if not exist "app\backend\app.py" goto WRONG_FOLDER
cd /d "app"

:APP_FOUND
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
echo.
echo ==========================================================
echo   Rubber Intelligence - Karet Alam
echo   Aplikasi lokal Windows 11
echo ==========================================================
echo.
if not exist "frontend\dist\index.html" goto MISSING_BUILD
if not exist "requirements-tested.txt" goto WRONG_FOLDER
if exist ".venv\Scripts\python.exe" goto CHECK_VENV
if exist ".venv" goto BAD_VENV

echo [1/3] Mencari Python 3.13 64-bit...
py -3.13 -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,13) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto CREATE_WITH_PY
python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,13) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto CREATE_WITH_PYTHON
goto MISSING_PYTHON

:CREATE_WITH_PY
py -3.13 -m venv ".venv"
if errorlevel 1 goto SETUP_FAILED
goto CHECK_VENV

:CREATE_WITH_PYTHON
python -m venv ".venv"
if errorlevel 1 goto SETUP_FAILED

:CHECK_VENV
".venv\Scripts\python.exe" -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,13) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if errorlevel 1 goto BAD_VENV
echo [2/3] Memeriksa dependensi aplikasi...
echo Instalasi pertama membutuhkan internet. Mohon tunggu.
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-input -r "requirements-tested.txt"
if errorlevel 1 goto INSTALL_FAILED

echo.
echo [3/3] Menjalankan aplikasi dan membuka browser...
echo Biarkan jendela ini terbuka selama aplikasi digunakan.
echo Tekan Ctrl+C untuk menghentikan server.
echo Data lokal berada di folder app\runtime secara default.
echo.
".venv\Scripts\python.exe" -x "%~f0" %*
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" goto RUN_FAILED
exit /b 0

:MISSING_PYTHON
echo.
echo Python 3.13 64-bit belum ditemukan.
echo Pasang Python 3.13 untuk Windows dari situs resminya:
echo https://www.python.org/downloads/windows/
echo Pilih Add python.exe to PATH dan Python Launcher saat instalasi.
echo Setelah instalasi selesai, klik dua kali start.bat lagi.
pause
exit /b 1

:BAD_VENV
echo.
echo Folder .venv tidak cocok atau belum lengkap untuk Windows Python 3.13.
echo Tutup server, lalu rename atau hapus HANYA folder app\.venv.
echo Setelah itu jalankan start.bat lagi. JANGAN hapus app\runtime.
pause
exit /b 1

:WRONG_FOLDER
echo.
echo Folder aplikasi tidak lengkap.
echo Letakkan start.bat di sebelah folder app atau di dalam folder app.
echo Ekstrak seluruh ZIP terlebih dahulu; jangan jalankan dari dalam ZIP.
pause
exit /b 1

:MISSING_BUILD
echo.
echo Frontend hasil build tidak ditemukan.
echo Gunakan paket Windows lengkap yang menyertakan frontend\dist.
echo Node.js tidak diperlukan jika memakai ZIP lengkap tersebut.
pause
exit /b 1

:SETUP_FAILED
echo.
echo Gagal membuat environment Python.
echo Pastikan folder aplikasi dapat ditulis dan Python 3.13 lengkap terpasang.
pause
exit /b 1

:INSTALL_FAILED
echo.
echo Instalasi dependensi gagal. Periksa koneksi internet dan pesan di atas.
echo Data di app\runtime tidak dihapus. Jalankan start.bat lagi untuk mencoba ulang.
pause
exit /b 1

:RUN_FAILED
echo.
echo Server berhenti dengan kesalahan. Periksa pesan di atas.
echo Jika port dipakai aplikasi lain, tutup aplikasi itu atau gunakan:
echo start.bat --port 8001
echo Data lokal tidak dihapus oleh launcher ini.
pause
exit /b 1
"""
# Self-contained Python launcher. The batch header is a raw string when Python
# runs this file with -x; no PowerShell scripts or helper downloads are needed.
import argparse
import json
import os
from pathlib import Path
import re
import socket
import sys
import threading
import time
import urllib.request
import webbrowser


def find_app_root(location):
    here = Path(location).resolve().parent
    for candidate in (here, here / 'app'):
        if (candidate / 'backend' / 'app.py').is_file():
            return candidate
    raise ValueError('Folder aplikasi tidak lengkap; ekstrak seluruh ZIP terlebih dahulu.')


def load_local_env(path):
    """Read plain .env values; never execute shell commands or print secrets."""
    if not path.is_file():
        return
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'Format .env tidak valid pada baris {number}.')
        # Only application/storage settings; do not replace PATH or Python paths.
        if not (key.startswith(('RUBBER_', 'AWS_')) or key == 'PORT'):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if '${' in value or '$(' in value:
            raise ValueError(f'Gunakan nilai literal, bukan ekspansi shell, pada .env baris {number}.')
        os.environ.setdefault(key, value)


def application_ready(port):
    """Probe loopback directly, without system HTTP proxies."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/api/health', timeout=1) as response:
            data = json.loads(response.read(8192))
        if not isinstance(data, dict):
            return False
        return (data.get('status') == 'ok' and data.get('mode') == 'single-node'
                and 'external_collectors_active' in data and 'collector_worker_running' in data)
    except (OSError, ValueError, TypeError):
        return False


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(('127.0.0.1', port)) == 0


def open_browser_when_ready(port, stopped):
    deadline = time.monotonic() + 120
    while not stopped.is_set() and time.monotonic() < deadline:
        if application_ready(port):
            try:
                webbrowser.open(f'http://127.0.0.1:{port}', new=2)
            except Exception:
                print(f'Buka browser secara manual: http://127.0.0.1:{port}', flush=True)
            return
        stopped.wait(0.5)
    if not stopped.is_set():
        print(f'Browser belum dibuka. Periksa log, lalu buka http://127.0.0.1:{port}', flush=True)


def main(argv=None):
    root = find_app_root(__file__)
    load_local_env(root / '.env')
    try:
        default_port = int(os.environ.get('PORT', '8000'))
    except ValueError:
        raise ValueError('PORT harus berupa angka 1 sampai 65535.') from None
    parser = argparse.ArgumentParser(description='Rubber Intelligence - server lokal Windows')
    parser.add_argument('--port', type=int, default=default_port)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise ValueError('Port harus 1 sampai 65535.')
    if not (root / 'frontend' / 'dist' / 'index.html').is_file():
        raise ValueError('Frontend belum tersedia; gunakan ZIP Windows lengkap.')
    os.chdir(root)
    sys.path.insert(0, str(root))
    url = f'http://127.0.0.1:{args.port}'
    if port_in_use(args.port):
        if application_ready(args.port):
            print(f'Aplikasi sudah berjalan. Alamat: {url}', flush=True)
            if not args.no_browser:
                webbrowser.open(url, new=2)
            return 0
        raise ValueError(f'Port {args.port} dipakai program lain. Gunakan --port 8001; tidak ada proses yang dimatikan.')
    print(f'Alamat aplikasi: {url}', flush=True)
    print('Akses hanya dari PC ini. Tutup tab tidak menghentikan kolektor; hentikan server untuk berhenti.', flush=True)
    print('Jangan hapus folder runtime. Simpan backup database dan raw bersama-sama.', flush=True)
    import uvicorn
    stopped = threading.Event()
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(args.port, stopped), daemon=True).start()
    try:
        uvicorn.run('backend.app:app', host='127.0.0.1', port=args.port, workers=1)
    finally:
        stopped.set()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f'Gagal memulai: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1)
