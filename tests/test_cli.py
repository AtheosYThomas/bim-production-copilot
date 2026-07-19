from __future__ import annotations

from argparse import Namespace

from bim_authority_gate.authority import sha256_file
from bim_authority_gate.cli import _evaluate


def test_non_ready_cli_writes_decision_but_never_work_package(tmp_path, ready_item: dict) -> None:
    authority = tmp_path / "authority.ifc"
    authority.write_bytes(b"read-only-authority-fixture")
    ready_item["authority_baseline"]["sha256"] = sha256_file(authority)
    ready_item["authority_baseline"]["observed_sha256"] = sha256_file(authority)
    ready_item["evidence"][1]["value"] = 1100
    source = tmp_path / "item.json"
    source.write_text(__import__("json").dumps(ready_item), encoding="utf-8")
    decision = tmp_path / "decision.json"
    work_package = tmp_path / "work-package.json"
    result = _evaluate(
        Namespace(
            input=str(source),
            authority=str(authority),
            decision_output=str(decision),
            work_package_output=str(work_package),
        )
    )
    assert result["status"] == "COORDINATION_REQUIRED"
    assert decision.is_file()
    assert not work_package.exists()


def test_ready_cli_preflights_both_outputs_before_writing(tmp_path, ready_item: dict) -> None:
    authority = tmp_path / "authority.ifc"
    authority.write_bytes(b"read-only-authority-fixture")
    ready_item["authority_baseline"]["sha256"] = sha256_file(authority)
    ready_item["authority_baseline"]["observed_sha256"] = sha256_file(authority)
    source = tmp_path / "item.json"
    source.write_text(__import__("json").dumps(ready_item), encoding="utf-8")
    decision = tmp_path / "decision.json"
    work_package = tmp_path / "work-package.json"
    work_package.write_text("occupied", encoding="utf-8")
    try:
        _evaluate(
            Namespace(
                input=str(source), authority=str(authority), decision_output=str(decision),
                work_package_output=str(work_package),
            )
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing work-package path must fail closed")
    assert not decision.exists()
    assert work_package.read_text(encoding="utf-8") == "occupied"
