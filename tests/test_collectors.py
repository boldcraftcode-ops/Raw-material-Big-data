"""Deterministic source fixtures. Live endpoint proof is recorded separately, not faked here."""
import csv
import hashlib
import io
import json
import threading
from zipfile import ZipFile, ZIP_DEFLATED

import httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.collector_http import PublicHTTP,FetchError
from backend.collectors import after

A={'X-Workspace-Token':'A'*64};B={'X-Workspace-Token':'B'*64}

def workbook(price=2.1,unit='($/kg)'):
    w=Workbook();s=w.active;s.title='Monthly Prices';s.append(['World Bank fixture'])
    s.append([None,'Rubber, TSR20 **','Rubber, RSS3']);s.append([None,unit,unit])
    s.append(['1960M01','…',0.5]);s.append(['2026M09',1.8,price])
    f=io.BytesIO();w.save(f);return f.getvalue()

def bulk():
    f=io.StringIO();w=csv.writer(f)
    w.writerow(['Area Code','Area Code (M49)','Area','Item Code','Item','Element Code','Element','Year','Unit','Value','Flag','Note'])
    w.writerow(['101',"'360",'Indonesia','836','Natural rubber in primary forms','5510','Production','2024','t','2345678.0','E','fixture estimate'])
    w.writerow(['216',"'764",'Thailand','836','Natural rubber in primary forms','5510','Production','2024','t','4000000','A',''])
    w.writerow(['44',"'170",'Colombia','836','Natural rubber in primary forms','5510','Production','2024','t','','M','missing'])
    w.writerow(['101',"'360",'Indonesia','15','Wheat','5510','Production','2024','t','50','A',''])
    w.writerow(['101',"'360",'Indonesia','836','Natural rubber in primary forms','5312','Area harvested','2024','ha','100','A',''])
    out=io.BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        z.writestr('Production_Crops_Livestock_E_All_Data_(Normalized).csv',f.getvalue())
        z.writestr('Production_Crops_Livestock_E_Flags.csv','Flag,Description\nA,Official figure\nE,Estimated value\nM,Missing\n')
    return out.getvalue()

class Fixtures:
    def __init__(self):self.calls=[];self.price=2.1;self.unit='($/kg)';self.fail=None;self.not_modified=False
    def handler(self,request):
        self.calls.append(request)
        if self.fail: return httpx.Response(self.fail,headers={'Retry-After':'120'},text='fixture downtime')
        if self.not_modified and request.headers.get('if-none-match'):return httpx.Response(304)
        path=request.url.path
        if request.url.host=='www.worldbank.org':
            body=b'<html><a href="https://thedocs.worldbank.org/en/doc/fixture/related/CMO-Historical-Data-Monthly.xlsx">Monthly</a></html>';mime='text/html'
        elif path.endswith('.xlsx'):body=workbook(self.price,self.unit);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif path.endswith('datasets_E.xml'):
            body=b'<Datasets><Dataset><DatasetCode>QCL</DatasetCode><DateUpdate>2025-12-31T00:00:00</DateUpdate><FileRows>5</FileRows><FileLocation>https://bulks-faostat.fao.org/production/qcl_fixture.zip</FileLocation></Dataset></Datasets>';mime='application/xml'
        elif path.endswith('.zip'):body=bulk();mime='application/zip'
        elif request.url.host=='api.bmkg.go.id':
            body=json.dumps({'lokasi':{'adm4':'12.71.01.1001','desa':'Pasar Baru','kotkab':'Kota Medan','timezone':'Asia/Jakarta'},'data':[{'lokasi':{'adm4':'12.71.01.1001'},'cuaca':[[{'utc_datetime':'2026-10-16 00:00:00','analysis_date':'2026-10-15T12:00:00','local_datetime':'2026-10-16 07:00:00','t':27,'hu':80,'ws':3.5,'weather_desc':'Berawan','weather':3}]]}]}).encode();mime='application/json'
        elif request.url.host=='news.google.com':
            body=b'<rss><channel><title>Fixture rubber news</title><item><title>=Natural rubber exports in fixture</title><link>https://example.org/rubber-news</link><guid>rubber-test-001</guid><pubDate>Thu, 15 Oct 2026 10:00:00 GMT</pubDate><source url="https://example.org">Fixture Publisher</source></item></channel></rss>';mime='application/rss+xml'
        elif request.url.host=='api.gdeltproject.org':body=b'{"articles":[]}';mime='application/json'
        else:raise AssertionError('Unexpected URL: '+str(request.url))
        return httpx.Response(200,content=body,headers={'Content-Type':mime,'ETag':'"fixture-v1"'})

