import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { handleRequest, backendOrigin, isBackendPath } from '../worker.mjs';

const site = 'https://rubber.example';
const origin = 'https://backend.example';
const env = { BACKEND_ORIGIN: origin };

for (const path of ['/api', '/api/health', '/api/versions/id/raw', '/api/uploads', '/blueprint']) {
  test(`Backend route: ${path}`, () => assert.equal(isBackendPath(path), true));
}
for (const path of ['/', '/assets/app.js', '/apiary', '/blueprints', '/explore']) {
  test(`Static/SPA route: ${path}`, () => assert.equal(isBackendPath(path), false));
}
for (const value of [undefined, '', 'not a url', 'http://backend.example', 'https://u:password@backend.example',
  'https://backend.example/path', 'https://backend.example/?token=secret', 'https://backend.example/#fragment',
  site, 'https://localhost', 'http://127.0.0.1:8000']) {
  test(`Reject invalid/unsafe/recursive origin ${JSON.stringify(value)}`, () => {
    assert.equal(backendOrigin({ BACKEND_ORIGIN: value }, site), null);
  });
}

test('HTTPS origin normalization and strictly opted-in local development', () => {
  assert.equal(backendOrigin({ BACKEND_ORIGIN: origin+'/' }, site), origin);
  assert.equal(backendOrigin({ BACKEND_ORIGIN: 'http://127.0.0.1:8000', ALLOW_LOCAL_BACKEND: '1' }, site), 'http://127.0.0.1:8000');
  assert.equal(backendOrigin({ BACKEND_ORIGIN: 'http://untrusted.example', ALLOW_LOCAL_BACKEND: '1' }, site), null);
});

test('Missing backend returns explicit JSON 503, not success or SPA HTML', async () => {
  const result = await handleRequest(new Request(site+'/api/config'), {}, () => assert.fail('must not fetch'));
  assert.equal(result.status, 503);
  assert.match((await result.json()).detail, /BACKEND_ORIGIN/);
  assert.equal(result.headers.get('cache-control'), 'no-store');
});

test('Non-API assets are delegated without hitting Python', async () => {
  let calls = 0;
  const result = await handleRequest(new Request(site+'/explore'), {
    ASSETS: { async fetch(request) { calls++; assert.equal(request.url, site+'/explore'); return new Response('asset'); } },
  }, () => assert.fail('must not fetch upstream'));
  assert.equal(await result.text(), 'asset'); assert.equal(calls, 1);
});

test('GET forwards only allowlisted headers and preserves query, status and JSON', async () => {
  const request = new Request(site+'/api/documents?dataset=live&limit=2', { headers: {
    'X-Workspace-Token': 'synthetic-qa-token', 'Cookie': 'never-send-cookie',
    'Authorization': 'never-send-bearer', 'X-Forwarded-Host': 'evil.example',
  } });
  const response = await handleRequest(request, env, async (target, options) => {
    assert.equal(target.url, origin+'/api/documents?dataset=live&limit=2');
    assert.equal(target.headers.get('x-workspace-token'), 'synthetic-qa-token');
    for (const name of ['cookie', 'authorization', 'x-forwarded-host']) assert.equal(target.headers.get(name), null);
    assert.equal(target.redirect, 'manual');
    assert.equal(options.cf.cacheTtl, 0);
    return Response.json({ detail: 'not found' }, { status: 404 });
  });
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { detail: 'not found' });
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.match(response.headers.get('vary'), /X-Workspace-Token/);
});

test('Multipart boundary and exact binary upload bytes survive proxy streaming', async () => {
  const payload = new Uint8Array([45,45,65,13,10,0,255,65,66,13,10,45,45,65,45,45]);
  const contentType = 'multipart/form-data; boundary=A';
  const request = new Request(site+'/api/uploads', { method: 'POST', headers: {
    'Content-Type': contentType, 'X-Workspace-Token': 'synthetic', 'Idempotency-Key': 'qa-batch-0001',
  }, body: payload, duplex: 'half' });
  const response = await handleRequest(request, env, async target => {
    assert.equal(target.method, 'POST'); assert.equal(target.headers.get('content-type'), contentType);
    assert.equal(target.headers.get('idempotency-key'), 'qa-batch-0001');
    assert.deepEqual(new Uint8Array(await target.arrayBuffer()), payload);
    return Response.json({ received: true }, { status: 202 });
  });
  assert.equal(response.status, 202);
});

