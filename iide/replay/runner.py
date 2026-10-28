"""Testbed loading, fresh-instance replay, and attack-level summarisation (spec 6.2)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from iide.config import DEFAULT_TELEMETRY_SCHEMA, REPO_ROOT, ReplayConfig
from iide.detection.interface import AttackMapping, load_attack_mapping
from iide.detection.json_rules import JsonRuleDetector
from iide.hashing import hash_patterns, sha256_bytes, sha256_file
from iide.ids import replay_correlation_id, replay_id
from iide.models import (
    AttackBaseline,
    AttackDefinition,
    FunctionalTestResult,
    ReplayRecord,
    RuleOutcomeRecord,
    load_attack_definition,
)
from iide.replay.reliability import (
    attack_detected,
    flake_rate,
    flake_within_limit,
    invalid_replay_rate,
    min_valid_replays,
    outcome_disagreement_rate,
)
from iide.replay.sandbox import run_in_fresh_process
from iide.telemetry.inventory import CatalogEntry, load_event_catalog
from iide.telemetry.normalize import normalize_events
from iide.telemetry.schema import validate_event


class TestbedContractError(ValueError):
    """The testbed's catalog, attacks, rules and mapping are inconsistent."""

    __test__ = False  # not a pytest test class


@dataclass(frozen=True)
class Testbed:
    __test__ = False  # not a pytest test class

    testbed_id: str
    root: Path
    schema_path: Path
    catalog: dict[str, CatalogEntry]
    attacks: dict[str, AttackDefinition]
    detector: JsonRuleDetector
    mapping: AttackMapping

    def emulation_path(self, attack: AttackDefinition) -> Path:
        return self.root / "attacks" / attack.emulation


def load_testbed(root: Path, *, schema_path: Path = DEFAULT_TELEMETRY_SCHEMA) -> Testbed:
    """Load every frozen artifact of a testbed and cross-validate them."""
    root = Path(root).resolve()
    mapping = load_attack_mapping(root / "detection" / "mapping.json")
    pack_files = sorted((root / "detection" / "rules").glob("*.json"))
    if len(pack_files) != 1:
        raise TestbedContractError(
            f"expected exactly one rule pack in {root / 'detection' / 'rules'}, "
            f"found {len(pack_files)}"
        )
    detector = JsonRuleDetector.from_file(pack_files[0])
    catalog = load_event_catalog(root / "event_catalog.yaml")
    attacks: dict[str, AttackDefinition] = {}
    for path in sorted((root / "attacks").glob("*.yaml")):
        attack = load_attack_definition(path)
        if attack.id in attacks:
            raise TestbedContractError(f"duplicate attack id {attack.id!r}")
        attacks[attack.id] = attack

    testbed = Testbed(
        mapping.testbed_id, root, Path(schema_path), catalog, attacks, detector, mapping
    )
    problems = cross_reference_problems(testbed)
    if problems:
        raise TestbedContractError("; ".join(problems))
    return testbed


