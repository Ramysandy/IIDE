"""Validation of canonical telemetry events against the versioned JSON Schema."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from iide.config import DEFAULT_TELEMETRY_SCHEMA


class TelemetryValidationError(ValueError):
    pass


@lru_cache(maxsize=4)
def _validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_event(
    event: Mapping[str, Any], schema_path: Path = DEFAULT_TELEMETRY_SCHEMA
) -> list[str]:
    """Return human-readable schema violations (empty list means valid)."""
    if not isinstance(event, Mapping):
        return [f"event must be an object, got {type(event).__name__}"]
    errors = sorted(
        _validator(Path(schema_path)).iter_errors(dict(event)),
        key=lambda e: (list(map(str, e.absolute_path)), e.message),
    )
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]


def require_valid_event(
    event: Mapping[str, Any], schema_path: Path = DEFAULT_TELEMETRY_SCHEMA
) -> None:
    errors = validate_event(event, schema_path)
    if errors:
        raise TelemetryValidationError("; ".join(errors))
