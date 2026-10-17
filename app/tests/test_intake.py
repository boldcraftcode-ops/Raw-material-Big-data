import hashlib
import io
import json
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

A={'X-Workspace-Token':'A'*64};B={'X-Workspace-Token':'B'*64}

@pytest.fixture
def client(app_factory):
    app=app_factory(seed_demo=False,start_worker=False,seed_sources=False)
    with TestClient(app) as c: yield c

def flush(client):
    for _ in range(100):
        if not client.app.state.service.process_next(): return
    raise AssertionError('Jobs not drained')

def archive(c, payload=b'{"material":"karet alam","sensor":42}', name='sensor.json', headers=A, **meta):
    r=c.post('/api/uploads',headers=headers,files={'file':(name,payload)},data={'consent':'true','intake_mode':'archive',**meta})
    assert r.status_code==202,r.text
    flush(c)
    return c.get('/api/versions/'+r.json()['version']['id'],headers=headers).json()

@pytest.mark.parametrize('name,payload,expected',[
    ('sensor.json',b'{"material":"karet alam","humidity":75}', 'indexed'),
    ('sensor.ndjson',b'{"material":"karet alam"}\n{"temperature":26}\n', 'indexed'),
    ('pasokan.xml',b'<rubber><supplier>Contoh Alam</supplier></rubber>', 'indexed'),
    ('laporan.md','Catatan mutu karet alam\nKKK dinyatakan 60%.'.encode(), 'indexed'),
    ('unknown.bin',b'\x00\x01\xff\xfeRAW-karet', 'raw_only'),
    ('do-not-execute.sh',b'#!/bin/sh\necho NEVER_EXECUTE\n', 'indexed'),
    ('bad.json',b'{broken-json-but-keep-original', 'extraction_failed'),
    ('external-entity.xml',b'<!DOCTYPE rubber [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><rubber>&xxe;</rubber>', 'extraction_failed'),
    ('active.html',b'<html><script>throw Error("NEVER_EXECUTE")</script><p>Natural rubber</p></html>', 'indexed'),
    ('not-a-pdf.pdf',b'%PDF-1.7\nmalformed-but-retained', 'extraction_failed'),
])
def test_all_formats_preserved_with_honest_extraction(client,name,payload,expected):
    v=archive(client,payload,name,category='quality',context='Mutu bahan baku karet alam')
    assert v['status']=='archived' and v['parsed_meta']['extraction_status']==expected
    assert v['sha256']==hashlib.sha256(payload).hexdigest()
    assert client.get('/api/versions/'+v['id']+'/raw',headers=A).content==payload
    assert v['intake_meta']['scope']=='natural_rubber_declared'
    assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==0
    assert client.get('/api/versions/'+v['id']+'/raw',headers=B).status_code==404
    assert client.get('/api/versions/'+v['id']+'/content',headers=B).status_code==404
    if name=='active.html':
        text=client.get('/api/versions/'+v['id']+'/content',headers=A).json()['text']
        assert 'Natural rubber' in text and 'NEVER_EXECUTE' not in text
    if name=='external-entity.xml':
        assert 'root:' not in client.get('/api/versions/'+v['id']+'/content',headers=A).text


def test_encrypted_pdf_raw_not_password_guessed(client):
    w=PdfWriter();w.add_blank_page(100,100);w.encrypt('not-shared-with-server');f=io.BytesIO();w.write(f)
    v=archive(client,f.getvalue(),'encrypted.pdf')
    assert v['parsed_meta']['extraction_status']=='raw_only'
    assert 'terenkripsi' in ' '.join(v['parsed_meta']['warnings'])


def test_archive_table_not_forced_to_purchase_schema(client):
    v=archive(client,b'kebun,kelembapan\nContoh,75\n','kelembapan.csv',category='weather')
    assert v['status']=='archived' and not v['parsed_meta']['sheets']
    r=client.get('/api/archives?dataset=live&q=kelembapan',headers=A).json()
    assert r['total']==1 and 'Contoh' in r['items'][0]['excerpt']
    assert client.get('/api/archives?dataset=live&q=kelembapan',headers=B).json()['total']==0
    assert client.post('/api/versions/'+v['id']+'/mapping',headers=A,json={'sheet':'CSV','fields':{},'options':{},'scope_confirmed':True}).status_code==400


def test_raw_versions_dedup_receipts_and_metadata_retained(client):
    one=archive(client,b'raw-rubber-v1','notes.txt',context='Penerimaan satu')
    duplicate=archive(client,b'raw-rubber-v1','notes.txt',context='Konteks akuisisi ulang')
    two=archive(client,b'raw-rubber-v2','notes.txt',context='Revisi isi')
    assert one['id']==duplicate['id'] and two['version_no']==2
    receipts=client.get('/api/versions/'+one['id']+'/acquisitions',headers=A).json()
    assert receipts['total']==2 and any(r['metadata'].get('context')=='Konteks akuisisi ulang' for r in receipts['items'])
    assert client.get('/api/versions/'+one['id']+'/raw',headers=A).content==b'raw-rubber-v1'
    # A provider can revert a snapshot to old bytes; re-acquisition remains visible, no third blob.
    again=archive(client,b'raw-rubber-v1','notes.txt')
    assert again['id']==one['id'] and again['is_active']
    docs=client.get('/api/documents?dataset=live',headers=A).json()
    assert len(docs[0]['versions'])==2


