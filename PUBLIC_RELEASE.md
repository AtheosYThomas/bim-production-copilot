# Public release scope

This snapshot contains the machine-readable BIM readiness engine, controlled
work-package and promotion contracts, synthetic tests, and the judge-facing UI.
It intentionally excludes authority models, project files, private evidence,
local work candidates, review records, internal identifiers, deployment IDs,
and customer or project names.

The UI uses two separately publication-authorized, redacted raster assets. Their
hashes and provenance are recorded in
`judge-ui/public/asset-provenance.json`. The demonstration reports the sanitized
result of a separate read-only review and a controlled new-REV promotion. The
private review record, model files, authority files, hashes, work package IDs,
and authorization originals remain excluded from this snapshot.

Before distribution, run the public-release auditor with an authorized source,
authorization manifest, and project-specific forbidden-term list supplied
outside this repository. The auditor verifies authorization, source and asset
hashes, and confidentiality rules; any finding fails the release.
