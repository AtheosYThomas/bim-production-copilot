"""Read-only authority IFC fingerprint capture and verification."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import ifcopenshell

from .models import ContractError


def sha256_file(path: str | Path) -> str:
    source = Path(path).resolve()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _unit_record(unit: Any) -> dict[str, Any]:
    record: dict[str, Any] = {"unit_type": getattr(unit, "UnitType", None)}
    if unit.is_a("IfcSIUnit"):
        record.update(
            {
                "kind": "SI",
                "name": str(getattr(unit, "Name", "")),
                "prefix": str(getattr(unit, "Prefix", "") or ""),
            }
        )
    else:
        record.update({"kind": unit.is_a(), "name": str(getattr(unit, "Name", ""))})
    return record


def capture_ifc_baseline(
    authority_path: str | Path,
    rev: str,
    *,
    coordinate_origin: list[float],
    hold_states: list[dict] | None = None,
    rfi_states: list[dict] | None = None,
) -> dict[str, Any]:
    """Open an authority IFC read-only and return its registered baseline."""

    path = Path(authority_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if len(coordinate_origin) != 3 or not all(
        isinstance(value, (int, float)) for value in coordinate_origin
    ):
        raise ContractError("coordinate_origin must contain three numbers")

    before_sha = sha256_file(path)
    model = ifcopenshell.open(str(path))
    products = model.by_type("IfcProduct")
    global_ids = sorted(
        str(product.GlobalId)
        for product in products
        if getattr(product, "GlobalId", None)
    )
    global_id_fingerprint = hashlib.sha256(
        "\n".join(global_ids).encode("utf-8")
    ).hexdigest().upper()
    assignments = model.by_type("IfcUnitAssignment")
    units = [_unit_record(unit) for unit in assignments[0].Units] if assignments else []
    storeys = [
        {
            "global_id": str(storey.GlobalId),
            "name": str(storey.Name or ""),
            "elevation": float(storey.Elevation) if storey.Elevation is not None else None,
        }
        for storey in model.by_type("IfcBuildingStorey")
    ]
    after_sha = sha256_file(path)
    if before_sha != after_sha:
        raise RuntimeError("authority IFC changed while its read-only baseline was captured")

    return {
        "schema_version": "1.0",
        "authority_file_path": str(path),
        "rev": rev,
        "sha256": before_sha,
        "ifc_product_count": len(products),
        "global_id_count": len(global_ids),
        "global_id_fingerprint": global_id_fingerprint,
        "project_units": units,
        "coordinate_origin": [float(value) for value in coordinate_origin],
        "storeys": storeys,
        "hold_states": hold_states or [],
        "rfi_states": rfi_states or [],
        "capture_policy": "READ_ONLY",
    }


def verify_ifc_baseline(authority_path: str | Path, registered: dict) -> dict[str, Any]:
    """Recapture the IFC and compare all authority identity fields."""

    observed = capture_ifc_baseline(
        authority_path,
        str(registered.get("rev", "")),
        coordinate_origin=list(registered.get("coordinate_origin", [])),
        hold_states=list(registered.get("hold_states", [])),
        rfi_states=list(registered.get("rfi_states", [])),
    )
    fields = (
        "sha256",
        "ifc_product_count",
        "global_id_count",
        "global_id_fingerprint",
        "project_units",
        "coordinate_origin",
        "storeys",
    )
    differences = [
        {"field": field, "registered": registered.get(field), "observed": observed.get(field)}
        for field in fields
        if registered.get(field) != observed.get(field)
    ]
    return {
        "matches": not differences,
        "b0": bool(differences),
        "differences": differences,
        "observed": observed,
    }