def cross_reference_problems(tb: Testbed) -> list[str]:
    """Consistency of attack -> rule -> event-type -> catalog references (spec 4.2-4.4)."""
    problems: list[str] = []
    rules = {r.rule_id: r for r in tb.detector.pack.rules}

    for attack in tb.attacks.values():
        if not tb.emulation_path(attack).is_file():
            problems.append(f"{attack.id}: emulation file {attack.emulation} not found")
        mapped = tb.mapping.attacks.get(attack.id)
        if mapped is None:
            problems.append(f"{attack.id}: missing from mapping.json")
            continue
        if set(mapped.expected_rule_ids) != set(attack.expected_rule_ids):
            problems.append(f"{attack.id}: expected_rule_ids differ between attack and mapping")
        if set(mapped.required_event_types) != set(attack.required_event_types):
            problems.append(f"{attack.id}: required_event_types differ between attack and mapping")
        covered: set[str] = set()
        for rule_id in attack.expected_rule_ids:
            if rule_id not in rules:
                problems.append(f"{attack.id}: expected rule {rule_id} not in rule pack")
                continue
            if attack.id not in rules[rule_id].mapped_attack_ids:
                problems.append(f"{rule_id}: does not list {attack.id} in mapped_attack_ids")
            covered |= set(rules[rule_id].required_event_types)
        for event_type in attack.required_event_types:
            if event_type not in tb.catalog:
                problems.append(f"{attack.id}: event type {event_type} not in catalog")
            if event_type not in covered:
                problems.append(f"{attack.id}: no expected rule consumes {event_type}")
            elif attack.id not in tb.catalog[event_type].required_by_attacks:
                problems.append(f"catalog {event_type}: required_by_attacks omits {attack.id}")
    for attack_id in tb.mapping.attacks:
        if attack_id not in tb.attacks:
            problems.append(f"mapping.json lists unknown attack {attack_id}")

    for rule in rules.values():
        for attack_id in rule.mapped_attack_ids:
            if attack_id not in tb.attacks:
                problems.append(f"{rule.rule_id}: maps unknown attack {attack_id}")
        for event_type in rule.required_event_types:
            if event_type not in tb.catalog:
                problems.append(f"{rule.rule_id}: event type {event_type} not in catalog")
            elif rule.rule_id not in tb.catalog[event_type].required_by_rules:
                problems.append(f"catalog {event_type}: required_by_rules omits {rule.rule_id}")
    for entry in tb.catalog.values():
        for rule_id in entry.required_by_rules:
            if rule_id not in rules or entry.event_type not in rules[rule_id].required_event_types:
                problems.append(f"catalog {entry.event_type}: stale required_by_rules {rule_id}")
        for attack_id in entry.required_by_attacks:
            attack = tb.attacks.get(attack_id)
            if attack is None or entry.event_type not in attack.required_event_types:
                problems.append(
                    f"catalog {entry.event_type}: stale required_by_attacks {attack_id}"
                )
    return problems


# ----------------------------------------------------------------------- freeze hashes


def compute_frozen_hashes(tb: Testbed) -> dict[str, str]:
    """Hashes of everything that must not change after baselines are recorded (spec 6.1)."""
    return {
        "rule_pack_hash": hash_patterns(
            tb.root, ["detection/rules/*.json", "detection/mapping.json"]
        ),
        "attack_set_hash": hash_patterns(tb.root, ["attacks/*"]),
        "telemetry_contract_hash": sha256_bytes(
            (
                f"{sha256_file(tb.schema_path)}\n{sha256_file(tb.root / 'event_catalog.yaml')}\n"
            ).encode()
        ),
        "detector_engine_hash": hash_patterns(
            REPO_ROOT,
            [
                "iide/detection/*.py",
                "iide/telemetry/normalize.py",
                "iide/telemetry/schema.py",
            ],
        ),
        "replay_harness_hash": hash_patterns(REPO_ROOT, ["iide/replay/*.py"]),
        "testbed_source_hash": hash_patterns(tb.root, ["app/**/*.py"]),
    }


# ----------------------------------------------------------------------- functional tests


