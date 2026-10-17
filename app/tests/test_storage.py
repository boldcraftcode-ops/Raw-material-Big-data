"""S3 protocol tests use botocore stubs; these are not a claim of a live cloud deployment."""
import hashlib
from pathlib import Path
import pytest
from botocore.stub import Stubber
from backend.storage import LocalObjects,S3Objects

@pytest.fixture
def s3(tmp_path,monkeypatch):
    monkeypatch.setenv('RUBBER_S3_BUCKET','rubber-unit-test')
    monkeypatch.setenv('RUBBER_S3_PREFIX','unit-private')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID','testing-only')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY','testing-only')
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED','true')
    return S3Objects(tmp_path)

def test_local_hash_integrity_and_atomic_write(tmp_path):
    store=LocalObjects(tmp_path);body=b'natural rubber';key='owner/'+hashlib.sha256(body).hexdigest()
    store.put(key,body);store.put(key,body)
    assert store.path(key,hashlib.sha256(body).hexdigest()).read_bytes()==body
    (tmp_path/key).write_bytes(b'tampered')
    with pytest.raises(ValueError):store.path(key,hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError):store.put(key,body)
    store.delete(key);assert not (tmp_path/key).exists()

def test_s3_private_put_and_dedup_metadata(s3):
    body=b'rubber-original';sha=hashlib.sha256(body).hexdigest();key='owner/'+sha;remote='unit-private/'+key
    with Stubber(s3.client) as stub:
        stub.add_client_error('head_object','404',http_status_code=404,expected_params={'Bucket':s3.bucket,'Key':remote})
        stub.add_response('put_object',{},expected_params={'Bucket':s3.bucket,'Key':remote,'Body':body,'ContentType':'application/octet-stream','Metadata':{'sha256':sha},'IfNoneMatch':'*'})
        s3.put(key,body)
        stub.add_response('head_object',{'ContentLength':len(body),'Metadata':{'sha256':sha}},expected_params={'Bucket':s3.bucket,'Key':remote})
        s3.put(key,body)
        stub.assert_no_pending_responses()

def test_s3_conditional_put_race_and_integrity(s3):
    body=b'rubber';sha=hashlib.sha256(body).hexdigest();key='owner/'+sha;remote='unit-private/'+key
    with Stubber(s3.client) as stub:
        stub.add_client_error('head_object','404',http_status_code=404)
        stub.add_client_error('put_object','PreconditionFailed',http_status_code=412)
        stub.add_response('head_object',{'ContentLength':len(body),'Metadata':{'sha256':sha}})
        s3.put(key,body);stub.assert_no_pending_responses()
    with Stubber(s3.client) as stub:
        stub.add_response('head_object',{'ContentLength':len(body),'Metadata':{'sha256':'incorrect'}})
        with pytest.raises(ValueError):s3.put(key,body)

def test_s3_materialization_hash_checked_and_authenticated_path(s3,monkeypatch):
    body=b'raw';key='owner/sha';sha=hashlib.sha256(body).hexdigest()
    def download(bucket,remote,filename):Path(filename).write_bytes(body)
    monkeypatch.setattr(s3.client,'download_file',download)
    assert s3.path(key,sha).read_bytes()==body
    (s3.cache/key).write_bytes(b'corrupted')
    with pytest.raises(ValueError):s3.path(key,sha)
    assert not (s3.cache/key).exists()

def test_s3_delete_removes_remote_and_local_cache(s3):
    key='owner/sha';p=s3.cache/key;p.parent.mkdir(parents=True);p.write_bytes(b'raw')
    with Stubber(s3.client) as stub:
        stub.add_response('delete_object',{},expected_params={'Bucket':s3.bucket,'Key':'unit-private/'+key})
        s3.delete(key);stub.assert_no_pending_responses()
    assert not p.exists()
