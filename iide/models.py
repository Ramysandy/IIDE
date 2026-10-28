"""Typed records for Phase 1 artifacts: attack definitions, replay records, baseline coverage.

Every record carries `schema_version` (spec section 4). Run records, instruction
records and the manifest arrive in later phases.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from iide.config import ReplayConfig

# Why a replay was not valid. Never interpreted as "alert silent" (spec 0.5, 6.2).
ReplayErrorCategory = Literal["TIMEOUT", "INFRA_ERROR"]
AttackStatus = Literal["DETECTED", "NOT_DETECTED", "UNKNOWN"]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AttackDefinition(_Record):
    """Spec 4.3."""

    schema_version: Literal["1.0"]
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    technique_id: str
    technique_mapping_status: Literal["UNVERIFIED", "VERIFIED"]
    attack_framework_version: str | None
    criticality: Literal[1, 2, 3]
    description: str
    required_event_types: list[str] = Field(min_length=1)
    expected_rule_ids: list[str] = Field(min_length=1)
    replay_count: int = Field(ge=1)
    emulation: str = Field(min_length=1)


def load_attack_definition(path: Path) -> AttackDefinition:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AttackDefinition.model_validate(data)


class RuleOutcomeRecord(_Record):
    rule_id: str
    fired: bool
    matched_event_types: list[str]


class ReplayRecord(_Record):
    """One replay of one attack against one program version (spec 6.2)."""

    schema_version: Literal["1.0"] = "1.0"
    replay_id: str
    testbed_id: str
    attack_id: str
    program_ref: str
    replay_index: int = Field(ge=1)
    correlation_id: str
    started_at: str
    elapsed_seconds: float = Field(ge=0.0)
    valid: bool
    error_category: ReplayErrorCategory | None = None
    error_detail: str | None = None
    # Spec 8.2: raw count, distinct types, firing rules and redundancy are separate fields.
    raw_event_count: int = Field(ge=0, default=0)
    distinct_event_type_count: int = Field(ge=0, default=0)
    malformed_line_count: int = Field(ge=0, default=0)
    schema_invalid_event_count: int = Field(ge=0, default=0)
    rule_outcomes: list[RuleOutcomeRecord] = []
    firing_rule_count: int = Field(ge=0, default=0)
    redundancy_event_types: list[str] = []
    redundancy_event_type_count: int = Field(ge=0, default=0)
    # None when the replay was invalid: an invalid replay is neither fired nor silent.
    attack_alert_fired: bool | None = None


class AttackBaseline(_Record):
    attack_id: str
    criticality: Literal[1, 2, 3]
    expected_rule_ids: list[str]
    planned_k: int
    valid_replays: int
    fired_count: int
    min_valid_required: int
    status: AttackStatus
    d: Literal[0, 1] | None
    invalid_replay_rate: float
    outcome_disagreement_rate: float | None
    flake_rate: float
    flake_limit: float
    flake_within_limit: bool


class FunctionalTestResult(_Record):
    command: list[str]
    working_directory: str
    passed: bool
    exit_code: int
    summary_line: str


class BaselineCoverage(_Record):
    """`baseline_coverage.json` (spec 6.1 step 7)."""

    schema_version: Literal["1.0"] = "1.0"
    experiment_version: str
    testbed_id: str
    generated_at: str
    # This project is not a git repository yet, so no commit exists to record (spec 4.5).
    git_commit: str | None
    git_commit_note: str
    frozen_hashes: dict[str, str]
    replay_config: ReplayConfig
    environment: dict[str, Any]
    isolation: dict[str, Any]
    functional_tests: FunctionalTestResult
    attacks: list[AttackBaseline]
    baseline_detected_attack_ids: list[str]  # A0 (spec 7.1)
    phase1_exit_criterion_met: bool
    exit_criterion_notes: list[str]
