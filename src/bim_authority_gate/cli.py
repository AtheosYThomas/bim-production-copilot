"""Command-line entry points for baseline capture and readiness evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .authority import capture_ifc_baseline, sha256_file
from .engine import evaluate_item
from .integrations.drawing_evidence import (
    build_incomplete_authority_item,
    import_drawing_evidence_case,
)
from .index import build_readiness_index
from .modeling import run_controlled_modeling
from .regression import run_regression_gate
from .promotion import promote_candidate
from .work_package import build_work_package


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_new_json(path: str | Path, value: dict) -> None:
    output = Path(path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_new_path(path: str | Path) -> None:
    output = Path(path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")


def _capture(args: argparse.Namespace) -> dict:
    baseline = capture_ifc_baseline(
        args.authority,
        args.rev,
        coordinate_origin=[float(value) for value in args.coordinate_origin],
    )
    _write_new_json(args.output, baseline)
    return {"status": "AUTHORITY_BASELINE_CAPTURED", "output": str(args.output)}


def _evaluate(args: argparse.Namespace) -> dict:
    payload = _read_json(args.input)
    authority_path = args.authority or payload.get("authority_baseline", {}).get("authority_file_path")
    if not authority_path:
        raise ValueError("authority path is required either by --authority or the registered baseline")
    observed_sha = sha256_file(authority_path)
    decision = evaluate_item(payload, observed_authority_sha=observed_sha)
    _require_new_path(args.decision_output)
    package_written = False
    if decision["work_package_allowed"]:
        if not args.work_package_output:
            raise ValueError("READY_TO_MODEL requires --work-package-output")
        _require_new_path(args.work_package_output)
        package = build_work_package(payload, decision)
        _write_new_json(args.decision_output, decision)
        _write_new_json(args.work_package_output, package)
        package_written = True
    else:
        _write_new_json(args.decision_output, decision)
    return {
        "status": decision["status"],
        "decision_output": str(args.decision_output),
        "work_package_written": package_written,
    }


def _import_drawing_evidence(args: argparse.Namespace) -> dict:
    payload = import_drawing_evidence_case(
        extraction_path=args.extraction,
        public_gate_report_path=args.public_gate_report,
        integration_config_path=args.integration_config,
        integration_manifest_path=args.integration_manifest,
        roles_path=args.roles,
        evidence_map_path=args.evidence_map,
        authorization_manifest_path=args.authorization_manifest,
        drawing_path=args.drawing,
        item_id=args.item_id,
        item_name=args.item_name,
        work_run=args.work_run,
    )
    _write_new_json(args.output, payload)
    return {"status": "EXTERNAL_EVIDENCE_IMPORTED_READ_ONLY", "output": str(args.output)}


def _create_incomplete_item(args: argparse.Namespace) -> dict:
    payload = build_incomplete_authority_item(
        integration_config_path=args.integration_config,
        integration_manifest_path=args.integration_manifest,
        roles_path=args.roles,
        candidate_index=args.candidate_index,
        item_id=args.item_id,
        item_name=args.item_name,
    )
    _write_new_json(args.output, payload)
    return {"status": "REAL_INCOMPLETE_ITEM_REGISTERED", "output": str(args.output)}


def _build_index(args: argparse.Namespace) -> dict:
    index = build_readiness_index(args.decisions)
    _write_new_json(args.output, index)
    return {
        "status": "READINESS_INDEX_BUILT",
        "real_project_item_count": index["real_project_item_count"],
        "counts": index["counts"],
        "output": str(args.output),
    }


def _model(args: argparse.Namespace) -> dict:
    manifest = run_controlled_modeling(
        source_item_path=args.source_item,
        work_package_path=args.work_package,
        external_capability_root=args.external_capability_root,
        workspace_root=args.workspace_root,
    )
    return {
        "status": manifest["status"],
        "package_id": manifest["package_id"],
        "authority_unchanged": manifest["authority"]["unchanged"],
        "candidate_hash_locked": manifest["candidate"]["hash_locked"],
    }


def _regress(args: argparse.Namespace) -> dict:
    gate = run_regression_gate(
        source_item_path=args.source_item,
        work_package_path=args.work_package,
        modeling_manifest_path=args.modeling_manifest,
        external_capability_root=args.external_capability_root,
        workspace_root=args.workspace_root,
    )
    return {
        "status": gate["status"],
        "summary": gate["summary"],
        "non_target_difference": gate["non_target"]["difference_count"],
        "authority_unchanged": gate["authority"]["unchanged"],
        "candidate_unchanged": gate["candidate"]["unchanged"],
    }


def _promote(args: argparse.Namespace) -> dict:
    manifest = promote_candidate(
        source_item_path=args.source_item,
        work_package_path=args.work_package,
        modeling_manifest_path=args.modeling_manifest,
        regression_gate_path=args.regression_gate,
        bonsai_gate_path=args.bonsai_gate,
        freecad_gate_path=args.freecad_gate,
        independent_review_path=args.independent_review,
        readiness_index_path=args.readiness_index,
        new_rev=args.new_rev,
        new_rev_ifc_path=args.new_rev_ifc,
        promotion_manifest_path=args.promotion_manifest,
        updated_authority_index_path=args.updated_authority_index,
    )
    return {
        "status": manifest["status"],
        "new_rev": manifest["new_authority"]["rev"],
        "new_rev_sha256": manifest["new_authority"]["sha256"],
        "source_authority_unchanged": manifest["source_authority_unchanged"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bim-authority-gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture-baseline")
    capture.add_argument("--authority", required=True)
    capture.add_argument("--rev", required=True)
    capture.add_argument("--coordinate-origin", nargs=3, required=True, metavar=("X", "Y", "Z"))
    capture.add_argument("--output", required=True)
    capture.set_defaults(handler=_capture)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--input", required=True)
    evaluate.add_argument("--authority")
    evaluate.add_argument("--decision-output", required=True)
    evaluate.add_argument("--work-package-output")
    evaluate.set_defaults(handler=_evaluate)
    importer = subparsers.add_parser("import-drawing-evidence")
    importer.add_argument("--extraction", required=True)
    importer.add_argument("--public-gate-report", required=True)
    importer.add_argument("--integration-config", required=True)
    importer.add_argument("--integration-manifest", required=True)
    importer.add_argument("--roles", required=True)
    importer.add_argument("--evidence-map")
    importer.add_argument("--authorization-manifest")
    importer.add_argument("--drawing")
    importer.add_argument("--item-id", default="AUTHORIZED-STAIR-01")
    importer.add_argument("--item-name", default="Authorized stair package")
    importer.add_argument("--work-run", default="run-01")
    importer.add_argument("--output", required=True)
    importer.set_defaults(handler=_import_drawing_evidence)
    incomplete = subparsers.add_parser("create-incomplete-authority-item")
    incomplete.add_argument("--integration-config", required=True)
    incomplete.add_argument("--integration-manifest", required=True)
    incomplete.add_argument("--roles", required=True)
    incomplete.add_argument("--candidate-index", type=int, required=True)
    incomplete.add_argument("--item-id", required=True)
    incomplete.add_argument("--item-name", required=True)
    incomplete.add_argument("--output", required=True)
    incomplete.set_defaults(handler=_create_incomplete_item)
    index = subparsers.add_parser("build-index")
    index.add_argument("--decisions", nargs="+", required=True)
    index.add_argument("--output", required=True)
    index.set_defaults(handler=_build_index)
    model = subparsers.add_parser("model")
    model.add_argument("--source-item", required=True)
    model.add_argument("--work-package", required=True)
    model.add_argument("--external-capability-root", required=True)
    model.add_argument("--workspace-root", default=".")
    model.set_defaults(handler=_model)
    regress = subparsers.add_parser("regress")
    regress.add_argument("--source-item", required=True)
    regress.add_argument("--work-package", required=True)
    regress.add_argument("--modeling-manifest", required=True)
    regress.add_argument("--external-capability-root", required=True)
    regress.add_argument("--workspace-root", default=".")
    regress.set_defaults(handler=_regress)
    promote = subparsers.add_parser("promote")
    promote.add_argument("--source-item", required=True)
    promote.add_argument("--work-package", required=True)
    promote.add_argument("--modeling-manifest", required=True)
    promote.add_argument("--regression-gate", required=True)
    promote.add_argument("--bonsai-gate", required=True)
    promote.add_argument("--freecad-gate", required=True)
    promote.add_argument("--independent-review", required=True)
    promote.add_argument("--readiness-index", required=True)
    promote.add_argument("--new-rev", required=True)
    promote.add_argument("--new-rev-ifc", required=True)
    promote.add_argument("--promotion-manifest", required=True)
    promote.add_argument("--updated-authority-index", required=True)
    promote.set_defaults(handler=_promote)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = args.handler(args)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
