"use client";

import { useState } from "react";
import demoStatus from "../public/demo-status.json";

type ItemKey = "ready" | "clarification";

const statusCounts = [
  { label: "READY TO MODEL", value: 1, tone: "ready" },
  { label: "CROSSCHECK", value: 0, tone: "crosscheck" },
  { label: "HUMAN CLARIFICATION", value: 1, tone: "clarification" },
  { label: "COORDINATION", value: 0, tone: "coordination" },
  { label: "BLOCKED", value: 0, tone: "blocked" },
];

const items = {
  ready: {
    id: "ETA-01",
    title: "Stair work package",
    subtitle: "Evidence-closed target scope",
    status: "READY_TO_MODEL",
    tone: "ready",
    modeling: "ALLOWED IN ISOLATED WORK ONLY",
    reason:
      "Fourteen accepted evidence records close geometry, elevation, orientation and interface requirements against the live authority baseline.",
    conflict: "None. Unresolved assumptions: 0.",
    next: demoStatus.ready_next_action,
    package: "CONTROLLED PACKAGE ETA-01",
    rev: demoStatus.current_rev_status,
    evidence: [
      ["4,200 mm", "floor height", "99%"],
      ["1,200 mm", "flight width", "96%"],
      ["250 mm", "tread depth", "99%"],
      ["13 + 12", "riser split", "98%"],
    ],
  },
  clarification: {
    id: "CTX-01",
    title: "Adjacent structural interface",
    subtitle: "Real authority product · evidence not registered",
    status: "HUMAN_CLARIFICATION_REQUIRED",
    tone: "clarification",
    modeling: "DENIED",
    reason:
      "No approved architectural or structural evidence is registered for this product and its interface with the stair scope.",
    conflict:
      "Missing: geometry and dimensions, interface clearance, coordinate definition and expected change set.",
    next:
      "Ask the design authority for the minimum interface detail and clearance confirmation; then create a new evidence version for reevaluation.",
    package: "NOT ISSUED",
    rev: "Baseline unchanged",
    evidence: [],
  },
} as const;

const readyGates = [
  ["01", "Evidence", "14 accepted records", "pass"],
  ["02", "Data audit", "34 / 34", "pass"],
  ["03", "Regression", "15 / 15", "pass"],
  ["04", "Non-target diff", "0 across 2,334", "pass"],
  ["05", "Bonsai GUI", "PASS · IFC unchanged", "pass"],
  ["06", "Independent review", demoStatus.independent_review.result, demoStatus.independent_review.state],
  ["07", "New authority REV", demoStatus.promotion.result, demoStatus.promotion.state],
];