@pytest.fixture
def system(app_factory):
    fixtures=Fixtures();http=PublicHTTP(httpx.MockTransport(fixtures.handler),validate_dns=False)
    app=app_factory(seed_demo=False,start_worker=False,seed_sources=False,collector_http=http)
    with TestClient(app) as client:yield client,app.state.collectors,fixtures

def create(c,adapter='worldbank',**values):
    r=c.post('/api/sources',headers=A,json={'adapter':adapter,**values})
    assert r.status_code==201,r.text
    return r.json()

def run(manager,source_id):
    with manager.db.connect() as c:c.execute('UPDATE external_sources SET next_due_at=?,last_attempt_at=NULL WHERE id=?',(after(-3600),source_id))
    assert manager.schedule_due()==1
    assert manager.process_next()

@pytest.mark.parametrize('adapter,kind,count',[('worldbank','market_price',3),('faostat_bulk','production_stat',2),('bmkg','weather_forecast',1),('news_rss','news_report',1)])
def test_each_adapter_real_pipeline_and_evidence_contract(system,adapter,kind,count):
    c,m,f=system;s=create(c,adapter);run(m,s['id'])
    r=c.get('/api/knowledge?dataset=live',headers=A).json()
    assert r['total']==count
    assert all(x['kind']==kind for x in r['items'])
    source=next(s for s in c.get('/api/sources',headers=A).json()['items'] if s['adapter']==adapter)
    assert source['last_status'] in ('succeeded','partial') and source['last_success_at']
    ev=c.get('/api/knowledge/'+r['items'][0]['id'],headers=A).json()
    assert ev['pointer'] and ev['sha256'] and ev['history'][0]['revision']==1
    raw=c.get('/api/versions/'+ev['version_id']+'/raw',headers=A)
    assert hashlib.sha256(raw.content).hexdigest()==ev['sha256']
    assert c.get('/api/knowledge/'+ev['id'],headers=B).status_code==404
    assert c.get('/api/knowledge?dataset=live',headers=B).json()['total']==0
    if adapter=='faostat_bulk':
        indonesia=next(r for r in r['items'] if r['fields']['area']=='Indonesia')
        assert indonesia['fields']['flag']=='E' and indonesia['fields']['production']=='2345678.0'
        detail=c.get('/api/runs/'+ev['run_id'],headers=A).json()
        assert detail['coverage']['source_missing_values']==1 and detail['rejected_records']==0
    if adapter=='worldbank':
        detail=c.get('/api/runs/'+ev['run_id'],headers=A).json()
        assert detail['coverage']['source_missing_values']==1 and detail['rejected_records']==0
    if adapter=='bmkg':
        assert ev['fields']['issued_at_utc']=='2026-10-15T12:00:00+00:00'
        assert ev['fields']['valid_time_utc']=='2026-10-16T00:00:00+00:00'
        assert ev['fields']['data_kind']=='forecast_not_observation'
    if adapter=='news_rss':
        assert ev['fields']['confirmation_status']=='unverified_report'
        assert not ev['fields']['full_article_collected']
        assert all(request.url.host=='news.google.com' for request in f.calls)
        assert "'=Natural rubber" in c.get('/api/knowledge/export.csv?dataset=live',headers=A).text


def test_repeated_fetch_304_no_duplicate_facts_then_revision(system):
    c,m,f=system;s=create(c);run(m,s['id'])
    records=c.get('/api/knowledge?dataset=live',headers=A).json()['items']
    target=next(r for r in records if r['fields']['grade']=='RSS3' and r['period']=='2026-09')
    f.not_modified=True;run(m,s['id'])
    latest=c.get('/api/sources',headers=A).json()['items'][0]['latest_run']
    assert latest['unchanged_records']==3 and latest['new_records']==0 and latest['revised_records']==0
    detail=c.get('/api/runs/'+latest['id'],headers=A).json()
    assert all(fetch['http_status']==304 for fetch in detail['fetches'])
    ev=c.get('/api/knowledge/'+target['id'],headers=A).json()
    assert len(ev['history'])==1
    assert c.get('/api/versions/'+target['version_id']+'/acquisitions',headers=A).json()['total']==2
    f.not_modified=False;f.price=2.2;run(m,s['id'])
    newer=c.get('/api/knowledge/'+target['id'],headers=A).json()
    assert newer['current_revision']==2 and newer['fields']['price']=='2.2'
    assert newer['version_id']!=target['version_id'] and len(newer['history'])==2
    assert c.get('/api/knowledge?dataset=live',headers=A).json()['total']==3
    with m.db.connect() as db:assert db.execute('SELECT COUNT(*) FROM knowledge_revisions').fetchone()[0]==4


