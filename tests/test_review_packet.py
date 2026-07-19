import json
import zipfile
from pathlib import Path

import pytest

from scripts.prepare_independent_review_packet import ReviewPacketError, build_review_packet, sha256_file
from scripts.verify_independent_review_packet import ReviewPacketVerificationError, verify_review_packet


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    elif isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path):
    authority = tmp_path / "authority.ifc"
    candidate = tmp_path / "work/AUTHORIZED-STAIR-01/run-01/candidate.ifc"
    _write(authority, b"authority")
    _write(candidate, b"candidate")
    candidate_sha = sha256_file(candidate)
    primary_source = tmp_path / "external/source.pdf"
    authorization = tmp_path / "external/authorization.json"
    _write(primary_source, b"authorized source")
    primary_source_sha = sha256_file(primary_source)
    _write(authorization, {
        "authorization_confirmed": True,
        "drawing_sha256": primary_source_sha,
    })
    source = tmp_path / "private/item.json"
    _write(source, {
        "authority_baseline": {"authority_file_path": str(authority), "sha256": sha256_file(authority), "rev": "REV-1"},
        "external_provenance": {"source_artifact": {
            "path": str(primary_source),
            "sha256": primary_source_sha,
            "authorization_manifest_path": str(authorization),
        }},
    })
    request = tmp_path / "work/AUTHORIZED-STAIR-01/run-01/request.json"
    fixed = {
        "work/AUTHORIZED-STAIR-01/run-01/external-integration-manifest.json": {},
        "work/AUTHORIZED-STAIR-01/run-01/standalone/auditable-stair-audit.json": {},
        "reports/repeatability.json": {},
        "docs/INDEPENDENT_REVIEW_PROTOCOL.md": "protocol",
        "schemas/independent-review.schema.json": {},
        "schemas/promotion-manifest.schema.json": {},
    }
    for path, value in fixed.items():
        _write(tmp_path / path, value)
    _write(request, {
        "status": "AWAITING_INDEPENDENT_REVIEW", "package_id": "WP-1", "decision_id": "DEC-1",
        "candidate": {"path": candidate.relative_to(tmp_path).as_posix(), "sha256": candidate_sha},
        "reviewer_constraints": {"required_role_id": "reviewer", "prohibited_role_id": "modeler", "read_only": True, "may_modify_candidate": False},
        "inputs": [], "required_result": {"B0": 0, "B1": 0, "B2": 0}, "output": "review.json",
    })
    index = tmp_path / "private/index.json"
    _write(index, {})
    return request, source, index, authority


def test_review_packet_is_hash_locked_and_read_only(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    output = tmp_path / "packet.zip"
    manifest = tmp_path / "manifest.json"
    result = build_review_packet(workspace=tmp_path, request_path=request, source_item_path=source, readiness_index_path=index, output_path=output, manifest_output_path=manifest)
    assert result["status"] == "REVIEW_PACKET_READY"
    assert result["authority_unchanged"] is True
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert names[0] == "review-packet-manifest.json"
        embedded = json.loads(archive.read(names[0]))
        assert set(names[1:]) == {record["path"] for record in embedded["files"]}
        assert not any(name.startswith("evidence/") for name in names)
        assert "primary-source/source.pdf" in names
        assert "primary-source/authorization.json" in names
    assert embedded["write_policy"] == "READ_ONLY"
    assert embedded["archive_path_policy"] == "MANIFEST_PATH_IS_LITERAL_ZIP_PATH"
    assert embedded["authority"]["included"] is False
    assert embedded["candidate"]["included"] is True
    verification = verify_review_packet(output)
    assert verification["status"] == "REVIEW_PACKET_VERIFIED"
    assert verification["file_count"] == len(embedded["files"])


def test_review_packet_includes_hash_locked_blend_snapshot(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    blend = tmp_path / "work/AUTHORIZED-STAIR-01/run-01/gui/run-01-bonsai-gui.blend"
    _write(blend, b"BLENDER-v300")
    output = tmp_path / "packet.zip"
    manifest = tmp_path / "manifest.json"
    build_review_packet(
        workspace=tmp_path,
        request_path=request,
        source_item_path=source,
        readiness_index_path=index,
        output_path=output,
        manifest_output_path=manifest,
    )
    with zipfile.ZipFile(output) as archive:
        embedded = json.loads(archive.read("review-packet-manifest.json"))
        record = next(item for item in embedded["files"] if item["path"].endswith("run-01-bonsai-gui.blend"))
        assert archive.read(record["path"]) == b"BLENDER-v300"
        assert record["sha256"] == sha256_file(blend)


def test_review_packet_accepts_zstd_compressed_blend_snapshot(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    blend = tmp_path / "work/AUTHORIZED-STAIR-01/run-01/gui/run-01-compressed.blend"
    _write(blend, b"\x28\xb5\x2f\xfdcompressed-blend")
    result = build_review_packet(
        workspace=tmp_path,
        request_path=request,
        source_item_path=source,
        readiness_index_path=index,
        output_path=tmp_path / "packet.zip",
        manifest_output_path=tmp_path / "manifest.json",
    )
    assert result["status"] == "REVIEW_PACKET_READY"


def test_review_packet_rejects_gui_extension_content_mismatch(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    bad_png = tmp_path / "work/AUTHORIZED-STAIR-01/run-01/gui/overview.png"
    _write(bad_png, b"\xff\xd8\xffnot-a-png")
    with pytest.raises(ReviewPacketError, match="extension/content mismatch"):
        build_review_packet(
            workspace=tmp_path,
            request_path=request,
            source_item_path=source,
            readiness_index_path=index,
            output_path=tmp_path / "packet.zip",
            manifest_output_path=tmp_path / "manifest.json",
        )


def test_review_packet_rejects_duplicate_gui_artifact_bytes(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    _write(tmp_path / "work/AUTHORIZED-STAIR-01/run-01/gui/a.jpg", b"\xff\xd8\xffsame")
    _write(tmp_path / "work/AUTHORIZED-STAIR-01/run-01/gui/b.jpg", b"\xff\xd8\xffsame")
    with pytest.raises(ReviewPacketError, match="duplicate GUI artifact bytes"):
        build_review_packet(
            workspace=tmp_path,
            request_path=request,
            source_item_path=source,
            readiness_index_path=index,
            output_path=tmp_path / "packet.zip",
            manifest_output_path=tmp_path / "manifest.json",
        )


def test_review_packet_rejects_changed_authority(tmp_path: Path) -> None:
    request, source, index, authority = _fixture(tmp_path)
    authority.write_bytes(b"changed")
    with pytest.raises(ReviewPacketError, match="authority source SHA-256 changed"):
        build_review_packet(workspace=tmp_path, request_path=request, source_item_path=source, readiness_index_path=index, output_path=tmp_path / "packet.zip", manifest_output_path=tmp_path / "manifest.json")


def test_review_packet_verifier_rejects_tampering(tmp_path: Path) -> None:
    request, source, index, _ = _fixture(tmp_path)
    output = tmp_path / "packet.zip"
    build_review_packet(workspace=tmp_path, request_path=request, source_item_path=source, readiness_index_path=index, output_path=output, manifest_output_path=tmp_path / "manifest.json")
    with zipfile.ZipFile(output, "a") as archive:
        archive.writestr("evidence/unlisted.txt", b"tampered")
    with pytest.raises(ReviewPacketVerificationError, match="inventory differs"):
        verify_review_packet(output)
