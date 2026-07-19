# Independent review protocol

The reviewer must be a role separate from the evidence researcher, readiness
engine, model builder, and authority controller. The review is read-only: it may
not edit the candidate, issue a replacement work package, or promote a REV.

The immutable handoff is the packet named by the authority controller for the
current run. Before inspection, verify that packet without extraction:

```powershell
python scripts/verify_independent_review_packet.py <packet.zip>
```

The verifier must return `REVIEW_PACKET_VERIFIED`, the package and decision IDs
declared by the packet manifest, the manifest-declared file count, the locked
candidate SHA, the registered authority SHA, `authority_unchanged: true`, and
`write_policy: READ_ONLY`. The manifest is the only authority for run ID,
inventory size, literal ZIP paths, and output binding; this protocol never
hard-codes those values.

Review the immutable request listed in the packet manifest and every input
listed by that request. Recompute the authority and candidate SHA-256 values
before and after inspection. Verify evidence sufficiency, package scope,
expected-versus-actual output, regression results, non-target difference 0,
GUI evidence, role separation, and the authority source's unchanged status.

Classify findings as:

- `B0`: authority integrity, authorization, hash, or unsafe-write failure.
- `B1`: material evidence, geometry, scope, regression, or Gate failure.
- `B2`: auditability or presentation issue that must be resolved before release.

Return one machine-readable review object conforming to
`schemas/independent-review.schema.json` through the reviewer session. The
reviewer must not create or modify any file, including the requested output
path. The authority controller may persist the returned object after the
reviewer session ends. A PASS requires candidate hashes to remain identical,
an empty findings array, and exactly `B0=0`, `B1=0`, `B2=0`. Any other result
keeps promotion locked.
