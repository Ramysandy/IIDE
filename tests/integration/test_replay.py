"""Replay runner behaviour: each replay is a fresh process; failures are never 'silent'."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from conftest import BILLING_ROOT

from iide.ids import replay_correlation_id
from iide.replay.runner import (
    read_events,
    run_attack_replays,
    run_single_replay,
    summarize_attack,
)
from iide.replay.sandbox import run_in_fresh_process

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ATTACK_ID = "credential_bruteforce"


def _events_for(testbed, emulation: Path, correlation_id="replay-test-001", timeout=60):
    with tempfile.TemporaryDirectory() as tmp:
        sink = Path(tmp) / "events.jsonl"
        sink.touch()
        result = run_in_fresh_process(
            testbed_dir=testbed.root,
            emulation_path=emulation,
            sink_path=sink,
            correlation_id=correlation_id,
            timeout_seconds=timeout,
            workdir=Path(tmp),
        )
        events, malformed = read_events(sink)
    assert result.exit_code == 0, result.stderr_tail
    assert malformed == 0
    return events


def test_single_replay_fires_and_records_event_accounting(testbed, config):
    attack = testbed.attacks[ATTACK_ID]
    record = run_single_replay(testbed, attack, 1, config)
    assert record.valid and record.error_category is None
    assert record.attack_alert_fired is True
    assert record.correlation_id == "replay-credential_bruteforce-001"
    # 6 attempts -> 6 login_failed + 1 lockout; two distinct semantic types.
    assert record.raw_event_count == 7
    assert record.distinct_event_type_count == 2
    assert record.malformed_line_count == 0 and record.schema_invalid_event_count == 0
    assert record.firing_rule_count == 1
    assert record.redundancy_event_types == ["auth.lockout", "auth.login_failed"]
    assert record.redundancy_event_type_count == 2
    assert [(o.rule_id, o.fired) for o in record.rule_outcomes] == [("IIDE-BILLING-001", True)]


def test_replays_run_in_fresh_instances_with_no_state_leakage(testbed):
    """If lockout state leaked, the 2nd replay would start locked and emit no lockout event."""
    emulation = testbed.emulation_path(testbed.attacks[ATTACK_ID])
    runs = [_events_for(testbed, emulation) for _ in range(3)]
    shapes = [sorted(e["event_type"] for e in events) for events in runs]
    assert shapes[0] == shapes[1] == shapes[2]
    assert shapes[0].count("auth.lockout") == 1 and shapes[0].count("auth.login_failed") == 6
    ids = [{e["event_id"] for e in events} for events in runs]
    assert not (ids[0] & ids[1]) and not (ids[1] & ids[2])  # event ids are random per instance


def test_events_carry_the_injected_correlation_id(testbed):
    emulation = testbed.emulation_path(testbed.attacks[ATTACK_ID])
    events = _events_for(testbed, emulation, correlation_id="replay-unique-xyz")
    assert {e["correlation_id"] for e in events} == {"replay-unique-xyz"}


def test_baseline_replays_are_repeatable_across_independent_batches(testbed, config):
    first = run_attack_replays(testbed, ATTACK_ID, config)
    second = run_attack_replays(testbed, ATTACK_ID, config)
    assert len(first) == len(second) == testbed.attacks[ATTACK_ID].replay_count == 5
    assert all(r.valid for r in first + second)

    def stable(record):
        data = record.model_dump()
        for volatile in ("started_at", "elapsed_seconds"):
            data.pop(volatile)
        return data

    assert [stable(r) for r in first] == [stable(r) for r in second]
    assert [r.replay_index for r in first] == [1, 2, 3, 4, 5]
    assert len({r.replay_id for r in first}) == 5  # distinct per replay, same across batches

    a, b = (summarize_attack(testbed.attacks[ATTACK_ID], rs, config) for rs in (first, second))
    assert a == b
    assert (a.status, a.fired_count, a.valid_replays, a.flake_rate) == ("DETECTED", 5, 5, 0.0)


def test_negative_control_benign_traffic_does_not_fire_the_rule(testbed):
    events = _events_for(testbed, FIXTURES / "benign_logins.py")
    assert events, "benign scenario should still produce telemetry"
    outcomes = testbed.detector.evaluate(events)
    assert [o.fired for o in outcomes] == [False]
    assert "auth.lockout" not in {e["event_type"] for e in events}


def test_silent_but_successful_replay_is_valid_and_not_fired(testbed, config):
    attack = testbed.attacks[ATTACK_ID]
    record = run_single_replay(
        testbed, attack, 1, config, emulation_path=FIXTURES / "silent_emulation.py"
    )
    assert record.valid and record.raw_event_count == 0
    assert record.attack_alert_fired is False  # genuinely silent, as opposed to invalid


def test_crashing_emulation_is_invalid_infra_error_not_silent(testbed, config):
    attack = testbed.attacks[ATTACK_ID]
    record = run_single_replay(
        testbed, attack, 1, config, emulation_path=FIXTURES / "crashing_emulation.py"
    )
    assert not record.valid and record.error_category == "INFRA_ERROR"
    assert "synthetic crash" in (record.error_detail or "")
    assert record.attack_alert_fired is None and record.rule_outcomes == []


def test_missing_emulation_file_is_invalid_infra_error(testbed, config):
    attack = testbed.attacks[ATTACK_ID]
    record = run_single_replay(
        testbed, attack, 1, config, emulation_path=FIXTURES / "does_not_exist.py"
    )
    assert not record.valid and record.error_category == "INFRA_ERROR"


def test_timeout_is_invalid_timeout_not_silent(testbed, config):
    attack = testbed.attacks[ATTACK_ID]
    fast = config.model_copy(update={"replay_timeout_seconds": 1})
    record = run_single_replay(
        testbed, attack, 1, fast, emulation_path=FIXTURES / "hanging_emulation.py"
    )
    assert not record.valid and record.error_category == "TIMEOUT"
    assert record.attack_alert_fired is None


def test_parent_environment_is_not_visible_to_the_replay_process(testbed, config, monkeypatch):
    monkeypatch.setenv("IIDE_TEST_SECRET_API_KEY", "synthetic-not-a-secret")
    record = run_single_replay(
        testbed,
        testbed.attacks[ATTACK_ID],
        1,
        config,
        emulation_path=FIXTURES / "env_probe_emulation.py",
    )
    assert record.valid, record.error_detail


def test_replay_correlation_ids_follow_deterministic_scheme():
    assert replay_correlation_id(ATTACK_ID, 3) == "replay-credential_bruteforce-003"


def test_replay_leaves_no_bytecode_in_the_testbed(testbed, config):
    before = set(BILLING_ROOT.rglob("*.pyc"))
    run_single_replay(testbed, testbed.attacks[ATTACK_ID], 1, config)
    assert set(BILLING_ROOT.rglob("*.pyc")) == before
