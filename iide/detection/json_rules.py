"""Deterministic JSON-rule detection engine.

This is a Sigma-compatible *prototype* (spec section 3), not a Sigma implementation.
A rule groups events by one field and fires when, for at least one group, every
`all_of` clause is satisfied: the group has at least `min_count` events of the clause's
`event_type` whose fields satisfy the clause's optional `where` conditions.

`where` maps a field name to exactly one condition, `{"eq": v}` or `{"gte": n}`. The
field is looked up at the event's top level first, then in `attributes`. `eq` requires
the same JSON type (`true` never equals `1`); `gte` accepts only real numbers. A
missing field never matches. Rules never inspect `event_id` or timestamps, so results
cannot depend on random identifiers (spec 4.1).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from iide.detection.interface import RuleResult
from iide.hashing import canonical_json_hash

_MISSING = object()


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    eq: StrictStr | StrictBool | StrictInt | StrictFloat | None = None
    gte: StrictInt | StrictFloat | None = None

    @model_validator(mode="after")
    def _exactly_one_operator(self) -> Condition:
        provided = self.model_fields_set & {"eq", "gte"}
        if len(provided) != 1:
            raise ValueError("a condition needs exactly one of 'eq' or 'gte'")
        if getattr(self, next(iter(provided))) is None:
            raise ValueError("condition value must not be null")
        return self

    def matches(self, value: Any) -> bool:
        if value is _MISSING:
            return False
        if "eq" in self.model_fields_set:
            return type(value) is type(self.eq) and value == self.eq
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and self.gte is not None
            and value >= self.gte
        )


class Clause(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    min_count: int = Field(ge=1)
    where: dict[str, Condition] = {}

    @model_validator(mode="after")
    def _where_field_names(self) -> Clause:
        for name in self.where:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError(f"invalid where field name {name!r}")
        return self


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


def _lookup(event: Mapping[str, Any], field: str) -> Any:
    if field in event:
        return event[field]
    attributes = event.get("attributes")
    if isinstance(attributes, Mapping) and field in attributes:
        return attributes[field]
    return _MISSING


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
        clauses = spec.all_of
        groups: dict[str, list[int]] = {}
        for event in events:
            key = event.get(spec.group_by)
            event_type = event.get("event_type")
            if not isinstance(key, str) or not isinstance(event_type, str):
                continue
            for i, clause in enumerate(clauses):
                if clause.event_type != event_type:
                    continue
                if all(c.matches(_lookup(event, f)) for f, c in clause.where.items()):
                    groups.setdefault(key, [0] * len(clauses))[i] += 1
        fired = any(
            all(counts[i] >= c.min_count for i, c in enumerate(clauses))
            for counts in groups.values()
        )
        if not fired:
            return RuleResult(rule.rule_id, False, ())
        return RuleResult(rule.rule_id, True, tuple(sorted({c.event_type for c in clauses})))
