import io
import json
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from backend.app import create_app

A={'X-Workspace-Token':'A'*64}
B={'X-Workspace-Token':'B'*64}
CSV=b'tanggal,pemasok,material,harga,mata_uang,unit,basis_berat,kkk_persen\n2026-10-15,Pemasok Contoh,Bokar,15000,IDR,kg,basah,60\n2026-10-15,Pemasok Contoh,Bokar,14000,IDR,kg,basah,120\n'

@pytest.fixture
def client(app_factory):
 app=app_factory(seed_demo=False,start_worker=False,seed_sources=False)
 with TestClient(app) as client: yield client

def flush(client):
 for _ in range(100):
  if not client.app.state.service.process_next():return
 raise AssertionError('Jobs did not drain')

def upload(client,data=CSV,name='pembelian.csv',headers=A):
 r=client.post('/api/uploads',headers=headers,files={'file':(name,data)},data={'consent':'true'})
 assert r.status_code==202,r.text
 return r.json()

def mapping(client,vid,headers=A):
 preview=client.get(f'/api/versions/{vid}/preview',headers=headers).json()
 return {'sheet':preview['sheet'],'fields':preview['suggested_mapping'],'options':{'number_format':'id-ID','date_format':'iso','drc_scale':'percent','default_price_kind':'dilaporkan'},'scope_confirmed':True}

def publish(client,data=CSV,name='pembelian.csv',headers=A):
 result=upload(client,data,name,headers);vid=result['version']['id'];flush(client)
 m=mapping(client,vid,headers)
 r=client.post(f'/api/versions/{vid}/mapping',headers=headers,json=m)
 assert r.status_code==202,r.text
 flush(client)
 return vid,m

def test_complete_pipeline(client):
 vid,_=publish(client)
 stats=client.get('/api/stats?dataset=live',headers=A).json()
 assert stats['observations']==1 and stats['issues']==1 and stats['documents']==1
 obs=client.get('/api/observations?dataset=live',headers=A).json()['items'][0]
 assert obs['dry_equivalent']=='25000' and not obs['is_demo']
 ev=client.get('/api/evidence/'+obs['id'],headers=A).json()
 assert ev['row_no']==2 and ev['sheet']=='CSV' and ev['mapping_rev']==1 and ev['is_active']
 assert len(ev['sha256'])==64 and ev['raw_values'][3]['value']=='15000'
 raw=client.get(f'/api/versions/{vid}/raw',headers=A)
 assert raw.content==CSV and 'attachment' in raw.headers['content-disposition']
 graph=client.get('/api/graph?dataset=live',headers=A).json()
 assert graph['nodes'] and any(e['evidence_ids'] for e in graph['edges'])
 assert not any('supplies' in e['kind'] for e in graph['edges'])

def test_upload_and_mapping_idempotent(client):
 vid,m=publish(client)
 duplicate=upload(client)
 assert duplicate['duplicate'] and duplicate['version']['id']==vid
 r=client.post(f'/api/versions/{vid}/mapping',headers=A,json=m)
 assert r.json()['reused']
 flush(client)
 assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==1
 with client.app.state.db.connect() as c:
  assert c.execute('SELECT COUNT(*) FROM acquisitions').fetchone()[0]==2
  assert c.execute('SELECT COUNT(*) FROM observations').fetchone()[0]==1

def test_new_version_switches_only_after_validation(client):
 old,_=publish(client)
 new=upload(client,CSV.replace(b'15000',b'16000'))['version']['id']
 assert old!=new
 before=client.get('/api/observations?dataset=live',headers=A).json()['items'][0]
 assert before['price']=='15000'
 flush(client)
 m=mapping(client,new)
 client.post(f'/api/versions/{new}/mapping',headers=A,json=m);flush(client)
 after=client.get('/api/observations?dataset=live',headers=A).json()
 assert after['total']==1 and after['items'][0]['price']=='16000'
 assert not client.get('/api/evidence/'+before['id'],headers=A).json()['is_active']
 assert client.get(f'/api/versions/{old}/raw',headers=A).content==CSV
 assert len(client.get('/api/documents?dataset=live',headers=A).json()[0]['versions'])==2

def test_mapping_revision_and_restoration(client):
 vid,m=publish(client)
 second=json.loads(json.dumps(m));second['fields']['drc']=None
 r=client.post(f'/api/versions/{vid}/mapping',headers=A,json=second)
 assert r.json()['revision']==2;flush(client)
 assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==2
 client.post(f'/api/versions/{vid}/mapping',headers=A,json=m);flush(client)
 assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==1
 with client.app.state.db.connect() as c:
  assert c.execute('SELECT COUNT(*) FROM mappings').fetchone()[0]==2

def test_owner_isolation_all_surfaces(client):
 vid,_=publish(client)
 obs=client.get('/api/observations?dataset=live',headers=A).json()['items'][0]
 assert client.get('/api/stats?dataset=live',headers=B).json()['observations']==0
 assert client.get('/api/documents?dataset=live',headers=B).json()==[]
 assert client.get('/api/graph?dataset=live',headers=B).json()['nodes']==[]
 assert client.get('/api/issues?dataset=live',headers=B).json()==[]
 assert client.get('/api/activity?dataset=live',headers=B).json()==[]
 for path in [f'/api/versions/{vid}',f'/api/versions/{vid}/raw',f'/api/versions/{vid}/preview','/api/evidence/'+obs['id']]:
  assert client.get(path,headers=B).status_code==404
 assert client.post(f'/api/versions/{vid}/mapping',headers=B,json=mapping(client,vid)).status_code==404
 assert client.delete('/api/documents/'+obs['document_id'],headers=B).status_code==404
 assert client.get('/api/stats?dataset=live').status_code==401