test('Raw download bytes, range and Content-Disposition remain intact; no cookie/cache leakage', async () => {
  const payload = new Uint8Array([0,255,254,100,42]);
  const result = await handleRequest(new Request(site+'/api/versions/id/raw', { headers: {
    'Range': 'bytes=0-4', 'X-Workspace-Token': 'synthetic',
  } }), env, async target => {
    assert.equal(target.headers.get('range'), 'bytes=0-4');
    return new Response(payload, { status: 206, headers: {
      'Content-Type': 'application/octet-stream', 'Content-Disposition': 'attachment; filename="raw.bin"',
      'Content-Range': 'bytes 0-4/5', 'Cache-Control': 'public, max-age=3600',
      'Set-Cookie': 'not-app-auth', 'Access-Control-Allow-Origin': '*',
    } });
  });
  assert.equal(result.status, 206); assert.deepEqual(new Uint8Array(await result.arrayBuffer()), payload);
  assert.equal(result.headers.get('content-disposition'), 'attachment; filename="raw.bin"');
  assert.equal(result.headers.get('cache-control'), 'no-store');
  assert.equal(result.headers.get('set-cookie'), null);
  assert.equal(result.headers.get('access-control-allow-origin'), null);
});

test('Redirects never forward a workspace token or body to a second host', async () => {
  let calls = 0;
  const result = await handleRequest(new Request(site+'/api/health'), env, async request => {
    calls++; assert.equal(request.redirect, 'manual');
    return new Response(null, { status: 302, headers: { Location: 'https://evil.example' } });
  });
  assert.equal(calls, 1); assert.equal(result.status, 502); assert.equal(result.headers.get('location'), null);
});

test('Successful HTML from a wrongly configured frontend is not accepted as a working API', async () => {
  const result = await handleRequest(new Request(site+'/api/health'), env,
    async () => new Response('<html>frontend</html>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } }));
  assert.equal(result.status, 502); assert.match((await result.json()).detail, /HTML/);
});

test('Blueprint HTML is allowed, streamed and not cached', async () => {
  const result = await handleRequest(new Request(site+'/blueprint'), env,
    async () => new Response('<h1>Blueprint</h1>', { headers: { 'Content-Type': 'text/html' } }));
  assert.equal(result.status, 200); assert.equal(await result.text(), '<h1>Blueprint</h1>');
  assert.equal(result.headers.get('cache-control'), 'no-store');
});

test('Transport errors are sanitized and do not echo credentials, URLs or payloads', async () => {
  const result = await handleRequest(new Request(site+'/api/health'), env,
    async () => { throw Error('private path /secret, TOKEN, payload'); });
  assert.equal(result.status, 502); assert.doesNotMatch(await result.text(), /TOKEN|\/secret|payload/);
});

test('Bodyless status and HTTP methods remain valid', async () => {
  for (const method of ['HEAD', 'OPTIONS', 'DELETE', 'PATCH']) {
    const result = await handleRequest(new Request(site+'/api/test', { method }), env,
      async request => { assert.equal(request.method, method); return new Response(null, { status: 204 }); });
    assert.equal(result.status, 204); assert.equal(await result.text(), '');
  }
});

test('Deployment config builds nested frontend and uses worker-first API routing', () => {
  const config = readFileSync(new URL('../../wrangler.jsonc', import.meta.url), 'utf8');
  assert.match(config, /"directory":\s*"\.\/app\/frontend\/dist"/);
  assert.match(config, /"command":\s*"npm run build"/);
  assert.match(config, /"run_worker_first":\s*\["\/api", "\/api\/\*", "\/blueprint"\]/);
  assert.doesNotMatch(config, /"BACKEND_ORIGIN"\s*:\s*"https?:\/\//);
  const pkg = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url)));
  assert.equal(pkg.devDependencies.wrangler, '4.151.0');
  assert.match(pkg.scripts.build, /--prefix app\/frontend/);
});
