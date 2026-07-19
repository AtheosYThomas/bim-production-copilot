from __future__ import annotations

import json

import pytest

from bim_authority_gate.engine import evaluate_item
from bim_authority_gate.index import build_readiness_index
from bim_authority_gate.models import ContractError


def _write(path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_index_counts_only_decision_artifacts(tmp_path, ready_item: dict) -> None:
    ready = evaluate_item(ready_item)
    blocked_item = json.loads(json.dumps(ready_item))
    blocked_item["item"]["item_id"] = "TEST-BEAM-02"
    blocked_item["item"]["name"] = "Synthetic missing-evidence contract fixture"
    blocked_item["evidence"] = []
    blocked = evaluate_item(blocked_item)
    first = tmp_path / "ready.json"
    second = tmp_path / "blocked.json"
    _write(first, ready)
    _write(second, blocked)
    index = build_readiness_index([first, second])
    assert index["real_project_item_count"] == 2
    assert index["counts"]["READY_TO_MODEL"] == 1
    assert index["counts"]["HUMAN_CLARIFICATION_REQUIRED"] == 1
    assert sum(index["counts"].values()) == 2


def test_index_rejects_duplicate_items(tmp_path, ready_item: dict) -> None:
    decision = evaluate_item(ready_item)
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    _write(first, decision)
    _write(second, decision)
    with pytest.raises(ContractError, match="duplicated"):
        build_readiness_index([first, second])

