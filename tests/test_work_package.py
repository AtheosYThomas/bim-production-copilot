from __future__ import annotations

import pytest

from bim_authority_gate.engine import evaluate_item
from bim_authority_gate.models import ContractError
from bim_authority_gate.work_package import build_work_package


def test_ready_item_generates_complete_isolated_work_package(ready_item: dict) -> None:
    decision = evaluate_item(ready_item)
    package = build_work_package(ready_item, decision)
    assert package["readiness"] == "READY_TO_MODEL"
    assert package["status"] == "CONTROLLED_WORK_PACKAGE_READY"
    assert package["unresolved_assumptions"] == []
    assert package["write_policy"] == {
        "authority_model": "READ_ONLY",
        "modeling_target": "ISOLATED_WORK_ONLY",
        "self_promotion_allowed": False,
        "single_work_writer_required": True,
    }
    assert len(package["approved_source_evidence"]) == 2


def test_work_package_output_must_be_in_isolated_work(ready_item: dict) -> None:
    ready_item["modeling_scope"]["output_paths"]["candidate_ifc"] = "authority/REV.ifc"
    decision = evaluate_item(ready_item)
    decision["status"] = "READY_TO_MODEL"
    decision["modeling_allowed"] = True
    with pytest.raises(ContractError, match="isolated work"):
        build_work_package(ready_item, decision)
