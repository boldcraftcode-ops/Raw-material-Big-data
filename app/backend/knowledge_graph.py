"""Evidence-linked graph projection, not causal inference or supplier geolocation."""
from __future__ import annotations
import hashlib
import json


def extend_graph(db, owner, base):
    nodes = {n['id']: n for n in base['nodes']}
    edges = {e['id']: e for e in base['edges']}
    def ident(prefix, key): return prefix + '_' + hashlib.sha256(key.encode()).hexdigest()[:20]
    def node(key, label, kind, detail, record=None, version=None):
        if key not in nodes:
            nodes[key] = {'id': key, 'label': label, 'type': kind, 'detail': detail, 'count': 0, 'evidence_ids': [], 'record_ids': []}
        n = nodes[key]
        if record:
            n['count'] += 1
            n.setdefault('record_ids', [])
            if len(n['record_ids']) < 5 and record not in n['record_ids']: n['record_ids'].append(record)
        if version: n['archive_version_id'] = version
        return key
    def edge(source, target, kind, label, record=None):
        key = ident('edge', source + target + kind)
        if key not in edges:
            edges[key] = {'id': key, 'source': source, 'target': target, 'kind': kind, 'label': label, 'count': 0, 'evidence_ids': [], 'record_ids': []}
        if record:
            edges[key]['count'] += 1
            if len(edges[key]['record_ids']) < 5 and record not in edges[key]['record_ids']: edges[key]['record_ids'].append(record)
    with db.connect() as c:
        total = c.execute('SELECT COUNT(*) FROM knowledge_records WHERE owner_id=?', (owner,)).fetchone()[0]
        rows = []
        for kind in ('market_price', 'production_stat', 'weather_forecast', 'news_report'):
            rows.extend(c.execute('''SELECT k.id,k.kind,k.title,k.source_id,r.payload,r.version_id,s.name,d.id AS document_id,d.filename
                FROM knowledge_records k JOIN knowledge_revisions r ON r.record_id=k.id AND r.revision=k.current_revision
                JOIN external_sources s ON s.id=k.source_id JOIN document_versions v ON v.id=r.version_id JOIN documents d ON d.id=v.document_id
                WHERE k.owner_id=? AND k.kind=? ORDER BY k.period DESC,k.id LIMIT 60''', (owner, kind)).fetchall())
        raw_count = c.execute('SELECT COUNT(*) FROM documents d JOIN document_versions v ON v.id=d.active_version_id JOIN archive_content a ON a.version_id=v.id WHERE d.owner_id=?', (owner,)).fetchone()[0]
        raw = c.execute('SELECT d.id,d.filename,v.id AS version_id,v.intake_meta FROM documents d JOIN document_versions v ON v.id=d.active_version_id JOIN archive_content a ON a.version_id=v.id WHERE d.owner_id=? ORDER BY d.created_at DESC LIMIT 40', (owner,)).fetchall()
    if rows or raw: node('workspace', 'Karet alam', 'workspace', 'Ruang lingkup yang dinyatakan. Hubungan konteks tidak membuktikan dampak, transaksi, atau asal kebun.')
    for r in rows:
        fields = json.loads(r['payload'])['fields']; rid = r['id']
        src = node('source_' + r['source_id'], r['name'], 'source', 'Sumber eksternal terdaftar. Koneksi berarti data telah diterima, bukan verifikasi independen isi.', rid)
        doc = node(ident('document', r['document_id']), r['filename'], 'document', 'Respons sumber asli tersimpan beserta checksum dan riwayat akuisisi.', rid, r['version_id'])
        label = 'Karet ' + fields['grade'] if r['kind'] == 'market_price' else 'Karet alam'
        mat = node(ident('material', label.lower()), label, 'material', 'Konteks karet alam dari adapter sumber; bukan penyamaan grade atau basis harga.', rid)
        signal = node('record_' + rid, r['title'], 'signal', 'Record eksternal: ' + r['kind'] + '. Buka bukti untuk nilai, periode, status, dan lokasi sumber.', rid)
        edge(src, doc, 'acquired_from', 'Respons dikumpulkan dari sumber', rid)
        edge(doc, signal, 'extracted_from', 'Record diekstrak dari raw', rid)
        edge(signal, mat, 'rubber_context', 'Terkait karet dalam lingkup sumber', rid)
        edge(src, 'workspace', 'monitored_source', 'Sumber yang dipantau')
        if r['kind'] == 'weather_forecast':
            location = fields.get('location', {}); code = location.get('adm4', '')
            loc = node(ident('location', 'bmkg:' + code), location.get('desa', code), 'location', 'Kode adm4 BMKG yang dipantau, bukan kebun atau pemasok terverifikasi.', rid)
            edge(signal, loc, 'forecast_for', 'Prakiraan untuk lokasi ini', rid)
        elif r['kind'] == 'production_stat':
            loc = node(ident('location', 'faostat:' + str(fields.get('area_code'))), fields.get('area', 'Wilayah FAO'), 'location', 'Wilayah statistik FAOSTAT. Tidak membuktikan asal material milik pengguna.', rid)
            edge(signal, loc, 'production_reported_for', 'Produksi dilaporkan untuk wilayah', rid)
    for r in raw:
        doc = node(ident('document', r['id']), r['filename'], 'document', 'Arsip raw. Kemampuan ekstraksi berbeda per format; lingkup karet dinyatakan pada intake.', version=r['version_id'])
        edge(doc, 'workspace', 'raw_archived', 'Raw tersimpan dalam ruang lingkup yang dinyatakan')
    ranking = {'workspace': 0, 'material': 1, 'source': 2, 'document': 3, 'location': 4, 'organization': 5, 'signal': 6}
    selected = sorted(nodes.values(), key=lambda n: (ranking.get(n['type'], 7), -n['count'], n['label']))[:160]
    visible = {n['id'] for n in selected}
    links = [e for e in edges.values() if e['source'] in visible and e['target'] in visible][:400]
    sampled = total > len(rows) or raw_count > len(raw)
    return {**base, 'nodes': selected, 'edges': links, 'total_nodes': len(nodes), 'total_edges': len(edges),
            'entity_count': sum(n['type'] in ('organization', 'material', 'location', 'source') for n in nodes.values()),
            'truncated': base['truncated'] or sampled or len(nodes) > len(selected) or len(edges) > len(links),
            'external_record_count': total, 'sampled_external_records': len(rows),
            'coverage_note': 'Proyeksi maksimum 60 record terbaru per jenis dan 40 arsip raw; layar maksimum 160 node/400 relasi. Pencarian memuat seluruh indeks.' if sampled else ''}
