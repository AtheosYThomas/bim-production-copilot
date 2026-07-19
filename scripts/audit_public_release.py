"""Fail closed when a public release contains confidential or unapproved material."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".jsx", ".md", ".mjs", ".svg", ".ts", ".tsx", ".txt", ".yaml", ".yml"
}
SKIP_PARTS = {".git", ".next", ".vinext", "build", "dist", "node_modules", "outputs", "work"}
GENERIC_FORBIDDEN = {
    "local_windows_path": re.compile(r"[A-Za-z]:\\(?:Users|ProgramData|Windows)\\", re.I),
    "cloud_sync_path": re.compile(r"\\(?:OneDrive|Dropbox)\\", re.I),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "secret": re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[^\s,;]+", re.I),
    "internal_work_package": re.compile(r"\bWP-[0-9A-F]{16}\b", re.I),
    "ifc_global_id": re.compile(r"[\"']GlobalId[\"']\s*[:=]\s*[\"'][0-3][0-9A-Za-z_$]{21}[\"']", re.I),
}
PRIVATE_MODEL_SUFFIXES = {".ifc", ".ifczip", ".fcstd", ".blend"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_forbidden_terms(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def iter_public_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.name.startswith("dev-server") and path.suffix == ".log":
            continue
        yield path


def audit(root: Path, forbidden_terms: list[str]) -> tuple[list[dict], int]:
    findings: list[dict] = []
    scanned = 0
    for path in iter_public_files(root):
        scanned += 1
        if path.suffix.lower() in PRIVATE_MODEL_SUFFIXES:
            findings.append({"file": path.relative_to(root).as_posix(), "rule": "private_model_file"})
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(root).as_posix()
        for rule, pattern in GENERIC_FORBIDDEN.items():
            if pattern.search(text):
                findings.append({"file": relative, "rule": rule})
        folded = text.casefold()
        for term in forbidden_terms:
            if term.casefold() in folded:
                findings.append({"file": relative, "rule": "project_forbidden_term"})
                break
    return findings, scanned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--forbidden-terms", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--authorized-source", required=True, type=Path)
    parser.add_argument("--provenance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    authorization = json.loads(args.authorization.read_text(encoding="utf-8-sig"))
    provenance = json.loads(args.provenance.read_text(encoding="utf-8-sig"))
    expected_source_sha = str(authorization.get("drawing_sha256", "")).upper()
    source_sha = sha256(args.authorized_source)
    authorization_checks = {
        "authorization_confirmed": authorization.get("authorization_confirmed") is True,
        "publication_authorized": authorization.get("publication_authorized") is True,
        "sanitization_confirmed": authorization.get("sanitization_confirmed") is True,
        "authorized_source_hash_matches": bool(expected_source_sha) and source_sha == expected_source_sha,
        "provenance_source_hash_matches": provenance.get("authorization", {}).get("authorized_source_sha256") == source_sha,
    }

    asset_checks = []
    for asset in provenance.get("assets", []):
        asset_path = args.provenance.parent / asset["file"]
        asset_checks.append({
            "file": asset["file"],
            "exists": asset_path.is_file(),
            "sha256_matches": asset_path.is_file() and sha256(asset_path) == asset["sha256"],
        })

    findings, scanned = audit(args.root, read_forbidden_terms(args.forbidden_terms))
    passed = all(authorization_checks.values()) and all(
        item["exists"] and item["sha256_matches"] for item in asset_checks
    ) and not findings
    report = {
        "schema_version": "1.0",
        "gate": "PUBLIC_RELEASE_SANITIZATION",
        "result": "PASS" if passed else "FAIL",
        "files_scanned": scanned,
        "authorization_checks": authorization_checks,
        "asset_checks": asset_checks,
        "confidentiality_findings": findings,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
