import test from "node:test";
import assert from "node:assert/strict";
import { handle, forwarded } from "./src/worker.js";

const env = { EDGE_SECRET: "s3cret", ORIGIN: "https://origin.example" };
const spy = () => { const calls = []; const f = async (u, init) => { calls.push({ u: String(u), init }); return new Response("{}", { status: 200, headers: { "set-cookie": "a=b" } }); }; return { calls, f }; };

test("only the api and the privacy page are forwarded", () => {
  assert.ok(forwarded("/api/config") && forwarded("/privacy.html"));
  assert.ok(!forwarded("/") && !forwarded("/app.html") && !forwarded("/apix") && !forwarded("/../api/x") === true);
});
test("a request for anything else is a 404 and never reaches the origin", async () => {
  const { calls, f } = spy();
  assert.equal((await handle(new Request("https://n.workers.dev/secret"), env, f)).status, 404);
  assert.equal(calls.length, 0);
});
test("the origin gets the secret and the visitor address; spoofed headers are dropped", async () => {
  const { calls, f } = spy();
  const req = new Request("https://n.workers.dev/api/config?x=1", { headers: { "x-edge-secret": "evil", "x-client-ip": "6.6.6.6", "x-forwarded-for": "6.6.6.6", "cf-connecting-ip": "203.0.113.9", cookie: "hub_session=t", origin: "https://n.workers.dev" } });
  const res = await handle(req, env, f);
  const h = calls[0].init.headers;
  assert.equal(calls[0].u, "https://origin.example/api/config?x=1");
  assert.equal(h.get("x-edge-secret"), "s3cret"); assert.equal(h.get("x-client-ip"), "203.0.113.9");
  assert.equal(h.get("x-forwarded-host"), "n.workers.dev"); assert.equal(h.get("x-forwarded-for"), null);
  assert.equal(h.get("cookie"), "hub_session=t"); assert.equal(res.headers.get("set-cookie"), "a=b");
});
test("a missing secret or origin is a 503, an unreachable origin a 502, a big body a 413", async () => {
  const { f } = spy();
  assert.equal((await handle(new Request("https://n.workers.dev/api/x"), {}, f)).status, 503);
  assert.equal((await handle(new Request("https://n.workers.dev/api/x"), env, async () => { throw new Error("down"); })).status, 502);
  const big = new Request("https://n.workers.dev/api/x", { method: "POST", headers: { "content-length": "500000" }, body: "x" });
  assert.equal((await handle(big, env, f)).status, 413);
});
