"""Controlled invocation of the unchanged external stair capability."""

from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import ifcopenshell

from .authority import sha256_file
from .engine import evaluate_item
from .models import ContractError


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_new_json(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolved_work_path(workspace_root: Path, relative: str) -> Path:
    target = (workspace_root / relative).resolve()
    work_root = (workspace_root / "work").resolve()
    if not target.is_relative_to(work_root):
        raise ContractError(f"controlled output escapes isolated WORK: {relative}")
    return target


@contextmanager
def exclusive_work_lock(work_directory: str | Path, owner: str) -> Iterator[dict[str, Any]]:
    directory = Path(work_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".work-writer.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"WORK writer lock is already held: {lock}") from exc
    record = {"policy": "SINGLE_WRITER", "owner": owner, "lock_path": str(lock)}
    try:
        os.write(descriptor, json.dumps(record, ensure_ascii=False).encode("utf-8"))
        os.close(descriptor)
        yield record
    finally:
        if lock.is_file():
            lock.unlink()


def _parameters_from_work_package(work_package: dict) -> dict[str, Any]:
    parameters = dict(work_package["dimensions_and_elevations"])
    parameters["schema_version"] = "2.1"
    parameters["missing_inputs"] = []
    parameters["requires_human_review"] = False
    parameters["evidence"] = [
        {
            "field": record["claim"],
            "value": str(record.get("value")),
            "unit": record.get("unit"),
            "drawing_source": record.get("drawing_source"),
            "source_description": record.get("source_description"),
            "observed_text": record.get("observed_text"),
            "page": record.get("page"),
            "region": record.get("region"),
            "evidence_type": record.get("external_evidence_type"),
            "confidence": record.get("confidence"),
            "human_review_status": "accepted",
        }
        for record in work_package["approved_source_evidence"]
    ]
    return parameters


def _integration_config(work_package: dict) -> dict[str, Any]:
    controls = work_package["interface_controls"]
    coordinates = work_package["coordinate_transformation"]
    expected = work_package["expected_geometry"]
    return {
        "authority_revision": work_package["authority_baseline"]["rev"],
        "authority_sha256": work_package["authority_baseline"]["sha256"],
        "required_extraction_mode": "live_ai",
        "source_evidence_count": len(work_package["approved_source_evidence"]),
        "target_storey_global_id": controls["target_storey_global_id"],
        "replace_global_ids": work_package["allowed_global_ids"],
        "opening_global_id": controls["opening_global_id"],
        "clash_candidate_global_ids": controls["clash_candidate_global_ids"],
        "representation_mirror_y_mm": coordinates["representation_mirror_y_mm"],
        "placement_matrix_mm": coordinates["transform_matrix"],
        "control_points": coordinates["control_points"],
        "coordinate_tolerance_mm": coordinates["coordinate_tolerance_mm"],
        "bbox_tolerance_mm": expected["bbox_tolerance_mm"],
        "clash_tolerance_mm": controls["clash_tolerance_mm"],
        "target_top_elevation_m": expected["target_top_elevation_m"],
        "expected_generated_bounds_m": expected["generated_bounds_m"],
    }


def _external_code_snapshot(external_root: Path) -> dict[str, str]:
    relative_paths = (
        "pipeline.py",
        "validation/stair.py",
        "builders/stair_ifc.py",
        "audit/ifc_audit.py",
        "review/bim_integration.py",
    )
    return {relative: sha256_file(external_root / relative) for relative in relative_paths}


def _axis_snapshot(axis: Any) -> dict[str, Any] | None:
    if axis is None:
        return None
    record: dict[str, Any] = {
        "ifc_type": axis.is_a(),
        "location": [float(value) for value in axis.Location.Coordinates],
    }
    for name in ("Axis", "RefDirection"):
        value = getattr(axis, name, None)
        record[name] = [float(item) for item in value.DirectionRatios] if value is not None else None
    return record


def _context_snapshot(context: Any) -> dict[str, Any]:
    true_north = getattr(context, "TrueNorth", None)
    return {
        "ifc_type": context.is_a(),
        "context_identifier": getattr(context, "ContextIdentifier", None),
        "context_type": getattr(context, "ContextType", None),
        "coordinate_space_dimension": getattr(context, "CoordinateSpaceDimension", None),
        "precision": getattr(context, "Precision", None),
        "world_coordinate_system": _axis_snapshot(getattr(context, "WorldCoordinateSystem", None)),
        "true_north": [float(value) for value in true_north.DirectionRatios] if true_north is not None else None,
    }


def _copy_direction(source: Any, target: Any) -> None:
    if source is None and target is None:
        return
    if source is None or target is None:
        raise RuntimeError("authority and candidate context direction topology differs")
    target.DirectionRatios = tuple(float(value) for value in source.DirectionRatios)


def restore_authority_representation_contexts(
    authority_path: str | Path, candidate_path: str | Path
) -> dict[str, Any]:
    """Restore only shared authority representation-context values in WORK."""

    authority_file = Path(authority_path).resolve()
    candidate_file = Path(candidate_path).resolve()
    authority_sha = sha256_file(authority_file)
    authority = ifcopenshell.open(str(authority_file))
    candidate = ifcopenshell.open(str(candidate_file))
    changed: list[dict[str, Any]] = []
    base_contexts = [
        context
        for context in authority.by_type("IfcGeometricRepresentationContext")
        if context.is_a() == "IfcGeometricRepresentationContext"
    ]
    for source in base_contexts:
        target = candidate.by_id(source.id())
        if target is None or target.is_a() != source.is_a():
            raise RuntimeError("candidate no longer preserves an authority representation context")
        before = _context_snapshot(target)
        expected = _context_snapshot(source)
        if before == expected:
            continue
        target.ContextIdentifier = source.ContextIdentifier
        target.ContextType = source.ContextType
        target.CoordinateSpaceDimension = source.CoordinateSpaceDimension
        target.Precision = source.Precision
        source_axis = source.WorldCoordinateSystem
        target_axis = target.WorldCoordinateSystem
        if source_axis is None or target_axis is None or source_axis.is_a() != target_axis.is_a():
            raise RuntimeError("authority and candidate WCS topology differs")
        target_axis.Location.Coordinates = tuple(float(value) for value in source_axis.Location.Coordinates)
        _copy_direction(getattr(source_axis, "Axis", None), getattr(target_axis, "Axis", None))
        _copy_direction(getattr(source_axis, "RefDirection", None), getattr(target_axis, "RefDirection", None))
        _copy_direction(getattr(source, "TrueNorth", None), getattr(target, "TrueNorth", None))
        after = _context_snapshot(target)
        if after != expected:
            raise RuntimeError("candidate context restoration did not match the authority baseline")
        changed.append(
            {
                "authority_step_id": source.id(),
                "before_sha256": hashlib.sha256(json.dumps(before, sort_keys=True).encode("utf-8")).hexdigest().upper(),
                "after_sha256": hashlib.sha256(json.dumps(after, sort_keys=True).encode("utf-8")).hexdigest().upper(),
            }
        )
    if changed:
        with tempfile.NamedTemporaryFile(
            prefix="context-restored-", suffix=".ifc", dir=candidate_file.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
        try:
            candidate.write(str(temporary))
            os.replace(temporary, candidate_file)
        finally:
            if temporary.exists():
                temporary.unlink()
    if sha256_file(authority_file) != authority_sha:
        raise RuntimeError("authority source changed while restoring the isolated candidate context")
    return {
        "policy": "RESTORE_SHARED_AUTHORITY_CONTEXT_IN_WORK_ONLY",
        "restored_context_count": len(changed),
        "contexts": changed,
        "authority_unchanged": True,
    }


def run_controlled_modeling(
    *,
    source_item_path: str | Path,
    work_package_path: str | Path,
    external_capability_root: str | Path,
    workspace_root: str | Path,
) -> dict[str, Any]:
    """Generate one isolated candidate under a complete work package."""

    source_item = _read(source_item_path)
    work_package = _read(work_package_path)
    workspace = Path(workspace_root).resolve()
    external_root = Path(external_capability_root).resolve()
    if work_package.get("status") != "CONTROLLED_WORK_PACKAGE_READY":
        raise ContractError("modeling requires a complete controlled work package")
    if work_package.get("unresolved_assumptions") != []:
        raise ContractError("modeling refuses unresolved assumptions")
    policy = work_package.get("write_policy", {})
    if policy.get("authority_model") != "READ_ONLY" or policy.get("modeling_target") != "ISOLATED_WORK_ONLY":
        raise ContractError("work package write policy is unsafe")

    authority_path = Path(source_item["authority_baseline"]["authority_file_path"])
    observed_authority_sha = sha256_file(authority_path)
    decision = evaluate_item(source_item, observed_authority_sha=observed_authority_sha)
    if decision["status"] != "READY_TO_MODEL" or decision["decision_id"] != work_package["decision_id"]:
        raise ContractError("live readiness decision does not match the work package")
    if observed_authority_sha != work_package["authority_baseline"]["sha256"]:
        raise ContractError("B0 authority SHA mismatch before modeling")

    outputs = {
        label: _resolved_work_path(workspace, relative)
        for label, relative in work_package["output_paths"].items()
        if label in {
            "standalone_ifc", "standalone_audit", "candidate_ifc",
            "integration_manifest", "modeling_manifest",
        }
    }
    required_outputs = {
        "standalone_ifc", "standalone_audit", "candidate_ifc",
        "integration_manifest", "modeling_manifest",
    }
    if set(outputs) != required_outputs:
        raise ContractError("work package is missing controlled modeling output paths")
    existing = [str(path) for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite controlled modeling outputs: " + ", ".join(existing))

    external_before = _external_code_snapshot(external_root)
    work_directory = outputs["candidate_ifc"].parent
    modeler = work_package["roles"]["modeling"]["role_id"]
    created: list[Path] = []
    with exclusive_work_lock(work_directory, modeler) as lock_record:
        try:
            sys.path.insert(0, str(external_root))
            pipeline = importlib.import_module("pipeline")
            integration = importlib.import_module("review.bim_integration")
            parameters = _parameters_from_work_package(work_package)
            result = pipeline.run_pipeline(parameters, extraction_mode="live_ai")
            if result.validation.status != "READY_TO_BUILD":
                raise RuntimeError("external deterministic validation did not reach READY_TO_BUILD")
            if result.audit.get("status") != "AUDIT PASSED":
                raise RuntimeError("external standalone IFC audit did not pass")

            for label in ("standalone_ifc", "standalone_audit"):
                outputs[label].parent.mkdir(parents=True, exist_ok=True)
            outputs["standalone_ifc"].write_bytes(result.ifc_bytes)
            created.append(outputs["standalone_ifc"])
            outputs["standalone_audit"].write_bytes(result.audit_bytes)
            created.append(outputs["standalone_audit"])

            integration_result = integration.integrate_authorized_bim(
                authority_path,
                outputs["standalone_ifc"],
                _integration_config(work_package),
                outputs["candidate_ifc"],
                outputs["integration_manifest"],
            )
            created.extend([outputs["candidate_ifc"], outputs["integration_manifest"]])
            if integration_result.get("status") != "INTEGRATION_BUILT":
                raise RuntimeError("external integration did not build the isolated candidate")
            if integration_result.get("authority", {}).get("unchanged") is not True:
                raise RuntimeError("authority source changed during controlled modeling")

            context_restoration = restore_authority_representation_contexts(
                authority_path, outputs["candidate_ifc"]
            )
            integration_result["derived"]["sha256"] = sha256_file(outputs["candidate_ifc"])
            integration_result["governance_adapter"] = context_restoration
            outputs["integration_manifest"].write_text(
                json.dumps(integration_result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            external_after = _external_code_snapshot(external_root)
            if external_before != external_after:
                raise RuntimeError("external capability code changed during controlled modeling")
            final_authority_sha = sha256_file(authority_path)
            if final_authority_sha != observed_authority_sha:
                raise RuntimeError("authority source changed during controlled modeling")
            manifest = {
                "schema_version": "1.0",
                "status": "ISOLATED_WORK_CANDIDATE_BUILT",
                "package_id": work_package["package_id"],
                "work_package_sha256": sha256_file(work_package_path),
                "decision_id": work_package["decision_id"],
                "modeler_role_id": modeler,
                "work_lock": {**lock_record, "acquired": True, "released_after_run": True},
                "authority": {
                    "rev": work_package["authority_baseline"]["rev"],
                    "sha256_before": observed_authority_sha,
                    "sha256_after": final_authority_sha,
                    "unchanged": True,
                    "write_policy": "READ_ONLY",
                },
                "external_capability": {
                    "name": "drawing-evidence-copilot",
                    "source_code_sha256": external_before,
                    "unchanged": True,
                },
                "standalone": {
                    "ifc_path": str(outputs["standalone_ifc"]),
                    "ifc_sha256": sha256_file(outputs["standalone_ifc"]),
                    "audit_path": str(outputs["standalone_audit"]),
                    "audit_status": result.audit["status"],
                    "audit_summary": result.audit["summary"],
                },
                "candidate": {
                    "path": str(outputs["candidate_ifc"]),
                    "sha256": sha256_file(outputs["candidate_ifc"]),
                    "hash_locked": True,
                    "generated_global_ids": [
                        integration_result["derived"]["generated_stair_global_id"],
                        *integration_result["derived"]["generated_child_global_ids"],
                    ],
                    "product_count": integration_result["derived"]["product_count"],
                },
                "candidate_safety_restoration": context_restoration,
                "self_review_allowed": False,
                "self_promotion_allowed": False,
            }
            _write_new_json(outputs["modeling_manifest"], manifest)
            created.append(outputs["modeling_manifest"])
            return manifest
        except Exception:
            for path in reversed(created):
                if path.is_file() and path.resolve().is_relative_to((workspace / "work").resolve()):
                    path.unlink()
            raise
        finally:
            if sys.path and sys.path[0] == str(external_root):
                sys.path.pop(0)
