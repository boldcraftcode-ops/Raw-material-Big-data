"""Resource-bounded schema-on-read indexer; not a full malware/container sandbox."""
from __future__ import annotations
import json
import logging
import sys


def main():
    limited = False
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        limited = True
    except (ImportError, ValueError, OSError):
        pass
    logging.disable(logging.CRITICAL)
    from pathlib import Path
    from .intake_breakdown import build_breakdown
    data = Path(sys.argv[1]).read_bytes()
    breakdown = None
    if '--breakdown-only' in sys.argv:
        obj={'breakdown':build_breakdown(data,sys.argv[2])}
        if not limited:obj['breakdown']['notes'].append('Batas memori/CPU OS tidak tersedia; timeout proses tetap diterapkan.')
    else:
        from .archive import extract_bytes
        text, status, parser, warnings = extract_bytes(data, sys.argv[2], sys.argv[3])
        if not limited: warnings.append('Batas memori/CPU OS tidak tersedia; timeout proses tetap diterapkan.')
        if '--with-breakdown' in sys.argv:breakdown=build_breakdown(data,sys.argv[2])
        obj={'text':text,'status':status,'parser':parser,'warnings':warnings,'breakdown':breakdown}
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, allow_nan=False))



if __name__ == '__main__': main()
