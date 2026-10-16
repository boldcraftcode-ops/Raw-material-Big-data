import os
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode,quote
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend.db import Database
from backend.app import create_app
from backend.migrate import migrate_sqlite

@pytest.mark.skipif(not os.environ.get('RUBBER_TEST_DATABASE_URL'),reason='Live PostgreSQL URL required for migration integration test')
def test_offline_migration_preserves_bytes_versions_ownership_and_refuses_overwrite(tmp_path):
    import psycopg
    from psycopg import sql
    base=os.environ['RUBBER_TEST_DATABASE_URL'];schema='rubber_migrate_'+uuid4().hex
    with psycopg.connect(base,autocommit=True) as c:c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    p=urlsplit(base);query=dict(parse_qsl(p.query));query['options']='-c search_path='+schema
    url=urlunsplit((p.scheme,p.netloc,p.path,urlencode(query,quote_via=quote),p.fragment))
    try:
        source=create_app(tmp_path/'source',database_url='',seed_demo=False,seed_sources=False,start_worker=False)
        headers={'X-Workspace-Token':'A'*64}
        with TestClient(source) as c:
            for body in (b'{"rubber":1}',b'{"rubber":2}'):
                r=c.post('/api/uploads',headers=headers,files={'file':('rubber.json',body)},data={'consent':'true','intake_mode':'archive'})
                assert r.status_code==202
            while source.state.service.process_next():pass
            docs=c.get('/api/documents?dataset=live',headers=headers).json()
        target=Database(tmp_path/'target',url=url)
        report=migrate_sqlite(source.state.db.path,source.state.db.raw,target)
        assert report['objects_verified']==2 and report['tables']['documents']==1 and not report['source_deleted']
        app=create_app(tmp_path/'target',database_url=url,seed_demo=False,seed_sources=False,start_worker=False)
        with TestClient(app) as c:
            migrated=c.get('/api/documents?dataset=live',headers=headers).json()
            assert migrated[0]['id']==docs[0]['id'] and migrated[0]['version_count']==2
            for v in migrated[0]['versions']:
                assert c.get('/api/versions/'+v['id']+'/raw',headers=headers).content==f'{{"rubber":{v["version_no"]}}}'.encode()
            assert c.get('/api/documents?dataset=live',headers={'X-Workspace-Token':'B'*64}).json()==[]
        with pytest.raises(ValueError,match='kosong'):migrate_sqlite(source.state.db.path,source.state.db.raw,target)
        assert source.state.db.path.is_file() and len(list(source.state.db.raw.glob('*/*')))==2
    finally:
        with psycopg.connect(base,autocommit=True) as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
