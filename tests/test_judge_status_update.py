import json
from pathlib import Path

import pytest

from scripts.render_award_video import VideoGateError
from scripts.update_judge_ui_status import update_judge_status


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inputs(tmp_path: Path):
    review = _write(tmp_path / "review.json", {"status": "PASS", "review_policy": "READ_ONLY", "issue_counts": {"B0": 0, "B1": 0, "B2": 0}, "findings": []})
    promotion = _write(tmp_path / "promotion.json", {"status": "PROMOTED_TO_NEW_AUTHORITY_REV", "review_findings": {"B0": 0, "B1": 0, "B2": 0}, "source_authority_unchanged": True, "overwrite_permitted": False, "gates": {"readiness": "READY_TO_MODEL", "regression": "PASS", "non_target_difference": 0, "bonsai": "PASS", "independent_review": "0/0/0"}, "new_authority": {"rev": "REV-2"}})
    index = _write(tmp_path / "index.json", {"real_project_item_count": 2, "counts": {"READY_TO_MODEL": 1, "CROSSCHECK_REQUIRED": 0, "HUMAN_CLARIFICATION_REQUIRED": 1, "COORDINATION_REQUIRED": 0, "BLOCKED": 0}})
    public = _write(tmp_path / "public.json", {"result": "PASS", "confidentiality_findings": []})
    output = _write(tmp_path / "demo-status.json", {"status": "PRE_REVIEW"})
    return review, promotion, index, public, output


def test_judge_status_updates_only_from_final_gate_records(tmp_path: Path) -> None:
    review, promotion, index, public, output = _inputs(tmp_path)
    result = update_judge_status(review=review, promotion=promotion, readiness_index=index, sanitization=public, output=output)
    assert result["status"] == "JUDGE_UI_FINAL_STATUS_WRITTEN"
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["independent_review"]["result"] == "PASS — 0 / 0 / 0"
    assert written["promotion"]["result"] == "NEW REV CREATED"
    assert written["rev_transition"] == {
        "source": "REV227 — unchanged",
        "work": "WORK-ETA-01 — reviewed",
        "promoted": "REV228 — created",
    }


def test_judge_status_refuses_pending_review(tmp_path: Path) -> None:
    review, promotion, index, public, output = _inputs(tmp_path)
    _write(review, {"status": "AWAITING_INDEPENDENT_REVIEW"})
    with pytest.raises(VideoGateError, match="0/0/0 PASS"):
        update_judge_status(review=review, promotion=promotion, readiness_index=index, sanitization=public, output=output)
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "PRE_REVIEW"
