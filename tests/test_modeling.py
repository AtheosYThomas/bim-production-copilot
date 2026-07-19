from __future__ import annotations

import json

import pytest

from bim_authority_gate.engine import evaluate_item
from bim_authority_gate.modeling import _parameters_from_work_package, exclusive_work_lock
from bim_authority_gate.work_package import build_work_package


def test_exclusive_work_lock_rejects_second_writer(tmp_path) -> None:
    with exclusive_work_lock(tmp_path / "work-item", "modeler-1"):
        with pytest.raises(RuntimeError, match="already held"):
            with exclusive_work_lock(tmp_path / "work-item", "modeler-2"):
                pass
    assert not (tmp_path / "work-item" / ".work-writer.lock").exists()


def test_work_package_reconstructs_external_evidence_contract(ready_item: dict) -> None:
    for record in ready_item["evidence"]:
        record.update(
            {
                "source_description": "contract fixture",
                "observed_text": "1200",
                "external_evidence_type": "explicit",
            }
        )
    decision = evaluate_item(ready_item)
    package = build_work_package(ready_item, decision)
    parameters = _parameters_from_work_package(package)
    assert parameters["schema_version"] == "2.1"
    assert parameters["requires_human_review"] is False
    assert parameters["evidence"][0]["field"] == "stair_width_mm"
    assert parameters["evidence"][0]["human_review_status"] == "accepted"

