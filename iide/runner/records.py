"""Run record and ledger (spec 4.5, 12). Every run, including failures, gets a record."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from iide.scoring.coverage import CoverageScores
from iide.scoring.types import MetricResult

RunStatus = Literal[
    "SCORED",
    "BUILD_ERROR",
    "TEST_FAIL",
    "NO_OP",
    "API_ERROR",
    "TIMEOUT",
    "INFRA_ERROR",
    "UNKNOWN",
]
TERMINAL_STATUSES = frozenset(RunStatus.__args__)  # type: ignore[attr-defined]

Classification = Literal["EROSION", "LATENT_EROSION", "NONE", "UNKNOWN", "NOT_SCORED"]


class _Rec(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FunctionalSummary(_Rec):
    passed: bool | None
    failed_count: int | None
    summary_line: str | None = None
    note: str = "frozen original tests run against the candidate app/ directory"


class BuildSummary(_Rec):
    passed: bool | None
    detail: str = ""


class ReplaySummary(_Rec):
    k: int
    successful_replays: int  # valid replays summed over all attacks
    planned_replays: int
    schema_invalid_event_count: int = 0
    malformed_line_count: int = 0


class AttackRunResult(_Rec):
    attack_id: str
    criticality: Literal[1, 2, 3]
    baseline_detected: bool | None  # d(a, P0)
    candidate_detected: bool | None  # d(a, P1); None = UNKNOWN
    candidate_status: str
    fired_count: int
    valid_replays: int
    planned_k: int
    r0: int
    r1: int
    rules0: int | None
    rules1: int | None
    unexpected_fired_rule_ids: list[str] = []
    # A miss must reproduce in a second fresh batch (spec 6.3).
    confirmation_status: str | None = None
    miss_confirmed: bool | None = None


class ErosionAssessment(_Rec):
    """Strict-mode assessment. Semantic mode (FORMAT_DRIFT, benign noise) needs human review."""

    eligible: bool
    ineligible_reasons: list[str]
    classification: Classification
    confirmed_erosion_attack_ids: list[str]
    unconfirmed_miss_attack_ids: list[str]
    latent_erosion_attack_ids: list[str]
    y: Literal[0, 1] | None  # 1 = at least one confirmed erosion; None = not eligible
    needs_semantic_review: bool = False


class AgentSummary(_Rec):
    final_summary: str | None = None
    exit_code: int | None = None
    tool_version: str | None = None
    elapsed_seconds: float | None = None
    error_category: str | None = None
    model_id: str | None = None
    seed_requested: int
    seed_honored: bool | None = None
    generation_params: dict[str, Any] = {}
    stdout_path: str | None = None
    stderr_path: str | None = None


class DiffInfo(_Rec):
    path: str | None = None
    sha256: str | None = None
    changed_files: list[str]
    patch_empty: bool | None = None
    tests_modified: bool | None = None
    outside_app_changed: list[str] = []


class IsolationInfo(_Rec):
    container: bool = False
    process_level: bool = True
    oracle_material_in_workspace: bool | None = None
    exceptions: list[str] = [
        "process-level isolation only: agent runs as the same OS user",
        "outbound network is not blocked",
    ]


class RunRecord(_Rec):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    attempt: int = 1
    attempt_id: str
    status: RunStatus
    failure_reason: str | None = None
    # Development-adapter runs test the pipeline; they are never pilot results.
    dev_adapter: bool
    gate_overrides: list[str] = []
    testbed_id: str
    testbed_commit: str | None
    baseline_commit: str | None
    experiment_version: str
    instruction_id: str
    family: str
    variant: str
    prompt_sha256: str
    agent_id: str
    agent_version: str
    seed: int
    started_at: str
    finished_at: str
    functional_tests: FunctionalSummary
    build: BuildSummary
    replay: ReplaySummary | None = None
    attack_results: list[AttackRunResult] = []
    scores: CoverageScores | None = None
    nrg: MetricResult | None = None
    benign_volume_baseline: int | None = None
    benign_volume_candidate: int | None = None
    erosion: ErosionAssessment
    agent: AgentSummary
    diff: DiffInfo
    isolation: IsolationInfo = IsolationInfo()
    frozen_hash_check: dict[str, Any] = {}


# ---------------------------------------------------------------- ledger on disk


def attempt_dir(raw_dir: Path, run_id: str, attempt: int) -> Path:
    return raw_dir / run_id / f"attempt-{attempt}"


def list_attempts(raw_dir: Path, run_id: str) -> list[RunRecord]:
    records = []
    base = raw_dir / run_id
    for d in sorted(base.glob("attempt-*")) if base.is_dir() else []:
        path = d / "run_record.json"
        if path.is_file():
            records.append(RunRecord.model_validate_json(path.read_text(encoding="utf-8")))
    return sorted(records, key=lambda r: r.attempt)


def next_attempt_number(raw_dir: Path, run_id: str) -> int:
    base = raw_dir / run_id
    nums = [int(d.name.split("-")[1]) for d in base.glob("attempt-*")] if base.is_dir() else []
    return max(nums, default=0) + 1


def write_record(record: RunRecord, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "run_record.json"
    path.write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return path


def select_primary(attempts: list[RunRecord]) -> RunRecord | None:
    """Pre-registered retry policy (D-33): the first attempt is primary unless every earlier
    attempt ended in INFRA_ERROR (a failure not attributable to the agent), in which case the
    first later attempt is. All attempts are retained."""
    for record in sorted(attempts, key=lambda r: r.attempt):
        if record.status != "INFRA_ERROR":
            return record
    return None if not attempts else sorted(attempts, key=lambda r: r.attempt)[-1]
