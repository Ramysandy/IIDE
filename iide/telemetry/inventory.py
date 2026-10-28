"""Event catalog and security-bearing event inventory (spec 4.2)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    owning_module: str = Field(min_length=1)
    security_bearing: bool
    # D-10: why the label holds. rule_dependency: a frozen rule consumes the event.
    # audit_category: audit evidence of auth failure, permission/sharing change, bulk export,
    # denied access, rate-limit, webhook or configuration change. none: neither.
    security_basis: Literal["rule_dependency", "audit_category", "none"]
    required_fields: list[str]
    required_by_attacks: list[str]
    required_by_rules: list[str]
    benign_absence_expected: bool
    criticality_rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _basis_is_consistent(self) -> CatalogEntry:
        if self.required_by_rules and self.security_basis != "rule_dependency":
            raise ValueError(
                f"{self.event_type}: consumed by rules, so basis must be rule_dependency"
            )
        if self.security_bearing != (self.security_basis != "none"):
            raise ValueError(f"{self.event_type}: security_bearing disagrees with security_basis")
        return self


def load_event_catalog(path: Path) -> dict[str, CatalogEntry]:
    with Path(path).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a YAML list of event entries")
    catalog: dict[str, CatalogEntry] = {}
    for item in raw:
        entry = CatalogEntry.model_validate(item)
        if entry.event_type in catalog:
            raise ValueError(f"{path}: duplicate event_type {entry.event_type!r}")
        catalog[entry.event_type] = entry
    return catalog


def security_bearing_event_types(catalog: Mapping[str, CatalogEntry]) -> frozenset[str]:
    return frozenset(t for t, e in catalog.items() if e.security_bearing)


def contract_violations(event: Mapping[str, Any], catalog: Mapping[str, CatalogEntry]) -> list[str]:
    """Check an event against its catalog entry's `required_fields`.

    A required field may live at the top level or inside `attributes`; a field set
    to None counts as missing.
    """
    event_type = event.get("event_type")
    entry = catalog.get(event_type) if isinstance(event_type, str) else None
    if entry is None:
        return [f"event_type {event_type!r} is not in the event catalog"]
    attributes = event.get("attributes")
    attributes = attributes if isinstance(attributes, Mapping) else {}
    problems = []
    for field in entry.required_fields:
        value = event.get(field, attributes.get(field))
        if value is None:
            problems.append(f"{event_type}: missing required field {field!r}")
    return problems


def observed_event_inventory(events: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Raw event count per event_type, sorted by event_type."""
    counts = Counter(e["event_type"] for e in events if isinstance(e.get("event_type"), str))
    return dict(sorted(counts.items()))
