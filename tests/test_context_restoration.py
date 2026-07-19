from __future__ import annotations

import ifcopenshell

from bim_authority_gate.authority import sha256_file
from bim_authority_gate.modeling import restore_authority_representation_contexts


def _context_ifc(path, y: float) -> None:
    model = ifcopenshell.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), Name="Context fixture")
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    point = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, y, 0.0))
    axis = model.create_entity("IfcAxis2Placement3D", Location=point)
    model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1.0e-5,
        WorldCoordinateSystem=axis,
    )
    model.write(str(path))


def test_candidate_context_is_restored_without_touching_authority(tmp_path) -> None:
    authority = tmp_path / "authority.ifc"
    candidate = tmp_path / "candidate.ifc"
    _context_ifc(authority, 0.0)
    _context_ifc(candidate, 2400.0)
    authority_sha = sha256_file(authority)
    result = restore_authority_representation_contexts(authority, candidate)
    assert result["restored_context_count"] == 1
    assert sha256_file(authority) == authority_sha
    reopened = ifcopenshell.open(str(candidate))
    context = reopened.by_type("IfcGeometricRepresentationContext")[0]
    assert context.WorldCoordinateSystem.Location.Coordinates == (0.0, 0.0, 0.0)

