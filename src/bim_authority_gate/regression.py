"""Read-only regression Gate for isolated WORK candidates."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
from ifcopenshell.util.element import get_aggregate, get_container, get_materials, get_psets, get_type
from ifcopenshell.util.placement import get_local_placement

from .authority import sha256_file
from .modeling import _integration_config
from .models import ContractError


def _read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()


def _without_entity_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_entity_ids(item) for key, item in value.items() if key != "id"}
    if isinstance(value, (list, tuple)):
        return [_without_entity_ids(item) for item in value]
    return value


def _simple_attributes(product: Any) -> dict[str, Any]:
    ignored = {"id", "type", "OwnerHistory", "ObjectPlacement", "Representation"}
    result: dict[str, Any] = {}
    for key, value in product.get_info().items():
        if key in ignored:
            continue
        if value is None or isinstance(value, (str, int, float, bool)):
            result[key] = value
    return result


def _entity_graph(value: Any, active: set[int] | None = None) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, (list, tuple)):
        return [_entity_graph(item, active) for item in value]
    if not isinstance(value, ifcopenshell.entity_instance):
        return str(value)
    active = set() if active is None else active
    identity = id(value)
    if identity in active:
        return {"cycle": value.is_a()}
    active.add(identity)
    try:
        record: dict[str, Any] = {"ifc_type": value.is_a()}
        global_id = getattr(value, "GlobalId", None)
        if global_id:
            record["global_id"] = str(global_id)
        attributes: dict[str, Any] = {}
        for index in range(len(value)):
            name = value.attribute_name(index)
            if name == "OwnerHistory":
                continue
            attributes[name] = _entity_graph(value[index], active)
        record["attributes"] = attributes
        return record
    finally:
        active.remove(identity)


def _geometry_record(product: Any, settings: Any) -> tuple[dict[str, Any], str | None, bool]:
    if getattr(product, "Representation", None) is None:
        return {"present": False}, None, False
    try:
        shape = ifcopenshell.geom.create_shape(settings, product)
        vertices = [round(float(value), 6) for value in shape.geometry.verts]
        faces = [int(value) for value in shape.geometry.faces]
        edges = [int(value) for value in getattr(shape.geometry, "edges", [])]
        return {
            "present": True,
            "vertices_sha256": _canonical_hash(vertices),
            "faces_sha256": _canonical_hash(faces),
            "edges_sha256": _canonical_hash(edges),
            "vertex_count": len(vertices) // 3,
            "triangle_count": len(faces) // 3,
        }, None, False
    except Exception as exc:  # IfcOpenShell raises several backend-specific types.
        try:
            raw_hash = _canonical_hash(_entity_graph(product.Representation))
            return {
                "present": True,
                "verification_mode": "IFC_REPRESENTATION_GRAPH_FALLBACK",
                "representation_graph_sha256": raw_hash,
                "tessellation_error_type": type(exc).__name__,
            }, None, True
        except Exception as fallback_exc:
            return {
                "present": True,
                "error": type(exc).__name__,
                "fallback_error": type(fallback_exc).__name__,
            }, type(fallback_exc).__name__, False


def _related_global_id(entity: Any) -> str | None:
    return str(entity.GlobalId) if entity is not None and getattr(entity, "GlobalId", None) else None


def _product_fingerprint(product: Any, settings: Any) -> tuple[str, str | None, bool]:
    placement = None
    if getattr(product, "ObjectPlacement", None) is not None:
        placement = [
            [round(float(value), 9) for value in row]
            for row in get_local_placement(product.ObjectPlacement).tolist()
        ]
    geometry, geometry_error, used_fallback = _geometry_record(product, settings)
    type_object = get_type(product)
    materials = sorted(
        {
            f"{material.is_a()}:{getattr(material, 'Name', '') or ''}"
            for material in get_materials(product)
        }
    )
    record = {
        "ifc_type": product.is_a(),
        "attributes": _simple_attributes(product),
        "placement": placement,
        "container_global_id": _related_global_id(get_container(product)),
        "aggregate_global_id": _related_global_id(get_aggregate(product)),
        "type_global_id": _related_global_id(type_object),
        "materials": materials,
        "psets": _without_entity_ids(get_psets(product)),
        "geometry": geometry,
    }
    return _canonical_hash(record), geometry_error, used_fallback


def _products_by_guid(model: Any) -> dict[str, Any]:
    return {
        str(product.GlobalId): product
        for product in model.by_type("IfcProduct")
        if getattr(product, "GlobalId", None)
    }


def _non_target_diff(authority_model: Any, candidate_model: Any, removed_ids: set[str], generated_ids: set[str]) -> dict[str, Any]:
    authority = _products_by_guid(authority_model)
    candidate = _products_by_guid(candidate_model)
    authority_non_target = set(authority) - removed_ids
    candidate_non_target = set(candidate) - generated_ids
    missing = sorted(authority_non_target - candidate_non_target)
    unexpected = sorted(candidate_non_target - authority_non_target)
    shared = sorted(authority_non_target & candidate_non_target)
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    changed: list[dict[str, str]] = []
    geometry_errors: list[dict[str, str]] = []
    geometry_fallback_count = 0
    for global_id in shared:
        authority_hash, authority_error, authority_fallback = _product_fingerprint(authority[global_id], settings)
        candidate_hash, candidate_error, candidate_fallback = _product_fingerprint(candidate[global_id], settings)
        if authority_fallback or candidate_fallback:
            geometry_fallback_count += 1
        if authority_error or candidate_error:
            geometry_errors.append(
                {
                    "global_id_hash": hashlib.sha256(global_id.encode("utf-8")).hexdigest().upper(),
                    "authority_error": authority_error or "",
                    "candidate_error": candidate_error or "",
                }
            )
        if authority_hash != candidate_hash:
            changed.append(
                {
                    "global_id_hash": hashlib.sha256(global_id.encode("utf-8")).hexdigest().upper(),
                    "ifc_type": authority[global_id].is_a(),
                }
            )
    return {
        "checked_product_count": len(shared),
        "missing_non_target_count": len(missing),
        "unexpected_non_target_count": len(unexpected),
        "changed_non_target_count": len(changed),
        "difference_count": len(missing) + len(unexpected) + len(changed),
        "changed_type_counts": dict(Counter(item["ifc_type"] for item in changed)),
        "changed": changed,
        "missing_global_id_hashes": [hashlib.sha256(value.encode("utf-8")).hexdigest().upper() for value in missing],
        "unexpected_global_id_hashes": [hashlib.sha256(value.encode("utf-8")).hexdigest().upper() for value in unexpected],
        "geometry_error_count": len(geometry_errors),
        "geometry_errors": geometry_errors,
        "geometry_fallback_verified_count": geometry_fallback_count,
    }


def _mesh_area_volume(product: Any, settings: Any) -> tuple[float, float]:
    shape = ifcopenshell.geom.create_shape(settings, product)
    raw = [float(value) for value in shape.geometry.verts]
    vertices = [(raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3)]
    faces = [int(value) for value in shape.geometry.faces]
    area = 0.0
    signed_volume = 0.0
    for index in range(0, len(faces), 3):
        a, b, c = (vertices[faces[index + offset]] for offset in range(3))
        ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        cross = (
            ab[1] * ac[2] - ab[2] * ac[1],
            ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        area += 0.5 * math.sqrt(sum(value * value for value in cross))
        signed_volume += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    return area, abs(signed_volume)


def _target_metrics(standalone_model: Any, candidate_model: Any, generated_child_ids: list[str]) -> dict[str, Any]:
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    standalone_children = [
        *standalone_model.by_type("IfcStairFlight"),
        *[slab for slab in standalone_model.by_type("IfcSlab") if slab.PredefinedType == "LANDING"],
    ]
    candidate_children = [candidate_model.by_guid(global_id) for global_id in generated_child_ids]
    standalone_values = [_mesh_area_volume(product, settings) for product in standalone_children]
    candidate_values = [_mesh_area_volume(product, settings) for product in candidate_children]
    source_area = sum(value[0] for value in standalone_values)
    source_volume = sum(value[1] for value in standalone_values)
    candidate_area = sum(value[0] for value in candidate_values)
    candidate_volume = sum(value[1] for value in candidate_values)
    return {
        "standalone_surface_area_m2": source_area,
        "candidate_surface_area_m2": candidate_area,
        "surface_area_delta_m2": abs(candidate_area - source_area),
        "standalone_volume_m3": source_volume,
        "candidate_volume_m3": candidate_volume,
        "volume_delta_m3": abs(candidate_volume - source_volume),
        "positive_area_and_volume": min(source_area, candidate_area, source_volume, candidate_volume) > 0,
        "area_volume_preserved": abs(candidate_area - source_area) <= 1e-6 and abs(candidate_volume - source_volume) <= 1e-6,
    }


def run_regression_gate(
    *,
    source_item_path: str | Path,
    work_package_path: str | Path,
    modeling_manifest_path: str | Path,
    external_capability_root: str | Path,
    workspace_root: str | Path,
) -> dict[str, Any]:
    source_item = _read(source_item_path)
    work_package = _read(work_package_path)
    modeling_manifest = _read(modeling_manifest_path)
    workspace = Path(workspace_root).resolve()
    external_root = Path(external_capability_root).resolve()
    gate_path = (workspace / work_package["output_paths"]["regression_gate"]).resolve()
    if not gate_path.is_relative_to((workspace / "work").resolve()):
        raise ContractError("regression output must remain inside isolated WORK")
    if gate_path.exists():
        raise FileExistsError(f"refusing to overwrite regression GateResult: {gate_path}")

    authority_path = Path(source_item["authority_baseline"]["authority_file_path"])
    candidate_path = Path(modeling_manifest["candidate"]["path"])
    standalone_path = Path(modeling_manifest["standalone"]["ifc_path"])
    integration_manifest_path = workspace / work_package["output_paths"]["integration_manifest"]
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str, severity: str = "B1") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity_if_failed": severity, "detail": detail})

    authority_before = sha256_file(authority_path)
    candidate_before = sha256_file(candidate_path)
    check("authority_baseline", authority_before == work_package["authority_baseline"]["sha256"], "Live authority SHA matches the complete work package.", "B0")
    check("work_package_binding", sha256_file(work_package_path) == modeling_manifest["work_package_sha256"], "Modeling manifest is bound to this exact work package.", "B0")
    check("candidate_hash_lock", candidate_before == modeling_manifest["candidate"]["sha256"] and modeling_manifest["candidate"]["hash_locked"] is True, "Candidate bytes match the locked modeling hash.", "B0")
    check("modeler_no_self_approval", modeling_manifest.get("self_review_allowed") is False and modeling_manifest.get("self_promotion_allowed") is False, "Modeler manifest forbids self-review and self-promotion.", "B0")

    authority_model = ifcopenshell.open(str(authority_path))
    candidate_model = ifcopenshell.open(str(candidate_path))
    standalone_model = ifcopenshell.open(str(standalone_path))
    authority_products = _products_by_guid(authority_model)
    candidate_products = _products_by_guid(candidate_model)
    removed_ids = set(work_package["allowed_global_ids"])
    generated_ids = set(modeling_manifest["candidate"]["generated_global_ids"])
    actual_removed = set(authority_products) - set(candidate_products)
    actual_added = set(candidate_products) - set(authority_products)
    expected_counts = work_package["expected_product_count_changes"]
    check("target_deletions", actual_removed == removed_ids and len(actual_removed) == expected_counts["deleted"], "Only work-package-authorized target GlobalIds were removed.")
    check("target_additions", actual_added == generated_ids and len(actual_added) == expected_counts["added"], "Only locked candidate target GlobalIds were added.")
    check("product_count_change", len(candidate_products) - len(authority_products) == expected_counts["net"], "IFC product-count change matches the work package.")

    non_target = _non_target_diff(authority_model, candidate_model, removed_ids, generated_ids)
    check("non_target_difference_zero", non_target["difference_count"] == 0, f"Compared {non_target['checked_product_count']} non-target products; difference count is {non_target['difference_count']}.", "B0")
    check(
        "non_target_geometry_verified",
        non_target["geometry_error_count"] == 0,
        f"Non-target geometry fingerprint errors: {non_target['geometry_error_count']}; exact IFC representation fallbacks verified: {non_target['geometry_fallback_verified_count']}.",
    )

    generated_child_ids = modeling_manifest["candidate"]["generated_global_ids"][1:]
    target_metrics = _target_metrics(standalone_model, candidate_model, generated_child_ids)
    check("target_area_volume_positive", target_metrics["positive_area_and_volume"], "Generated target surface area and volume are positive.")
    check("target_area_volume_preserved", target_metrics["area_volume_preserved"], "Placement and mirroring preserve target surface area and volume.")
    check("standalone_audit", modeling_manifest["standalone"]["audit_status"] == "AUDIT PASSED" and modeling_manifest["standalone"]["audit_summary"] == {"checks_passed": 34, "checks_total": 34}, "External semantic and geometry audit is 34/34.")

    integration_manifest = _read(integration_manifest_path)
    try:
        sys.path.insert(0, str(external_root))
        integration = importlib.import_module("review.bim_integration")
        with tempfile.TemporaryDirectory(prefix="regression-audit-", dir=gate_path.parent) as temporary:
            external_audit = integration.audit_integrated_bim(
                candidate_path,
                _integration_config(work_package),
                integration_manifest,
                Path(temporary) / "external-integration-audit.json",
            )
        check("context_geometry_and_interfaces", external_audit.get("status") == "BIM_INTEGRATION_AUDIT_PASSED" and external_audit.get("summary") == {"checks_passed": 13, "checks_total": 13}, "Bounds, coordinates, storey, opening, interface and exact clash audit is 13/13.")
    except Exception as exc:
        external_audit = {"status": "ERROR", "error_type": type(exc).__name__}
        check("context_geometry_and_interfaces", False, f"External integration audit failed with {type(exc).__name__}.")
    finally:
        if sys.path and sys.path[0] == str(external_root):
            sys.path.pop(0)

    authority_after = sha256_file(authority_path)
    candidate_after = sha256_file(candidate_path)
    check("authority_source_unchanged", authority_before == authority_after, "Regression opened the authority source read-only.", "B0")
    check("candidate_source_unchanged", candidate_before == candidate_after, "Regression reviewer did not modify the candidate.", "B0")

    passed = all(item["passed"] for item in checks)
    findings = [item for item in checks if not item["passed"]]
    gate = {
        "schema_version": "1.0",
        "gate": "REGRESSION",
        "status": "PASS" if passed else "FAIL",
        "package_id": work_package["package_id"],
        "decision_id": work_package["decision_id"],
        "authority": {"sha256_before": authority_before, "sha256_after": authority_after, "unchanged": authority_before == authority_after},
        "candidate": {"sha256_before": candidate_before, "sha256_after": candidate_after, "unchanged": candidate_before == candidate_after},
        "checks": checks,
        "summary": {"checks_passed": sum(item["passed"] for item in checks), "checks_total": len(checks)},
        "non_target": non_target,
        "target_metrics": target_metrics,
        "external_integration_audit": {
            "status": external_audit.get("status"),
            "summary": external_audit.get("summary"),
            "clash_count": len(external_audit.get("clash_scan", {}).get("collisions", [])) + len(external_audit.get("clash_scan", {}).get("intersections", [])),
        },
        "findings": findings,
        "review_policy": "READ_ONLY",
    }
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gate
