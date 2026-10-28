"""Detector interface and the attack -> rule -> event-type mapping (spec 4.4)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class RuleResult:
    """Outcome of one rule over one replay's event stream.

    `matched_event_types` is the set of distinct semantic event types that
    participated in the rule firing (empty when the rule is silent). It is the raw
    material for the redundancy r(a, P) of spec 7.3 / 8.2.
    """

    rule_id: str
    fired: bool
    matched_event_types: tuple[str, ...] = ()


class Detector(Protocol):
    @property
    def rule_ids(self) -> tuple[str, ...]: ...

    def evaluate(self, events: Sequence[Mapping[str, Any]]) -> list[RuleResult]:
        """Evaluate every rule over normalized, schema-valid events."""
        ...


class MappedAttack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_rule_ids: list[str] = Field(min_length=1)
    required_event_types: list[str] = Field(min_length=1)


class AttackMapping(BaseModel):
    """`attack_id -> expected_rule_ids -> required_event_types` (spec 4.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    mapping_version: str
    testbed_id: str
    attacks: dict[str, MappedAttack]


def load_attack_mapping(path: Path) -> AttackMapping:
    return AttackMapping.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
