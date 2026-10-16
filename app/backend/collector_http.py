"""Bounded HTTPS requests to an explicit source-policy allowlist (not an open proxy)."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

APPROVED_HOSTS = {
    'www.worldbank.org', 'thedocs.worldbank.org', 'pubdocs.worldbank.org',
    'bulks-faostat.fao.org', 'api.bmkg.go.id', 'news.google.com', 'api.gdeltproject.org',
}
SAFE_HEADERS = {'content-type', 'content-length', 'etag', 'last-modified', 'retry-after', 'date'}


class FetchError(ValueError):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


@dataclass
class HTTPResult:
    url: str
    status: int
    headers: dict
    body: bytes


class PublicHTTP:
    def __init__(self, transport=None, validate_dns=True, on_request=None):
        self.on_request = on_request
        self.transport = transport
        self.validate_dns = validate_dns

    def validate(self, url):
        try:
            u = urlsplit(url)
            if u.scheme != 'https' or u.port not in (None, 443) or u.username or u.password or u.fragment or '\\' in url:
                raise ValueError()
            host = (u.hostname or '').lower()
            if host not in APPROVED_HOSTS: raise ValueError()
        except ValueError:
            raise FetchError('URL/redirect di luar kebijakan sumber HTTPS yang disetujui.')
        if self.validate_dns:
            try: addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            except OSError: raise FetchError('DNS sumber tidak dapat diresolusikan.')
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise FetchError('Alamat jaringan privat/non-publik ditolak.')
        return url

    def get(self, url, *, max_bytes=10 * 1024 * 1024, headers=None):
        current = self.validate(url)
        request_headers = {'User-Agent': 'RubberIntelligence/0.2 (bounded public-data collection)',
                           'Accept': '*/*', 'Accept-Encoding': 'identity', **(headers or {})}
        try:
            with httpx.Client(transport=self.transport, follow_redirects=False, trust_env=False,
                              timeout=httpx.Timeout(45, connect=12)) as client:
                for _ in range(5):
                    self.validate(current)
                    if self.on_request: self.on_request(current)
                    with client.stream('GET', current, headers=request_headers) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get('location')
                            if not location: raise FetchError('Redirect sumber tanpa tujuan.', response.status_code)
                            current = self.validate(urljoin(current, location))
                            request_headers = {k: v for k, v in request_headers.items() if k.lower() not in ('if-none-match', 'if-modified-since')}
                            continue
                        safe = {k.lower(): v[:1000] for k, v in response.headers.items() if k.lower() in SAFE_HEADERS}
                        if response.status_code == 304: return HTTPResult(current, 304, safe, b'')
                        if response.status_code != 200:
                            retry = response.headers.get('retry-after', '')
                            raise FetchError(f'Sumber mengembalikan HTTP {response.status_code}; data terakhir yang berhasil tetap dipertahankan.', response.status_code, retry)
                        length = response.headers.get('content-length', '')
                        if length.isdigit() and int(length) > max_bytes:
                            raise FetchError('Respons melampaui batas byte sumber; tidak diarsipkan sebagian.', 200)
                        chunks = []; size = 0
                        for chunk in response.iter_bytes(chunk_size=65536):
                            size += len(chunk)
                            if size > max_bytes: raise FetchError('Respons/dekompresi HTTP melampaui batas byte sumber.', 200)
                            chunks.append(chunk)
                        return HTTPResult(current, response.status_code, safe, b''.join(chunks))
                raise FetchError('Terlalu banyak redirect sumber.')
        except httpx.TimeoutException:
            raise FetchError('Batas waktu koneksi/transfer sumber terlampaui; akan dicoba ulang.')
        except httpx.HTTPError:
            raise FetchError('Koneksi HTTPS sumber gagal; akan dicoba ulang.')
