from __future__ import annotations

import copy

import pytest

from bim_authority_gate.engine import evaluate_item
from bim_authority_gate.models import ContractError, ReadinessStatus
from bim_authority_gate.work_package import build_work_package


def test_ready_item_is_the_only_state_that_allows_modeling(ready_item: dict) -> None:
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.READY_TO_MODEL
    assert decision["modeling_allowed"] is True
    assert decision["work_package_allowed"] is True
    assert decision["authority_write_allowed"] is False


def test_authority_sha_mismatch_is_b0_and_blocked(ready_item: dict) -> None:
    decision = evaluate_item(ready_item, observed_authority_sha="0" * 64)
    assert decision["status"] == ReadinessStatus.BLOCKED
    assert decision["modeling_allowed"] is False
    assert decision["reasons"][0]["code"] == "B0_AUTHORITY_BASELINE_MISMATCH"


def test_conflicting_architecture_and_structure_requires_coordination(ready_item: dict) -> None:
    ready_item["evidence"][1]["value"] = 1100
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.COORDINATION_REQUIRED
    assert decision["work_package_allowed"] is False
    with pytest.raises(ContractError, match="only for READY_TO_MODEL"):
        build_work_package(ready_item, decision)


def test_missing_evidence_requires_human_clarification(ready_item: dict) -> None:
    ready_item["evidence"] = []
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED


def test_missing_discipline_requires_crosscheck(ready_item: dict) -> None:
    ready_item["evidence"] = ready_item["evidence"][:1]
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.CROSSCHECK_REQUIRED


def test_hard_block_has_precedence_over_evidence_conflict(ready_item: dict) -> None:
    ready_item["authorization"]["project_use_authorized"] = False
    ready_item["evidence"][1]["value"] = 1100
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.BLOCKED


def test_duplicate_role_cannot_self_approve(ready_item: dict) -> None:
    ready_item["roles"]["review"]["role_id"] = ready_item["roles"]["modeling"]["role_id"]
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.BLOCKED
    assert decision["reasons"][0]["code"] == "ROLE_SEPARATION_INVALID"


def test_reviewer_must_be_read_only(ready_item: dict) -> None:
    ready_item["roles"]["review"]["read_only"] = False
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.BLOCKED
    assert any(reason["code"] == "REVIEWER_NOT_READ_ONLY" for reason in decision["reasons"])


def test_incomplete_authority_baseline_is_b0(ready_item: dict) -> None:
    del ready_item["authority_baseline"]["global_id_fingerprint"]
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.BLOCKED
    assert any(reason["code"] == "B0_AUTHORITY_BASELINE_INCOMPLETE" for reason in decision["reasons"])


def test_incomplete_work_package_input_is_not_ready(ready_item: dict) -> None:
    del ready_item["coordinate_definition"]["transform_matrix"]
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED
    assert decision["modeling_allowed"] is False


def test_output_path_outside_work_is_not_ready(ready_item: dict) -> None:
    ready_item["modeling_scope"]["output_paths"]["candidate_ifc"] = "authority/REV.ifc"
    decision = evaluate_item(ready_item)
    assert decision["status"] == ReadinessStatus.HUMAN_CLARIFICATION_REQUIRED


def test_ready_decision_is_deterministic(ready_item: dict) -> None:
    assert evaluate_item(ready_item)["decision_id"] == evaluate_item(copy.deepcopy(ready_item))["decision_id"]
