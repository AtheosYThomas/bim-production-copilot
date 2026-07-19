from __future__ import annotations

import json

import ifcopenshell
import pytest

from bim_authority_gate.authority import capture_ifc_baseline, sha256_file
from bim_authority_gate.models import ContractError
from bim_authority_gate.promotion import promote_candidate, validate_promotion_gates


def _write_json(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_ifc(path, names: list[str]) -> None:
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Promotion fixture")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    for index, name in enumerate(names):
        model.create_entity(
            "IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name=name,
            CompositionType="ELEMENT", Elevation=float(index) * 3.0,
        )
    model.write(str(path))


def _records(tmp_path):
    authority = tmp_path / "REV-001.ifc"
    candidate = tmp_path / "candidate.ifc"
    _write_ifc(authority, ["1F"])
    _write_ifc(candidate, ["1F", "Approved target"])
    baseline = capture_ifc_baseline(authority, "REV-001", coordinate_origin=[0, 0, 0])
    package_id = "WP-PROMOTION-TEST"
    decision_id = "DEC-PROMOTION-TEST"
    candidate_sha = sha256_file(candidate)
    roles = {
        "modeling": {"role_id": "modeler-1"},
        "review": {"role_id": "reviewer-1", "read_only": True},
        "authority_promotion": {"role_id": "authority-1"},
    }
    source_item = {"item": {"item_id": "TEST-01"}, "authority_baseline": baseline}
    work_package = {
        "status": "CONTROLLED_WORK_PACKAGE_READY", "readiness": "READY_TO_MODEL",
        "unresolved_assumptions": [], "package_id": package_id, "decision_id": decision_id,
        "authority_baseline": {"sha256": baseline["sha256"]},
        "gui_requirements": {"freecad": {"required": False}}, "roles": roles,
    }
    modeling = {
        "status": "ISOLATED_WORK_CANDIDATE_BUILT", "package_id": package_id,
        "decision_id": decision_id, "authority": {"sha256_before": baseline["sha256"], "unchanged": True},
        "candidate": {"path": str(candidate), "sha256": candidate_sha, "hash_locked": True, "product_count": 2},
    }
    regression = {
        "status": "PASS", "package_id": package_id, "decision_id": decision_id,
        "non_target": {"difference_count": 0}, "authority": {"unchanged": True},
        "candidate": {"unchanged": True, "sha256_after": candidate_sha},
    }
    bonsai = {
        "gate_result": "PASS", "work_package_id": package_id,
        "candidate": {"sha256_before_gui": candidate_sha, "sha256_after_gui": candidate_sha},
    }
    freecad = {"gate_result": "NOT_APPLICABLE", "work_package_id": package_id}
    review = {
        "status": "PASS", "review_policy": "READ_ONLY", "reviewer_role_id": "reviewer-1",
        "modeler_role_id": "modeler-1", "package_id": package_id,
        "candidate": {"sha256_before": candidate_sha, "sha256_after": candidate_sha},
        "issue_counts": {"B0": 0, "B1": 0, "B2": 0}, "findings": [],
    }
    index = {
        "schema_version": "1.0", "real_project_item_count": 1,
        "counts": {"READY_TO_MODEL": 1, "CROSSCHECK_REQUIRED": 0, "HUMAN_CLARIFICATION_REQUIRED": 0, "COORDINATION_REQUIRED": 0, "BLOCKED": 0},
        "items": [{"item_id": "TEST-01", "status": "READY_TO_MODEL"}],
        "authority_write_policy": "DENIED_AT_READINESS_PHASE", "count_policy": "MEASURED_FROM_DECISION_ARTIFACTS",
    }
    return authority, candidate, source_item, work_package, modeling, regression, bonsai, freecad, review, index


def test_validate_promotion_rejects_self_review(tmp_path) -> None:
    records = _records(tmp_path)
    source, package, modeling, regression, bonsai, freecad, review = records[2:9]
    review["reviewer_role_id"] = "modeler-1"
    with pytest.raises(ContractError, match="reviewer role binding"):
        validate_promotion_gates(
            source_item=source, work_package=package, modeling_manifest=modeling,
            regression_gate=regression, bonsai_gate=bonsai, freecad_gate=freecad,
            independent_review=review,
        )


def test_promotion_creates_new_rev_and_preserves_source(tmp_path) -> None:
    records = _records(tmp_path)
    authority, candidate, source, package, modeling, regression, bonsai, freecad, review, index = records
    paths = {}
    for name, value in {
        "source": source, "package": package, "modeling": modeling, "regression": regression,
        "bonsai": bonsai, "freecad": freecad, "review": review, "index": index,
    }.items():
        paths[name] = tmp_path / f"{name}.json"
        _write_json(paths[name], value)
    original = authority.read_bytes()
    promoted = tmp_path / "REV-002.ifc"
    manifest_path = tmp_path / "promotion.json"
    authority_index = tmp_path / "authority-index.json"
    manifest = promote_candidate(
        source_item_path=paths["source"], work_package_path=paths["package"],
        modeling_manifest_path=paths["modeling"], regression_gate_path=paths["regression"],
        bonsai_gate_path=paths["bonsai"], freecad_gate_path=paths["freecad"],
        independent_review_path=paths["review"], readiness_index_path=paths["index"],
        new_rev="REV-002", new_rev_ifc_path=promoted, promotion_manifest_path=manifest_path,
        updated_authority_index_path=authority_index,
    )
    assert promoted.read_bytes() == candidate.read_bytes()
    assert authority.read_bytes() == original
    assert manifest["source_authority_unchanged"] is True
    assert manifest["review_findings"] == {"B0": 0, "B1": 0, "B2": 0}
    updated = json.loads(authority_index.read_text(encoding="utf-8"))
    assert updated["authority"]["current_rev"] == "REV-002"
    assert updated["items"][0]["current_rev_status"] == "PROMOTED"


def test_promotion_never_overwrites_existing_rev(tmp_path) -> None:
    records = _records(tmp_path)
    source, package, modeling, regression, bonsai, freecad, review, index = records[2:]
    names = ("source", "package", "modeling", "regression", "bonsai", "freecad", "review", "index")
    paths = {}
    for name, value in zip(names, (source, package, modeling, regression, bonsai, freecad, review, index)):
        paths[name] = tmp_path / f"{name}.json"
        _write_json(paths[name], value)
    occupied = tmp_path / "REV-002.ifc"
    occupied.write_bytes(b"do-not-overwrite")
    with pytest.raises(FileExistsError):
        promote_candidate(
            source_item_path=paths["source"], work_package_path=paths["package"],
            modeling_manifest_path=paths["modeling"], regression_gate_path=paths["regression"],
            bonsai_gate_path=paths["bonsai"], freecad_gate_path=paths["freecad"],
            independent_review_path=paths["review"], readiness_index_path=paths["index"],
            new_rev="REV-002", new_rev_ifc_path=occupied,
            promotion_manifest_path=tmp_path / "promotion.json",
            updated_authority_index_path=tmp_path / "authority-index.json",
        )
    assert occupied.read_bytes() == b"do-not-overwrite"
