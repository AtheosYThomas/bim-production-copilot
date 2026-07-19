# BIM Production Copilot

Role-Separated Evidence and Model Governance for Authoritative BIM.

This standalone project decides **what may safely become BIM, what may not, and
why**. Its primary outputs are machine-readable readiness decisions and, only
for `READY_TO_MODEL` items, complete controlled work packages.

It is not a BIM component generator. `drawing-evidence-copilot` remains an
unchanged external capability. Authority IFC files are opened read-only for
fingerprinting; all future modeling must occur in isolated, disposable `WORK`
models.

## Readiness states

- `READY_TO_MODEL`
- `CROSSCHECK_REQUIRED`
- `HUMAN_CLARIFICATION_REQUIRED`
- `COORDINATION_REQUIRED`
- `BLOCKED`

The engine is fail-closed. Missing authorization, an authority SHA mismatch,
or invalid role separation returns `BLOCKED`. Conflicting evidence returns
`COORDINATION_REQUIRED`. Every non-ready result forbids modeling and produces
no work package.

## Implemented proof

The product keeps a deliberately small decision core:

```text
source item -> evidence records -> readiness decision -> controlled work package
```

The real-project proof adds controlled external modeling, isolated regression,
GUI Gate records, a fail-closed promotion controller, and a judge-facing status
UI. It still does not add a database, new BIM builder, or generic multi-agent
execution platform. Promotion can create a brand-new derived REV only after an
independent reviewer reports 0 critical, 0 major, and 0 unresolved findings;
the registered authority source can never be overwritten.

The demonstrated claim is a **role-separated agent workflow**: evidence research,
readiness reasoning, modeling, read-only review, and authority promotion have
separate role identities. The independent reviewer also ran in a separate session.
Architectural, structural, and section/detail evidence are distinct evidence streams
handled by one external research capability; this proof does not claim three
simultaneous specialist research agents.

## CLI

Install the core and test dependencies:

```powershell
python -m pip install -e ".[test]"
```

Capture a read-only IFC baseline:

```powershell
python -m bim_authority_gate capture-baseline `
  --authority private/authority.ifc `
  --rev REV-001 `
  --coordinate-origin 0 0 0 `
  --output private/authority-baseline.json
```

Evaluate one item against the live authority file:

```powershell
python -m bim_authority_gate evaluate `
  --input private/items/eta-stair.json `
  --authority private/authority.ifc `
  --decision-output private/decisions/eta-stair.json `
  --work-package-output private/work-packages/eta-stair.json
```

`--authority` may be omitted when the private source-item already contains its
registered `authority_file_path`; the live SHA is still recomputed on every run.

Output files are never overwritten. A non-ready evaluation may write the
decision file, but never writes the requested work-package file.

The `promote` command accepts the source item, work package, modeling and Gate
records, independent review, and readiness index. It fails closed unless every
binding, hash, role-separation rule, GUI requirement, regression check, and
review threshold passes, and writes only to new paths supplied by the authority
controller.

## Judge UI and public safety

The judge-facing UI lives in `judge-ui/`. It leads with the role-separated evidence,
readiness, modeling, and independent-check workflow, then displays the five readiness
states, one controlled ready case, one safe failure, and a real 508-change regression
defect as proof that post-model cross-checking matters. Public assets are separately authorized and their
hashes are recorded in `judge-ui/public/asset-provenance.json`. Run
`scripts/audit_public_release.py` before any public release; it fails closed on
confidential terms, local paths, internal package identifiers, private model
files, missing authorization, or asset-hash drift.

## Independent review and final video

`scripts/prepare_independent_review_packet.py` creates an immutable private
review packet with a deterministic inventory and SHA-256 for every input.
`scripts/verify_independent_review_packet.py` lets a separate reviewer verify
the packet without extraction or mutation.

The optional video tooling is installed with `python -m pip install -e
".[video]"`. The Build Week submission video is 2 minutes 45 seconds and tells
the same public-safe story as this repository: cross-source evidence before
modeling, safe release or safe block, isolated work, full-model comparison,
separate read-only review, and controlled creation of a new official version.
It was rendered only after the review returned 0/0/0, the source authority
remained unchanged, every public-safety Gate passed, and the exact model visuals
received narrow submission-video authorization.

This public repository intentionally excludes the raw model screenshots, raw
IFC and Blender files, private authorization record, internal REV identifier,
project name, local paths, and user names. `scripts/render_award_video.py`
remains a 60-second minimal reproducibility sample of the same fail-closed Gates;
it is not the final 2:45 submission video renderer.

## License and excluded materials

The source code and repository documentation are licensed under the
[MIT License](LICENSE).

The license does **not** grant rights to any project BIM/IFC model, Blender
file, source drawing, project evidence, authorization record, or original model
image. Those materials are intentionally excluded from this repository. Any
publication authorization used for the submission video is narrow, separate,
and does not permit redistribution of the underlying project materials.
