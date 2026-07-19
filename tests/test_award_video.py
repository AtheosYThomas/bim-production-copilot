import json
from pathlib import Path

import pytest

from scripts.render_award_video import (
    EVIDENCE_MATRIX_NOTE,
    NARRATION,
    RESULT_CARDS,
    ROLE_RESEARCH_SUBTITLE,
    VideoGateError,
    validate_final_video_gates,
)


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _records(tmp_path: Path):
    review = _write(tmp_path / "review.json", {
        "status": "PASS", "review_policy": "READ_ONLY", "issue_counts": {"B0": 0, "B1": 0, "B2": 0}, "findings": []
    })
    promotion = _write(tmp_path / "promotion.json", {
        "status": "PROMOTED_TO_NEW_AUTHORITY_REV", "review_findings": {"B0": 0, "B1": 0, "B2": 0},
        "source_authority_unchanged": True, "overwrite_permitted": False,
        "gates": {
            "readiness": "READY_TO_MODEL",
            "regression": "PASS",
            "non_target_difference": 0,
            "bonsai": "PASS",
            "independent_review": "0/0/0",
        },
        "new_authority": {"rev": "REV-2"},
    })
    index = _write(tmp_path / "index.json", {"real_project_item_count": 2, "counts": {
        "READY_TO_MODEL": 1, "CROSSCHECK_REQUIRED": 0, "HUMAN_CLARIFICATION_REQUIRED": 1, "COORDINATION_REQUIRED": 0, "BLOCKED": 0
    }})
    public = _write(tmp_path / "public.json", {"result": "PASS", "confidentiality_findings": []})
    return review, promotion, index, public


def test_final_video_gate_accepts_only_complete_truthful_state(tmp_path: Path) -> None:
    review, promotion, index, public = _records(tmp_path)
    result = validate_final_video_gates(review_path=review, promotion_path=promotion, readiness_index_path=index, sanitization_report_path=public)
    assert result["status"] == "FINAL_VIDEO_GATES_PASS"
    assert result["new_rev"] == "REV-2"


def test_final_video_gate_rejects_pending_review(tmp_path: Path) -> None:
    review, promotion, index, public = _records(tmp_path)
    _write(review, {"status": "AWAITING_INDEPENDENT_REVIEW"})
    with pytest.raises(VideoGateError, match="0/0/0 PASS"):
        validate_final_video_gates(review_path=review, promotion_path=promotion, readiness_index_path=index, sanitization_report_path=public)


def test_narration_carries_the_verified_defect_story() -> None:
    assert "role-separated agent workflow" in NARRATION
    assert "separate readiness engine closes fourteen requirements" in NARRATION
    assert "one thousand two hundred" in NARRATION
    assert "four thousand two hundred" in NARRATION
    assert "one hundred fifty" in NARRATION
    assert "not every value is duplicated" in NARRATION
    assert "five hundred eight non-target differences" in NARRATION
    assert "two thousand three hundred thirty-four protected products" in NARRATION
    assert "separate read-only reviewer" in NARRATION
    assert "No agent can approve its own work" in NARRATION


def test_storyboard_labels_distinguish_roles_and_representative_evidence() -> None:
    assert ROLE_RESEARCH_SUBTITLE == (
        "One research role gathers traceable evidence across disciplines.\n"
        "A separate readiness engine decides what may proceed."
    )
    assert EVIDENCE_MATRIX_NOTE == "3 REPRESENTATIVE RECORDS SHOWN · 14 REQUIREMENTS EVALUATED"
    assert [card[2] for card in RESULT_CARDS] == [
        "FULL-MODEL REGRESSION",
        "REGRESSION GATE",
        "READ-ONLY INDEPENDENT REVIEW",
    ]
