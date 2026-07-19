"""Requirement-by-requirement final audit for the award submission."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def audit_final_submission(
    *,
    source_item_path: Path,
    ready_decision_path: Path,
    blocked_decision_path: Path,
    work_package_path: Path,
    run_dir: Path,
    readiness_index_path: Path,
    repeatability_path: Path,
    review_path: Path,
    promotion_path: Path,
    site_deployment_path: Path,
    public_sanitization_path: Path,
    public_repo_release_path: Path,
    video_path: Path,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []

    def record(name: str, passed: bool, evidence: Any, blocker: str) -> None:
        checks[name] = {"status": "PASS" if passed else "FAIL", "evidence": evidence}
        if not passed:
            blockers.append(blocker)

    source = _read(source_item_path)
    ready = _read(ready_decision_path)
    blocked = _read(blocked_decision_path)
    package = _read(work_package_path)
    index = _read(readiness_index_path)
    repeatability = _read(repeatability_path)
    modeling = _read(run_dir / "modeling-manifest.json")
    regression = _read(run_dir / "regression-gate.json")
    bonsai = _read(run_dir / "gui/gui-gate.json")
    freecad = _read(run_dir / "gui/freecad-gate.json")

    authority = (source or {}).get("authority_baseline", {})
    authority_path = Path(str(authority.get("authority_file_path", "")))
    authority_registered = str(authority.get("sha256", "")).upper()
    authority_live = _sha(authority_path) if authority_path.is_file() else None
    record("authority_baseline", bool(authority_live and authority_live == authority_registered), {
        "rev": authority.get("rev"), "registered_sha256": authority_registered, "live_sha256": authority_live
    }, "authority baseline is unavailable or changed")

    expected_states = {"READY_TO_MODEL", "CROSSCHECK_REQUIRED", "HUMAN_CLARIFICATION_REQUIRED", "COORDINATION_REQUIRED", "BLOCKED"}
    counts = (index or {}).get("counts", {})
    counts_valid = set(counts) == expected_states and sum(int(value) for value in counts.values()) == (index or {}).get("real_project_item_count") == 2
    record("machine_readable_readiness", counts_valid and counts.get("READY_TO_MODEL") == 1, counts, "readiness counts are incomplete or not based on two real items")
    record("successful_ready_case", bool(ready and ready.get("status") == "READY_TO_MODEL" and ready.get("modeling_allowed") is True and ready.get("authority_write_allowed") is False), ready.get("decision_id") if ready else None, "successful case is not a valid READY_TO_MODEL decision")
    record("safe_blocked_case", bool(blocked and blocked.get("status") in expected_states - {"READY_TO_MODEL"} and blocked.get("modeling_allowed") is False and blocked.get("work_package_allowed") is False and blocked.get("authority_write_allowed") is False), blocked.get("decision_id") if blocked else None, "blocked case does not fail safely")

    assumptions = (package or {}).get("unresolved_assumptions")
    record("controlled_work_package", bool(package and ready and package.get("decision_id") == ready.get("decision_id") and assumptions == []), package.get("package_id") if package else None, "controlled work package is missing, misbound, or contains unresolved assumptions")

    candidate_path = run_dir / "candidate.ifc"
    candidate_sha = _sha(candidate_path) if candidate_path.is_file() else None
    model_candidate = (modeling or {}).get("candidate", {})
    isolated_ok = bool(modeling and candidate_sha and model_candidate.get("sha256") == candidate_sha and model_candidate.get("hash_locked") is True and (modeling.get("authority") or {}).get("unchanged") is True)
    record("isolated_work", isolated_ok, {"candidate_sha256": candidate_sha}, "isolated WORK candidate is missing or not hash locked")

    regression_ok = bool(regression and regression.get("status") == "PASS" and (regression.get("non_target") or {}).get("difference_count") == 0 and (regression.get("authority") or {}).get("unchanged") is True)
    record("regression_gate", regression_ok, {"non_target_difference": (regression or {}).get("non_target", {}).get("difference_count")}, "regression Gate is not PASS with non-target difference 0")
    record("bonsai_gate", bool(bonsai and bonsai.get("gate_result") == "PASS" and (bonsai.get("candidate") or {}).get("sha256_after_gui") == candidate_sha), bonsai.get("gate_result") if bonsai else None, "Bonsai GUI Gate did not pass")
    freecad_required = bool((package or {}).get("gui_requirements", {}).get("freecad", {}).get("required"))
    freecad_expected = "PASS" if freecad_required else "NOT_APPLICABLE"
    record("freecad_gate", bool(freecad and freecad.get("gate_result") == freecad_expected), freecad.get("gate_result") if freecad else None, "FreeCAD Gate/applicability record is invalid")

    repeat_runs = (repeatability or {}).get("runs", [])
    repeat_ok = bool(repeatability and repeatability.get("result") == "PASS_SEMANTIC_REPEATABILITY" and len(repeat_runs) >= 3 and all(run.get("authority_unchanged") is True and run.get("non_target_difference_count") == 0 for run in repeat_runs))
    record("three_clean_runs", repeat_ok, {"run_count": len(repeat_runs)}, "three clean semantic repeatability runs are not proven")

    review = _read(review_path)
    review_ok = bool(review and review.get("status") == "PASS" and review.get("review_policy") == "READ_ONLY" and review.get("issue_counts") == {"B0": 0, "B1": 0, "B2": 0} and review.get("findings") == [] and (review.get("candidate") or {}).get("sha256_before") == candidate_sha == (review.get("candidate") or {}).get("sha256_after"))
    record("independent_review", review_ok, (review or {}).get("issue_counts"), "independent read-only review 0/0/0 is missing")

    promotion = _read(promotion_path)
    new_authority = (promotion or {}).get("new_authority", {})
    new_authority_path = Path(str(new_authority.get("path", ""))) if new_authority.get("path") else None
    new_authority_sha = _sha(new_authority_path) if new_authority_path and new_authority_path.is_file() else None
    promotion_ok = bool(
        promotion and promotion.get("status") == "PROMOTED_TO_NEW_AUTHORITY_REV"
        and promotion.get("overwrite_permitted") is False and promotion.get("source_authority_unchanged") is True
        and new_authority_sha and new_authority_sha == str(new_authority.get("sha256", "")).upper()
        and authority_live == authority_registered
    )
    record("new_rev_promotion", promotion_ok, {"new_rev": new_authority.get("rev"), "sha256": new_authority_sha}, "controlled promotion into a new REV is missing")

    site = _read(site_deployment_path)
    site_ok = bool(site and site.get("status") == "SUCCEEDED" and site.get("url") and site.get("public_access") is True)
    record("judge_ui", site_ok, {"url": (site or {}).get("url"), "access": (site or {}).get("access")}, "judge UI is not publicly accessible")
    public = _read(public_sanitization_path)
    record("public_sanitization", bool(public and public.get("result") == "PASS" and public.get("confidentiality_findings") == []), {"files_scanned": (public or {}).get("files_scanned")}, "public sanitization Gate did not pass")
    repo = _read(public_repo_release_path)
    repo_ok = bool(repo and repo.get("status") == "PUBLISHED" and repo.get("public") is True and repo.get("remote_url"))
    record("public_repo", repo_ok, {"commit": (repo or {}).get("commit"), "remote_url": (repo or {}).get("remote_url")}, "public source repository is not published")
    record("final_video", video_path.is_file() and video_path.stat().st_size > 0, {"path": str(video_path), "exists": video_path.is_file()}, "final 60-second video is missing")

    return {
        "schema_version": "1.0",
        "audit": "FINAL_BIM_PRODUCTION_COPILOT_SUBMISSION",
        "phase_result": "READY_TO_SUBMIT" if not blockers else "BLOCKED",
        "passed": sum(check["status"] == "PASS" for check in checks.values()),
        "total": len(checks),
        "checks": checks,
        "current_blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("source_item", "ready_decision", "blocked_decision", "work_package", "run_dir", "readiness_index", "repeatability", "review", "promotion", "site_deployment", "public_sanitization", "public_repo_release", "video", "output"):
        parser.add_argument(f"--{name.replace('_', '-')}", required=True, type=Path)
    args = parser.parse_args()
    report = audit_final_submission(
        source_item_path=args.source_item, ready_decision_path=args.ready_decision, blocked_decision_path=args.blocked_decision,
        work_package_path=args.work_package, run_dir=args.run_dir, readiness_index_path=args.readiness_index,
        repeatability_path=args.repeatability, review_path=args.review, promotion_path=args.promotion,
        site_deployment_path=args.site_deployment, public_sanitization_path=args.public_sanitization,
        public_repo_release_path=args.public_repo_release, video_path=args.video,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["phase_result"] == "READY_TO_SUBMIT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