export default function Home() {
  const [selected, setSelected] = useState<ItemKey>("ready");
  const item = items[selected];

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="BIM Production Copilot home">
          <span className="brand-mark">BP</span>
          <span>
            <strong>BIM PRODUCTION COPILOT</strong>
            <small>GOVERNANCE BEFORE GEOMETRY</small>
          </span>
        </a>
        <div className="topbar-meta">
          <span className="live-dot" aria-hidden="true" />
          AUTHORIZED REAL-PROJECT DEMO
        </div>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">PRODUCTION READINESS · MEASURED FROM MACHINE DECISIONS</p>
          <h1>Know what is safe to model <em>before</em> BIM production begins.</h1>
          <p className="hero-lede">
            AI evaluates source sufficiency, controls scope, and blocks unsafe work before any
            agent can touch the authoritative BIM.
          </p>
          <div className="hero-facts" aria-label="Project summary">
            <div><strong>2</strong><span>real items assessed</span></div>
            <div><strong>1</strong><span>controlled package</span></div>
            <div><strong>0</strong><span>non-target differences</span></div>
          </div>
        </div>
        <figure className="hero-visual">
          <img src="/authorized-bim-oblique.png" alt="Publication-authorized stair candidate shown within a redacted BIM context" />
          <figcaption>
            <span>ISOLATED WORK CANDIDATE</span>
            Publication-authorized, redacted project view
          </figcaption>
        </figure>
      </section>

      <section className="readiness" aria-labelledby="readiness-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PROJECT READINESS</p>
            <h2 id="readiness-title">Every item ends in exactly one state.</h2>
          </div>
          <p>Counts below are measured from two real decision artifacts. Zero is a real result.</p>
        </div>
        <div className="status-grid">
          {statusCounts.map((status) => (
            <article className={`status-card ${status.tone}`} key={status.label}>
              <span className="status-label">{status.label}</span>
              <strong>{status.value}</strong>
              <span className="status-bar" aria-hidden="true" />
            </article>
          ))}
        </div>
      </section>

      <section className="decision-explorer" aria-labelledby="explorer-title">
        <div className="explorer-sidebar">
          <div className="sidebar-title">
            <p className="eyebrow">REAL PROJECT ITEMS</p>
            <h2 id="explorer-title">Decision explorer</h2>
          </div>
          <div className="item-list" role="list" aria-label="Readiness decisions">
            {(Object.keys(items) as ItemKey[]).map((key) => {
              const candidate = items[key];
              return (
                <button
                  type="button"
                  className={`item-button ${selected === key ? "active" : ""}`}
                  onClick={() => setSelected(key)}
                  aria-pressed={selected === key}
                  data-testid={`item-${key}`}
                  key={key}
                >
                  <span className={`item-dot ${candidate.tone}`} aria-hidden="true" />
                  <span>
                    <small>{candidate.id}</small>
                    <strong>{candidate.title}</strong>
                    <em>{candidate.subtitle}</em>
                  </span>
                  <b aria-hidden="true">›</b>
                </button>
              );
            })}
          </div>
          <div className="sidebar-rule">
            <span>WRITE POLICY</span>
            <strong>Authority BIM is read-only</strong>
            <small>No modeling agent can self-promote.</small>
          </div>
        </div>

        <article className="decision-panel" data-testid="decision-panel">
          <div className="decision-header">
            <div>
              <p className="eyebrow">{item.id} · MACHINE DECISION</p>
              <h2>{item.title}</h2>
            </div>
            <span className={`decision-badge ${item.tone}`}>{item.status}</span>
          </div>

          <div className="decision-summary">
            <div className={`modeling-callout ${item.tone}`}>
              <span>MODELING</span>
              <strong>{item.modeling}</strong>
            </div>
            <dl>
              <div><dt>Decision reason</dt><dd>{item.reason}</dd></div>
              <div><dt>Missing / conflicting</dt><dd>{item.conflict}</dd></div>
              <div><dt>Recommended next action</dt><dd>{item.next}</dd></div>
              <div><dt>Work package</dt><dd className="mono">{item.package}</dd></div>
              <div><dt>Current REV status</dt><dd>{item.rev}</dd></div>
            </dl>
          </div>

          {selected === "ready" ? (
            <>
              <div className="evidence-strip">
                <div className="evidence-image">
                  <img src="/authorized-drawing-evidence.png" alt="Publication-authorized redacted stair drawing with traceable measured values" />
                  <span>DRAWING EVIDENCE · REDACTED FOR PUBLICATION</span>
                </div>
                <div className="evidence-values">
                  {item.evidence.map(([value, label, confidence]) => (
                    <div key={label}>
                      <strong>{value}</strong>
                      <span>{label}</span>
                      <small>{confidence} CONF.</small>
                    </div>
                  ))}
                </div>
              </div>
              <div className="gates">
                <div className="subheading">
                  <div><p className="eyebrow">CONTROLLED PRODUCTION CYCLE</p><h3>Independent review passed. A new REV was created.</h3></div>
                  <span>VERIFIED FINAL STATUS</span>
                </div>
                <div className="gate-track">
                  {readyGates.map(([step, label, result, state]) => (
                    <div className={`gate ${state}`} key={step}>
                      <span>{step}</span><strong>{label}</strong><small>{result}</small>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="blocked-proof">
              <div className="stop-mark">NO MODEL<br />WRITTEN</div>
              <div>
                <p className="eyebrow">SAFE FAILURE IS A PRODUCT FEATURE</p>
                <h3>No work package. No IFC change. One precise clarification request.</h3>
                <p>
                  The baseline hash was checked and remained unchanged. The readiness engine
                  stopped before modeling because the minimum evidence contract was incomplete.
                </p>
                <div className="blocked-facts">
                  <span>WORK PACKAGE <strong>NOT ISSUED</strong></span>
                  <span>IFC MODIFICATION <strong>0</strong></span>
                  <span>NEXT ACTION <strong>MINIMUM RFI</strong></span>
                </div>
              </div>
            </div>
          )}
        </article>
      </section>

      <section className="defect-story" aria-labelledby="defect-title">
        <div className="defect-intro">
          <p className="eyebrow">A REAL DEFECT THE GATE STOPPED</p>
          <h2 id="defect-title">The stair was correct. <em>The integration was not.</em></h2>
          <p>
            Authority Gate stopped 508 unintended non-target changes before they reached the
            authoritative BIM. The source authority was never modified.
          </p>
        </div>
        <dl className="defect-ledger">
          <div><dt>Standalone stair audit</dt><dd className="pass-text">PASS · 34 / 34</dd></div>
          <div><dt>Initial authority regression</dt><dd className="blocked-text">BLOCKED</dd></div>
          <div><dt>Unintended non-target changes</dt><dd className="blocked-text">508</dd></div>
          <div><dt>Root cause</dt><dd>Shared IFC representation context</dd></div>
          <div><dt>After repair</dt><dd className="pass-text">0 differences across 2,334 products</dd></div>
          <div><dt>Authority source modified</dt><dd className="pass-text">NO</dd></div>
        </dl>
        <div className="defect-flow" aria-label="Defect containment sequence">
          <span>34 / 34<br /><b>STAIR PASS</b></span><i>→</i>
          <span>508<br /><b>INTEGRATION BLOCKED</b></span><i>→</i>
          <span>ROOT CAUSE<br /><b>CONTEXT ISOLATED</b></span><i>→</i>
          <span>0 / 2,334<br /><b>SAFE TO REVIEW</b></span>
        </div>
      </section>

      <section className="integrity">
        <div>
          <p className="eyebrow">AUTHORITY INTEGRITY</p>
          <h2>One writer. Separate reviewer. Controlled promotion.</h2>
        </div>
        <div className="integrity-flow" aria-label="Governed production sequence">
          <span>AUTHORITY<br /><b>READ ONLY</b></span><i>→</i>
          <span>WORK<br /><b>ISOLATED</b></span><i>→</i>
          <span>REVIEW<br /><b>INDEPENDENT</b></span><i>→</i>
          <span>NEW REV<br /><b>{demoStatus.promotion.flow_label}</b></span>
        </div>
        <dl className="hashes">
          <div><dt>REV227 — unchanged</dt><dd>VERIFIED — VALUE WITHHELD</dd></div>
          <div><dt>WORK-ETA-01 — reviewed</dt><dd>INDEPENDENT REVIEW · 0 / 0 / 0</dd></div>
          <div><dt>REV228 — created</dt><dd className="pass-text">CONTROLLED PROMOTION</dd></div>
        </dl>
        <dl className="hashes secondary-hashes">
          <div><dt>Source authority SHA-256</dt><dd>VERIFIED — VALUE WITHHELD</dd></div>
          <div><dt>New authority SHA-256</dt><dd>VERIFIED — VALUE WITHHELD</dd></div>
          <div><dt>Authority source</dt><dd className="pass-text">UNCHANGED</dd></div>
        </dl>
      </section>

      <footer>
        <p>AI can research and model. <strong>No agent can approve its own work.</strong></p>
        <span>PUBLIC DEMO · CONFIDENTIAL PROJECT IDENTIFIERS WITHHELD</span>
      </footer>
    </main>
  );
}
