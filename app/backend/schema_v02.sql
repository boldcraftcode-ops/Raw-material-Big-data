CREATE TABLE IF NOT EXISTS archive_content (
 version_id TEXT PRIMARY KEY REFERENCES document_versions(id) ON DELETE CASCADE,
 extraction_status TEXT NOT NULL, parser TEXT NOT NULL, text_content TEXT NOT NULL,
 warnings TEXT NOT NULL, extracted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_requests (
 owner_id TEXT NOT NULL, request_key TEXT NOT NULL, sha256 TEXT NOT NULL,
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, PRIMARY KEY(owner_id,request_key)
);
CREATE TABLE IF NOT EXISTS external_sources (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, source_key TEXT NOT NULL,
 name TEXT NOT NULL, adapter TEXT NOT NULL, config TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1, interval_seconds INTEGER NOT NULL,
 next_due_at TEXT NOT NULL, created_at TEXT NOT NULL,
 last_attempt_at TEXT, last_success_at TEXT, last_status TEXT NOT NULL DEFAULT 'never',
 last_error TEXT, consecutive_failures INTEGER NOT NULL DEFAULT 0,
 UNIQUE(owner_id,source_key)
);
CREATE INDEX IF NOT EXISTS sources_due ON external_sources(enabled,next_due_at);
CREATE TABLE IF NOT EXISTS collection_runs (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES external_sources(id) ON DELETE CASCADE,
 trigger_kind TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
 started_at TEXT, finished_at TEXT, lease_until TEXT, attempt INTEGER NOT NULL DEFAULT 1,
 resources INTEGER NOT NULL DEFAULT 0, records INTEGER NOT NULL DEFAULT 0,
 new_records INTEGER NOT NULL DEFAULT 0, revised_records INTEGER NOT NULL DEFAULT 0,
 unchanged_records INTEGER NOT NULL DEFAULT 0, rejected_records INTEGER NOT NULL DEFAULT 0,
 error TEXT, coverage TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS runs_status ON collection_runs(status,created_at);
CREATE INDEX IF NOT EXISTS runs_source ON collection_runs(source_id,created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS runs_one_pending ON collection_runs(source_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS source_fetches (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
 source_id TEXT NOT NULL REFERENCES external_sources(id) ON DELETE CASCADE,
 resource_key TEXT NOT NULL, url TEXT NOT NULL, requested_at TEXT NOT NULL,
 http_status INTEGER, response_headers TEXT NOT NULL, version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL,
 sha256 TEXT, size_bytes INTEGER NOT NULL DEFAULT 0, error TEXT,
 UNIQUE(run_id,resource_key)
);
CREATE INDEX IF NOT EXISTS fetches_resource ON source_fetches(source_id,resource_key,requested_at DESC);
CREATE TABLE IF NOT EXISTS knowledge_records (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES external_sources(id) ON DELETE CASCADE,
 owner_id TEXT NOT NULL, record_key TEXT NOT NULL, kind TEXT NOT NULL,
 title TEXT NOT NULL, period TEXT NOT NULL, current_revision INTEGER NOT NULL,
 search_text TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(source_id,record_key)
);
CREATE INDEX IF NOT EXISTS knowledge_owner_kind ON knowledge_records(owner_id,kind,period DESC);
CREATE TABLE IF NOT EXISTS knowledge_revisions (
 record_id TEXT NOT NULL REFERENCES knowledge_records(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL, payload_hash TEXT NOT NULL, payload TEXT NOT NULL,
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 run_id TEXT NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
 pointer TEXT NOT NULL, captured_at TEXT NOT NULL,
 PRIMARY KEY(record_id,revision)
);
CREATE INDEX IF NOT EXISTS revisions_raw ON knowledge_revisions(version_id);
CREATE TABLE IF NOT EXISTS collection_rejections (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 pointer TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS rejections_run ON collection_rejections(run_id);

CREATE TABLE IF NOT EXISTS acquisition_details (
 acquisition_id TEXT PRIMARY KEY REFERENCES acquisitions(id) ON DELETE CASCADE,
 metadata TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS host_throttles (
 host TEXT PRIMARY KEY, next_allowed_at TEXT NOT NULL
);

-- Explicitly approved per-workspace rules, not model training or copied cell values.
CREATE TABLE IF NOT EXISTS excel_templates (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, signature TEXT NOT NULL,
 field_labels TEXT NOT NULL, options TEXT NOT NULL,
 source_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 source_revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(owner_id,signature)
);
CREATE INDEX IF NOT EXISTS excel_templates_owner ON excel_templates(owner_id,updated_at);

-- Immutable, explicit metadata review snapshots. Derived profile remains a suggestion.
CREATE TABLE IF NOT EXISTS intake_classification_reviews (
 version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL, profile_hash TEXT NOT NULL, decision TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(version_id,revision)
);
