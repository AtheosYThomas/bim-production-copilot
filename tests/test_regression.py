from __future__ import annotations

import ifcopenshell

from bim_authority_gate.regression import _non_target_diff


def _model(path, *, changed_name: bool = False):
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Regression fixture")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    model.create_entity(
        "IfcBuildingStorey",
        GlobalId="0YvctVUKn4YQZk0GfN8V9A",
        Name="Changed" if changed_name else "1F",
        Elevation=0.0,
    )
    model.write(str(path))
    return ifcopenshell.open(str(path))


def test_non_target_diff_detects_semantic_change(tmp_path) -> None:
    authority = _model(tmp_path / "authority.ifc")
    identical = _model(tmp_path / "identical.ifc")
    changed = _model(tmp_path / "changed.ifc", changed_name=True)
    assert _non_target_diff(authority, identical, set(), set())["difference_count"] == 0
    result = _non_target_diff(authority, changed, set(), set())
    assert result["difference_count"] == 1
    assert result["changed_type_counts"] == {"IfcBuildingStorey": 1}

