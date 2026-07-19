"""Fail-closed promotion of an independently approved WORK candidate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .authority import capture_ifc_baseline, sha256_file
from .models import ContractError, ReadinessStatus


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_new_json(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _copy_new(source: Path, target: Path) -> None:
    """Copy bytes to a brand-new path without a race that could overwrite a REV."""

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as reader, target.open("xb") as writer:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _review_counts(review: dict[str, Any]) -> dict[str, int]:
    counts = review.get("issue_counts")
    _require(isinstance(counts, dict), "independent review issue_counts are missing")
    result: dict[str, int] = {}
    for level in ("B0", "B1", "B2"):
        value = counts.get(level)
        _require(isinstance(value, int) and value >= 0, f"independent review {level} count is invalid")
        result[level] = value
    return result


def validate_promotion_gates(
    *,
    source_item: dict[str, Any],
    work_package: dict[str, Any],
    modeling_manifest: dict[str, Any],
    regression_gate: dict[str, Any],
    bonsai_gate: dict[str, Any],
    freecad_gate: dict[str, Any],
    independent_review: dict[str, Any],
) -> dict[str, Any]:
    """Validate every promotion prerequisite without writing any file."""

    package_id = work_package.get("package_id")
    decision_id = work_package.get("decision_id")
    _require(work_package.get("status") == "CONTROLLED_WORK_PACKAGE_READY", "work package is incomplete")
    _require(work_package.get("readiness") == ReadinessStatus.READY_TO_MODEL.value, "readiness is not READY_TO_MODEL")
    _require(work_package.get("unresolved_assumptions") == [], "work package has unresolved assumptions")
    _require(modeling_manifest.get("status") == "ISOLATED_WORK_CANDIDATE_BUILT", "isolated WORK candidate is missing")
    _require(modeling_manifest.get("package_id") == package_id, "candidate is not bound to the work package")
    _require(modeling_manifest.get("decision_id") == decision_id, "candidate decision binding is invalid")
    _require(modeling_manifest.get("candidate", {}).get("hash_locked") is True, "candidate hash is not locked")
    candidate_sha = str(modeling_manifest.get("candidate", {}).get("sha256", "")).upper()
    _require(len(candidate_sha) == 64, "candidate SHA-256 is missing")

    authority = source_item.get("authority_baseline", {})
    expected_authority_sha = str(work_package.get("authority_baseline", {}).get("sha256", "")).upper()
    _require(str(authority.get("sha256", "")).upper() == expected_authority_sha, "source authority binding differs from work package")
    _require(modeling_manifest.get("authority", {}).get("sha256_before") == expected_authority_sha, "modeling authority baseline differs")
    _require(modeling_manifest.get("authority", {}).get("unchanged") is True, "modeling did not preserve the authority source")

    _require(regression_gate.get("status") == "PASS", "regression Gate did not pass")
    _require(regression_gate.get("package_id") == package_id, "regression Gate package binding is invalid")
    _require(regression_gate.get("decision_id") == decision_id, "regression Gate decision binding is invalid")
    _require(regression_gate.get("non_target", {}).get("difference_count") == 0, "non-target difference is not zero")
    _require(regression_gate.get("authority", {}).get("unchanged") is True, "regression did not preserve the authority source")
    _require(regression_gate.get("candidate", {}).get("unchanged") is True, "regression modified the candidate")
    _require(regression_gate.get("candidate", {}).get("sha256_after") == candidate_sha, "regression candidate hash differs")

    _require(bonsai_gate.get("gate_result") == "PASS", "Bonsai GUI Gate did not pass")
    _require(bonsai_gate.get("work_package_id") == package_id, "Bonsai Gate package binding is invalid")
    _require(bonsai_gate.get("candidate", {}).get("sha256_before_gui") == candidate_sha, "Bonsai Gate candidate hash differs")
    _require(bonsai_gate.get("candidate", {}).get("sha256_after_gui") == candidate_sha, "Bonsai inspection rewrote the candidate")

    freecad_required = bool(work_package.get("gui_requirements", {}).get("freecad", {}).get("required"))
    if freecad_required:
        _require(freecad_gate.get("gate_result") == "PASS", "required FreeCAD GUI Gate did not pass")
        _require(freecad_gate.get("candidate", {}).get("sha256_after_gui") == candidate_sha, "FreeCAD inspection rewrote the candidate")
    else:
        _require(freecad_gate.get("gate_result") == "NOT_APPLICABLE", "FreeCAD applicability decision is missing")
    _require(freecad_gate.get("work_package_id") == package_id, "FreeCAD Gate package binding is invalid")

    roles = work_package.get("roles", {})
    modeler = roles.get("modeling", {}).get("role_id")
    reviewer = roles.get("review", {}).get("role_id")
    promoter = roles.get("authority_promotion", {}).get("role_id")
    _require(reviewer and reviewer != modeler, "reviewer is not independent from the modeler")
    _require(promoter and promoter not in {modeler, reviewer}, "authority promotion role is not separated")
    _require(independent_review.get("status") == "PASS", "independent review did not pass")
    _require(independent_review.get("review_policy") == "READ_ONLY", "independent review was not read-only")
    _require(independent_review.get("reviewer_role_id") == reviewer, "independent reviewer role binding is invalid")
    _require(independent_review.get("modeler_role_id") == modeler, "independent review modeler disclosure is invalid")
    _require(independent_review.get("package_id") == package_id, "independent review package binding is invalid")
    _require(independent_review.get("candidate", {}).get("sha256_before") == candidate_sha, "review candidate hash differs")
    _require(independent_review.get("candidate", {}).get("sha256_after") == candidate_sha, "review modified the candidate")
    counts = _review_counts(independent_review)
    _require(counts == {"B0": 0, "B1": 0, "B2": 0}, "independent review findings are not 0/0/0")
    _require(independent_review.get("findings") == [], "independent review contains unresolved findings")

    return {
        "status": "ALL_PROMOTION_GATES_PASS",
        "package_id": package_id,
        "decision_id": decision_id,
        "candidate_sha256": candidate_sha,
        "authority_sha256": expected_authority_sha,
        "freecad_required": freecad_required,
        "review_findings": counts,
        "promoter_role_id": promoter,
    }


def promote_candidate(
    *,
    source_item_path: str | Path,
    work_package_path: str | Path,
    modeling_manifest_path: str | Path,
    regression_gate_path: str | Path,
    bonsai_gate_path: str | Path,
    freecad_gate_path: str | Path,
    independent_review_path: str | Path,
    readiness_index_path: str | Path,
    new_rev: str,
    new_rev_ifc_path: str | Path,
    promotion_manifest_path: str | Path,
    updated_authority_index_path: str | Path,
) -> dict[str, Any]:
    """Create a new derived authoritative REV only after all immutable Gates pass."""

    source_item = _read(source_item_path)
    work_package = _read(work_package_path)
    modeling_manifest = _read(modeling_manifest_path)
    regression_gate = _read(regression_gate_path)
    bonsai_gate = _read(bonsai_gate_path)
    freecad_gate = _read(freecad_gate_path)
    independent_review = _read(independent_review_path)
    readiness_index = _read(readiness_index_path)
    gates = validate_promotion_gates(
        source_item=source_item,
        work_package=work_package,
        modeling_manifest=modeling_manifest,
        regression_gate=regression_gate,
        bonsai_gate=bonsai_gate,
        freecad_gate=freecad_gate,
        independent_review=independent_review,
    )

    authority_path = Path(source_item["authority_baseline"]["authority_file_path"]).resolve()
    candidate_path = Path(modeling_manifest["candidate"]["path"]).resolve()
    new_rev_path = Path(new_rev_ifc_path).resolve()
    manifest_path = Path(promotion_manifest_path).resolve()
    index_path = Path(updated_authority_index_path).resolve()
    _require(new_rev.strip() and new_rev != source_item["authority_baseline"]["rev"], "new REV must differ from the baseline REV")
    _require(authority_path != candidate_path and authority_path != new_rev_path, "promotion must use a derived output path")
    _require(candidate_path != new_rev_path, "candidate and promoted REV paths must differ")
    for output in (new_rev_path, manifest_path, index_path):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite promotion output: {output}")

    authority_before = sha256_file(authority_path)
    _require(authority_before == gates["authority_sha256"], "B0 authority baseline changed before promotion")
    _require(sha256_file(candidate_path) == gates["candidate_sha256"], "B0 locked candidate changed before promotion")

    created: list[Path] = []
    try:
        _copy_new(candidate_path, new_rev_path)
        created.append(new_rev_path)
        promoted_baseline = capture_ifc_baseline(
            new_rev_path,
            new_rev,
            coordinate_origin=list(source_item["authority_baseline"].get("coordinate_origin", [])),
            hold_states=list(source_item["authority_baseline"].get("hold_states", [])),
            rfi_states=list(source_item["authority_baseline"].get("rfi_states", [])),
        )
        authority_after = sha256_file(authority_path)
        _require(authority_after == authority_before, "B0 authority source changed during promotion")
        _require(promoted_baseline["sha256"] == gates["candidate_sha256"], "promoted REV is not an exact copy of the approved candidate")

        item_id = source_item["item"]["item_id"]
        updated_items = []
        item_found = False
        for item in readiness_index.get("items", []):
            updated = dict(item)
            if item.get("item_id") == item_id:
                item_found = True
                updated["current_rev_status"] = "PROMOTED"
                updated["promoted_rev"] = new_rev
                updated["promotion_package_id"] = gates["package_id"]
            updated_items.append(updated)
        _require(item_found, "readiness index does not contain the promoted item")
        authority_index = {
            **readiness_index,
            "schema_version": "1.1",
            "items": updated_items,
            "authority_write_policy": "CONTROLLED_PROMOTION_ONLY",
            "authority": {
                "previous_rev": source_item["authority_baseline"]["rev"],
                "previous_sha256": authority_before,
                "current_rev": new_rev,
                "current_sha256": promoted_baseline["sha256"],
                "ifc_product_count": promoted_baseline["ifc_product_count"],
                "global_id_fingerprint": promoted_baseline["global_id_fingerprint"],
                "source_authority_unchanged": True,
            },
            "rfi_update": {
                "item_id": item_id,
                "state": "NO_OPEN_RFI",
                "preserved_baseline_rfi_states": source_item["authority_baseline"].get("rfi_states", []),
            },
            "design_decision": {
                "decision_id": gates["decision_id"],
                "package_id": gates["package_id"],
                "independent_review": "B0/B1/B2=0/0/0",
                "result": "PROMOTED_TO_NEW_REV",
            },
        }
        _write_new_json(index_path, authority_index)
        created.append(index_path)
        manifest = {
            "schema_version": "1.0",
            "status": "PROMOTED_TO_NEW_AUTHORITY_REV",
            "promotion_policy": "CONTROLLING_AUTHORITY_ONLY",
            "promoter_role_id": gates["promoter_role_id"],
            "package_id": gates["package_id"],
            "decision_id": gates["decision_id"],
            "review_findings": gates["review_findings"],
            "gates": {
                "readiness": "READY_TO_MODEL",
                "regression": "PASS",
                "non_target_difference": 0,
                "bonsai": "PASS",
                "freecad": "PASS" if gates["freecad_required"] else "NOT_APPLICABLE",
                "independent_review": "0/0/0",
            },
            "previous_authority": {
                "rev": source_item["authority_baseline"]["rev"],
                "sha256_before": authority_before,
                "sha256_after": authority_after,
                "unchanged": True,
                "ifc_product_count": source_item["authority_baseline"]["ifc_product_count"],
                "global_id_fingerprint": source_item["authority_baseline"]["global_id_fingerprint"],
            },
            "approved_candidate": {
                "sha256": gates["candidate_sha256"],
                "product_count": modeling_manifest["candidate"]["product_count"],
            },
            "new_authority": {
                "rev": new_rev,
                "path": str(new_rev_path),
                "sha256": promoted_baseline["sha256"],
                "ifc_product_count": promoted_baseline["ifc_product_count"],
                "global_id_fingerprint": promoted_baseline["global_id_fingerprint"],
            },
            "authority_index_path": str(index_path),
            "overwrite_permitted": False,
            "source_authority_unchanged": True,
        }
        _write_new_json(manifest_path, manifest)
        created.append(manifest_path)
        return manifest
    except Exception:
        for output in reversed(created):
            output.unlink(missing_ok=True)
        raise
