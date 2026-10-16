#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Trusted operator configuration only; never an uploaded file.
if [ -f .env ]; then set -a; source .env; set +a; fi
if [ ! -f frontend/dist/index.html ]; then
  echo 'Frontend belum dibangun. Jalankan: bash prepare.sh' >&2
  exit 1
fi
PYTHON="${PYTHON:-python}"
if [ -f .venv/bin/python ]; then PYTHON=.venv/bin/python; fi
exec "$PYTHON" -m uvicorn backend.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
