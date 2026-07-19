"""Deterministic, fail-closed BIM readiness classification."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

from .models import (
    ROLE_NAMES,
    ContractError,
    ReadinessStatus,
    require_list,
    require_mapping,
    require_text,
    validate_work_output_paths,
)

_SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")


def _canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def _reason(code: str, message: str, evidence_ids: list[str] | None = None) -> dict:
    return {"code": code, "message": message, "evidence_ids": evidence_ids or []}


def _next_action(status: ReadinessStatus) -> str:
    return {
        ReadinessStatus.READY_TO_MODEL: "Generate the controlled work package; model only in isolated WORK.",
        ReadinessStatus.CROSSCHECK_REQUIRED: "Obtain and register the required independent source cross-check.",
        ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED: "Obtain the minimum human clarification and update the evidence record.",
        ReadinessStatus.COORDINATION_REQUIRED: "Resolve the multidisciplinary conflict; do not create WORK or IFC.",
        ReadinessStatus.BLOCKED: "Resolve the safety or authority baseline blocker before any production action.",
    }[status]


def _required_scope_complete(payload: dict) -> list[str]:
    missing: list[str] = []
    coordinates = payload.get("coordinate_definition")
    if not isinstance(coordinates, dict) or coordinates.get("complete") is not True:
        missing.append("coordinate_definition.complete")
    else:
        for field in ("source_coordinate_system", "authority_coordinate_system", "transform_matrix"):
            if field not in coordinates:
                missing.append(f"coordinate_definition.{field}")

    scope = payload.get("modeling_scope")
    required_scope_fields = (
        "allowed_component_scope",
        "allowed_global_ids",
        "protected_non_target_scope",
        "expected_geometry",
        "interface_controls",
        "dimensions_and_elevations",
        "expected_product_count_changes",
        "expected_global_id_changes",
        "regression_requirements",
        "gui_requirements",
        "independent_review_requirements",
        "output_paths",
    )
    if not isinstance(scope, dict):
        return missing + [f"modeling_scope.{field}" for field in required_scope_fields]
    for field in required_scope_fields:
        if field not in scope or scope[field] in (None, "", [], {}):
            if field == "allowed_global_ids" and scope.get(field) == []:
                continue
            missing.append(f"modeling_scope.{field}")
    missing.extend(validate_work_output_paths(scope.get("output_paths")))
    if payload.get("unresolved_assumptions") != []:
        missing.append("unresolved_assumptions")
    return missing


def evaluate_item(payload: dict, *, observed_authority_sha: str | None = None) -> dict[str, Any]:
    """Return exactly one readiness state and a fail-closed modeling decision."""

    require_mapping(payload, "source item")
    item = require_mapping(payload.get("item"), "item")
    item_id = require_text(item.get("item_id"), "item.item_id")
    authorization = require_mapping(payload.get("authorization"), "authorization")
    baseline = require_mapping(payload.get("authority_baseline"), "authority_baseline")
    evidence = require_list(payload.get("evidence"), "evidence")
    requirements = require_list(payload.get("requirements"), "requirements")
    issues = require_list(payload.get("issues", []), "issues")
    source_hierarchy = require_list(payload.get("source_hierarchy"), "source_hierarchy")
    roles = require_mapping(payload.get("roles"), "roles")

    buckets: dict[ReadinessStatus, list[dict]] = defaultdict(list)

    required_authorizations = (
        "project_use_authorized",
        "drawing_use_authorized",
        "authority_inspection_authorized",
    )
    denied = [name for name in required_authorizations if authorization.get(name) is not True]
    if denied:
        buckets[ReadinessStatus.BLOCKED].append(
            _reason("AUTHORIZATION_MISSING", f"Required authorization is not true: {', '.join(denied)}")
        )

    registered_sha = str(baseline.get("sha256", ""))
    observed_sha = observed_authority_sha or str(baseline.get("observed_sha256", ""))
    if not _SHA256.fullmatch(registered_sha) or not _SHA256.fullmatch(observed_sha):
        buckets[ReadinessStatus.BLOCKED].append(
            _reason("B0_AUTHORITY_BASELINE_UNVERIFIED", "Registered and observed authority SHA-256 are required.")
        )
    elif registered_sha.upper() != observed_sha.upper():
        buckets[ReadinessStatus.BLOCKED].append(
            _reason("B0_AUTHORITY_BASELINE_MISMATCH", "Observed authority SHA-256 does not match the registered baseline.")
        )

    baseline_required = {
        "authority_file_path": lambda value: isinstance(value, str) and bool(value.strip()),
        "rev": lambda value: isinstance(value, str) and bool(value.strip()),
        "ifc_product_count": lambda value: isinstance(value, int) and value >= 0,
        "global_id_fingerprint": lambda value: isinstance(value, str) and bool(_SHA256.fullmatch(value)),
        "project_units": lambda value: isinstance(value, list) and bool(value),
        "coordinate_origin": lambda value: isinstance(value, list) and len(value) == 3 and all(isinstance(item, (int, float)) for item in value),
        "storeys": lambda value: isinstance(value, list) and bool(value),
        "hold_states": lambda value: isinstance(value, list),
        "rfi_states": lambda value: isinstance(value, list),
    }
    incomplete_baseline = [
        field for field, valid in baseline_required.items() if not valid(baseline.get(field))
    ]
    if incomplete_baseline:
        buckets[ReadinessStatus.BLOCKED].append(
            _reason(
                "B0_AUTHORITY_BASELINE_INCOMPLETE",
                "Authority baseline fields are missing or invalid: " + ", ".join(incomplete_baseline),
            )
        )

    role_ids: list[str] = []
    missing_roles: list[str] = []
    for role_name in ROLE_NAMES:
        role = roles.get(role_name)
        if not isinstance(role, dict) or not isinstance(role.get("role_id"), str) or not role["role_id"].strip():
            missing_roles.append(role_name)
        else:
            role_ids.append(role["role_id"].strip())
    if missing_roles or len(role_ids) != len(set(role_ids)):
        detail = "missing roles: " + ", ".join(missing_roles) if missing_roles else "role IDs are not independent"
        buckets[ReadinessStatus.BLOCKED].append(
            _reason("ROLE_SEPARATION_INVALID", f"Research, reasoning, modeling, review, and authority promotion must be independent; {detail}.")
        )
    review_role = roles.get("review")
    if isinstance(review_role, dict) and review_role.get("read_only") is not True:
        buckets[ReadinessStatus.BLOCKED].append(
            _reason("REVIEWER_NOT_READ_ONLY", "The independent reviewer must be explicitly read-only.")
        )

    active_hold_ids = {
        str(entry.get("item_id"))
        for entry in baseline.get("hold_states", [])
        if isinstance(entry, dict) and entry.get("status") not in ("RESOLVED", "CLOSED")
    }
    active_rfi_ids = {
        str(entry.get("item_id"))
        for entry in baseline.get("rfi_states", [])
        if isinstance(entry, dict) and entry.get("status") not in ("RESOLVED", "CLOSED")
    }
    if item_id in active_hold_ids:
        buckets[ReadinessStatus.BLOCKED].append(_reason("ACTIVE_HOLD", "The item has an unresolved authority HOLD."))
    if item_id in active_rfi_ids:
        buckets[ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED].append(
            _reason("ACTIVE_RFI", "The item has an unresolved RFI.")
        )

    issue_map = {
        "HARD_BLOCK": ReadinessStatus.BLOCKED,
        "B0": ReadinessStatus.BLOCKED,
        "CONFLICT": ReadinessStatus.COORDINATION_REQUIRED,
        "COORDINATION": ReadinessStatus.COORDINATION_REQUIRED,
        "MISSING": ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED,
        "AMBIGUITY": ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED,
        "HUMAN_CLARIFICATION": ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED,
        "CROSSCHECK": ReadinessStatus.CROSSCHECK_REQUIRED,
    }
    for issue in issues:
        if not isinstance(issue, dict):
            raise ContractError("each issue must be an object")
        issue_type = str(issue.get("type", "")).upper()
        status = issue_map.get(issue_type)
        if status is None:
            raise ContractError(f"unsupported issue type: {issue_type or '<empty>'}")
        buckets[status].append(
            _reason(
                f"ISSUE_{issue_type}",
                require_text(issue.get("description"), "issue.description"),
                [str(value) for value in issue.get("evidence_ids", [])],
            )
        )

    evidence_by_claim: dict[str, list[dict]] = defaultdict(list)
    for record in evidence:
        record = require_mapping(record, "evidence record")
        claim = require_text(record.get("claim"), "evidence.claim")
        evidence_by_claim[claim].append(record)
        source_type = record.get("source_type")
        if source_type not in source_hierarchy:
            buckets[ReadinessStatus.CROSSCHECK_REQUIRED].append(
                _reason("SOURCE_NOT_IN_HIERARCHY", f"Evidence for {claim} uses an unranked source type.", [str(record.get("evidence_id", ""))])
            )
        review_status = str(record.get("review_status", "")).upper()
        if review_status != "ACCEPTED":
            buckets[ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED].append(
                _reason("EVIDENCE_NOT_ACCEPTED", f"Evidence for {claim} is not human-accepted.", [str(record.get("evidence_id", ""))])
            )

    for requirement in requirements:
        requirement = require_mapping(requirement, "requirement")
        claim = require_text(requirement.get("claim"), "requirement.claim")
        records = [
            record
            for record in evidence_by_claim.get(claim, [])
            if str(record.get("review_status", "")).upper() == "ACCEPTED"
        ]
        if not records:
            buckets[ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED].append(
                _reason("REQUIRED_EVIDENCE_MISSING", f"No accepted evidence supports required claim {claim}.")
            )
            continue
        minimum_confidence = float(requirement.get("minimum_confidence", 0.0))
        weak = [record for record in records if float(record.get("confidence", 0.0)) < minimum_confidence]
        if weak:
            buckets[ReadinessStatus.CROSSCHECK_REQUIRED].append(
                _reason("EVIDENCE_CONFIDENCE_LOW", f"Evidence for {claim} is below the required confidence.", [str(record.get("evidence_id", "")) for record in weak])
            )
        required_disciplines = set(requirement.get("required_disciplines", []))
        observed_disciplines = {str(record.get("discipline", "")) for record in records}
        missing_disciplines = sorted(required_disciplines - observed_disciplines)
        if missing_disciplines:
            buckets[ReadinessStatus.CROSSCHECK_REQUIRED].append(
                _reason("DISCIPLINE_CROSSCHECK_MISSING", f"Claim {claim} lacks required disciplines: {', '.join(missing_disciplines)}.")
            )
        values = {
            json.dumps(record.get("value"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for record in records
        }
        if len(values) > 1:
            buckets[ReadinessStatus.COORDINATION_REQUIRED].append(
                _reason("MULTIDISCIPLINARY_EVIDENCE_CONFLICT", f"Accepted evidence has conflicting values for {claim}.", [str(record.get("evidence_id", "")) for record in records])
            )

    missing_scope = _required_scope_complete(payload)
    if missing_scope:
        buckets[ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED].append(
            _reason("WORK_PACKAGE_INPUT_INCOMPLETE", "Required controlled work-package inputs are incomplete: " + ", ".join(missing_scope))
        )

    precedence = (
        ReadinessStatus.BLOCKED,
        ReadinessStatus.COORDINATION_REQUIRED,
        ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED,
        ReadinessStatus.CROSSCHECK_REQUIRED,
    )
    status = next((candidate for candidate in precedence if buckets[candidate]), ReadinessStatus.READY_TO_MODEL)
    reasons = buckets[status] if status != ReadinessStatus.READY_TO_MODEL else [
        _reason("ALL_READINESS_REQUIREMENTS_SATISFIED", "Authorization, authority baseline, evidence, scope, coordinates, assumptions, and role separation are complete.")
    ]
    modeling_allowed = status == ReadinessStatus.READY_TO_MODEL
    return {
        "schema_version": "1.0",
        "decision_id": "DEC-" + _canonical_hash(payload)[:16],
        "item_id": item_id,
        "item_name": str(item.get("name", item_id)),
        "status": status.value,
        "modeling_allowed": modeling_allowed,
        "work_package_allowed": modeling_allowed,
        "authority_write_allowed": False,
        "authority_baseline_rev": str(baseline.get("rev", "")),
        "authority_baseline_sha256": registered_sha.upper(),
        "observed_authority_sha256": observed_sha.upper(),
        "reasons": reasons,
        "next_action": _next_action(status),
    }
