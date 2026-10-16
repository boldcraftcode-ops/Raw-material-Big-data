# Verifikasi rilis · 15 Oktober 2026

## Matriks requirement → implementasi → bukti

| Requirement | Implementasi | Bukti verifikasi |
|---|---|---|
| Menerima seluruh raw yang diotorisasi dalam batas konfigurasi, fokus karet alam | `/api/uploads` mode archive/purchase; `/api/intake/events`; private raw object store; SHA-256; manifests, versions, acquisition receipts, metadata, job queue | Heterogeneous-format exact-byte tests, empty/size/scope/rights/idempotency tests; ownership/deletion/version tests; UI upload/raw download/dedup/history/search |
| Track & collect eksternal secara otomatis | Source registry, durable `next_due_at`, worker server, adapters, per-host rate slots, conditional HTTP, lease, backoff, raw capture + atomic normalized revisions | Fixture contracts untuk 4 adapter dan failures; scheduler integration; actual public acquisitions; browser BMKG private scheduled fetch + resume recollection tanpa manual-run |
| Galaxy bermakna, provenance tetap terbuka | Source/archive/record nodes + evidence pointers, bounded projection, context/relation distinction | Backend graph provenance contract, browser node selection/filter, evidence drawer, real workbook/raw download, fullscreen/mobile |
| Alur lama tidak rusak | Mapping/validation/publish purchase slice, per-owner/demo/public isolation | Original domain/pipeline suite, expanded cross-mode raw-sharing regression, browser mapping gate + invalid-row quarantine |
| Fondasi database sesuai arah teknis | PostgreSQL optional repository/FTS + S3 object store adapter; offline migration | Actual PostgreSQL 17 integration matrix & SQLite→PG migration; **S3 stub protocol only**, not live cloud |

## Reproducible automated checks

CPython **3.13**, Linux; fresh venv resolved from `requirements-tested.txt`. PostgreSQL **17**, database UTF-8; test creates/drops isolated schemas, not runtime data. Passing a production DB as test target is not recommended; use a dedicated test database.

```text
pip check
No broken requirements found.

RUBBER_TEST_DATABASE_URL=<dedicated PostgreSQL> python -m pytest -q --maxfail=2
152 passed, 1 warning in 19.15s
```

One warning: Starlette's TestClient usage with httpx deprecated in this installed version. No live network is used by deterministic collector fixtures. The real-background-worker test proves scheduled execution without calling manual-run. S3 stubs assert private put/head/conditional-write collision, dedup integrity, materialization hash validation, and delete/cache semantics; they do not validate cloud IAM, bucket policy, outage resilience or provider compatibility.

Frontend:

```text
npm run build --prefix frontend
tsc -b && vite build
Vite 6.4.4, 1623 modules, succeeded
CSS 76.15 kB; JS 359.43 kB (gzip 107.68 kB)
```

`bash -n prepare.sh run.sh` passes. The ZIP was extracted into a clean directory and its actual `SKIP_FRONTEND_BUILD=1 bash prepare.sh` successfully created/installed a fresh venv; packaged static JS, blueprint route, API event intake, indexing, exact raw download, and cleanup were smoke-tested successfully. Manifest file hashes were checked against every ZIP entry; no runtime/credentials/dependency directories are bundled. Python dependency clean installation + `pip check` passes. Docker is not available in this sandbox, so Dockerfile/Compose are supplied **without a claim of a container run test**. MinIO/S3 live service not started; no bucket credentials were supplied or invented.

## Browser end-to-end (Chromium)

Runner: `scripts/browser_smoke.py` (opt-in; Playwright/Chromium are QA dependencies, not required app runtime). It creates its own anonymous workspace, tests operations, then deletes only its generated private QA documents/source. It never edits the four public source configs or deletes other workspaces.

Completed successfully:

1. Public default galaxy, six balanced rows representing all four kinds, no external browser dependencies at startup.
2. Graph node selection, fullscreen and Escape.
3. Public actual acquisition ledger, response artifacts, focus containment, Shift+Tab and Escape.
4. External record kind filter, page 2, raw/evidence chain and 64-character SHA manifest.
5. Natural-rubber/rights consent, raw TXT, safe index, byte-identical download.
6. Search by content, identical-byte acquisition receipt 2, unchanged raw v1, same-name changed content v2, history.
7. Purchase CSV suggested mapping remains gated by explicit scope confirmation; 1 valid observation, 1 invalid row withheld; evidence/raw exact bytes.
8. Private BMKG source created enabled and actually acquired **18 real forecast intervals** with `trigger_kind=scheduled`, without a manual run. Pause, edit context, resume, second scheduled acquisition and source deletion all succeed.
9. QA private raw/source cleanup leaves own documents and knowledge empty. Other workspaces and public source settings untouched.
10. Galaxy/sources at **390, 768, 1024, 1440 px**: no horizontal page overflow, mobile navigation works. **0 page JavaScript errors**.

Initial QA runner selector/wait-assertion issues were fixed before the complete successful run. Application workflow assertions, not an unverified sleep, establish collection completion. Screenshots were visually inspected. QA scratch/browser storage (capability secrets) lives outside the release and is not bundled.

## Actual public data check

Machine-readable public-only acquisition evidence: [`LIVE_SOURCE_PROOF.json`](LIVE_SOURCE_PROOF.json). No private owner capability, credential or raw dataset is packaged with this proof.

- **World Bank:** 1,134 monthly observations, RSS3 and TSR20, through **2026-09**. Latest run succeeded, 0 rejected, source-missing values separate. Workbook discovery and sheet/row/column pointers retained. Identical semantic workbook values produced **0 new / 0 revised** on repeat fetch.
- **FAOSTAT:** 1,256 production facts since 2000; streamed scan **4,209,110 bulk CSV rows**; source update metadata **2025-12-31**. Raw ZIP retained; full CSV declared uncompressed size about 545 MB. Latest run succeeded, 0 rejected, 131 unavailable source values—not zeros. Flag descriptions/citation metadata were verified from the actual bulk; metadata enrichment revisions are not claimed as numerical production changes.
- **BMKG:** latest response **18 intervals** for **Pasar Baru, Medan Kota**, adm4 **12.71.01.1001**. Runtime retains **36 distinct valid-time keys across two successful snapshots**. These are archival records, not a claim of 36 simultaneous/current forecast slots, full 72-hour coverage or verified farm location.
- **RSS:** **14** metadata report records at verification; partial/nonexhaustive by policy. No publisher page crawling or verified-event claim.
- Total retained at verification: **2,440** records. Shared-source schedules 4 active, 4 have successful/partial acquisitions, 0 source failures then; values/status can change after verification.
- Runtime integrity check: SQLite integrity `ok`, **0 foreign-key violations**. Raw is outside the DB; integrity/hash download checks are separate and tested.

## What these tests do not establish

No petabyte throughput or load benchmark, exhaustive global coverage, verified economic truth, verified supplier/farm identities, article republication rights, full malware isolation, formal security audit, cloud durability/IAM, managed backups, HA/multiprocess safety, 24/7 hosting or SLA. The release is a functional single-node foundation with real automated collectors and extensible storage, not a claim that production governance/infrastructure already exists.
