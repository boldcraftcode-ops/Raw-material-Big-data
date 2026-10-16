"""Offline, non-destructive SQLite -> PostgreSQL (+ optional private S3) migration."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from .db import Database, now

TABLES=('raw_assets','documents','document_versions','acquisitions','acquisition_details','raw_rows','mappings','excel_templates','intake_classification_reviews','jobs',
        'observations','issues','activity','archive_content','intake_requests','external_sources','collection_runs',
        'host_throttles','source_fetches','knowledge_records','knowledge_revisions','collection_rejections')


def migrate_sqlite(sqlite_path: Path, source_raw: Path, target: Database):
    if target.kind!='postgresql': raise ValueError('Target migrasi harus PostgreSQL.')
    source=sqlite3.connect('file:'+str(sqlite_path.resolve())+'?mode=ro',uri=True)
    source.row_factory=sqlite3.Row
    try:
        source.execute('BEGIN')
        names={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'documents','raw_assets','document_versions'}.issubset(names): raise ValueError('Database sumber bukan workspace Rubber Intelligence.')
        with target.connect() as c:
            if any(c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in TABLES):
                raise ValueError('Target harus kosong. Migrasi tidak akan menimpa atau menggabungkan workspace aktif.')
        count=0;size=0
        for asset in source.execute('SELECT * FROM raw_assets'):
            path=source_raw/asset['object_key']
            if not path.is_file(): raise ValueError('Ada objek raw sumber yang hilang; migrasi dihentikan.')
            data=path.read_bytes()
            if len(data)!=asset['size_bytes'] or hashlib.sha256(data).hexdigest()!=asset['sha256']:
                raise ValueError('Integritas objek sumber tidak cocok; migrasi dihentikan.')
            target.objects.put(asset['object_key'],data);count+=1;size+=len(data)
        counts={}
        with target.connect() as c:
            c.execute('BEGIN IMMEDIATE');c.execute('SET CONSTRAINTS ALL DEFERRED')
            # Recheck while holding the publication/manifest lock.
            if any(c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in TABLES):
                raise ValueError('Target telah berubah selama migrasi; hentikan semua writer terlebih dahulu.')
            for table in TABLES:
                if table not in names: continue
                cursor=source.execute('SELECT * FROM '+table)
                columns=[d[0] for d in cursor.description]
                # Table/column names only come from this fixed schema, never user input.
                expected={r['column_name'] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(table,))}
                if set(columns)-expected: raise ValueError('Sumber memiliki kolom yang belum dikenal; jangan hilangkan informasi secara diam-diam.')
                stmt='INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')'
                total=0
                while batch:=cursor.fetchmany(1000):
                    c.executemany(stmt,[tuple(r) for r in batch]);total+=len(batch)
                counts[table]=total
            c.execute("UPDATE jobs SET status='queued',started_at=NULL WHERE status='running'")
            c.execute("UPDATE collection_runs SET status='interrupted',finished_at=?,lease_until=NULL,error=? WHERE status='running'",(now(),'Run terputus saat migrasi offline; retry dijadwalkan.'))
            c.execute("UPDATE external_sources SET next_due_at=? WHERE enabled=1 AND last_status='running'",(now(),))
            c.execute("UPDATE external_sources SET last_status='interrupted',last_error=? WHERE last_status='running'",('Worker dihentikan untuk migrasi; jadwal akan dilanjutkan.',))
            for table,total in counts.items():
                if c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]!=total: raise ValueError('Verifikasi jumlah baris target gagal.')
        report={'completed_at':now(),'source':'sqlite','target':target.kind,'object_storage':target.objects.kind,
                'objects_verified':count,'raw_bytes':size,'tables':counts,'source_deleted':False}
        (target.root/'migration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        return report
    finally: source.close()


def main():
    parser=argparse.ArgumentParser(description='Hentikan server sumber dan target sebelum migrasi. Sumber tidak dihapus.')
    parser.add_argument('--sqlite',type=Path,required=True)
    parser.add_argument('--raw-dir',type=Path,required=True)
    parser.add_argument('--target-dir',type=Path,required=True)
    args=parser.parse_args()
    if not os.environ.get('RUBBER_DATABASE_URL'): raise SystemExit('Set RUBBER_DATABASE_URL PostgreSQL target terlebih dahulu.')
    target=Database(args.target_dir)
    report=migrate_sqlite(args.sqlite,args.raw_dir,target)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
