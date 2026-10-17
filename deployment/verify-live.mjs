// Deployment gate. A 200 HTML page alone is NOT a successful full-MVP deploy.
// --intake uses a fresh private token and synthetic data, then deletes only its own document.
import assert from 'node:assert/strict';
import { randomBytes, createHash } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { setTimeout as wait } from 'node:timers/promises';

const args = process.argv.slice(2);
const value = flag => { const i = args.indexOf(flag); return i >= 0 ? args[i+1] : undefined; };
if (!value('--url')) {
  console.error('Usage: npm run verify:deployment -- --url https://YOUR_WORKER_HOST [--intake] [--output report.json]');
  process.exit(2);
}
const site = new URL(value('--url'));
const local = ['localhost','127.0.0.1','[::1]'].includes(site.hostname);
assert.ok(!site.username && !site.password && !site.search && !site.hash && site.pathname === '/', 'Use an origin URL without credentials/path/query/fragment.');
assert.ok(site.protocol === 'https:' || local && args.includes('--allow-local'), 'Use HTTPS; --allow-local is only for loopback QA.');
const token = randomBytes(48).toString('base64url');
const privateHeaders = { 'X-Workspace-Token': token };
const report = { checked_at: new Date().toISOString(), target: site.origin, synthetic_data_only: true, checks: [], cleanup: null };
let documentId;
const passed = name => { report.checks.push(name); console.log('PASS:', name); };
async function call(path, options={}) {
  return fetch(site.origin+path, { ...options, headers: { ...privateHeaders, ...options.headers }, signal: AbortSignal.timeout(15000), redirect: 'manual' });
}
async function json(path, options={}) {
  const response = await call(path, options);
  assert.ok(response.ok, `${options.method||'GET'} ${path.split('?')[0]} returned HTTP ${response.status}; check backend configuration.`);
  assert.match(response.headers.get('content-type')||'', /application\/json/, 'API must return JSON, not SPA HTML.');
  return response.json();
}
try {
  const page = await call('/');
  assert.equal(page.status, 200); const html = await page.text(); assert.match(html, /id="root"/);
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^\"]+)"/g)].map(match => match[1]);
  assert.ok(assets.length >= 2, 'Compiled frontend assets are missing.');
  for (const path of assets) assert.equal((await call(path)).status, 200, 'Frontend asset did not load.');
  passed('Frontend HTML and bundled JS/CSS are served');
  const health = await json('/api/health');
  assert.equal(health.status, 'ok'); assert.equal(health.mode, 'single-node');
  const config = await json('/api/config');
  assert.ok(config.breakdown_formats?.includes('csv'));
  passed('Real Python health and intake configuration are reachable through /api');
  if (args.includes('--intake')) {
    const payload = Buffer.from('Tanggal,Material,Stok,Gudang\n'+new Date().toISOString().slice(0,10)+',Lateks,0,QA\n');
    const form = new FormData();
    form.append('file', new Blob([payload], { type: 'text/csv' }), 'QA_DEPLOY_'+randomBytes(6).toString('hex')+'.csv');
    form.append('consent','true'); form.append('intake_mode','archive'); form.append('category','general');
    form.append('context','Synthetic deployment check; no sensitive data.');
    const received = await json('/api/uploads', { method: 'POST', body: form });
    documentId = received.version?.document_id; const versionId = received.version?.id;
    assert.ok(documentId && versionId, 'Upload did not return source IDs.');
    const deadline = Date.now()+45000; let version;
    do {
      version = await json('/api/versions/'+versionId);
      assert.notEqual(version.status, 'failed', 'Intake job failed.');
      if (version.status === 'archived') break;
      await wait(450);
    } while (Date.now() < deadline);
    assert.equal(version.status, 'archived', 'Intake job did not finish within the QA deadline.');
    passed('Synthetic multipart upload is retained and the real background intake job completes');
    const profile = await json('/api/versions/'+versionId+'/breakdown');
    assert.equal(profile.profile?.classification,'inventory'); assert.equal(profile.profile.external_ai_used,false);
    const table = profile.profile.sheets.flatMap(sheet => sheet.tables)[0];
    assert.ok(table?.columns.some(column => column.role === 'stock'));
    const raw = await call('/api/versions/'+versionId+'/raw'); assert.equal(raw.status,200);
    assert.deepEqual(Buffer.from(await raw.arrayBuffer()),payload);
    assert.equal(version.sha256,createHash('sha256').update(payload).digest('hex'));
    passed('Breakdown/classification work and raw bytes/SHA-256 survive the Worker proxy');
    const review = await json('/api/versions/'+versionId+'/breakdown/review', { method: 'POST',
      headers: {'Content-Type':'application/json'}, body: JSON.stringify({ confirmed:true,profile_hash:profile.profile_hash,
        tables:[{table_id:table.id,category:table.classification.category,columns:table.columns.map(column => ({column_id:column.id,role:column.role,datatype:column.observed_type}))}] }) });
    assert.equal(review.published,false); assert.equal(review.raw_changed,false);
    const reviewed = await json('/api/versions/'+versionId+'/breakdown');
    assert.equal(reviewed.review?.revision,1); assert.equal(reviewed.profile_hash,profile.profile_hash);
    const stats = await json('/api/stats?dataset=live'); assert.equal(stats.observations,0);
    passed('Version-bound review persists without publishing transactions or mutating raw');
    const foreign = await call('/api/versions/'+versionId+'/breakdown', { headers: {'X-Workspace-Token':randomBytes(48).toString('base64url')} });
    assert.equal(foreign.status,404);
    passed('A different workspace token cannot read the private breakdown');
  }
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.failure = error.message;
  console.error('FAIL:',error.message); process.exitCode = 1;
} finally {
  if (documentId) {
    try {
      const deleted = await call('/api/documents/'+documentId,{method:'DELETE'});
      assert.ok(deleted.ok);
      const remaining = await json('/api/documents?dataset=live');
      assert.ok(!remaining.some(document => document.id === documentId));
      report.cleanup = true; console.log('PASS: This check\'s synthetic document was removed');
    } catch {
      report.cleanup = false; report.status = 'failed'; process.exitCode = 1;
      console.error('QA cleanup failed. Check the synthetic QA_DEPLOY_ document using this verification session; no other document was deleted.');
    }
  }
  if (value('--output')) await writeFile(value('--output'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({status:report.status,checks:report.checks.length,cleanup:report.cleanup}));
}
