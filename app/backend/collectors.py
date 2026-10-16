"""Durable schedules, acquisition receipts, atomic publication, retries and provenance."""
from __future__ import annotations

import hashlib
import json
import os
import time
from urllib.parse import urlsplit
import re
import logging
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from .adapters import ADAPTERS, CATALOG, validate_config
from .collector_http import FetchError, PublicHTTP
from .db import dumps, now, uid

DEFAULT_ADAPTERS = ('worldbank', 'faostat_bulk', 'bmkg', 'news_rss')
KINDS = {'market_price', 'production_stat', 'weather_forecast', 'news_report'}


def after(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec='microseconds')


class CollectionContext:
    def __init__(self, manager, source, run):
        self.manager = manager
        self.source = source
        self.run = run
        self.resources = 0

    def heartbeat(self):
        with self.manager.db.connect() as c:
            changed = c.execute("UPDATE collection_runs SET lease_until=? WHERE id=? AND status='running'", (after(1200), self.run['id'])).rowcount
            if not changed: raise ValueError('Lease koleksi berakhir; hasil worker lama tidak dipublikasikan.')

    def fetch(self, resource_key, url, filename, max_bytes=10 * 1024 * 1024):
        self.heartbeat()
        m = self.manager
        with m.db.connect() as c:
            previous = c.execute('''SELECT f.*,a.object_key,a.sha256 AS asset_sha FROM source_fetches f
                JOIN document_versions v ON v.id=f.version_id JOIN raw_assets a ON a.id=v.asset_id
                WHERE f.source_id=? AND f.resource_key=? AND f.url=? AND f.http_status IN (200,304)
                ORDER BY f.requested_at DESC,f.id DESC LIMIT 1''', (self.source['id'], resource_key, url)).fetchone()
        conditional = {}
        if previous:
            old_headers = json.loads(previous['response_headers'])
            if old_headers.get('etag'): conditional['If-None-Match'] = old_headers['etag']
            if old_headers.get('last-modified'): conditional['If-Modified-Since'] = old_headers['last-modified']
        requested = now()
        try:
            response = m.http.get(url, max_bytes=max_bytes, headers=conditional)
        except FetchError as exc:
            with m.db.connect() as c:
                c.execute('INSERT INTO source_fetches(id,run_id,source_id,resource_key,url,requested_at,http_status,response_headers,error) VALUES(?,?,?,?,?,?,?,?,?)',
                          (uid(), self.run['id'], self.source['id'], resource_key, url, requested, exc.status, dumps({'retry-after': exc.retry_after} if exc.retry_after else {}), str(exc)))
            raise
        headers = response.headers
        if response.status == 304:
            if not previous: raise ValueError('HTTP 304 diterima tanpa arsip raw sebelumnya.')
            body = m.db.object_path(previous['object_key'], previous['asset_sha']).read_bytes()
            headers = {**json.loads(previous['response_headers']), **headers}
        else: body = response.body
        policy = CATALOG[self.source['adapter']]
        receipt = m.service.archive(self.source['owner_id'], filename, body, category=policy['category'],
                                    context=policy['description'], source_uri=response.url,
                                    media_type=headers.get('content-type', ''), logical_key=f'collector:{self.source["id"]}:{resource_key}',
                                    source_id=self.source['id'], run_id=self.run['id'], internal=True)
        version = receipt['version']
        with m.db.connect() as c:
            c.execute('INSERT INTO source_fetches(id,run_id,source_id,resource_key,url,requested_at,http_status,response_headers,version_id,sha256,size_bytes) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (uid(), self.run['id'], self.source['id'], resource_key, response.url, requested, response.status, dumps(headers), version['id'], version['sha256'], len(body)))
        self.resources += 1
        return {'body': body, 'url': response.url, 'version_id': version['id'], 'sha256': version['sha256'], 'status': response.status}


class Collectors:
    def __init__(self, db, service, http=None, enabled=None):
        self.db = db; self.service = service; self._sleep = time.sleep; self.http = http or PublicHTTP(on_request=self.reserve_host_slot)
        self.enabled = enabled if enabled is not None else os.environ.get('RUBBER_COLLECTORS_ENABLED', '1') != '0'

    def reserve_host_slot(self, url):
        host=urlsplit(url).hostname
        interval={'api.bmkg.go.id':1.1,'api.gdeltproject.org':6.1,'bulks-faostat.fao.org':2.0}.get(host,1.0)
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT next_allowed_at FROM host_throttles WHERE host=?',(host,)).fetchone()
            current=datetime.now(timezone.utc)
            allowed=max(current,datetime.fromisoformat(row['next_allowed_at'])) if row else current
            delay=(allowed-current).total_seconds()
            if delay>60: raise FetchError('Anggaran laju host sedang penuh; retry dijadwalkan.')
            next_at=(allowed+timedelta(seconds=interval)).isoformat(timespec='microseconds')
            c.execute('INSERT INTO host_throttles(host,next_allowed_at) VALUES(?,?) ON CONFLICT(host) DO UPDATE SET next_allowed_at=excluded.next_allowed_at',(host,next_at))
        if delay>0: self._sleep(delay)

    def seed(self):
        # Shared public reference feeds. Private user streams and demo never mix with these.
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            for adapter in DEFAULT_ADAPTERS:
                if c.execute("SELECT 1 FROM external_sources WHERE owner_id='external' AND source_key=?", (adapter,)).fetchone(): continue
                item = CATALOG[adapter]
                c.execute('''INSERT INTO external_sources(id,owner_id,source_key,name,adapter,config,enabled,interval_seconds,next_due_at,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (uid(), 'external', adapter, item['name'], adapter, dumps(item['config']), 1, item['interval'], now(), now()))

    def create(self, owner, adapter, config, name=None, interval=None, enabled=True):
        config = validate_config(adapter, config)
        policy = CATALOG[adapter]
        interval = interval if interval is not None else policy['interval']
        if isinstance(interval, bool) or not isinstance(interval, int) or not policy['minimum_interval'] <= interval <= 2592000:
            raise ValueError(f'Interval harus {policy["minimum_interval"]}–2592000 detik untuk sumber ini.')
        name = (name or policy['name']).strip()
        if not 3 <= len(name) <= 120: raise ValueError('Nama sumber harus 3–120 karakter.')
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT COUNT(*) FROM external_sources WHERE owner_id=?', (owner,)).fetchone()[0] >= 12:
                raise ValueError('Maksimum 12 sumber privat per workspace. Atur skala koleksi pada operator server.')
            source_id = uid()
            c.execute('INSERT INTO external_sources(id,owner_id,source_key,name,adapter,config,enabled,interval_seconds,next_due_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (source_id, owner, uid(), name, adapter, dumps(config), int(enabled), interval, now(), now()))
            self.db.activity(c, owner, 'source_created', 'Sumber eksternal ditambahkan: ' + name, details={'source_id': source_id, 'enabled': enabled})
        return self.get(source_id, owner)

    def _read(self, c, source_id, owner, write=False):
        source = c.execute('SELECT * FROM external_sources WHERE id=?', (source_id,)).fetchone()
        if not source or source['owner_id'] not in (owner, 'external') or (write and source['owner_id'] != owner):
            raise LookupError('Sumber tidak ditemukan atau tidak dapat diubah.')
        return dict(source)

    def _public(self, c, source, owner):
        item = dict(source); scope = item.pop('owner_id')
        item['config'] = json.loads(item['config']); item['enabled'] = bool(item['enabled'])
        item['is_public'] = scope == 'external'; item['is_mine'] = scope == owner
        item['policy'] = CATALOG[item['adapter']]
        item['worker_enabled'] = self.enabled
        count = c.execute('SELECT COUNT(*) FROM knowledge_records WHERE source_id=?', (item['id'],)).fetchone()[0]
        item['record_count'] = count
        run = c.execute('SELECT * FROM collection_runs WHERE source_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (item['id'],)).fetchone()
        item['latest_run'] = self._run_public(run) if run else None
        item['stale'] = bool(item['last_success_at'] and item['last_success_at'] < after(-max(item['interval_seconds'] * 2, 86400)))
        return item

    def list(self, owner):
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM external_sources WHERE owner_id IN (?,'external') ORDER BY owner_id DESC,created_at,id", (owner,)).fetchall()
            return [self._public(c, r, owner) for r in rows]

    def get(self, source_id, owner):
        with self.db.connect() as c: return self._public(c, self._read(c, source_id, owner), owner)

    def patch(self, source_id, owner, changes):
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            source = self._read(c, source_id, owner, write=True)
            if c.execute("SELECT 1 FROM collection_runs WHERE source_id=? AND status IN ('queued','running')", (source_id,)).fetchone():
                raise ValueError('Tunggu run yang sedang berjalan sebelum mengubah konfigurasi.')
            config = validate_config(source['adapter'], changes.get('config', json.loads(source['config'])))
            interval = changes.get('interval_seconds', source['interval_seconds'])
            if isinstance(interval, bool) or not isinstance(interval, int) or not CATALOG[source['adapter']]['minimum_interval'] <= interval <= 2592000:
                raise ValueError('Interval di luar kebijakan sumber.')
            name = changes.get('name', source['name']).strip()
            if not 3 <= len(name) <= 120: raise ValueError('Nama sumber harus 3–120 karakter.')
            enabled = changes.get('enabled', bool(source['enabled']))
            c.execute('UPDATE external_sources SET config=?,interval_seconds=?,enabled=?,name=?,next_due_at=? WHERE id=?',
                      (dumps(config), interval, int(enabled), name, now() if enabled else after(interval), source_id))
            self.db.activity(c, owner, 'source_updated', 'Jadwal/konfigurasi sumber diubah: ' + name, details={'source_id': source_id, 'enabled': enabled})
        return self.get(source_id, owner)

    def request_run(self, source_id, owner):
        if not self.enabled: raise ValueError('Worker kolektor dinonaktifkan oleh operator server.')
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            source = self._read(c, source_id, owner)
            pending = c.execute("SELECT id FROM collection_runs WHERE source_id=? AND status IN ('queued','running')", (source_id,)).fetchone()
            if pending: return {'run_id': pending['id'], 'reused': True}
            if source['last_attempt_at'] and source['last_attempt_at'] > after(-60):
                raise ValueError('Tunggu minimal 60 detik antar-run manual. Jadwal otomatis tetap berjalan.')
            run_id = self._enqueue(c, source, 'manual')
            return {'run_id': run_id, 'reused': False}

    def _enqueue(self, c, source, trigger):
        run_id = uid()
        c.execute('INSERT INTO collection_runs(id,source_id,trigger_kind,status,created_at,attempt) VALUES(?,?,?,?,?,?)',
                  (run_id, source['id'], trigger, 'queued', now(), source['consecutive_failures'] + 1))
        c.execute('UPDATE external_sources SET next_due_at=? WHERE id=?', (after(source['interval_seconds']), source['id']))
        return run_id

    def schedule_due(self):
        if not self.enabled: return 0
        self.recover_expired()
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            due = c.execute("SELECT * FROM external_sources s WHERE enabled=1 AND next_due_at<=? AND NOT EXISTS(SELECT 1 FROM collection_runs r WHERE r.source_id=s.id AND r.status IN ('queued','running')) ORDER BY next_due_at,s.id LIMIT 20", (now(),)).fetchall()
            for source in due: self._enqueue(c, dict(source), 'retry' if source['consecutive_failures'] else 'scheduled')
            return len(due)

    def recover_expired(self):
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            rows = c.execute("SELECT r.id,r.source_id FROM collection_runs r WHERE r.status='running' AND r.lease_until<?", (now(),)).fetchall()
            for r in rows:
                c.execute("UPDATE collection_runs SET status='interrupted',finished_at=?,error=? WHERE id=? AND status='running'", (now(), 'Lease worker berakhir; retry dijadwalkan tanpa menghapus arsip yang telah diterima.', r['id']))
                c.execute("UPDATE external_sources SET last_status='interrupted',last_error=?,consecutive_failures=consecutive_failures+1,next_due_at=? WHERE id=?", ('Worker terputus; menunggu retry.', after(60), r['source_id']))
            return len(rows)

    def process_next(self):
        if not self.enabled: return False
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            suffix = ' FOR UPDATE SKIP LOCKED' if self.db.kind == 'postgresql' else ''
            run = c.execute("SELECT * FROM collection_runs WHERE status='queued' ORDER BY created_at,id LIMIT 1" + suffix).fetchone()
            if not run: return False
            run = dict(run)
            source = dict(c.execute('SELECT * FROM external_sources WHERE id=?', (run['source_id'],)).fetchone())
            c.execute("UPDATE collection_runs SET status='running',started_at=?,lease_until=? WHERE id=?", (now(), after(1200), run['id']))
            c.execute("UPDATE external_sources SET last_attempt_at=?,last_status='running',last_error=NULL WHERE id=?", (now(), source['id']))
        ctx = CollectionContext(self, source, run)
        try:
            config = validate_config(source['adapter'], json.loads(source['config']))
            records, rejected, coverage = ADAPTERS[source['adapter']](ctx, config)
            self._publish(source, run, records, rejected, coverage, ctx.resources)
        except Exception as exc:
            message = str(exc)[:600] if isinstance(exc, ValueError) else 'Ekstraksi sumber gagal; skema/format perlu diperiksa. Arsip terakhir tidak dihapus.'
            delay = min(86400, 60 * (2 ** min(source['consecutive_failures'], 10)))
            if isinstance(exc, FetchError) and str(exc.retry_after or '').isdigit(): delay = max(delay, min(86400, int(exc.retry_after)))
            with self.db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                changed = c.execute("UPDATE collection_runs SET status='failed',finished_at=?,error=?,resources=? WHERE id=? AND status='running'", (now(), message, ctx.resources, run['id'])).rowcount
                if changed:
                    c.execute("UPDATE external_sources SET last_status='failed',last_error=?,consecutive_failures=consecutive_failures+1,next_due_at=? WHERE id=?", (message, after(delay), source['id']))
                    logging.getLogger('uvicorn.error').warning('Collector source=%s run=%s failed: %s',source['id'],run['id'],message)
                    self.db.activity(c, source['owner_id'], 'collector_failed', source['name'] + ': ' + message, details={'source_id': source['id'], 'run_id': run['id'], 'retry_seconds': delay})
        return True

    def _publish(self, source, run, records, rejected, coverage, resources):
        if len(records) > 20000: raise ValueError('Batas 20.000 record terlampaui; tidak dipublikasikan sebagian secara diam-diam.')
        rows = {}; captured = now()
        for r in records:
            if r['kind'] not in KINDS: raise ValueError('Jenis record eksternal tidak dikenali.')
            payload = {'title': r['title'], 'period': r['period'], 'kind': r['kind'], 'fields': r['fields']}
            encoded = json.dumps(payload,ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False); digest = hashlib.sha256(encoded.encode()).hexdigest()
            key = r['key'] if len(r['key']) <= 2000 else hashlib.sha256(r['key'].encode()).hexdigest()
            if key in rows and rows[key][2] != digest: raise ValueError('Sumber mengirim nilai konflik untuk identifier/periode yang sama; perlu review.')
            rows[key] = (r, encoded, digest)
        new = revised = unchanged = 0
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            claim = c.execute('SELECT status,lease_until FROM collection_runs WHERE id=?', (run['id'],)).fetchone()
            if not claim or claim['status'] != 'running' or claim['lease_until'] < now(): raise ValueError('Lease publikasi sudah tidak berlaku.')
            existing = {r['record_key']: r for r in c.execute('SELECT k.record_key,k.id,k.current_revision,r.payload_hash,r.payload FROM knowledge_records k JOIN knowledge_revisions r ON r.record_id=k.id AND r.revision=k.current_revision WHERE k.source_id=?', (source['id'],))}
            new_keys = []; revisions = []; updates = []; seen = []
            for key, (r, encoded, digest) in rows.items():
                previous = existing.get(key)
                if previous and (previous['payload_hash'] == digest or json.dumps(json.loads(previous['payload']),ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False)==encoded):
                    unchanged += 1; seen.append((captured, previous['id'])); continue
                rid = previous['id'] if previous else uuid5(NAMESPACE_URL, source['id'] + ':' + key).hex
                revision = previous['current_revision'] + 1 if previous else 1
                search = (r['title'] + ' ' + dumps(r['fields'])).lower()[:20000]
                if not previous:
                    new += 1
                    new_keys.append((rid, source['id'], source['owner_id'], key, r['kind'], r['title'], r['period'], revision, search, captured, captured))
                else:
                    revised += 1; updates.append((r['title'], r['period'], revision, search, captured, rid))
                revisions.append((rid, revision, digest, encoded, r['version_id'], run['id'], dumps(r['pointer']), captured))
            c.executemany('INSERT INTO knowledge_records VALUES(?,?,?,?,?,?,?,?,?,?,?)', new_keys)
            c.executemany('INSERT INTO knowledge_revisions VALUES(?,?,?,?,?,?,?,?)', revisions)
            c.executemany('UPDATE knowledge_records SET title=?,period=?,current_revision=?,search_text=?,updated_at=? WHERE id=?', updates)
            c.executemany('UPDATE knowledge_records SET updated_at=? WHERE id=?', seen)
            c.executemany('INSERT INTO collection_rejections VALUES(?,?,?,?,?)', [(uid(), run['id'], v, dumps(ptr), reason[:600]) for v, ptr, reason in rejected[:20000]])
            status = 'partial' if coverage.get('complete_within_scope') is False or rejected else 'succeeded'
            c.execute('UPDATE collection_runs SET status=?,finished_at=?,lease_until=NULL,resources=?,records=?,new_records=?,revised_records=?,unchanged_records=?,rejected_records=?,coverage=? WHERE id=?',
                      (status, captured, resources, len(rows), new, revised, unchanged, len(rejected), dumps(coverage), run['id']))
            c.execute('UPDATE external_sources SET last_status=?,last_success_at=?,last_error=NULL,consecutive_failures=0,next_due_at=? WHERE id=?',
                      (status, captured, after(source['interval_seconds']), source['id']))
            logging.getLogger('uvicorn.error').info('Collector source=%s run=%s status=%s records=%s new=%s revised=%s',source['id'],run['id'],status,len(rows),new,revised)
            self.db.activity(c, source['owner_id'], 'collector_succeeded', f'{source["name"]}: {new} baru, {revised} revisi, {unchanged} tidak berubah; {len(rejected)} ditahan.', details={'source_id': source['id'], 'run_id': run['id'], 'coverage': coverage})

    def _run_public(self, row):
        item = dict(row); item['coverage'] = json.loads(item['coverage']); return item

    def runs(self, source_id, owner, limit=30, offset=0):
        with self.db.connect() as c:
            self._read(c, source_id, owner)
            count = c.execute('SELECT COUNT(*) FROM collection_runs WHERE source_id=?', (source_id,)).fetchone()[0]
            rows = c.execute('SELECT * FROM collection_runs WHERE source_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', (source_id, limit, offset)).fetchall()
            return {'items': [self._run_public(r) for r in rows], 'total': count, 'limit': limit, 'offset': offset}

    def run_detail(self, run_id, owner):
        with self.db.connect() as c:
            run = c.execute('SELECT * FROM collection_runs WHERE id=?', (run_id,)).fetchone()
            if not run: raise LookupError('Run koleksi tidak ditemukan.')
            self._read(c, run['source_id'], owner)
            out = self._run_public(run)
            out['fetches'] = [{**dict(r), 'response_headers': json.loads(r['response_headers'])} for r in c.execute('SELECT f.*,d.filename FROM source_fetches f LEFT JOIN document_versions v ON v.id=f.version_id LEFT JOIN documents d ON d.id=v.document_id WHERE f.run_id=? ORDER BY f.requested_at,f.id', (run_id,))]
            out['rejections'] = [{**dict(r), 'pointer': json.loads(r['pointer'])} for r in c.execute('SELECT * FROM collection_rejections WHERE run_id=? LIMIT 50', (run_id,))]
            return out

    def records(self, owner, q='', kind='', source_id='', limit=20, offset=0):
        if kind and kind not in KINDS: raise ValueError('Jenis record tidak dikenal.')
        where = ' FROM knowledge_records k JOIN knowledge_revisions r ON r.record_id=k.id AND r.revision=k.current_revision JOIN external_sources s ON s.id=k.source_id WHERE k.owner_id=? '
        params = [owner]
        if source_id: where += ' AND k.source_id=?'; params.append(source_id)
        if kind: where += ' AND k.kind=?'; params.append(kind)
        if q:
            escaped = q.lower().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            if self.db.kind=='postgresql':
                where += " AND to_tsvector('simple',k.search_text) @@ plainto_tsquery('simple',?)";params.append(q)
            else:
                where += " AND k.search_text LIKE ? ESCAPE '\\'"; params.append('%' + escaped + '%')
        with self.db.connect() as c:
            total = c.execute('SELECT COUNT(*)' + where, params).fetchone()[0]
            rows = c.execute('SELECT k.id,k.source_id,k.kind,k.title,k.period,k.current_revision,k.updated_at,r.payload,r.version_id,r.captured_at,s.name AS source_name' + where + ' ORDER BY k.period DESC,k.id LIMIT ? OFFSET ?', params + [limit, offset]).fetchall()
            out = []
            for r in rows:
                item = dict(r); item['fields'] = json.loads(item.pop('payload'))['fields']; out.append(item)
            return {'items': out, 'total': total, 'limit': limit, 'offset': offset}

    def evidence(self, record_id, owner):
        with self.db.connect() as c:
            item = c.execute('SELECT k.*,r.payload,r.version_id,r.run_id,r.pointer,r.captured_at,s.name AS source_name,v.version_no,d.filename,a.sha256,a.size_bytes FROM knowledge_records k JOIN knowledge_revisions r ON r.record_id=k.id AND r.revision=k.current_revision JOIN external_sources s ON s.id=k.source_id JOIN document_versions v ON v.id=r.version_id JOIN documents d ON d.id=v.document_id JOIN raw_assets a ON a.id=v.asset_id WHERE k.id=? AND k.owner_id IN (?,\'external\')', (record_id, owner)).fetchone()
            if not item: raise LookupError('Record/bukti eksternal tidak ditemukan.')
            out = dict(item); out.pop('owner_id'); out.pop('search_text')
            out['fields'] = json.loads(out.pop('payload'))['fields']; out['pointer'] = json.loads(out['pointer'])
            out['history'] = [{**dict(r), 'payload': json.loads(r['payload']), 'pointer': json.loads(r['pointer'])} for r in c.execute('SELECT revision,payload,version_id,run_id,pointer,captured_at FROM knowledge_revisions WHERE record_id=? ORDER BY revision DESC LIMIT 100', (record_id,))]
            return out

    def revisions(self,record_id,owner,limit=50,offset=0):
        with self.db.connect() as c:
            record=c.execute("SELECT id FROM knowledge_records WHERE id=? AND owner_id IN (?,'external')",(record_id,owner)).fetchone()
            if not record: raise LookupError('Record tidak dapat diakses.')
            total=c.execute('SELECT COUNT(*) FROM knowledge_revisions WHERE record_id=?',(record_id,)).fetchone()[0]
            rows=c.execute('SELECT revision,payload,version_id,run_id,pointer,captured_at FROM knowledge_revisions WHERE record_id=? ORDER BY revision DESC LIMIT ? OFFSET ?',(record_id,limit,offset)).fetchall()
            return {'items':[{**dict(r),'payload':json.loads(r['payload']),'pointer':json.loads(r['pointer'])} for r in rows],'total':total,'offset':offset,'limit':limit}

    def summary(self, owner=None):
        with self.db.connect() as c:
            where = " WHERE owner_id IN (?,'external')" if owner and owner not in ('demo', 'external') else " WHERE owner_id='external'"
            args = (owner,) if owner and owner not in ('demo', 'external') else ()
            rows = c.execute('SELECT enabled,last_status FROM external_sources' + where, args).fetchall()
            return {'enabled': sum(bool(r['enabled']) for r in rows),
                    'successful': sum(r['last_status'] in ('succeeded', 'partial') for r in rows),
                    'failed': sum(r['last_status'] in ('failed', 'interrupted') for r in rows),
                    'worker_enabled': self.enabled}

    def delete(self, source_id, owner):
        paths = []
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE'); source = self._read(c, source_id, owner, write=True)
            if c.execute("SELECT 1 FROM collection_runs WHERE source_id=? AND status='running'", (source_id,)).fetchone():
                raise ValueError('Tunggu koleksi yang sedang berjalan sebelum menghapus sumber.')
            docs = c.execute('SELECT DISTINCT d.id FROM documents d JOIN document_versions v ON v.document_id=d.id JOIN source_fetches f ON f.version_id=v.id WHERE f.source_id=?', (source_id,)).fetchall()
            for doc in docs:
                if c.execute("SELECT 1 FROM jobs j JOIN document_versions v ON v.id=j.version_id WHERE v.document_id=? AND j.status='running'", (doc['id'],)).fetchone():
                    raise ValueError('Tunggu indeks raw selesai sebelum menghapus sumber.')
            assets = c.execute('SELECT DISTINCT a.* FROM raw_assets a JOIN document_versions v ON v.asset_id=a.id JOIN source_fetches f ON f.version_id=v.id WHERE f.source_id=?', (source_id,)).fetchall()
            c.execute('DELETE FROM external_sources WHERE id=?', (source_id,))
            for doc in docs:
                c.execute('UPDATE documents SET latest_version_id=NULL,active_version_id=NULL WHERE id=?', (doc['id'],))
                c.execute('DELETE FROM activity WHERE document_id=?', (doc['id'],))
                c.execute('DELETE FROM documents WHERE id=?', (doc['id'],))
            for asset in assets:
                if not c.execute('SELECT 1 FROM document_versions WHERE asset_id=?', (asset['id'],)).fetchone():
                    c.execute('DELETE FROM raw_assets WHERE id=?', (asset['id'],)); paths.append(asset['object_key'])
            self.db.activity(c, owner, 'source_deleted', 'Sumber privat dan arsip koleksinya dihapus: ' + source['name'])
        for key in paths: self.db.objects.delete(key)
