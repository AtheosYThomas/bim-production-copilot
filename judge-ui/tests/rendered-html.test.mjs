import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the judge-facing product", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /BIM Production Copilot/i);
  assert.match(html, /READY TO MODEL/);
  assert.match(html, /HUMAN CLARIFICATION/);
  assert.match(html, /non-target differences/i);
  assert.match(html, /No agent can approve its own work/i);
  assert.match(html, /The stair was correct/i);
  assert.match(html, /508 unintended non-target changes/i);
  assert.match(html, /PASS — 0 \/ 0 \/ 0/i);
  assert.match(html, /REV228 — created/i);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|[A-Z]:\\Users\\/i);
  assert.doesNotMatch(html, /WP-[0-9A-F]{16}|[0-9A-F]{64}|["']GlobalId["']\s*[:=]/i);
});
