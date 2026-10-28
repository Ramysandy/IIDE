"""Deterministic JSON-rule detection engine.

This is a Sigma-compatible *prototype* (spec section 3), not a Sigma implementation.
A rule groups events by one field and fires when, for at least one group, every
`all_of` clause is satisfied (the group has at least `min_count` events of the
clause's `event_type`). Rules never inspect `event_id` or timestamps, so results
cannot depend on random identifiers (spec 4.1).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from iide.detection.interface import RuleResult
from iide.hashing import canonical_json_hash


class Clause(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    min_count: int = Field(ge=1)


class DetectionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_by: Literal["target_id", "actor_id", "correlation_id"]
    all_of: list[Clause] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_clause_types(self) -> DetectionSpec:
        types = [c.event_type for c in self.all_of]
        if len(types) != len(set(types)):
            raise ValueError("all_of clauses must use distinct event types")
        return self


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(pattern=r"^IIDE-[A-Z]+-[0-9]{3}$")
    title: str
    rule_version: str
    criticality: Literal[1, 2, 3]
    mapped_attack_ids: list[str] = Field(min_length=1)
    required_event_types: list[str] = Field(min_length=1)
    detection: DetectionSpec

    @model_validator(mode="after")
    def _required_types_match_clauses(self) -> Rule:
        if set(self.required_event_types) != {c.event_type for c in self.detection.all_of}:
            raise ValueError(
                f"{self.rule_id}: required_event_types must equal the event types "
                "used by detection.all_of"
            )
        return self


class RulePack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    format: Literal["iide-json-rules-v1"]
    description: str
    rule_pack_id: str
    rule_pack_version: str
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> RulePack:
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule_id in rule pack")
        return self


class JsonRuleDetector:
    def __init__(self, pack: RulePack) -> None:
        self.pack = pack

    @classmethod
    def from_file(cls, path: Path) -> JsonRuleDetector:
        return cls(RulePack.model_validate(json.loads(Path(path).read_text(encoding="utf-8"))))

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(r.rule_id for r in self.pack.rules)

    def rule(self, rule_id: str) -> Rule:
        for r in self.pack.rules:
            if r.rule_id == rule_id:
                return r
        raise KeyError(rule_id)

    def rule_hash(self, rule_id: str) -> str:
        return canonical_json_hash(self.rule(rule_id).model_dump(mode="json"))

    def evaluate(self, events: Sequence[Mapping[str, Any]]) -> list[RuleResult]:
        return [self._evaluate_rule(rule, events) for rule in self.pack.rules]

    @staticmethod
    def _evaluate_rule(rule: Rule, events: Sequence[Mapping[str, Any]]) -> RuleResult:
        spec = rule.detection
        groups: dict[str, Counter[str]] = defaultdict(Counter)
        for event in events:
            key = event.get(spec.group_by)
            event_type = event.get("event_type")
            if isinstance(key, str) and isinstance(event_type, str):
                groups[key][event_type] += 1
        fired = any(
            all(counts[c.event_type] >= c.min_count for c in spec.all_of)
            for counts in groups.values()
        )
        if not fired:
            return RuleResult(rule.rule_id, False, ())
        return RuleResult(rule.rule_id, True, tuple(sorted({c.event_type for c in spec.all_of})))
