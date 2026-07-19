from __future__ import annotations

import json

import ifcopenshell

from bim_authority_gate.authority import sha256_file
from bim_authority_gate.engine import evaluate_item
from bim_authority_gate.integrations.drawing_evidence import import_drawing_evidence_case


def _write_json(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _authority(path) -> None:
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="External adapter test")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    model.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="1F", Elevation=0.0)
    model.write(str(path))


def test_external_import_is_read_only_and_missing_attribution_crosschecks(tmp_path) -> None:
    authority = tmp_path / "authority.ifc"
    _authority(authority)
    authority_sha = sha256_file(authority)
    extraction = tmp_path / "extracted.json"
    _write_json(
        extraction,
        {
            "schema_version": "2.1", "units": "mm", "component_type": "dog_leg_stair",
            "stair_width_mm": 1200, "missing_inputs": [], "requires_human_review": False,
            "evidence": [{
                "field": "stair_width_mm", "value": "1200", "unit": "mm",
                "drawing_source": "drawing dimension", "page": 1, "region": "stair plan",
                "evidence_type": "explicit", "confidence": 0.98, "human_review_status": "accepted",
            }],
        },
    )
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "status": "LIVE_PUBLIC_RELEASE_GATE_PASSED", "authorization_binding_verified": True,
            "fallback_used": False, "runs_required": 3, "runs_completed": 3,
            "runs": [{"checks": {"checks_passed": 34, "checks_total": 34}}],
        },
    )
    config = tmp_path / "config.json"
    _write_json(
        config,
        {
            "authority_revision": "REV-TEST", "authority_sha256": authority_sha,
            "source_evidence_count": 1, "placement_matrix_mm": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "replace_global_ids": ["A", "B", "C", "D"], "representation_mirror_y_mm": 2400,
            "control_points": [], "coordinate_tolerance_mm": 0.02, "clash_tolerance_mm": 1.0,
        },
    )
    manifest = tmp_path / "manifest.json"
    _write_json(
        manifest,
        {
            "status": "INTEGRATION_BUILT",
            "authority": {"path": str(authority), "revision": "REV-TEST", "sha256_before": authority_sha, "sha256_after": authority_sha, "unchanged": True},
        },
    )
    roles = tmp_path / "roles.json"
    _write_json(
        roles,
        {
            "research": {"role_id": "r1"}, "reasoning": {"role_id": "r2"},
            "modeling": {"role_id": "r3"}, "review": {"role_id": "r4", "read_only": True},
            "authority_promotion": {"role_id": "r5"},
        },
    )
    before = {path: path.read_bytes() for path in (authority, extraction, gate, config, manifest, roles)}
    payload = import_drawing_evidence_case(
        extraction_path=extraction, public_gate_report_path=gate, integration_config_path=config,
        integration_manifest_path=manifest, roles_path=roles,
    )
    decision = evaluate_item(payload)
    assert decision["status"] == "CROSSCHECK_REQUIRED"
    assert decision["modeling_allowed"] is False
    assert all(path.read_bytes() == content for path, content in before.items())

