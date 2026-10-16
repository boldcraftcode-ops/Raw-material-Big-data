from __future__ import annotations

import json
import sqlite3
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, filename TEXT NOT NULL,
 logical_key TEXT NOT NULL, created_at TEXT NOT NULL,
 latest_version_id TEXT, active_version_id TEXT,
 UNIQUE(owner_id,logical_key),
 FOREIGN KEY(latest_version_id) REFERENCES document_versions(id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(active_version_id) REFERENCES document_versions(id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS raw_assets (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, sha256 TEXT NOT NULL,
 object_key TEXT NOT NULL, size_bytes INTEGER NOT NULL, UNIQUE(owner_id,sha256)
);
CREATE TABLE IF NOT EXISTS document_versions (
 id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 asset_id TEXT NOT NULL REFERENCES raw_assets(id), version_no INTEGER NOT NULL,
 status TEXT NOT NULL, created_at TEXT NOT NULL, parsed_meta TEXT,
 active_mapping_rev INTEGER, error TEXT, valid_count INTEGER NOT NULL DEFAULT 0,
 issue_count INTEGER NOT NULL DEFAULT 0, total_rows INTEGER NOT NULL DEFAULT 0,
 UNIQUE(document_id,version_no)
);
CREATE TABLE IF NOT EXISTS acquisitions (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 filename TEXT NOT NULL, captured_at TEXT NOT NULL, duplicate INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS raw_rows (
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 sheet TEXT NOT NULL, row_no INTEGER NOT NULL, line_end INTEGER NOT NULL,
 cells TEXT NOT NULL, PRIMARY KEY(version_id,sheet,row_no)
);
CREATE TABLE IF NOT EXISTS mappings (
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL, config TEXT NOT NULL, config_hash TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(version_id,revision), UNIQUE(version_id,config_hash)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 kind TEXT NOT NULL, mapping_rev INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
 error TEXT, UNIQUE(version_id,kind,mapping_rev)
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status,created_at);
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 mapping_rev INTEGER NOT NULL, sheet TEXT NOT NULL, row_no INTEGER NOT NULL,
 observed_date TEXT NOT NULL, supplier TEXT NOT NULL, supplier_identifier TEXT,
 location TEXT, material TEXT NOT NULL, grade TEXT, price TEXT NOT NULL,
 currency TEXT NOT NULL, unit TEXT NOT NULL, weight_basis TEXT NOT NULL,
 drc_percent TEXT, quantity_kg TEXT, price_kind TEXT NOT NULL,
 price_per_kg TEXT NOT NULL, dry_equivalent TEXT,
 transform_notes TEXT NOT NULL, raw_cells TEXT NOT NULL,
 UNIQUE(version_id,mapping_rev,sheet,row_no)
);
CREATE INDEX IF NOT EXISTS observations_version ON observations(version_id,mapping_rev);
CREATE TABLE IF NOT EXISTS issues (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 mapping_rev INTEGER NOT NULL, sheet TEXT NOT NULL, row_no INTEGER NOT NULL,
 errors TEXT NOT NULL, raw_cells TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, document_id TEXT,
 kind TEXT NOT NULL, message TEXT NOT NULL, details TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS activity_owner ON activity(owner_id,created_at DESC);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def uid() -> str:
    return uuid4().hex


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


class HybridRow(dict):
    """The domain repository supports both named and positional access."""
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def hybrid_row(cursor):
    names = [col.name for col in cursor.description] if cursor.description else []
    return lambda values: HybridRow(zip(names, values))


class PGConnection:
    def __init__(self, conn): self.conn = conn
    def _sql(self, sql):
        # Translate DB-API placeholders outside SQL literals (not user input).
        parts = re.split(r"('(?:''|[^'])*')", sql)
        for i in range(0, len(parts), 2):
            parts[i] = re.sub(r'\browid\b', 'seq', parts[i]).replace('%', '%%').replace('?', '%s')
        # Percent characters in literals must be escaped for psycopg as well.
        for i in range(1, len(parts), 2): parts[i] = parts[i].replace('%', '%%')
        return ''.join(parts)
    def execute(self, sql, params=None):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # Short manifest/publication critical section. Queue claims use row locks.
            return self.conn.execute('SELECT pg_advisory_xact_lock(74638291)')
        return self.conn.execute(self._sql(sql), params or ())
    def executemany(self, sql, params):
        cur = self.conn.cursor()
        cur.executemany(self._sql(sql), params)
        return cur
    def __getattr__(self, name): return getattr(self.conn, name)


class Database:
    def __init__(self, root: Path, url: str | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.raw = self.root / 'raw'
        self.raw.mkdir(exist_ok=True)
        self.path = self.root / 'workspace.sqlite3'
        self.url = url if url is not None else os.environ.get('RUBBER_DATABASE_URL', '')
        self.kind = 'postgresql' if self.url else 'sqlite'
        if self.url and not self.url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('RUBBER_DATABASE_URL harus PostgreSQL.')
        from .storage import LocalObjects, S3Objects
        self.objects = S3Objects(self.root / '.cache' / 'raw') if os.environ.get('RUBBER_S3_BUCKET') else LocalObjects(self.raw)
        extra = (Path(__file__).parent / 'schema_v02.sql').read_text()
        if self.url:
            import psycopg
            with psycopg.connect(self.url, autocommit=True, client_encoding='utf8') as conn:
                conn.execute('SELECT pg_advisory_lock(74638290)')
                try:
                    schema = SCHEMA.replace('PRAGMA foreign_keys=ON;', '')
                    schema = re.sub(r',\n FOREIGN KEY\(latest_version_id\).*?DEFERRED,\n FOREIGN KEY\(active_version_id\).*?DEFERRED', '', schema, flags=re.S)
                    for table in ('documents', 'jobs', 'activity'):
                        start = schema.index('CREATE TABLE IF NOT EXISTS ' + table + ' (')
                        end = schema.index('\n);', start)
                        schema = schema[:end] + ',\n seq BIGSERIAL NOT NULL' + schema[end:]
                    conn.execute(schema, prepare=False)
                    conn.execute("ALTER TABLE document_versions ADD COLUMN IF NOT EXISTS intake_meta TEXT NOT NULL DEFAULT '{}' ")
                    conn.execute(extra, prepare=False)
                    for col in ('latest_version_id', 'active_version_id'):
                        name = 'documents_' + col + '_fk'
                        if not conn.execute("SELECT 1 FROM pg_constraint WHERE conname=%s AND conrelid='documents'::regclass", (name,)).fetchone():
                            conn.execute(f'ALTER TABLE documents ADD CONSTRAINT {name} FOREIGN KEY({col}) REFERENCES document_versions(id) DEFERRABLE INITIALLY DEFERRED')
                    conn.execute("CREATE INDEX IF NOT EXISTS archive_text_search ON archive_content USING GIN(to_tsvector('simple',text_content))")
                    conn.execute("CREATE INDEX IF NOT EXISTS knowledge_text_search ON knowledge_records USING GIN(to_tsvector('simple',search_text))")
                finally:
                    conn.execute('SELECT pg_advisory_unlock(74638290)')
        else:
            with self.connect() as conn:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.executescript(SCHEMA)
                columns = {r['name'] for r in conn.execute('PRAGMA table_info(document_versions)')}
                if 'intake_meta' not in columns:
                    conn.execute("ALTER TABLE document_versions ADD COLUMN intake_meta TEXT NOT NULL DEFAULT '{}' ")
                conn.executescript(extra)

    def object_path(self, key, sha=None): return self.objects.path(key, sha)

    @contextmanager
    def connect(self):
        if self.url:
            import psycopg
            conn = psycopg.connect(self.url, row_factory=hybrid_row, connect_timeout=10, client_encoding='utf8')
            try:
                yield PGConnection(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally: conn.close()
        else:
            conn = sqlite3.connect(self.path, timeout=30, isolation_level='DEFERRED')
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=30000')
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally: conn.close()

    def activity(self, conn, owner, kind, message, document_id=None, details=None):
        conn.execute('INSERT INTO activity(id,owner_id,document_id,kind,message,details,created_at) VALUES(?,?,?,?,?,?,?)',
                     (uid(), owner, document_id, kind, message, dumps(details or {}), now()))
