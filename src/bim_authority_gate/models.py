"""Shared constants and validation helpers for machine-readable contracts."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath


class ReadinessStatus(StrEnum):
    READY_TO_MODEL = "READY_TO_MODEL"
    CROSSCHECK_REQUIRED = "CROSSCHECK_REQUIRED"
    HUMAN_CLARIFICATION_REQUIRED = "HUMAN_CLARIFICATION_REQUIRED"
    COORDINATION_REQUIRED = "COORDINATION_REQUIRED"
    BLOCKED = "BLOCKED"


ROLE_NAMES = (
    "research",
    "reasoning",
    "modeling",
    "review",
    "authority_promotion",
)


class ContractError(ValueError):
    """Raised when a machine-readable input or output contract is malformed."""


def require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    return value


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a non-empty string")
    return value.strip()


def validate_work_output_paths(paths: object) -> list[str]:
    """Return validation errors for paths that escape the isolated WORK root."""

    if not isinstance(paths, dict) or not paths:
        return ["modeling_scope.output_paths"]
    errors: list[str] = []
    for label, value in paths.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"modeling_scope.output_paths.{label}")
            continue
        normalized = value.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0].lower() != "work":
            errors.append(f"modeling_scope.output_paths.{label}")
    return errors