def test_hash_dedup_scoped_by_owner(client):
 one=upload(client,headers=A)
 two=upload(client,headers=B)
 assert not two['duplicate'] and one['version']['id']!=two['version']['id']

def test_delete_removes_versions_rows_and_raw(client):
 vid,_=publish(client)
 docs=client.get('/api/documents?dataset=live',headers=A).json()
 response=client.delete('/api/documents/'+docs[0]['id'],headers=A)
 assert response.status_code==200,response.text
 assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==0
 assert client.get(f'/api/versions/{vid}/raw',headers=A).status_code==404
 assert not list(client.app.state.db.raw.glob('*/*'))
 with client.app.state.db.connect() as c:
  for table in ['observations','issues','raw_rows','mappings','jobs','raw_assets','acquisitions']:
   assert c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0

def test_unsupported_and_consent(client):
 assert client.post('/api/uploads',headers=A,files={'file':('data.pdf',b'%PDF-1.0')},data={'consent':'true'}).status_code==400
 assert client.post('/api/uploads',headers=A,files={'file':('data.csv',CSV)}).status_code==400

def test_invalid_file_failed_not_silent_success(client):
 result=upload(client,b'tanggal,pemasok\n')
 flush(client)
 v=client.get('/api/versions/'+result['version']['id'],headers=A).json()
 assert v['status']=='failed' and 'tidak ada baris' in v['error']

def test_xlsx_multi_sheet_and_native_date(client):
 from datetime import datetime
 wb=Workbook();ws=wb.active;ws.title='Kosong';ws.append(['tanggal','pemasok'])
 ws=wb.create_sheet('Pembelian');ws.append(['tanggal','pemasok','material','harga','mata_uang','unit','basis_berat','kkk_persen']);ws.append([datetime(2026,10,15),'Contoh','Bokar',15000,'IDR','kg','basah',60])
 out=io.BytesIO();wb.save(out)
 vid=upload(client,out.getvalue(),'contoh.xlsx')['version']['id'];flush(client)
 p=client.get(f'/api/versions/{vid}/preview?sheet=Pembelian',headers=A).json()
 assert len(p['sheets'])==2 and p['row_count']==1
 config={'sheet':'Pembelian','fields':p['suggested_mapping'],'options':{'number_format':'id-ID','date_format':'dmy','drc_scale':'percent'},'scope_confirmed':True}
 assert client.post(f'/api/versions/{vid}/mapping',headers=A,json=config).status_code==202;flush(client)
 assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==1

def test_search_literal_and_export_formula_safety(client):
 data=CSV.replace(b'Pemasok Contoh',b'=Contoh')
 publish(client,data)
 export=client.get('/api/observations/export.csv?dataset=live',headers=A)
 assert export.status_code==200 and "'=Contoh" in export.text
 assert client.get('/api/observations?dataset=live&q=%25',headers=A).json()['total']==0
 assert client.get('/api/observations?dataset=live&q=Contoh',headers=B).json()['total']==0

def test_recover_durable_job(client):
 upload(client)
 with client.app.state.db.connect() as c: c.execute("UPDATE jobs SET status='running'")
 client.app.state.service.recover();flush(client)
 assert client.get('/api/documents?dataset=live',headers=A).json()[0]['latest']['status']=='awaiting_mapping'

def test_demo_separated_and_readonly(app_factory):
 app=app_factory(seed_demo=True,start_worker=False,seed_sources=False)
 with TestClient(app) as client:
  assert client.get('/api/stats?dataset=demo',headers=A).json()['observations']==36
  assert client.get('/api/stats?dataset=live',headers=A).json()['observations']==0
  doc=client.get('/api/documents?dataset=demo',headers=A).json()[0]
  vid=doc['latest']['id']
  assert client.post(f'/api/versions/{vid}/mapping',headers=A,json=mapping(client,vid)).status_code==404
  assert client.delete('/api/documents/'+doc['id'],headers=A).status_code==404


def test_request_size_rejected_before_multipart_spooling(client):
 r=client.post('/api/uploads',headers={**A,'Content-Length':str(12*1024*1024)},content=b'x')
 assert r.status_code==413
 assert client.get('/api/documents?dataset=live',headers=A).json()==[]

def test_chunked_request_limit():
 import asyncio
 from backend.limits import UploadBodyLimit
 from starlette.formparsers import MultiPartException
 async def run():
  async def downstream(scope,receive,send): await receive()
  async def receive(): return {'type':'http.request','body':b'12345','more_body':False}
  async def send(message): pass
  wrapped=UploadBodyLimit(downstream,limit=4)
  with pytest.raises(MultiPartException):
   await wrapped({'type':'http','path':'/api/uploads','method':'POST','headers':[]},receive,send)
 asyncio.run(run())
