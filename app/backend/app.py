from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import io
import os
import re
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .db import Database
from .domain import FIELDS
from .limits import UploadBodyLimit
from .service import Service, MAX_UPLOAD
from .archive import CATEGORIES, MAX_FILE
from .collectors import Collectors
from .adapters import CATALOG
from .knowledge_graph import extend_graph

BASE=Path(__file__).resolve().parents[1]


class MappingBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sheet: str
    fields: dict[str,str | None]
    options: dict
    scope_confirmed: bool
    header_row: int | None = Field(None,ge=1,le=50)
    header_depth: int = Field(1,ge=1,le=2)


class RememberMappingBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int = Field(ge=1)


class ColumnReviewBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    column_id: str = Field(max_length=12)
    role: str = Field(max_length=40)
    datatype: str = Field(max_length=40)

class TableReviewBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    table_id: str = Field(max_length=40)
    category: str = Field(max_length=40)
    columns: list[ColumnReviewBody] = Field(min_length=1,max_length=64)

class BreakdownReviewBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    profile_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirmed: bool
    tables: list[TableReviewBody] = Field(min_length=1,max_length=20)


class SourceBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    adapter: str
    config: dict = {}
    name: str | None = None
    interval_seconds: int | None = None
    enabled: bool = True

class SourcePatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    config: dict | None = None
    name: str | None = None
    interval_seconds: int | None = None
    enabled: bool | None = None


