"""Import a completed Drawing Evidence Copilot run without modifying it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ifcopenshell

from ..authority import capture_ifc_baseline, sha256_file
from ..models import ContractError


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _external_source_state(paths: list[Path]) -> dict[str, str]:
    return {str(path.resolve()): sha256_file(path) for path in paths}


def _assert_unchanged(before: dict[str, str]) -> None:
    changed = [path for path, digest in before.items() if sha256_file(path) != digest]
    if changed:
        raise RuntimeError("external Drawing Evidence Copilot artifacts changed during read-only import")


def import_drawing_evidence_case(
    *,
    extraction_path: str | Path,
    public_gate_report_path: str | Path,
    integration_config_path: str | Path,
    integration_manifest_path: str | Path,
    roles_path: str | Path,
    evidence_map_path: str | Path | None = None,
    authorization_manifest_path: str | Path | None = None,
    drawing_path: str | Path | None = None,
    item_id: str = "AUTHORIZED-STAIR-01",
    item_name: str = "Authorized stair package",
    work_run: str = "run-01",
) -> dict[str, Any]:
    """Build a source-item contract from verified external evidence.

    Missing discipline/source attribution intentionally yields a later
    CROSSCHECK_REQUIRED decision. The adapter never guesses an architectural or
    structural source merely from extracted geometry text.
    """

    inputs = [
        Path(extraction_path),
        Path(public_gate_report_path),
        Path(integration_config_path),
        Path(integration_manifest_path),
        Path(roles_path),
    ]
    if evidence_map_path:
        inputs.append(Path(evidence_map_path))
    if bool(authorization_manifest_path) != bool(drawing_path):
        raise ContractError("authorization manifest and drawing path must be supplied together")
    if authorization_manifest_path and drawing_path:
        inputs.extend([Path(authorization_manifest_path), Path(drawing_path)])
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    before = _external_source_state(inputs)

    extraction = _read(extraction_path)
    public_gate = _read(public_gate_report_path)
    config = _read(integration_config_path)
    manifest = _read(integration_manifest_path)
    roles = _read(roles_path)
    evidence_map = _read(evidence_map_path) if evidence_map_path else {"records": {}, "requirements": {}}
    source_artifact: dict[str, Any] | None = None
    if authorization_manifest_path and drawing_path:
        authorization_manifest = _read(authorization_manifest_path)
        drawing_sha = sha256_file(drawing_path)
        if authorization_manifest.get("authorization_confirmed") is not True:
            raise ContractError("drawing use authorization is not confirmed")
        if authorization_manifest.get("sanitization_confirmed") is not True:
            raise ContractError("drawing sanitization is not confirmed")
        if authorization_manifest.get("publication_authorized") is not True:
            raise ContractError("drawing publication authorization is not confirmed")
        if str(authorization_manifest.get("drawing_sha256", "")).upper() != drawing_sha:
            raise ContractError("drawing SHA does not match its authorization manifest")
        source_artifact = {
            "path": str(Path(drawing_path).resolve()),
            "sha256": drawing_sha,
            "authorization_manifest_path": str(Path(authorization_manifest_path).resolve()),
            "release_status": "PUBLIC_RELEASE_AUTHORIZED",
        }

    if public_gate.get("status") != "LIVE_PUBLIC_RELEASE_GATE_PASSED":
        raise ContractError("external public release gate has not passed")
    if public_gate.get("authorization_binding_verified") is not True or public_gate.get("fallback_used") is not False:
        raise ContractError("external evidence authorization or live provenance is invalid")
    if public_gate.get("runs_completed") != public_gate.get("runs_required") or public_gate.get("runs_completed", 0) < 3:
        raise ContractError("external public evidence requires at least three complete runs")
    authority = manifest.get("authority", {})
    if authority.get("unchanged") is not True:
        raise ContractError("external authority source was not proven unchanged")
    configured_sha = str(config.get("authority_sha256", "")).upper()
    if not configured_sha or authority.get("sha256_before") != authority.get("sha256_after"):
        raise ContractError("external authority SHA history is invalid")
    if str(authority.get("sha256_before", "")).upper() != configured_sha:
        raise ContractError("integration configuration and manifest authority SHA disagree")
    if int(config.get("source_evidence_count", -1)) != len(extraction.get("evidence", [])):
        raise ContractError("external extraction evidence count does not match the authorized integration")

    authority_path = Path(str(authority.get("path", "")))
    if not authority_path.is_file():
        raise FileNotFoundError("registered external authority IFC is unavailable")
    matrix = config.get("placement_matrix_mm")
    if not isinstance(matrix, list) or len(matrix) != 4 or any(not isinstance(row, list) or len(row) != 4 for row in matrix):
        raise ContractError("authorized placement matrix must be 4x4")
    origin = [float(matrix[index][3]) for index in range(3)]
    baseline = capture_ifc_baseline(
        authority_path,
        str(config.get("authority_revision", authority.get("revision", ""))),
        coordinate_origin=origin,
    )
    if baseline["sha256"] != configured_sha:
        raise ContractError("live authority IFC no longer matches the authorized integration baseline")
    baseline["observed_sha256"] = baseline["sha256"]

    record_map = evidence_map.get("records", {})
    requirement_map = evidence_map.get("requirements", {})
    source_hierarchy = list(evidence_map.get("source_hierarchy", []))
    if "unclassified_source" not in source_hierarchy:
        source_hierarchy.append("unclassified_source")
    evidence: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    for index, record in enumerate(extraction.get("evidence", []), start=1):
        field = str(record.get("field", "")).strip()
        if not field:
            raise ContractError("external evidence field is empty")
        mapping = record_map.get(field, {})
        discipline = str(mapping.get("discipline", "unclassified"))
        source_type = str(mapping.get("source_type", "unclassified_source"))
        source_ref = str(mapping.get("source_ref", record.get("drawing_source", "external-public-evidence")))
        if source_type not in source_hierarchy:
            source_hierarchy.append(source_type)
        evidence.append(
            {
                "evidence_id": f"ETA-{index:02d}-{field.upper()}",
                "claim": field,
                "discipline": discipline,
                "source_type": source_type,
                "source_ref": source_ref,
                "drawing_source": record.get("drawing_source"),
                "page": record.get("page"),
                "region": record.get("region"),
                "value": record.get("value"),
                "unit": record.get("unit"),
                "confidence": record.get("confidence"),
                "review_status": "ACCEPTED" if record.get("human_review_status") == "accepted" else "NEEDS_REVIEW",
                "external_evidence_type": record.get("evidence_type"),
                "source_description": record.get("source_description"),
                "observed_text": record.get("observed_text"),
                "source_artifact_sha256": source_artifact["sha256"] if source_artifact else None,
            }
        )
        requirement = requirement_map.get(field)
        if requirement is None:
            requirement = {
                "minimum_confidence": 0.9,
                "required_disciplines": ["verified_source_attribution"],
            }
        requirements.append({"claim": field, **requirement})

    extraction_values = {
        key: value
        for key, value in extraction.items()
        if key not in {"evidence", "missing_inputs", "requires_human_review", "schema_version"}
    }
    output_root = f"work/{item_id}/{work_run}"
    payload = {
        "schema_version": "1.0",
        "item": {"item_id": item_id, "name": item_name, "component_type": "IfcStair", "work_run": work_run},
        "authorization": {
            "project_use_authorized": True,
            "drawing_use_authorized": True,
            "authority_inspection_authorized": True,
        },
        "authority_baseline": baseline,
        "source_hierarchy": source_hierarchy,
        "requirements": requirements,
        "evidence": evidence,
        "issues": [],
        "coordinate_definition": {
            "complete": True,
            "source_coordinate_system": "drawing-local-millimetres",
            "authority_coordinate_system": "registered-authority-project-millimetres",
            "transform_matrix": matrix,
            "representation_mirror_y_mm": config.get("representation_mirror_y_mm"),
            "control_points": config.get("control_points", []),
            "coordinate_tolerance_mm": config.get("coordinate_tolerance_mm"),
        },
        "modeling_scope": {
            "allowed_component_scope": ["IfcStair", "IfcStairFlight", "IfcSlab/LANDING"],
            "allowed_global_ids": list(config.get("replace_global_ids", [])),
            "protected_non_target_scope": ["ALL_AUTHORITY_PRODUCTS_EXCEPT_ALLOWED_GLOBAL_IDS"],
            "expected_geometry": {
                "generated_component_count": 4,
                "generated_bounds_m": config.get("expected_generated_bounds_m"),
                "target_top_elevation_m": config.get("target_top_elevation_m"),
                "bbox_tolerance_mm": config.get("bbox_tolerance_mm"),
            },
            "interface_controls": {
                "target_storey_global_id": config.get("target_storey_global_id"),
                "opening_global_id": config.get("opening_global_id"),
                "clash_candidate_global_ids": config.get("clash_candidate_global_ids", []),
                "clash_tolerance_mm": config.get("clash_tolerance_mm"),
            },
            "dimensions_and_elevations": extraction_values,
            "expected_product_count_changes": {"added": 4, "modified": 0, "deleted": 4, "net": 0},
            "expected_global_id_changes": {
                "created": 4,
                "deleted": len(config.get("replace_global_ids", [])),
                "preserved": "ALL_NON_TARGET_GLOBAL_IDS",
            },
            "regression_requirements": [
                "authority_sha_unchanged == true",
                "non_target_difference_count == 0",
                "product_count_change == 0",
                "global_id_changes_match_work_package == true",
                f"control_point_max_residual_mm <= {config.get('coordinate_tolerance_mm')}",
                f"focused_exact_geometry_clashes == 0 at {config.get('clash_tolerance_mm')} mm",
            ],
            "gui_requirements": {
                "bonsai": {"required": True, "close_reopen": True, "ifc_hash_unchanged": True},
                "freecad": {"required": False, "reason": "Applicability requires a separate decision."},
            },
            "independent_review_requirements": [
                "reviewer_read_only == true",
                "reviewer_role != modeling_role",
                "B0 == 0",
                "B1 == 0",
                "B2 == 0",
            ],
            "output_paths": {
                "standalone_ifc": f"{output_root}/standalone/auditable-stair.ifc",
                "standalone_audit": f"{output_root}/standalone/auditable-stair-audit.json",
                "candidate_ifc": f"{output_root}/candidate.ifc",
                "integration_manifest": f"{output_root}/external-integration-manifest.json",
                "modeling_manifest": f"{output_root}/modeling-manifest.json",
                "regression_gate": f"{output_root}/regression-gate.json",
                "gui_evidence": f"{output_root}/gui/",
                "review": f"{output_root}/independent-review.json",
            },
        },
        "unresolved_assumptions": [],
        "roles": roles,
        "external_provenance": {
            "capability": "drawing-evidence-copilot",
            "public_release_gate_status": public_gate["status"],
            "runs_completed": public_gate["runs_completed"],
            "audit_checks": public_gate["runs"][0]["checks"],
            "authority_context_integration_status": manifest.get("status"),
            "authority_source_unchanged": authority.get("unchanged"),
            "source_artifact": source_artifact,
        },
    }
    _assert_unchanged(before)
    return payload


def build_incomplete_authority_item(
    *,
    integration_config_path: str | Path,
    integration_manifest_path: str | Path,
    roles_path: str | Path,
    candidate_index: int,
    item_id: str,
    item_name: str,
) -> dict[str, Any]:
    """Register one real authority product with deliberately incomplete evidence."""

    config_file = Path(integration_config_path)
    manifest_file = Path(integration_manifest_path)
    roles_file = Path(roles_path)
    before = _external_source_state([config_file, manifest_file, roles_file])
    config = _read(config_file)
    manifest = _read(manifest_file)
    roles = _read(roles_file)
    candidates = list(config.get("clash_candidate_global_ids", []))
    if candidate_index < 0 or candidate_index >= len(candidates):
        raise ContractError("candidate index is outside the authorized integration candidate set")
    authority_record = manifest.get("authority", {})
    if authority_record.get("unchanged") is not True:
        raise ContractError("authority source was not proven unchanged")
    authority_path = Path(str(authority_record.get("path", "")))
    matrix = config.get("placement_matrix_mm", [])
    origin = [float(matrix[index][3]) for index in range(3)]
    baseline = capture_ifc_baseline(
        authority_path,
        str(config.get("authority_revision", authority_record.get("revision", ""))),
        coordinate_origin=origin,
    )
    if baseline["sha256"] != str(config.get("authority_sha256", "")).upper():
        raise ContractError("live authority IFC does not match the registered baseline")
    baseline["observed_sha256"] = baseline["sha256"]

    model = ifcopenshell.open(str(authority_path))
    global_id = str(candidates[candidate_index])
    try:
        product = model.by_guid(global_id)
    except RuntimeError as exc:
        raise ContractError("authorized candidate GlobalId is absent from the authority baseline") from exc
    component_type = product.is_a()
    output_root = f"work/{item_id}"
    payload = {
        "schema_version": "1.0",
        "item": {"item_id": item_id, "name": item_name, "component_type": component_type},
        "authorization": {
            "project_use_authorized": True,
            "drawing_use_authorized": True,
            "authority_inspection_authorized": True,
        },
        "authority_baseline": baseline,
        "source_hierarchy": ["structural_detail", "architectural_detail"],
        "requirements": [
            {"claim": "geometry_and_dimensions", "minimum_confidence": 0.9, "required_disciplines": ["structure"]},
            {"claim": "stair_interface_clearance", "minimum_confidence": 0.9, "required_disciplines": ["architecture", "structure"]},
        ],
        "evidence": [],
        "issues": [
            {
                "type": "MISSING",
                "description": "No approved architectural/structural evidence is registered for this real adjacent authority product and its stair interface.",
                "evidence_ids": [],
            }
        ],
        "coordinate_definition": {"complete": False},
        "modeling_scope": {
            "allowed_component_scope": [component_type],
            "allowed_global_ids": [global_id],
            "protected_non_target_scope": ["ALL_AUTHORITY_PRODUCTS_EXCEPT_ALLOWED_GLOBAL_IDS"],
            "expected_geometry": {},
            "interface_controls": {},
            "dimensions_and_elevations": {},
            "expected_product_count_changes": {},
            "expected_global_id_changes": {},
            "regression_requirements": ["non_target_difference_count == 0"],
            "gui_requirements": {"bonsai": {"required": True}},
            "independent_review_requirements": ["B0 == 0", "B1 == 0", "B2 == 0"],
            "output_paths": {"candidate_ifc": f"{output_root}/candidate.ifc"},
        },
        "unresolved_assumptions": [],
        "roles": roles,
        "external_provenance": {
            "capability": "drawing-evidence-copilot",
            "candidate_set": "AUTHORIZED_STAIR_CONTEXT_CLASH_CANDIDATES",
            "candidate_index": candidate_index,
            "authority_source_unchanged": authority_record["unchanged"],
        },
    }
    _assert_unchanged(before)
    return payload