def test_schema_failure_archived_but_not_published_retry_preserves_success(system):
    c,m,f=system;s=create(c);run(m,s['id']);old=c.get('/api/knowledge?dataset=live',headers=A).json()
    f.unit='USD/tonne';f.price=9;run(m,s['id'])
    source=c.get('/api/sources',headers=A).json()['items'][0]
    assert source['last_status']=='failed' and source['consecutive_failures']==1 and source['last_success_at']
    latest=c.get('/api/runs/'+source['latest_run']['id'],headers=A).json()
    assert latest['resources']==2 and len(latest['fetches'])==2 and 'Unit' in latest['error']
    after_failure=c.get('/api/knowledge?dataset=live',headers=A).json()
    assert after_failure['items']==old['items']
    f.unit='($/kg)';f.price=2.3;run(m,s['id'])
    source=c.get('/api/sources',headers=A).json()['items'][0]
    assert source['last_status']=='succeeded' and source['consecutive_failures']==0


def test_http_failure_logged_and_retry_backoff(system):
    c,m,f=system;s=create(c);f.fail=429;run(m,s['id'])
    source=c.get('/api/sources',headers=A).json()['items'][0]
    assert source['last_status']=='failed' and 'HTTP 429' in source['last_error']
    detail=c.get('/api/runs/'+source['latest_run']['id'],headers=A).json()
    assert detail['fetches'][0]['http_status']==429 and not detail['fetches'][0]['version_id']
    assert source['next_due_at']>source['last_attempt_at'] and source['consecutive_failures']==1
    assert not m.process_next() and c.get('/api/knowledge?dataset=live',headers=A).json()['total']==0
    assert m.schedule_due()==0
    f.fail=None;run(m,s['id'])
    assert c.get('/api/sources',headers=A).json()['items'][0]['last_status']=='succeeded'


def test_schedule_pause_resume_one_pending_manual_cooldown(system):
    c,m,f=system;s=create(c,enabled=False)
    assert m.schedule_due()==0
    assert c.patch('/api/sources/'+s['id'],headers=A,json={'enabled':True}).status_code==200
    assert m.schedule_due()==1 and m.schedule_due()==0
    first=c.post('/api/sources/'+s['id']+'/run',headers=A)
    assert first.status_code==202 and first.json()['reused']
    assert c.patch('/api/sources/'+s['id'],headers=A,json={'enabled':False}).status_code==400
    assert m.process_next()
    assert c.post('/api/sources/'+s['id']+'/run',headers=A).status_code==400
    assert c.patch('/api/sources/'+s['id'],headers=A,json={'enabled':False}).status_code==200
    assert m.schedule_due()==0
    assert len(c.get('/api/sources/'+s['id']+'/runs',headers=A).json()['items'])==1


def test_stale_lease_recovered_not_reclaimed_before_expiry(system):
    c,m,f=system;s=create(c);assert m.schedule_due()==1
    with m.db.connect() as db:
        db.execute("UPDATE collection_runs SET status='running',lease_until=?",(after(1200),))
    assert m.recover_expired()==0
    with m.db.connect() as db:db.execute('UPDATE collection_runs SET lease_until=?',(after(-30),))
    assert m.recover_expired()==1
    source=c.get('/api/sources',headers=A).json()['items'][0]
    assert source['latest_run']['status']=='interrupted' and source['consecutive_failures']==1
    run(m,s['id'])
    assert c.get('/api/knowledge?dataset=live',headers=A).json()['total']==3


def test_source_auth_allowlist_and_readonly_public_separation(system):
    c,m,f=system;s=create(c)
    assert c.get('/api/sources',headers=B).json()['items']==[]
    assert c.patch('/api/sources/'+s['id'],headers=B,json={'enabled':False}).status_code==404
    assert c.post('/api/sources/'+s['id']+'/run',headers=B).status_code==404
    assert c.post('/api/sources',json={'adapter':'worldbank'}).status_code==401
    assert c.post('/api/sources',headers=A,json={'adapter':'worldbank','config':{'url':'https://127.0.0.1'}}).status_code==400
    assert c.post('/api/sources',headers=A,json={'adapter':'bmkg','config':{'adm4':'invalid'}}).status_code==400
    assert c.post('/api/sources',headers=A,json={'adapter':'news_rss','interval_seconds':1}).status_code==400
    m.seed();public=next(x for x in c.get('/api/sources',headers=B).json()['items'] if x['is_public'])
    assert c.patch('/api/sources/'+public['id'],headers=A,json={'enabled':False}).status_code==404
    assert c.delete('/api/sources/'+public['id'],headers=A).status_code==404


