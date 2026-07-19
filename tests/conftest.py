from __future__ import annotations

import copy

import pytest


@pytest.fixture
def ready_item() -> dict:
    sha = "A" * 64
    payload = {
        "schema_version": "1.0",
        "item": {"item_id": "TEST-STAIR-01", "name": "Synthetic contract-test stair", "component_type": "IfcStair"},
        "authorization": {
            "project_use_authorized": True,
            "drawing_use_authorized": True,
            "authority_inspection_authorized": True,
        },
        "authority_baseline": {
            "authority_file_path": "private/test-authority.ifc",
            "rev": "REV-TEST-001",
            "sha256": sha,
            "observed_sha256": sha,
            "ifc_product_count": 100,
            "global_id_fingerprint": "B" * 64,
            "project_units": [{"unit_type": "LENGTHUNIT", "kind": "SI", "name": "METRE", "prefix": "MILLI"}],
            "coordinate_origin": [0.0, 0.0, 0.0],
            "storeys": [{"global_id": "TEST_STOREY", "name": "1F", "elevation": 0.0}],
            "hold_states": [],
            "rfi_states": [],
        },
        "source_hierarchy": ["structural_detail", "architectural_plan"],
        "requirements": [
            {"claim": "stair_width_mm", "minimum_confidence": 0.9, "required_disciplines": ["architecture", "structure"]}
        ],
        "evidence": [
            {
                "evidence_id": "E-ARCH-01", "claim": "stair_width_mm", "discipline": "architecture",
                "source_type": "architectural_plan", "source_ref": "TEST-A-101", "drawing_source": "drawing dimension", "page": 1,
                "region": "stair plan", "value": 1200, "unit": "mm", "confidence": 0.98,
                "review_status": "ACCEPTED",
            },
            {
                "evidence_id": "E-STR-01", "claim": "stair_width_mm", "discipline": "structure",
                "source_type": "structural_detail", "source_ref": "TEST-S-501", "drawing_source": "drawing dimension", "page": 1,
                "region": "stair detail", "value": 1200, "unit": "mm", "confidence": 0.97,
                "review_status": "ACCEPTED",
            },
        ],
        "issues": [],
        "coordinate_definition": {
            "complete": True,
            "source_coordinate_system": "drawing-local-mm",
            "authority_coordinate_system": "authority-project-mm",
            "transform_matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        },
        "modeling_scope": {
            "allowed_component_scope": ["IfcStair", "IfcStairFlight", "IfcSlab/LANDING"],
            "allowed_global_ids": [],
            "protected_non_target_scope": ["ALL_AUTHORITY_PRODUCTS_EXCEPT_ALLOWED_SCOPE"],
            "expected_geometry": {
                "generated_component_count": 4,
                "generated_bounds_m": {
                    "flight_1": [0, 0, 0, 1, 1, 1],
                    "flight_2": [0, 0, 1, 1, 1, 2],
                    "landing": [0, 0, 1, 1, 1, 1.2]
                },
                "target_top_elevation_m": 2.0,
                "bbox_tolerance_mm": 1.0
            },
            "interface_controls": {
                "target_storey_global_id": "TEST_STOREY",
                "opening_global_id": "TEST_OPENING",
                "clash_candidate_global_ids": ["TEST_BEAM"],
                "clash_tolerance_mm": 1.0
            },
            "dimensions_and_elevations": {"stair_width_mm": 1200, "base_elevation_mm": 0},
            "expected_product_count_changes": {"added": 4, "modified": 0, "deleted": 0},
            "expected_global_id_changes": {"created": 4, "preserved": "ALL_NON_TARGET", "deleted": 0},
            "regression_requirements": ["non_target_difference_count == 0", "authority_sha_unchanged == true"],
            "gui_requirements": {"bonsai": {"required": True}, "freecad": {"required": False}},
            "independent_review_requirements": ["read_only == true", "B0 == 0", "B1 == 0", "B2 == 0"],
            "output_paths": {"candidate_ifc": "work/TEST-STAIR-01/candidate.ifc", "audit": "work/TEST-STAIR-01/audit.json"},
        },
        "unresolved_assumptions": [],
        "roles": {
            "research": {"role_id": "researcher-1"},
            "reasoning": {"role_id": "reasoner-1"},
            "modeling": {"role_id": "modeler-1"},
            "review": {"role_id": "reviewer-1", "read_only": True},
            "authority_promotion": {"role_id": "authority-1"},
        },
    }
    return copy.deepcopy(payload)
