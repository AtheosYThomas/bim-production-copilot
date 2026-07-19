import json
from pathlib import Path

from scripts.audit_final_submission import audit_final_submission, _sha


def _write(path: Path, value) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        path.write_bytes(value)
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_final_submission_audit_reports_ready_only_when_every_requirement_passes(tmp_path: Path) -> None:
    authority = _write(tmp_path / "authority.ifc", b"authority")
    candidate = _write(tmp_path / "run/candidate.ifc", b"candidate")
    new_rev = _write(tmp_path / "authority/REV-2.ifc", candidate.read_bytes())
    authority_sha, candidate_sha = _sha(authority), _sha(candidate)
    source = _write(tmp_path / "source.json", {"authority_baseline": {"authority_file_path": str(authority), "sha256": authority_sha, "rev": "REV-1"}})
    ready = _write(tmp_path / "ready.json", {"decision_id": "DEC-1", "status": "READY_TO_MODEL", "modeling_allowed": True, "authority_write_allowed": False})
    blocked = _write(tmp_path / "blocked.json", {"decision_id": "DEC-2", "status": "HUMAN_CLARIFICATION_REQUIRED", "modeling_allowed": False, "work_package_allowed": False, "authority_write_allowed": False})
    package = _write(tmp_path / "package.json", {"package_id": "WP-1", "decision_id": "DEC-1", "unresolved_assumptions": [], "gui_requirements": {"freecad": {"required": False}}})
    _write(tmp_path / "run/modeling-manifest.json", {"candidate": {"sha256": candidate_sha, "hash_locked": True}, "authority": {"unchanged": True}})
    _write(tmp_path / "run/regression-gate.json", {"status": "PASS", "non_target": {"difference_count": 0}, "authority": {"unchanged": True}})
    _write(tmp_path / "run/gui/gui-gate.json", {"gate_result": "PASS", "candidate": {"sha256_after_gui": candidate_sha}})
    _write(tmp_path / "run/gui/freecad-gate.json", {"gate_result": "NOT_APPLICABLE"})
    index = _write(tmp_path / "index.json", {"real_project_item_count": 2, "counts": {"READY_TO_MODEL": 1, "CROSSCHECK_REQUIRED": 0, "HUMAN_CLARIFICATION_REQUIRED": 1, "COORDINATION_REQUIRED": 0, "BLOCKED": 0}})
    repeatability = _write(tmp_path / "repeat.json", {"result": "PASS_SEMANTIC_REPEATABILITY", "runs": [{"authority_unchanged": True, "non_target_difference_count": 0}] * 3})
    review = _write(tmp_path / "review.json", {"status": "PASS", "review_policy": "READ_ONLY", "issue_counts": {"B0": 0, "B1": 0, "B2": 0}, "findings": [], "candidate": {"sha256_before": candidate_sha, "sha256_after": candidate_sha}})
    promotion = _write(tmp_path / "promotion.json", {"status": "PROMOTED_TO_NEW_AUTHORITY_REV", "overwrite_permitted": False, "source_authority_unchanged": True, "new_authority": {"rev": "REV-2", "path": str(new_rev), "sha256": candidate_sha}})
    site = _write(tmp_path / "site.json", {"status": "SUCCEEDED", "url": "https://example.test", "public_access": True, "access": "PUBLIC"})
    public = _write(tmp_path / "public.json", {"result": "PASS", "confidentiality_findings": [], "files_scanned": 10})
    repo = _write(tmp_path / "repo.json", {"status": "PUBLISHED", "public": True, "remote_url": "https://example.test/repo", "commit": "abc"})
    video = _write(tmp_path / "video.mp4", b"video")
    report = audit_final_submission(source_item_path=source, ready_decision_path=ready, blocked_decision_path=blocked, work_package_path=package, run_dir=tmp_path / "run", readiness_index_path=index, repeatability_path=repeatability, review_path=review, promotion_path=promotion, site_deployment_path=site, public_sanitization_path=public, public_repo_release_path=repo, video_path=video)
    assert report["phase_result"] == "READY_TO_SUBMIT"
    assert report["passed"] == report["total"]


def test_final_submission_audit_fails_closed_when_external_release_is_missing(tmp_path: Path) -> None:
    authority = _write(tmp_path / "authority.ifc", b"authority")
    source = _write(tmp_path / "source.json", {"authority_baseline": {"authority_file_path": str(authority), "sha256": _sha(authority), "rev": "REV-1"}})
    empty = _write(tmp_path / "empty.json", {})
    report = audit_final_submission(source_item_path=source, ready_decision_path=empty, blocked_decision_path=empty, work_package_path=empty, run_dir=tmp_path / "run", readiness_index_path=empty, repeatability_path=empty, review_path=tmp_path / "missing-review.json", promotion_path=tmp_path / "missing-promotion.json", site_deployment_path=empty, public_sanitization_path=empty, public_repo_release_path=empty, video_path=tmp_path / "missing.mp4")
    assert report["phase_result"] == "BLOCKED"
    assert "public source repository is not published" in report["current_blockers"]