def test_source_deletion_removes_its_raw_and_knowledge(system):
    c,m,f=system;s=create(c);run(m,s['id'])
    # Drain extraction queue before delete.
    while c.app.state.service.process_next():pass
    item=c.get('/api/knowledge?dataset=live',headers=A).json()['items'][0]
    version=c.get('/api/versions/'+item['version_id'],headers=A).json()
    assert c.delete('/api/documents/'+version['document_id'],headers=A).status_code==400
    assert c.delete('/api/sources/'+s['id'],headers=A).status_code==200
    assert c.get('/api/knowledge?dataset=live',headers=A).json()['total']==0
    assert c.get('/api/versions/'+version['id']+'/raw',headers=A).status_code==404
    with m.db.connect() as db:
        for table in ('external_sources','knowledge_records','knowledge_revisions','source_fetches','collection_runs','raw_assets'):
            assert db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]==0


def test_graph_links_real_records_and_raw(system):
    c,m,f=system;s=create(c);run(m,s['id'])
    graph=c.get('/api/graph?dataset=live',headers=A).json()
    assert any(n['type']=='source' for n in graph['nodes'])
    assert any(e.get('record_ids') for e in graph['edges'])
    node=next(n for n in graph['nodes'] if n.get('record_ids'))
    assert c.get('/api/knowledge/'+node['record_ids'][0],headers=A).status_code==200
    assert not any(e['kind'] in ('causes','supplies') for e in graph['edges'])


def test_background_collection_works_without_manual_run_or_browser(app_factory):
    f=Fixtures();http=PublicHTTP(httpx.MockTransport(f.handler),validate_dns=False)
    app=app_factory(seed_demo=False,start_worker=True,seed_sources=False,collector_http=http)
    event=threading.Event();m=app.state.collectors;publish=m._publish
    def observed(*args,**kwargs):publish(*args,**kwargs);event.set()
    m._publish=observed
    with TestClient(app) as c:
        create(c)
        assert event.wait(10),'Automatic scheduler did not publish'
        assert c.get('/api/knowledge?dataset=live',headers=A).json()['total']==3


def test_disabled_worker_reports_truthfully(system):
    c,m,f=system;m.enabled=False;m.seed()
    health=c.get('/api/health').json()
    assert health['external_collectors_active']==0 and not health['collector_worker_running']
    assert m.schedule_due()==0 and not m.process_next()
    source=c.get('/api/sources',headers=A).json()['items'][0]
    assert not source['worker_enabled']
    assert c.post('/api/sources/'+source['id']+'/run',headers=A).status_code==400

@pytest.mark.parametrize('url',['http://www.worldbank.org/a','https://127.0.0.1/raw','https://169.254.169.254/latest/meta-data','https://user:pass@www.worldbank.org/','https://www.worldbank.org:444/','https://unapproved.example.org/feed'])
def test_http_refuses_unsafe_urls(url):
    http=PublicHTTP(validate_dns=False)
    with pytest.raises(FetchError):http.get(url)


def test_http_redirect_revalidated_and_private_dns_denied(monkeypatch):
    http=PublicHTTP(httpx.MockTransport(lambda _:httpx.Response(302,headers={'location':'http://169.254.169.254/latest'})),validate_dns=False)
    with pytest.raises(FetchError):http.get('https://www.worldbank.org/public')
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(FetchError):PublicHTTP().validate('https://www.worldbank.org/public')


def test_http_bounds_declared_and_streamed_body():
    for headers in ({'Content-Length':'1000'},{}):
        http=PublicHTTP(httpx.MockTransport(lambda _:httpx.Response(200,stream=httpx.ByteStream(b'x'*1000),headers=headers)),validate_dns=False)
        with pytest.raises(FetchError):http.get('https://www.worldbank.org/public',max_bytes=10)


def test_durable_host_budget_enforces_global_bmkg_spacing(system):
    c,m,f=system;delays=[];m._sleep=delays.append
    url='https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=12.71.01.1001'
    m.reserve_host_slot(url);m.reserve_host_slot(url);m.reserve_host_slot(url)
    assert len(delays)==2 and delays[0]>.9 and delays[1]>1.9
    with m.db.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM host_throttles').fetchone()[0]==1


def test_record_revision_pagination_and_private_ownership(system):
    c,m,f=system;s=create(c);run(m,s['id'])
    f.price=2.2;run(m,s['id'])
    row=next(r for r in c.get('/api/knowledge?dataset=live',headers=A).json()['items'] if r['fields'].get('price')=='2.2')
    path='/api/knowledge/'+row['id']+'/revisions'
    page=c.get(path+'?limit=1&offset=1',headers=A).json()
    assert page['total']==2 and len(page['items'])==1 and page['items'][0]['revision']==1
    assert page['items'][0]['payload']['fields']['price']=='2.1'
    assert c.get(path,headers=B).status_code==404
    assert c.get(path+'?limit=101',headers=A).status_code==422
