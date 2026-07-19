from pathlib import Path

from scripts.audit_public_release import audit


def test_public_audit_rejects_internal_work_package(tmp_path: Path) -> None:
    (tmp_path / "page.tsx").write_text("const packageId = 'WP-0123456789ABCDEF';", encoding="utf-8")
    findings, scanned = audit(tmp_path, [])
    assert scanned == 1
    assert findings == [{"file": "page.tsx", "rule": "internal_work_package"}]


def test_public_audit_rejects_project_forbidden_term(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Secret Project Alpha", encoding="utf-8")
    findings, _ = audit(tmp_path, ["Project Alpha"])
    assert findings == [{"file": "README.md", "rule": "project_forbidden_term"}]


def test_public_audit_accepts_sanitized_alias(tmp_path: Path) -> None:
    (tmp_path / "page.tsx").write_text("CONTROLLED PACKAGE ETA-01", encoding="utf-8")
    findings, _ = audit(tmp_path, ["Project Alpha"])
    assert findings == []
