"""Private, content-addressed raw objects. No browser-facing object-store URLs."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import uuid4


class LocalObjects:
    kind = 'filesystem'

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes):
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(data).hexdigest():
                raise ValueError('Objek raw yang sudah ada gagal pemeriksaan integritas.')
            return
        tmp = target.with_name(target.name + '.' + uuid4().hex + '.tmp')
        try:
            with tmp.open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

    def path(self, key: str, expected_hash: str | None = None):
        path = self.root / key
        if not path.is_file():
            raise LookupError('Objek raw tidak tersedia.')
        if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError('Integritas raw tidak cocok dengan manifest; unduhan dihentikan.')
        return path

    def delete(self, key):
        (self.root / key).unlink(missing_ok=True)


class S3Objects:
    kind = 's3'

    def __init__(self, cache: Path):
        import boto3
        from botocore.config import Config
        self.cache = cache
        cache.mkdir(parents=True, exist_ok=True)
        self.bucket = os.environ['RUBBER_S3_BUCKET']
        self.prefix = os.environ.get('RUBBER_S3_PREFIX', 'rubber-raw').strip('/')
        self.client = boto3.client('s3', endpoint_url=os.environ.get('RUBBER_S3_ENDPOINT') or None,
                                  region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'),
                                  config=Config(connect_timeout=10, read_timeout=60, retries={'max_attempts': 3}))

    def _key(self, key):
        return f'{self.prefix}/{key}' if self.prefix else key

    def put(self, key, data):
        from botocore.exceptions import ClientError
        sha = hashlib.sha256(data).hexdigest()
        try:
            existing = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            if existing['Metadata'].get('sha256') != sha or existing['ContentLength'] != len(data):
                raise ValueError('Manifest objek S3 tidak cocok dengan raw.')
            return
        except ClientError as exc:
            if exc.response['Error']['Code'] not in ('404', 'NoSuchKey', 'NotFound'):
                raise
        kwargs = {}
        if os.environ.get('RUBBER_S3_SSE'):
            kwargs['ServerSideEncryption'] = os.environ['RUBBER_S3_SSE']
        # Bucket must be private. No public ACL, credentials or presigned URL is emitted.
        try:
            self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data,
                                   ContentType='application/octet-stream', Metadata={'sha256': sha},
                                   IfNoneMatch='*', **kwargs)
        except ClientError as exc:
            if exc.response['Error']['Code'] not in ('PreconditionFailed', '412'):
                raise
            existing = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            if existing['Metadata'].get('sha256') != sha or existing['ContentLength'] != len(data):
                raise ValueError('Konflik integritas objek S3.')

    def path(self, key, expected_hash=None):
        # Materialize only for bounded parsers/authenticated attachment downloads.
        path = self.cache / key
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
            try:
                self.client.download_file(self.bucket, self._key(key), str(tmp))
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)
        if expected_hash and hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            path.unlink(missing_ok=True)
            raise ValueError('Integritas raw S3 tidak cocok dengan manifest.')
        return path

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        (self.cache / key).unlink(missing_ok=True)
