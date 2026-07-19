"""Verify an independent-review packet without extracting or modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any


class ReviewPacketVerificationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewPacketVerificationError(message)


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def verify_review_packet(path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        _require(bool(names) and names[0] == "review-packet-manifest.json", "packet manifest is missing or not first")
        _require(len(names) == len(set(names)), "packet contains duplicate paths")
        _require(all(_safe_name(name) for name in names), "packet contains an unsafe path")
        _require(archive.testzip() is None, "packet CRC validation failed")
        manifest = json.loads(archive.read(names[0]).decode("utf-8"))
        _require(manifest.get("packet_type") == "INDEPENDENT_READ_ONLY_REVIEW", "packet type is invalid")
        _require(manifest.get("status") == "AWAITING_REVIEWER", "packet is not awaiting a reviewer")
        _require(manifest.get("write_policy") == "READ_ONLY", "packet review policy is not read-only")
        _require(manifest.get("authority", {}).get("unchanged") is True, "authority source was not verified unchanged")
        _require(manifest.get("authority", {}).get("included") is False, "full authority model must not be distributed in the packet")
        _require(manifest.get("candidate", {}).get("included") is True, "candidate IFC is missing from the packet")

        _require(
            manifest.get("archive_path_policy") == "MANIFEST_PATH_IS_LITERAL_ZIP_PATH",
            "packet archive path policy is missing or invalid",
        )
        expected_entries = {record["path"]: record for record in manifest.get("files", [])}
        _require(set(names[1:]) == set(expected_entries), "packet file inventory differs from the manifest")
        for name, record in expected_entries.items():
            data = archive.read(name)
            _require(len(data) == record["bytes"], f"packet byte count differs: {name}")
            actual_sha = hashlib.sha256(data).hexdigest().upper()
            _require(actual_sha == record["sha256"], f"packet SHA-256 differs: {name}")
        candidate_path = next(
            (name for name, record in expected_entries.items() if record["sha256"] == manifest["candidate"]["sha256"]),
            None,
        )
        _require(candidate_path is not None, "candidate hash is not present in the packet inventory")
    return {
        "status": "REVIEW_PACKET_VERIFIED",
        "package_id": manifest["package_id"],
        "decision_id": manifest["decision_id"],
        "file_count": len(expected_entries),
        "candidate_sha256": manifest["candidate"]["sha256"],
        "authority_sha256": manifest["authority"]["live_sha256"],
        "authority_unchanged": True,
        "write_policy": "READ_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet")
    args = parser.parse_args()
    print(json.dumps(verify_review_packet(args.packet), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
