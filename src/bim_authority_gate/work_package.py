"""Controlled work-package generation for ready items only."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import ContractError, ReadinessStatus, validate_work_output_paths


def _package_id(decision_id: str, item_id: str, authority_sha: str) -> str:
    material = f"{decision_id}\n{item_id}\n{authority_sha}".encode("utf-8")
    return "WP-" + hashlib.sha256(material).hexdigest()[:16].upper()


def _validate_output_paths(paths: dict) -> None:
    errors = validate_work_output_paths(paths)
    if errors:
        raise ContractError("output paths must be workspace-relative and inside isolated work/: " + ", ".join(errors))


def build_work_package(payload: dict, decision: dict) -> dict[str, Any]:
    if decision.get("status") != ReadinessStatus.READY_TO_MODEL.value:
        raise ContractError("a work package may be generated only for READY_TO_MODEL")
    if decision.get("modeling_allowed") is not True:
        raise ContractError("the readiness decision does not permit modeling")

    scope = payload["modeling_scope"]
    paths = scope["output_paths"]
    _validate_output_paths(paths)
    evidence = [
        {
            "evidence_id": record["evidence_id"],
            "claim": record["claim"],
            "discipline": record["discipline"],
            "source_type": record["source_type"],
            "source_ref": record["source_ref"],
            "drawing_source": record.get("drawing_source"),
            "page": record.get("page"),
            "region": record.get("region"),
            "value": record.get("value"),
            "unit": record.get("unit"),
            "confidence": record.get("confidence"),
            "review_status": record.get("review_status"),
            "source_description": record.get("source_description"),
            "observed_text": record.get("observed_text"),
            "source_artifact_sha256": record.get("source_artifact_sha256"),
            "external_evidence_type": record.get("external_evidence_type"),
        }
        for record in payload["evidence"]
        if str(record.get("review_status", "")).upper() == "ACCEPTED"
    ]
    if not evidence:
        raise ContractError("a controlled work package requires accepted evidence")

    package = {
        "schema_version": "1.0",
        "package_id": _package_id(
            decision["decision_id"], decision["item_id"], decision["authority_baseline_sha256"]
        ),
        "status": "CONTROLLED_WORK_PACKAGE_READY",
        "decision_id": decision["decision_id"],
        "readiness": decision["status"],
        "item": payload["item"],
        "authority_baseline": {
            "rev": decision["authority_baseline_rev"],
            "sha256": decision["authority_baseline_sha256"],
            "ifc_product_count": payload["authority_baseline"]["ifc_product_count"],
            "global_id_fingerprint": payload["authority_baseline"]["global_id_fingerprint"],
        },
        "approved_source_evidence": evidence,
        "source_hierarchy": payload["source_hierarchy"],
        "external_provenance": payload.get("external_provenance"),
        "allowed_component_scope": scope["allowed_component_scope"],
        "allowed_global_ids": scope["allowed_global_ids"],
        "protected_non_target_scope": scope["protected_non_target_scope"],
        "expected_geometry": scope["expected_geometry"],
        "interface_controls": scope["interface_controls"],
        "coordinate_transformation": payload["coordinate_definition"],
        "dimensions_and_elevations": scope["dimensions_and_elevations"],
        "expected_product_count_changes": scope["expected_product_count_changes"],
        "expected_global_id_changes": scope["expected_global_id_changes"],
        "regression_requirements": scope["regression_requirements"],
        "gui_requirements": scope["gui_requirements"],
        "independent_review_requirements": scope["independent_review_requirements"],
        "output_paths": paths,
        "unresolved_assumptions": [],
        "roles": payload["roles"],
        "write_policy": {
            "authority_model": "READ_ONLY",
            "modeling_target": "ISOLATED_WORK_ONLY",
            "self_promotion_allowed": False,
            "single_work_writer_required": True,
        },
    }
    # Keep the artifact deterministic and prove it is JSON-serializable now.
    json.dumps(package, ensure_ascii=False, sort_keys=True)
    return package