def create_app(data_dir=None,seed_demo=True,start_worker=True,*,database_url=None,seed_sources=True,enable_collectors=None,collector_http=None):
    db=Database(Path(data_dir or os.environ.get('RUBBER_DATA_DIR',BASE/'runtime')),url=database_url)
    service=Service(db)
    collectors=Collectors(db,service,http=collector_http,enabled=enable_collectors)
    if seed_sources: collectors.seed()
    @asynccontextmanager
    async def lifespan(app):
        service.recover()
        if seed_demo: await asyncio.to_thread(service.seed_demo)
        async def worker():
            while True:
                try:
                    done=await asyncio.to_thread(service.process_next)
                    if not done: await asyncio.sleep(.35)
                except asyncio.CancelledError: raise
                except Exception:
                    # A transient DB issue must not silently kill the worker.
                    await asyncio.sleep(1)
        async def collector_worker():
            while True:
                try:
                    await asyncio.to_thread(collectors.schedule_due)
                    done=await asyncio.to_thread(collectors.process_next)
                    if not done: await asyncio.sleep(2)
                except asyncio.CancelledError: raise
                except Exception: await asyncio.sleep(2)
        task=asyncio.create_task(worker()) if start_worker else None
        collection_task=asyncio.create_task(collector_worker()) if start_worker and collectors.enabled else None
        app.state.collector_task=collection_task
        yield
        for running in (task,collection_task):
            if running:
                running.cancel()
                with contextlib.suppress(asyncio.CancelledError): await running
    app=FastAPI(title='Rubber Intelligence',version='0.2.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url='/api/openapi.json')
    app.state.service=service
    app.state.db=db
    app.state.collectors=collectors
    app.add_middleware(UploadBodyLimit)

    @app.middleware('http')
    async def headers(request:Request,call_next):
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.exception_handler(ValueError)
    async def invalid(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)
    @app.exception_handler(LookupError)
    async def missing(request,exc): return JSONResponse({'detail':str(exc)},status_code=404)

    def owner(request:Request):
        token=request.headers.get('x-workspace-token','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,160}',token):
            from fastapi import HTTPException
            raise HTTPException(401,'Token workspace lokal tidak valid. Muat ulang aplikasi.')
        return hashlib.sha256(token.encode()).hexdigest()
    def dataset_owner(request,dataset):
        actual=owner(request)
        return dataset if dataset in ('demo','external') else actual

    @app.get('/api/health')
    def health():
        summary=collectors.summary()
        task=getattr(app.state,'collector_task',None)
        return {'status':'ok','mode':'single-node','storage':db.kind+'+'+db.objects.kind,
                'external_collectors_active':summary['enabled'] if summary['worker_enabled'] else 0,
                'external_collectors_successful':summary['successful'],'external_collectors_failed':summary['failed'],
                'collector_worker_running':bool(task and not task.done()),'version':'0.2.0'}
    @app.get('/api/config')
    def config(): return {'fields':FIELDS,'max_upload_bytes':MAX_UPLOAD,'max_rows':10000,'supported_formats':['csv','xlsx'],
                          'breakdown_formats':['csv','tsv','xlsx'],'breakdown_mode':'local_rules','raw_archive_formats':'any','indexed_formats':['csv','xlsx','tsv','json','ndjson','xml','rss','atom','pdf-text','txt','md','html'],
                          'raw_categories':sorted(CATEGORIES),'event_max_bytes':1024*1024,
                          'external_collectors_active':collectors.summary()['enabled'] if collectors.enabled else 0,'storage':db.kind+'+'+db.objects.kind}
    @app.post('/api/uploads',status_code=202)
    async def upload(request:Request,file:UploadFile=File(...),consent:bool=Form(False),intake_mode:str=Form('purchase'),category:str=Form('general'),context:str=Form(''),source_uri:str=Form('')):
        actual=owner(request)
        if not consent:
            await file.close()
            raise ValueError('Konfirmasi hak unggah dan batas preview sebelum mengunggah.')
        chunks=[]
        size=0
        try:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_UPLOAD: raise ValueError(f'Maksimum ukuran file {MAX_UPLOAD/1024/1024:g} MB sesuai konfigurasi server.')
                chunks.append(chunk)
            if intake_mode=='archive':
                return await asyncio.to_thread(service.archive,actual,file.filename,b''.join(chunks),category=category,context=context,source_uri=source_uri,media_type=file.content_type or '')
            if intake_mode!='purchase': raise ValueError('Mode intake harus purchase atau archive.')
            if category not in CATEGORIES: raise ValueError('Kategori tidak dikenal.')
            return await asyncio.to_thread(service.upload,actual,file.filename,b''.join(chunks),{'intake_mode':'purchase','category':category,'context':context,'source_uri':source_uri,'media_type':(file.content_type or '')[:200],'rights':'user_confirmed','scope':'natural_rubber_declared'})
        finally: await file.close()
    @app.get('/api/versions/{version_id}')
    def version(request:Request,version_id:str): return service.version(version_id,owner(request))
    @app.get('/api/versions/{version_id}/breakdown')
    def breakdown(request:Request,version_id:str):return service.breakdown(version_id,owner(request))
    @app.post('/api/versions/{version_id}/breakdown',status_code=202)
    def request_breakdown(request:Request,version_id:str):return service.request_breakdown(version_id,owner(request))
    @app.post('/api/versions/{version_id}/breakdown/review')
    def review_breakdown(request:Request,version_id:str,body:BreakdownReviewBody):return service.review_breakdown(version_id,owner(request),body.model_dump())
    @app.get('/api/versions/{version_id}/preview')
    def preview(request:Request,version_id:str,sheet:str | None=None,header_row:int | None=Query(None,ge=1,le=50),header_depth:int=Query(1,ge=1,le=2)):
        return service.preview(version_id,owner(request),sheet,header_row,header_depth)
    @app.post('/api/versions/{version_id}/mapping/check')
    def check_mapping(request:Request,version_id:str,body:MappingBody):
        return service.check_assistant_mapping(version_id,owner(request),body.model_dump())
    @app.post('/api/versions/{version_id}/mapping/remember')
    def remember_mapping(request:Request,version_id:str,body:RememberMappingBody):
        return service.remember_excel_template(version_id,owner(request),body.revision)
    @app.delete('/api/excel-templates/{template_id}')
    def forget_mapping(request:Request,template_id:str): return service.forget_excel_template(template_id,owner(request))
    @app.post('/api/versions/{version_id}/mapping',status_code=202)
    def mapping(request:Request,version_id:str,body:MappingBody): return service.map_version(version_id,owner(request),body.model_dump())
    @app.get('/api/versions/{version_id}/raw')
    def raw(request:Request,version_id:str):
        with db.connect() as conn:
            row=service.can_read(conn,version_id,owner(request))
            asset=conn.execute('SELECT sha256 FROM raw_assets WHERE object_key=?',(row['object_key'],)).fetchone()
            path=db.object_path(row['object_key'],asset['sha256'])
            return FileResponse(path,media_type='application/octet-stream',filename=row['filename'],headers={'Cache-Control':'no-store'})
    @app.get('/api/documents')
    def documents(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$'),limit:int=Query(100,ge=1,le=100),offset:int=Query(0,ge=0)): return service.list_documents(dataset_owner(request,dataset),limit,offset)
    @app.get('/api/documents/{document_id}/versions')
    def document_versions(request:Request,document_id:str,limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        return service.document_versions(document_id,owner(request),limit,offset)
    @app.delete('/api/documents/{document_id}')
    def delete(request:Request,document_id:str):
        service.delete_document(document_id,owner(request))
        return {'deleted':True}
    @app.get('/api/stats')
    def stats(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$')):
        actual=dataset_owner(request,dataset); result=service.stats(actual)
        with db.connect() as c:
            result['knowledge_records']=c.execute('SELECT COUNT(*) FROM knowledge_records WHERE owner_id=?',(actual,)).fetchone()[0]
            result['raw_bytes']=c.execute('SELECT COALESCE(SUM(size_bytes),0) FROM raw_assets WHERE owner_id=?',(actual,)).fetchone()[0]
            result['pending_jobs']+=c.execute("SELECT COUNT(*) FROM collection_runs r JOIN external_sources s ON s.id=r.source_id WHERE s.owner_id=? AND r.status IN ('queued','running')",(actual,)).fetchone()[0]
            kind_sql="v.intake_meta::jsonb->>'intake_kind'" if db.kind=='postgresql' else "json_extract(v.intake_meta,'$.intake_kind')"
            result['archives']=c.execute('SELECT COUNT(*) FROM documents d JOIN document_versions v ON v.id=d.latest_version_id WHERE d.owner_id=? AND '+kind_sql+' IS NOT NULL',(actual,)).fetchone()[0]
        result['external_sources_active']=collectors.summary(actual)['enabled'] if collectors.enabled else 0
        result['entities']=extend_graph(db,actual,service.graph(actual))['entity_count']
        return result
    @app.get('/api/graph')
    def graph(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$')):
        actual=dataset_owner(request,dataset)
        return extend_graph(db,actual,service.graph(actual))
    @app.get('/api/observations')
    def observations(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$'),q:str=Query('',max_length=150),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        return service.observations(dataset_owner(request,dataset),q,limit,offset)
    @app.get('/api/observations/export.csv')
    def export(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$'),q:str=Query('',max_length=150)):
        data=service.observations(dataset_owner(request,dataset),q,limit=10001)
        if data['total']>10000: raise ValueError('Ekspor preview dibatasi 10.000 baris. Persempit pencarian terlebih dahulu.')
        fields=['observed_date','supplier','supplier_identifier','location','material','grade','price','currency','unit','weight_basis','drc_percent','price_kind','filename','version_no','sheet','row_no','sha256','is_demo']
        output=io.StringIO()
        w=csv.writer(output)
        w.writerow(fields)
        def safe(v):
            text='' if v is None else str(v)
            if text.lstrip().startswith(('=','+','-','@','\t','\r')): return "'"+text
            return text
        for row in data['items']: w.writerow([safe(row.get(k)) for k in fields])
        return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="observasi_{dataset}.csv"'})
    @app.get('/api/evidence/{observation_id}')
    def evidence(request:Request,observation_id:str): return service.evidence(observation_id,owner(request))
    @app.get('/api/issues')
    def issues(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$')): return service.issues(dataset_owner(request,dataset))
    @app.get('/api/activity')
    def activity(request:Request,dataset:str=Query('demo',pattern='^(demo|live|external)$')): return service.activity(dataset_owner(request,dataset))
    @app.get('/api/versions/{version_id}/acquisitions')
    def acquisitions(request:Request,version_id:str,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return service.acquisitions(version_id,owner(request),limit,offset)

    @app.get('/api/versions/{version_id}/content')
    def archive_content(request:Request,version_id:str,offset:int=Query(0,ge=0),limit:int=Query(12000,ge=1,le=20000)):
        return service.archive_content(version_id,owner(request),offset,limit)

    @app.get('/api/archives')
    def archives(request:Request,dataset:str=Query('live',pattern='^(demo|live|external)$'),q:str=Query('',max_length=150),limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        return service.archive_search(dataset_owner(request,dataset),q,limit,offset)

    @app.post('/api/intake/events',status_code=202)
    async def intake_event(request:Request,stream:str=Query(...,min_length=1,max_length=100),category:str=Query('general'),
                           scope_confirmed:bool=Query(False),rights_confirmed:bool=Query(False),context:str=Query('',max_length=2000)):
        actual=owner(request)
        if not scope_confirmed or not rights_confirmed: raise ValueError('Konfirmasi lingkup karet alam dan hak pengiriman sebelum intake.')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',stream): raise ValueError('Nama stream hanya huruf, angka, titik, garis bawah, dan tanda hubung.')
        from fastapi import HTTPException
        parts=[]; size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>1024*1024: raise HTTPException(413,'Payload event maksimum 1 MB; kirim batch terpisah, tidak ada pemotongan diam-diam.')
            parts.append(chunk)
        media=request.headers.get('content-type','application/octet-stream')
        extension='.csv' if media.split(';')[0]=='text/csv' else '.tsv' if media.split(';')[0]=='text/tab-separated-values' else '.json' if media.split(';')[0]=='application/json' else '.ndjson' if media.split(';')[0]=='application/x-ndjson' else '.txt' if media.startswith('text/') else '.bin'
        return await asyncio.to_thread(service.archive,actual,stream+extension,b''.join(parts),category=category,context=context,media_type=media,
                                       logical_key='event:'+stream,request_key=request.headers.get('idempotency-key'))

    @app.get('/api/sources/catalog')
    def source_catalog(request:Request):
        owner(request)
        return [{'adapter':key,**value} for key,value in CATALOG.items()]
    @app.get('/api/sources')
    def sources(request:Request): return {'items':collectors.list(owner(request)),'summary':collectors.summary(owner(request))}
    @app.post('/api/sources',status_code=201)
    def source_create(request:Request,body:SourceBody):
        return collectors.create(owner(request),body.adapter,body.config,body.name,body.interval_seconds,body.enabled)
    @app.patch('/api/sources/{source_id}')
    def source_patch(request:Request,source_id:str,body:SourcePatch):
        return collectors.patch(source_id,owner(request),body.model_dump(exclude_unset=True,exclude_none=True))
    @app.delete('/api/sources/{source_id}')
    def source_delete(request:Request,source_id:str):
        collectors.delete(source_id,owner(request)); return {'deleted':True}
    @app.post('/api/sources/{source_id}/run',status_code=202)
    def source_run(request:Request,source_id:str): return collectors.request_run(source_id,owner(request))
    @app.get('/api/sources/{source_id}/runs')
    def source_runs(request:Request,source_id:str,limit:int=Query(30,ge=1,le=100),offset:int=Query(0,ge=0)):
        return collectors.runs(source_id,owner(request),limit,offset)
    @app.get('/api/runs/{run_id}')
    def run_detail(request:Request,run_id:str): return collectors.run_detail(run_id,owner(request))
    @app.get('/api/knowledge')
    def knowledge(request:Request,dataset:str=Query('external',pattern='^(demo|live|external)$'),q:str=Query('',max_length=150),kind:str='',source_id:str='',limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0)):
        return collectors.records(dataset_owner(request,dataset),q,kind,source_id,limit,offset)
    @app.get('/api/knowledge/export.csv')
    def knowledge_export(request:Request,dataset:str=Query('external',pattern='^(demo|live|external)$'),q:str=Query('',max_length=150),kind:str=''):
        actual=dataset_owner(request,dataset)
        result=collectors.records(actual,q,kind,limit=10001)
        if result['total']>10000: raise ValueError('Ekspor maksimum 10.000 record; persempit jenis/pencarian.')
        output=io.StringIO(); w=csv.writer(output)
        w.writerow(['id','kind','title','period','source','revision','fields_json','raw_version_id','captured_at'])
        def safe(value):
            text=str(value)
            return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text
        for row in result['items']:
            w.writerow([safe(v) for v in [row['id'],row['kind'],row['title'],row['period'],row['source_name'],row['current_revision'],json.dumps(row['fields'],ensure_ascii=False),row['version_id'],row['captured_at']]])
        return Response('\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="rubber_external_records.csv"'})
    @app.get('/api/knowledge/{record_id}/revisions')
    def record_revisions(request:Request,record_id:str,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
        return collectors.revisions(record_id,owner(request),limit,offset)
    @app.get('/api/knowledge/{record_id}')
    def record_evidence(request:Request,record_id:str): return collectors.evidence(record_id,owner(request))

    @app.get('/api/template.csv')
    def template():
        return Response('\ufefftanggal,pemasok,id_pemasok,lokasi_pemasok,material,grade,harga,mata_uang,unit,basis_berat,kkk_persen,jenis_harga,kuantitas_kg\r\n',media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="template_pembelian_karet.csv"'})
    @app.get('/blueprint')
    def blueprint():
        path=BASE.parent/'blueprint.html'
        if not path.is_file():path=BASE/'docs'/'blueprint.html'
        if not path.is_file(): raise LookupError('Blueprint tidak ditemukan.')
        return FileResponse(path)

    dist=BASE/'frontend'/'dist'
    if (dist/'assets').exists(): app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    def index():
        if (dist/'index.html').exists(): return FileResponse(dist/'index.html',headers={'Cache-Control':'no-store'})
        return JSONResponse({'detail':'Frontend belum dibangun. Jalankan npm run build di folder frontend.'},status_code=503)
    return app


app=create_app()
