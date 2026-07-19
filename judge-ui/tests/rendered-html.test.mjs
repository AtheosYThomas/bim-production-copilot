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
  assert.match(html, /role-separated agent workflow/i);
  assert.match(html, /does not claim three simultaneous specialist agents/i);
  assert.match(html, /ARCHITECTURAL PLAN/);
  assert.match(html, /STRUCTURAL DETAIL/);
  assert.match(html, /READINESS ENGINE/);
  assert.match(html, /READ-ONLY REVIEWER/);
  assert.match(html, /CROSS-SOURCE EVIDENCE MATRIX/);
  assert.match(html, /Flight width/);
  assert.match(html, /Architectural plan/);
  assert.match(html, /1,200 mm/);
  assert.match(html, /Architectural section/);
  assert.match(html, /4,200 mm/);
  assert.match(html, /Structural detail/);
  assert.match(html, /150 mm/);
  assert.match(html, /Complementary requirement closure/);
  assert.match(html, /No approved architectural or structural evidence registered/);
  assert.match(html, /A correct stair almost changed/i);
  assert.match(html, /508 unrelated BIM products/i);
  assert.match(html, /BLOCKED · 14 \/ 15/i);
  assert.match(html, /350 slabs · 124 beams/i);
  assert.match(html, /World coordinate system Y/i);
  assert.match(html, /2,400 mm/i);
  assert.match(html, /PASS — 0 \/ 0 \/ 0/i);
  assert.match(html, /REV228 — created/i);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton|[A-Z]:\\Users\\/i);
  assert.doesNotMatch(html, /WP-[0-9A-F]{16}|[0-9A-F]{64}|["']GlobalId["']\s*[:=]/i);
});
