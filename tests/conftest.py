"""Run the same repository/API tests on SQLite and a real optional PostgreSQL server."""
import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
from uuid import uuid4
import pytest

BACKENDS = ['sqlite'] + (['postgresql'] if os.environ.get('RUBBER_TEST_DATABASE_URL') else [])

@pytest.fixture(params=BACKENDS)
def app_factory(tmp_path, request):
    from backend.app import create_app
    schemas=[]
    def make(**kwargs):
        url=None
        if request.param=='postgresql':
            import psycopg
            from psycopg import sql
            base=os.environ['RUBBER_TEST_DATABASE_URL']; schema='rubber_test_'+uuid4().hex
            with psycopg.connect(base,autocommit=True) as c:
                c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            schemas.append((base,schema))
            parts=urlsplit(base); query=dict(parse_qsl(parts.query)); query['options']='-c search_path='+schema
            url=urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query,quote_via=quote),parts.fragment))
        n=len(list(tmp_path.iterdir()))
        return create_app(tmp_path/f'runtime-{n}',database_url=url,**kwargs)
    yield make
    if schemas:
        import psycopg
        from psycopg import sql
        for base,schema in schemas:
            with psycopg.connect(base,autocommit=True) as c:
                c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
