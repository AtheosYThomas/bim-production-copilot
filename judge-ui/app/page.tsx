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
          <p className="eyebrow">ROLE-SEPARATED EVIDENCE + MODEL GOVERNANCE</p>
          <h1>Cross-check evidence <em>before</em> BIM production begins.</h1>
          <p className="hero-lede">
            Separate roles research traceable drawing evidence, classify readiness, control
            modeling scope, and independently review results before authority promotion.
          </p>
          <div className="hero-facts" aria-label="Project summary">
            <div><strong>14</strong><span>accepted evidence records</span></div>
            <div><strong>2</strong><span>real readiness outcomes</span></div>
            <div><strong>5</strong><span>separated role boundaries</span></div>
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

      <section className="role-workflow" aria-labelledby="workflow-title">
        <div className="workflow-heading">
          <div>
            <p className="eyebrow">HOW THE PRODUCT WORKS</p>
            <h2 id="workflow-title">Evidence is cross-checked before geometry. Models are cross-checked before authority.</h2>
          </div>
          <p>
            This demonstration proves a role-separated agent workflow. One evidence-research
            capability covers multiple disciplines; it does not claim three simultaneous specialist agents.
          </p>
        </div>
        <div className="workflow-grid">
          <article>
            <span>01 · EVIDENCE RESEARCH</span>
            <h3>Traceable source claims</h3>
            <div className="discipline-chips"><b>ARCHITECTURAL PLAN</b><b>STRUCTURAL DETAIL</b><b>SECTION / DETAIL</b></div>
            <p>An external research role records source, region, discipline, confidence and authorization.</p>
          </article>
          <article>
            <span>02 · READINESS ENGINE</span>
            <h3>Cross-check requirements</h3>
            <div className="workflow-outcomes"><b>STAIR · 14 / 14 → READY</b><b>INTERFACE · MISSING → HUMAN</b></div>
            <p>A separate reasoning role decides whether evidence closes the scope. No evidence means no model.</p>
          </article>
          <article>
            <span>03 · CONTROLLED MODELING</span>
            <h3>Package before production</h3>
            <div className="workflow-outcomes"><b>READY → WORK PACKAGE</b><b>ISOLATED WORK ONLY</b></div>
            <p>The builder receives explicit targets and protected non-targets. Authority remains read-only.</p>
          </article>
          <article>
            <span>04 · INDEPENDENT CHECKS</span>
            <h3>Model result cross-check</h3>
            <div className="workflow-outcomes"><b>FULL REGRESSION</b><b>READ-ONLY REVIEWER</b></div>
            <p>The reviewer is a separate session and cannot build, repair, reclassify, or self-promote.</p>
          </article>
        </div>
        <div className="evidence-matrix" aria-labelledby="evidence-matrix-title">
          <div className="matrix-heading">
            <div>
              <p className="eyebrow">CROSS-SOURCE EVIDENCE MATRIX</p>
              <h3 id="evidence-matrix-title">The sources close different parts of one bounded stair requirement set.</h3>
            </div>
            <p>Complementary requirement closure across authorized sources — not a claim that every value is independently duplicated.</p>
          </div>
          <div className="matrix-table" role="table" aria-label="Verified stair evidence matrix">
            <div className="matrix-row matrix-labels" role="row">
              <span role="columnheader">Requirement</span><span role="columnheader">Authorized source</span><span role="columnheader">Accepted value</span><span role="columnheader">Decision</span>
            </div>
            <div className="matrix-row" role="row">
              <strong role="cell">Flight width</strong><span role="cell">Architectural plan</span><b role="cell">1,200 mm</b><em role="cell">ACCEPTED</em>
            </div>
            <div className="matrix-row" role="row">
              <strong role="cell">Floor height</strong><span role="cell">Architectural section</span><b role="cell">4,200 mm</b><em role="cell">ACCEPTED</em>
            </div>
            <div className="matrix-row" role="row">
              <strong role="cell">Waist thickness</strong><span role="cell">Structural detail</span><b role="cell">150 mm</b><em role="cell">ACCEPTED</em>
            </div>
          </div>
          <div className="matrix-results">
            <div className="matrix-ready"><span>STAIR SCOPE</span><strong>14 / 14 requirements closed</strong><b>READY_TO_MODEL</b></div>
            <div className="matrix-human"><span>ADJACENT INTERFACE</span><strong>No approved architectural or structural evidence registered</strong><b>HUMAN_CLARIFICATION_REQUIRED</b></div>
          </div>
        </div>
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
          <h2 id="defect-title">A correct stair almost changed <em>508 unrelated BIM products.</em></h2>
          <p>
            The stair passed in isolation. The first integrated WORK candidate did not.
            Authority Gate blocked 508 unintended non-target representation differences before
            promotion, so the authoritative BIM was never modified.
          </p>
        </div>
        <div className="defect-comparison">
          <article className="defect-before">
            <div className="comparison-label"><span>BEFORE</span><strong>INITIAL WORK INTEGRATION</strong></div>
            <div className="audit-line"><span>Isolated stair audit</span><strong>34 / 34 PASS</strong></div>
            <div className="regression-line"><span>Authority regression</span><strong>BLOCKED · 14 / 15</strong></div>
            <div className="defect-number"><strong>508</strong><span>unintended non-target<br />representation differences</span></div>
            <p className="type-breakdown">350 slabs · 124 beams · 19 annotations · 13 columns · 2 stairs</p>
          </article>
          <article className="defect-cause">
            <div className="comparison-label"><span>ROOT CAUSE</span><strong>SHARED IFC CONTEXT</strong></div>
            <p>World coordinate system Y</p>
            <div className="coordinate-change"><strong>0</strong><i>→</i><strong>2,400 mm</strong></div>
            <small>A shared representation context was changed inside the candidate. The Gate detected its downstream fingerprint impact.</small>
          </article>
          <article className="defect-after">
            <div className="comparison-label"><span>AFTER</span><strong>WORK-ONLY REPAIR</strong></div>
            <div className="after-result"><strong>0 / 2,334</strong><span>protected non-target differences</span></div>
            <ul>
              <li>Regression rerun <strong>15 / 15 PASS</strong></li>
              <li>Independent review <strong>0 / 0 / 0</strong></li>
              <li>Authority source <strong>UNCHANGED</strong></li>
            </ul>
          </article>
        </div>
        <div className="defect-flow" aria-label="Defect containment sequence">
          <span>34 / 34<br /><b>STAIR PASS</b></span><i>→</i>
          <span>508<br /><b>GATE BLOCKED</b></span><i>→</i>
          <span>WORK ONLY<br /><b>CONTEXT REPAIRED</b></span><i>→</i>
          <span>0 / 2,334<br /><b>REVIEW + PROMOTION</b></span>
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