def run_functional_tests(tb: Testbed, timeout_seconds: int = 300) -> FunctionalTestResult:
    """Run the testbed's own functional suite (spec 6.1 step 5) in its own directory."""
    cmd = ["python", "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"]
    proc = subprocess.run(
        [sys.executable, *cmd[1:]],
        cwd=tb.root,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout_seconds,
        check=False,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return FunctionalTestResult(
        command=cmd,
        working_directory=str(_display_path(tb.root)),
        passed=proc.returncode == 0,
        exit_code=proc.returncode,
        summary_line=lines[-1] if lines else "",
    )


def _display_path(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


# ----------------------------------------------------------------------------- replay


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def read_events(sink: Path) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    malformed = 0
    for line in sink.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
        else:
            malformed += 1
    return events, malformed


def run_single_replay(
    tb: Testbed,
    attack: AttackDefinition,
    replay_index: int,
    config: ReplayConfig,
    *,
    program_ref: str = "baseline",
    emulation_path: Path | None = None,
) -> ReplayRecord:
    """One replay (spec 6.2 steps 1-8): fresh instance, one emulation, normalize, detect."""
    correlation_id = replay_correlation_id(attack.id, replay_index)
    base = {
        "replay_id": replay_id(
            tb.testbed_id, attack.id, program_ref, config.experiment_version, replay_index
        ),
        "testbed_id": tb.testbed_id,
        "attack_id": attack.id,
        "program_ref": program_ref,
        "replay_index": replay_index,
        "correlation_id": correlation_id,
    }
    started = _utc_now()
    emulation = emulation_path or tb.emulation_path(attack)

    with tempfile.TemporaryDirectory(prefix="iide-replay-") as tmp:
        workdir = Path(tmp)
        sink = workdir / "events.jsonl"
        sink.touch()  # the oracle creates the sink; a missing sink afterwards is an infra error
        result = run_in_fresh_process(
            testbed_dir=tb.root,
            emulation_path=emulation,
            sink_path=sink,
            correlation_id=correlation_id,
            timeout_seconds=config.replay_timeout_seconds,
            workdir=workdir,
        )

        def invalid(category: str, detail: str) -> ReplayRecord:
            return ReplayRecord(
                **base,
                started_at=_iso(started),
                elapsed_seconds=result.elapsed_seconds,
                valid=False,
                error_category=category,
                error_detail=detail[-2000:],
            )

        if result.timed_out:
            return invalid("TIMEOUT", f"replay exceeded {config.replay_timeout_seconds}s")
        if result.exit_code != 0:
            return invalid(
                "INFRA_ERROR", f"worker exit code {result.exit_code}: {result.stderr_tail}"
            )
        if not sink.is_file():
            return invalid("INFRA_ERROR", "event sink file disappeared during replay")
        raw_events, malformed = read_events(sink)

    normalized = normalize_events(raw_events)
    schema_valid = [e for e in normalized if not validate_event(e, tb.schema_path)]
    outcomes = tb.detector.evaluate(schema_valid)
    expected = set(attack.expected_rule_ids)
    fired_expected = [o for o in outcomes if o.rule_id in expected and o.fired]
    redundancy = sorted({t for o in fired_expected for t in o.matched_event_types})
    return ReplayRecord(
        **base,
        started_at=_iso(started),
        elapsed_seconds=result.elapsed_seconds,
        valid=True,
        raw_event_count=len(raw_events),
        distinct_event_type_count=len(
            {e["event_type"] for e in raw_events if isinstance(e.get("event_type"), str)}
        ),
        malformed_line_count=malformed,
        schema_invalid_event_count=len(normalized) - len(schema_valid),
        rule_outcomes=[
            RuleOutcomeRecord(
                rule_id=o.rule_id, fired=o.fired, matched_event_types=list(o.matched_event_types)
            )
            for o in outcomes
        ],
        firing_rule_count=len(fired_expected),
        redundancy_event_types=redundancy,
        redundancy_event_type_count=len(redundancy),
        # attack_alert_aggregation == "any_expected_rule" (configs/replay.yaml)
        attack_alert_fired=bool(fired_expected),
    )


def run_attack_replays(
    tb: Testbed,
    attack_id: str,
    config: ReplayConfig,
    *,
    planned_k: int | None = None,
    program_ref: str = "baseline",
) -> list[ReplayRecord]:
    attack = tb.attacks[attack_id]
    k = attack.replay_count if planned_k is None else planned_k
    if k < 1:
        raise ValueError("planned_k must be >= 1")
    return [
        run_single_replay(tb, attack, i, config, program_ref=program_ref) for i in range(1, k + 1)
    ]


def summarize_attack(
    attack: AttackDefinition, records: list[ReplayRecord], config: ReplayConfig
) -> AttackBaseline:
    """Aggregate k replay records into d(a, P), status and reliability measures."""
    if not records:
        raise ValueError("no replay records to summarize")
    if any(r.attack_id != attack.id for r in records):
        raise ValueError("records contain replays of a different attack")
    planned_k = len(records)
    valid = [r for r in records if r.valid]
    fired = sum(1 for r in valid if r.attack_alert_fired)
    decision = attack_detected(
        fired, len(valid), planned_k, min_valid_percent=config.min_valid_percent
    )
    rate = flake_rate(planned_k, len(valid), fired)
    return AttackBaseline(
        attack_id=attack.id,
        criticality=attack.criticality,
        expected_rule_ids=attack.expected_rule_ids,
        planned_k=planned_k,
        valid_replays=len(valid),
        fired_count=fired,
        min_valid_required=min_valid_replays(planned_k, config.min_valid_percent),
        status="UNKNOWN" if decision is None else ("DETECTED" if decision else "NOT_DETECTED"),
        d=None if decision is None else int(decision),
        invalid_replay_rate=invalid_replay_rate(planned_k, len(valid)),
        outcome_disagreement_rate=outcome_disagreement_rate(fired, len(valid)),
        flake_rate=rate,
        flake_limit=config.flake_rate_limit,
        flake_within_limit=flake_within_limit(rate, config.flake_rate_limit),
    )
