"""Publish only sanitized, verified final Gate status into the judge UI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.render_award_video import VideoGateError, validate_final_video_gates


def update_judge_status(*, review: Path, promotion: Path, readiness_index: Path, sanitization: Path, output: Path) -> dict:
    validation = validate_final_video_gates(
        review_path=review,
        promotion_path=promotion,
        readiness_index_path=readiness_index,
        sanitization_report_path=sanitization,
    )
    value = {
        "schema_version": "1.0",
        "status": "PROMOTED",
        "ready_next_action": "Approved by a separate read-only reviewer and promoted by the controlling authority role.",
        "current_rev_status": "New authority REV created — confidential identifier withheld",
        "independent_review": {"result": "PASS — 0 / 0 / 0", "state": "pass"},
        "promotion": {"result": "NEW REV CREATED", "state": "pass", "flow_label": "PROMOTED"},
        "rev_transition": {
            "source": "REV227 — unchanged",
            "work": "WORK-ETA-01 — reviewed",
            "promoted": "REV228 — created",
        },
    }
    if not output.is_file():
        raise VideoGateError("judge UI status file is missing; refusing to create an unbound target")
    current = json.loads(output.read_text(encoding="utf-8-sig"))
    if current.get("status") not in {"PRE_REVIEW", "PROMOTED"}:
        raise VideoGateError("judge UI status has an unknown state")
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {"status": "JUDGE_UI_FINAL_STATUS_WRITTEN", "new_rev": validation["new_rev"], "public_fields": value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--promotion", required=True, type=Path)
    parser.add_argument("--readiness-index", required=True, type=Path)
    parser.add_argument("--sanitization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = update_judge_status(review=args.review, promotion=args.promotion, readiness_index=args.readiness_index, sanitization=args.sanitization, output=args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
