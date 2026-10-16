#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then echo 'Python 3.13 diperlukan. Set PYTHON ke executable yang sesuai.' >&2; exit 1; fi
if [ ! -f .venv/bin/python ]; then "$PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install -r requirements-tested.txt
if [ "${SKIP_FRONTEND_BUILD:-0}" = 1 ]; then
  test -f frontend/dist/index.html || { echo 'Frontend build tidak ada; jalankan ulang tanpa SKIP_FRONTEND_BUILD.' >&2; exit 1; }
else
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi
