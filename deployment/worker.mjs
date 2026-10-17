// Cloudflare is an asset host and same-origin API gateway, NOT the Python runtime.
// Never infer an upstream from a URL, query, or request header supplied by a visitor.
const REQUEST_HEADERS = ['accept', 'content-type', 'x-workspace-token', 'idempotency-key',
  'range', 'if-range', 'if-none-match', 'if-modified-since'];
const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
};

export function isBackendPath(path) {
  return path === '/api' || path.startsWith('/api/') || path === '/blueprint';
}

export function backendOrigin(env, incomingUrl) {
  if (typeof env.BACKEND_ORIGIN !== 'string' || !env.BACKEND_ORIGIN.trim()) return null;
  let url;
  try { url = new URL(env.BACKEND_ORIGIN.trim()); } catch { return null; }
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/') return null;
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local && env.ALLOW_LOCAL_BACKEND === '1')) return null;
  if (local && env.ALLOW_LOCAL_BACKEND !== '1') return null;
  if (url.origin === new URL(incomingUrl).origin) return null; // Do not recurse into this Worker.
  return url.origin;
}

function failure(status, detail) {
  return Response.json({ detail }, { status, headers: { ...SECURITY_HEADERS, 'Cache-Control': 'no-store' } });
}

export async function handleRequest(request, env, upstreamFetch = fetch) {
  const incoming = new URL(request.url);
  if (!isBackendPath(incoming.pathname)) {
    if (!env.ASSETS) return failure(503, 'Build frontend belum tersedia. Periksa assets.directory dan langkah build.');
    return env.ASSETS.fetch(request);
  }

  const origin = backendOrigin(env, incoming);
  if (!origin) return failure(503,
    'Backend Python belum dikonfigurasi dengan benar. Atur BACKEND_ORIGIN pada runtime Worker ke origin HTTPS hosting backend Anda. Deploy frontend saja belum menjalankan MVP.');

  // Assign path/search, not new URL(untrustedPath, origin): double slashes must never change hosts.
  const destination = new URL(origin);
  destination.pathname = incoming.pathname;
  destination.search = incoming.search;
  const headers = new Headers();
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  // Do not forward browser cookies, Authorization/Cloudflare account credentials or arbitrary headers.
  const init = { method: request.method, headers, redirect: 'manual' };
  if (!['GET', 'HEAD'].includes(request.method)) {
    init.body = request.body;
    init.duplex = 'half';
  }

  let upstream;
  try {
    upstream = await upstreamFetch(new Request(destination.toString(), init), {
      cf: { cacheEverything: false, cacheTtl: 0 },
    });
  } catch {
    return failure(502, 'Backend Python tidak dapat dihubungi. Periksa URL HTTPS, status server, dan jaringan. Raw jangan dikirim ulang sampai status penerimaan diperiksa.');
  }
  // A redirect could send the workspace token/payload to another host. Require a canonical origin.
  if (upstream.status >= 300 && upstream.status < 400 && upstream.status !== 304) {
    upstream.body?.cancel().catch(() => {});
    return failure(502, 'Backend mengembalikan redirect. Gunakan origin HTTPS backend langsung dan path API yang benar.');
  }
  // Never let the SPA's index.html masquerade as a successful JSON API response.
  if (incoming.pathname.startsWith('/api') && upstream.headers.get('content-type')?.toLowerCase().includes('text/html')) {
    upstream.body?.cancel().catch(() => {});
    return failure(502, 'Origin backend mengembalikan HTML, bukan API Python. BACKEND_ORIGIN tidak boleh menunjuk frontend atau halaman login.');
  }
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.set('Cache-Control', 'no-store');
  const vary = responseHeaders.get('Vary');
  if (vary !== '*' && !vary?.toLowerCase().split(',').map(value => value.trim()).includes('x-workspace-token')) {
    responseHeaders.set('Vary', vary ? vary+', X-Workspace-Token' : 'X-Workspace-Token');
  }
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) responseHeaders.set(name, value);
  for (const name of ['set-cookie', 'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'transfer-encoding', 'access-control-allow-origin', 'access-control-allow-credentials']) responseHeaders.delete(name);
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: responseHeaders });
}

export default { fetch(request, env) { return handleRequest(request, env); } };
