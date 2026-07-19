"""Build a deterministic, read-only packet for an independent BIM reviewer."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


class ReviewPacketError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_inside(workspace: Path, relative: str) -> Path:
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise ReviewPacketError(f"packet input escapes workspace: {relative}") from exc
    if not candidate.is_file():
        raise ReviewPacketError(f"packet input is missing: {relative}")
    return candidate


def deterministic_zip_write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(PurePosixPath(name).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100444 << 16
    archive.writestr(info, data)


def validate_gui_artifacts(contents: dict[str, bytes], gui_relatives: list[str]) -> None:
    """Fail closed on misleading media types or duplicated GUI evidence."""
    observed_digests: dict[str, str] = {}
    for relative in gui_relatives:
        data = contents[relative]
        suffix = PurePosixPath(relative).suffix.lower()
        if suffix in {".jpg", ".jpeg"} and not data.startswith(b"\xff\xd8\xff"):
            raise ReviewPacketError(f"GUI artifact extension/content mismatch: {relative}")
        if suffix == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ReviewPacketError(f"GUI artifact extension/content mismatch: {relative}")
        # Blender may store an uncompressed BLENDER header or a Zstandard-
        # compressed stream (magic 28 B5 2F FD) depending on save settings.
        if suffix == ".blend" and not (
            data.startswith(b"BLENDER") or data.startswith(b"\x28\xb5\x2f\xfd")
        ):
            raise ReviewPacketError(f"GUI artifact is not a Blender snapshot: {relative}")
        digest = hashlib.sha256(data).hexdigest().upper()
        prior = observed_digests.get(digest)
        if prior is not None:
            raise ReviewPacketError(f"duplicate GUI artifact bytes: {prior} and {relative}")
        observed_digests[digest] = relative


def build_review_packet(
    *,
    workspace: Path,
    request_path: Path,
    source_item_path: Path,
    readiness_index_path: Path,
    output_path: Path,
    manifest_output_path: Path,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    request = read_json(request_path)
    source_item = read_json(source_item_path)

    if request.get("status") != "AWAITING_INDEPENDENT_REVIEW":
        raise ReviewPacketError("review request is not awaiting independent review")
    constraints = request.get("reviewer_constraints", {})
    if constraints.get("read_only") is not True or constraints.get("may_modify_candidate") is not False:
        raise ReviewPacketError("review request does not enforce read-only inspection")

    candidate_record = request.get("candidate", {})
    candidate_path = resolve_inside(workspace, str(candidate_record.get("path", "")))
    candidate_sha = sha256_file(candidate_path)
    if candidate_sha != str(candidate_record.get("sha256", "")).upper():
        raise ReviewPacketError("candidate SHA-256 differs from the review request")

    authority_record = source_item.get("authority_baseline", {})
    authority_path = Path(str(authority_record.get("authority_file_path", ""))).resolve()
    if not authority_path.is_file():
        raise ReviewPacketError("registered authority source is unavailable")
    authority_live_sha = sha256_file(authority_path)
    authority_registered_sha = str(authority_record.get("sha256", "")).upper()
    if authority_live_sha != authority_registered_sha:
        raise ReviewPacketError("registered authority source SHA-256 changed")

    requested_relatives = [str(value) for value in request.get("inputs", [])]
    run_dir = candidate_path.parent
    run_relative = run_dir.relative_to(workspace).as_posix()
    fixed_relatives = [
        request_path.resolve().relative_to(workspace).as_posix(),
        source_item_path.resolve().relative_to(workspace).as_posix(),
        readiness_index_path.resolve().relative_to(workspace).as_posix(),
        candidate_record["path"],
        f"{run_relative}/external-integration-manifest.json",
        f"{run_relative}/standalone/auditable-stair-audit.json",
        "reports/repeatability.json",
        "docs/INDEPENDENT_REVIEW_PROTOCOL.md",
        "schemas/independent-review.schema.json",
        "schemas/promotion-manifest.schema.json",
    ]
    gui_dir = run_dir / "gui"
    gui_relatives = [
        path.relative_to(workspace).as_posix()
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.blend")
        for path in sorted(gui_dir.glob(pattern))
    ]
    relative_paths = sorted(set(requested_relatives + fixed_relatives + gui_relatives))

    files: list[dict[str, Any]] = []
    contents: dict[str, bytes] = {}
    for relative in relative_paths:
        path = resolve_inside(workspace, relative)
        data = path.read_bytes()
        contents[relative] = data
        files.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest().upper()})

    validate_gui_artifacts(contents, gui_relatives)

    # Primary source and authorization evidence may remain in the authorized
    # external capability workspace.  Copy their bytes into the private packet
    # under stable, non-local archive names; never expose the absolute source
    # path in the manifest.
    source_artifact = source_item.get("external_provenance", {}).get("source_artifact", {})
    if source_artifact:
        primary_source = Path(str(source_artifact.get("path", ""))).resolve()
        authorization = Path(str(source_artifact.get("authorization_manifest_path", ""))).resolve()
        if not primary_source.is_file():
            raise ReviewPacketError("primary source artifact is unavailable")
        if not authorization.is_file():
            raise ReviewPacketError("primary authorization record is unavailable")
        primary_source_sha = sha256_file(primary_source)
        registered_source_sha = str(source_artifact.get("sha256", "")).upper()
        if primary_source_sha != registered_source_sha:
            raise ReviewPacketError("primary source artifact SHA-256 differs from the source item")
        authorization_record = read_json(authorization)
        if authorization_record.get("authorization_confirmed") is not True:
            raise ReviewPacketError("primary authorization record is not confirmed")
        if str(authorization_record.get("drawing_sha256", "")).upper() != primary_source_sha:
            raise ReviewPacketError("primary authorization record is not bound to the source artifact")
        for archive_name, path in (
            (f"primary-source/{primary_source.name}", primary_source),
            (f"primary-source/{authorization.name}", authorization),
        ):
            if archive_name in contents:
                raise ReviewPacketError(f"duplicate packet archive path: {archive_name}")
            data = path.read_bytes()
            contents[archive_name] = data
            files.append(
                {
                    "path": archive_name,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest().upper(),
                }
            )

    files.sort(key=lambda record: record["path"])

    manifest = {
        "schema_version": "1.0",
        "packet_type": "INDEPENDENT_READ_ONLY_REVIEW",
        "status": "AWAITING_REVIEWER",
        "package_id": request["package_id"],
        "decision_id": request["decision_id"],
        "reviewer_role_id": constraints["required_role_id"],
        "modeler_role_id": constraints["prohibited_role_id"],
        "write_policy": "READ_ONLY",
        "candidate": {"sha256": candidate_sha, "included": True},
        "authority": {
            "rev": authority_record.get("rev"),
            "registered_sha256": authority_registered_sha,
            "live_sha256": authority_live_sha,
            "unchanged": True,
            "included": False,
            "exclusion_reason": "The full authority model remains in its authorized local source location and is verified by hash without broadening distribution.",
        },
        "required_result": request["required_result"],
        "review_output": request["output"],
        "archive_path_policy": "MANIFEST_PATH_IS_LITERAL_ZIP_PATH",
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() or manifest_output_path.exists():
        raise ReviewPacketError("review packet outputs already exist; immutable outputs are never overwritten")
    try:
        with zipfile.ZipFile(output_path, "x") as archive:
            deterministic_zip_write(archive, "review-packet-manifest.json", manifest_bytes)
            for record in files:
                deterministic_zip_write(archive, record["path"], contents[record["path"]])
        manifest_output_path.write_bytes(manifest_bytes)
    except Exception:
        output_path.unlink(missing_ok=True)
        manifest_output_path.unlink(missing_ok=True)
        raise
    return {
        "status": "REVIEW_PACKET_READY",
        "packet": str(output_path),
        "packet_sha256": sha256_file(output_path),
        "manifest": str(manifest_output_path),
        "file_count": len(files),
        "authority_unchanged": True,
        "candidate_sha256": candidate_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--source-item", type=Path, required=True)
    parser.add_argument("--readiness-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    result = build_review_packet(
        workspace=args.workspace,
        request_path=args.request,
        source_item_path=args.source_item,
        readiness_index_path=args.readiness_index,
        output_path=args.output,
        manifest_output_path=args.manifest_output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