def test_archive_same_blob_different_document_and_owner(client):
    one=archive(client,b'karet-natural','a.txt')
    two=archive(client,b'karet-natural','b.txt')
    other=archive(client,b'karet-natural','a.txt',headers=B)
    assert len({one['id'],two['id'],other['id']})==3
    with client.app.state.db.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM raw_assets').fetchone()[0]==2


def test_literal_archive_search_and_paged_content(client):
    v=archive(client,('Karet awal. '+'x'*25000+' akhir.').encode(),'long.txt')
    assert client.get('/api/archives?dataset=live&q=%25',headers=A).json()['total']==0
    first=client.get('/api/versions/'+v['id']+'/content?limit=100&offset=0',headers=A).json()
    second=client.get('/api/versions/'+v['id']+'/content?limit=100&offset=100',headers=A).json()
    assert len(first['text'])==100 and len(second['text'])==100
    assert first['total_characters']>25000
    assert client.get('/api/archives?dataset=live&q=KARET',headers=A).json()['total']==1


def test_event_stream_exact_bytes_idempotency_and_conflicts(client):
    path='/api/intake/events?stream=warehouse-rubber&category=quality&scope_confirmed=true&rights_confirmed=true'
    body=b'{ "sensor": 17, "material": "rubber" }\n'
    headers={**A,'Content-Type':'application/json','Idempotency-Key':'sensor-batch-0001'}
    one=client.post(path,headers=headers,content=body)
    assert one.status_code==202,one.text
    vid=one.json()['version']['id']
    repeat=client.post(path,headers=headers,content=body)
    assert repeat.status_code==202 and repeat.json()['idempotent_replay']
    assert client.post(path,headers=headers,content=body.replace(b'17',b'18')).status_code==409
    assert client.post(path.replace('warehouse-rubber','different-stream'),headers=headers,content=body).status_code==409
    flush(client)
    assert client.get('/api/versions/'+vid+'/raw',headers=A).content==body
    assert client.get('/api/versions/'+vid+'/acquisitions',headers=A).json()['total']==2
    assert client.get('/api/archives?dataset=live&q=sensor',headers=A).json()['total']==1


def test_event_requires_scope_rights_auth_and_bounded_body(client):
    path='/api/intake/events?stream=sensor'
    assert client.post(path,headers=A,content=b'x').status_code==400
    path+='&scope_confirmed=true&rights_confirmed=true'
    assert client.post(path,content=b'x').status_code==401
    assert client.post(path,headers=A,content=b'x'*(1024*1024+1)).status_code==413
    assert client.post(path.replace('stream=sensor','stream=../unsafe'),headers=A,content=b'x').status_code==400
    assert client.get('/api/documents?dataset=live',headers=A).json()==[]


def test_archive_metadata_validation_and_path_sanitization(client):
    assert client.post('/api/uploads',headers=A,files={'file':('x.txt',b'x')},data={'intake_mode':'archive'}).status_code==400
    for url in ('javascript:alert(1)','https://user:password@example.org/raw','https://example.org/raw?api_key=secret'):
        r=client.post('/api/uploads',headers=A,files={'file':('x.txt',b'x')},data={'intake_mode':'archive','consent':'true','source_uri':url})
        assert r.status_code==400
    v=archive(client,b'natural rubber','../../safe.txt')
    assert v['filename']=='safe.txt'


def test_delete_raw_removes_index_receipts_and_graph(client):
    v=archive(client,b'Rubber raw','delete.txt')
    graph=client.get('/api/graph?dataset=live',headers=A).json()
    assert any(n.get('archive_version_id')==v['id'] for n in graph['nodes'])
    assert client.delete('/api/documents/'+v['document_id'],headers=A).status_code==200
    assert client.get('/api/archives?dataset=live',headers=A).json()['total']==0
    with client.app.state.db.connect() as c:
        for table in ('archive_content','acquisitions','acquisition_details','raw_assets'):
            assert c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


def test_document_history_and_listing_are_bounded_and_paged(client):
    for i in range(22):
        r=client.post('/api/uploads',headers=A,files={'file':('stream.txt',f'natural rubber {i}'.encode())},data={'consent':'true','intake_mode':'archive'})
        assert r.status_code==202
    docs=client.get('/api/documents?dataset=live&limit=1',headers=A).json()
    assert docs[0]['version_count']==22 and len(docs[0]['versions'])==20
    older=client.get('/api/documents/'+docs[0]['id']+'/versions?limit=20&offset=20',headers=A).json()
    assert older['total']==22 and len(older['items'])==2 and older['items'][-1]['version_no']==1
    assert client.get('/api/documents/'+docs[0]['id']+'/versions',headers=B).status_code==404


def test_same_csv_can_be_archived_then_mapped_without_losing_shared_raw(client):
    body=b'tanggal,pemasok,harga\n2026-10-15,QA,15000\n'
    raw=archive(client,body,'rubber.csv')
    r=client.post('/api/uploads',headers=A,files={'file':('rubber.csv',body)},data={'consent':'true'})
    assert r.status_code==202 and not r.json()['duplicate']
    vid=r.json()['version']['id'];flush(client)
    purchase=client.get('/api/versions/'+vid,headers=A).json()
    assert purchase['status']=='awaiting_mapping' and purchase['id']!=raw['id']
    with client.app.state.db.connect() as c:assert c.execute('SELECT COUNT(*) FROM raw_assets').fetchone()[0]==1
    stats=client.get('/api/stats?dataset=live',headers=A).json()
    assert stats['archives']==1 and stats['documents']==2
    assert client.delete('/api/documents/'+raw['document_id'],headers=A).status_code==200
    assert client.get('/api/versions/'+vid+'/raw',headers=A).content==body
