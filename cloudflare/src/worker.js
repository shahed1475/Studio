// Nightloom's edge on Cloudflare (13 Nov 2026): static site files come from Workers Static Assets; only /api/* and the privacy page reach this Worker,
// which forwards them to the hub on the owner's server with the edge secret and the visitor's address. Everything else the visitor sends is dropped, never trusted.
const FORWARD = [/^\/api\//, /^\/privacy\.html$/];
const STRIP = ["x-edge-secret", "x-client-ip", "x-forwarded-for", "x-forwarded-host", "x-edge-host", "x-forwarded-proto", "x-real-ip", "forwarded", "cf-connecting-ip", "host"];
const MAX_BODY = 100_000;

export const forwarded = (pathname) => FORWARD.some((r) => r.test(pathname));

export async function handle(request, env, fetchFn = fetch) {
  const url = new URL(request.url);
  if (!forwarded(url.pathname)) return new Response("Not found", { status: 404 });
  if (!env.EDGE_SECRET || !env.ORIGIN) return new Response("The site is not configured yet.", { status: 503 });
  const headers = new Headers(request.headers);
  for (const k of STRIP) headers.delete(k);
  const sends = request.method !== "GET" && request.method !== "HEAD";
  if (sends && Number(request.headers.get("content-length") || 0) > MAX_BODY) return new Response("Too large", { status: 413 });
  headers.set("X-Edge-Secret", env.EDGE_SECRET);
  headers.set("X-Client-IP", request.headers.get("cf-connecting-ip") || "");
  headers.set("X-Edge-Host", url.host);  // not X-Forwarded-Host: the proxy in front of the hub overwrites that one with its own name
  let res;
  try {
    res = await fetchFn(new URL(url.pathname + url.search, env.ORIGIN), { method: request.method, headers, body: sends ? request.body : undefined, redirect: "manual" });
  } catch {
    return new Response("The hub is not reachable right now. Try again in a moment.", { status: 502 });
  }
  return new Response(res.body, { status: res.status, headers: res.headers });
}

export default { fetch: (request, env) => handle(request, env) };
