"""Attack-level summarisation from replay records (no subprocesses)."""

import pytest
from conftest import BILLING_ROOT

from iide.models import ReplayRecord, load_attack_definition
from iide.replay.runner import summarize_attack

ATTACK = load_attack_definition(BILLING_ROOT / "attacks" / "credential_bruteforce.yaml")


def _record(i: int, *, valid=True, fired=True, attack_id=ATTACK.id) -> ReplayRecord:
    return ReplayRecord(
        replay_id=f"r{i}",
        testbed_id="billing_api",
        attack_id=attack_id,
        program_ref="baseline",
        replay_index=i,
        correlation_id=f"c{i}",
        started_at="2026-10-27T12:00:00Z",
        elapsed_seconds=0.1,
        valid=valid,
        error_category=None if valid else "INFRA_ERROR",
        attack_alert_fired=fired if valid else None,
    )


def _records(fired_flags, invalid=()):
    return [
        _record(i + 1, valid=(i not in invalid), fired=flag) for i, flag in enumerate(fired_flags)
    ]


def test_all_fired_is_detected_with_zero_flake(config):
    s = summarize_attack(ATTACK, _records([True] * 5), config)
    assert (s.status, s.d, s.fired_count, s.valid_replays, s.planned_k) == ("DETECTED", 1, 5, 5, 5)
    assert s.flake_rate == 0.0 and s.flake_within_limit
    assert s.min_valid_required == 4 and s.invalid_replay_rate == 0.0


def test_none_fired_is_not_detected(config):
    s = summarize_attack(ATTACK, _records([False] * 5), config)
    assert (s.status, s.d) == ("NOT_DETECTED", 0)


def test_majority_vote_with_one_dissenter_flags_flake(config):
    s = summarize_attack(ATTACK, _records([True, True, True, True, False]), config)
    assert s.status == "DETECTED"
    assert s.flake_rate == pytest.approx(0.2) and not s.flake_within_limit


def test_one_invalid_replay_still_decides_but_counts_as_flake(config):
    s = summarize_attack(ATTACK, _records([True] * 5, invalid={0}), config)
    assert s.valid_replays == 4 and s.status == "DETECTED"
    assert s.invalid_replay_rate == pytest.approx(0.2) and not s.flake_within_limit


def test_too_many_invalid_replays_is_unknown_not_undetected(config):
    s = summarize_attack(ATTACK, _records([False] * 5, invalid={0, 1}), config)
    assert s.valid_replays == 3 < s.min_valid_required
    assert (s.status, s.d) == ("UNKNOWN", None)


def test_all_invalid_is_unknown_with_undefined_disagreement(config):
    s = summarize_attack(ATTACK, _records([False] * 5, invalid=set(range(5))), config)
    assert s.status == "UNKNOWN" and s.outcome_disagreement_rate is None
    assert s.flake_rate == 1.0


def test_invalid_replays_are_never_counted_as_fired_or_silent(config):
    records = _records([True] * 5, invalid={4})
    assert records[4].attack_alert_fired is None
    assert summarize_attack(ATTACK, records, config).fired_count == 4


def test_empty_and_foreign_records_are_rejected(config):
    with pytest.raises(ValueError):
        summarize_attack(ATTACK, [], config)
    with pytest.raises(ValueError):
        summarize_attack(ATTACK, [_record(1, attack_id="other_attack")], config)
