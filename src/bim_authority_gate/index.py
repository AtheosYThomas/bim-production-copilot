"""Aggregate verified decision artifacts into a measured readiness index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import ContractError, ReadinessStatus


def build_readiness_index(decision_paths: Iterable[str | Path]) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    seen_items: set[str] = set()
    valid_statuses = {status.value for status in ReadinessStatus}
    for source in decision_paths:
        path = Path(source)
        decision = json.loads(path.read_text(encoding="utf-8"))
        item_id = str(decision.get("item_id", ""))
        status = str(decision.get("status", ""))
        if not item_id or item_id in seen_items:
            raise ContractError(f"decision item_id is missing or duplicated: {item_id or '<empty>'}")
        if status not in valid_statuses:
            raise ContractError(f"decision has unsupported readiness status: {status}")
        if decision.get("authority_write_allowed") is not False:
            raise ContractError("readiness decisions must not authorize authority writes")
        if (status == ReadinessStatus.READY_TO_MODEL) != bool(decision.get("modeling_allowed")):
            raise ContractError("modeling_allowed contradicts the readiness status")
        seen_items.add(item_id)
        decisions.append(decision)

    counts = {status.value: 0 for status in ReadinessStatus}
    for decision in decisions:
        counts[decision["status"]] += 1
    items = [
        {
            "item_id": decision["item_id"],
            "item_name": decision["item_name"],
            "status": decision["status"],
            "modeling_allowed": decision["modeling_allowed"],
            "decision_id": decision["decision_id"],
            "authority_baseline_rev": decision["authority_baseline_rev"],
            "reason_codes": [reason["code"] for reason in decision["reasons"]],
            "next_action": decision["next_action"],
        }
        for decision in sorted(decisions, key=lambda item: item["item_id"])
    ]
    return {
        "schema_version": "1.0",
        "real_project_item_count": len(items),
        "counts": counts,
        "items": items,
        "authority_write_policy": "DENIED_AT_READINESS_PHASE",
        "count_policy": "MEASURED_FROM_DECISION_ARTIFACTS",
    }

