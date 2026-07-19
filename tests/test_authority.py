from __future__ import annotations

import ifcopenshell

from bim_authority_gate.authority import capture_ifc_baseline, verify_ifc_baseline


def _write_minimal_ifc(path) -> None:
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Contract test")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    model.create_entity(
        "IfcBuildingStorey",
        GlobalId=ifcopenshell.guid.new(),
        Name="1F",
        CompositionType="ELEMENT",
        Elevation=0.0,
    )
    model.write(str(path))


def test_capture_and_verify_authority_are_read_only(tmp_path) -> None:
    authority = tmp_path / "authority.ifc"
    _write_minimal_ifc(authority)
    original = authority.read_bytes()
    baseline = capture_ifc_baseline(authority, "REV-001", coordinate_origin=[0, 0, 0])
    verification = verify_ifc_baseline(authority, baseline)
    assert verification["matches"] is True
    assert verification["b0"] is False
    assert baseline["ifc_product_count"] == 1
    assert baseline["global_id_count"] == 1
    assert baseline["storeys"][0]["name"] == "1F"
    assert authority.read_bytes() == original


def test_verify_detects_authority_change(tmp_path) -> None:
    authority = tmp_path / "authority.ifc"
    _write_minimal_ifc(authority)
    baseline = capture_ifc_baseline(authority, "REV-001", coordinate_origin=[0, 0, 0])
    model = ifcopenshell.open(str(authority))
    model.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="2F", Elevation=3.0)
    model.write(str(authority))
    verification = verify_ifc_baseline(authority, baseline)
    assert verification["matches"] is False
    assert verification["b0"] is True
    assert {item["field"] for item in verification["differences"]} >= {"sha256", "ifc_product_count", "global_id_fingerprint"}
