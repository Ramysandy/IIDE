"""Replay records -> AttackOutcome, and the report generator (no subprocesses)."""

from __future__ import annotations

import json

import pytest
from conftest import BILLING_ROOT

from iide.analysis.reports import (
    build_coverage_report,
    render_json,
    render_markdown,
    scoring_package_hash,
)
from iide.models import ReplayRecord, RuleOutcomeRecord, load_attack_definition
from iide.scoring.adapters import InconsistentEvidenceError, attack_redundancy, build_attack_outcome
from iide.scoring.types import AttackOutcome

ATTACK = load_attack_definition(BILLING_ROOT / "attacks" / "credential_bruteforce.yaml")
RULE = ATTACK.expected_rule_ids[0]


def _rec(i, *, valid=True, rules: dict[str, list[str]] | None = None) -> ReplayRecord:
    """rules maps rule_id -> matched event types (a fired rule); absent => silent."""
    rules = rules or {}
    outcomes = [
        RuleOutcomeRecord(rule_id=r, fired=True, matched_event_types=t) for r, t in rules.items()
    ]
    if RULE not in rules:
        outcomes.append(RuleOutcomeRecord(rule_id=RULE, fired=False, matched_event_types=[]))
    return ReplayRecord(
        replay_id=f"r{i}",
        testbed_id="billing_api",
        attack_id=ATTACK.id,
        program_ref="p",
        replay_index=i,
        correlation_id=f"c{i}",
        started_at="2026-10-27T12:00:00Z",
        elapsed_seconds=0.1,
        valid=valid,
        error_category=None if valid else "INFRA_ERROR",
        rule_outcomes=outcomes if valid else [],
        attack_alert_fired=(any(o.fired for o in outcomes) if valid else None),
    )


FIRED2 = {RULE: ["auth.login_failed", "auth.lockout"]}
FIRED1 = {RULE: ["auth.login_failed"]}


def test_redundancy_is_the_distinct_event_types_of_majority_firing_rules():
    records = [_rec(i, rules=FIRED2) for i in range(1, 6)]
    r, rules, types = attack_redundancy(ATTACK, records)
    assert (r, rules, types) == (2, 1, ["auth.lockout", "auth.login_failed"])


def test_repeated_replays_and_duplicate_types_do_not_inflate_redundancy():
    dup = {RULE: ["auth.login_failed", "auth.login_failed", "auth.login_failed"]}
    r, _, types = attack_redundancy(ATTACK, [_rec(i, rules=dup) for i in range(1, 6)])
    assert r == 1 and types == ["auth.login_failed"]


def test_invalid_replays_are_ignored_by_redundancy():
    records = [_rec(1, valid=False)] + [_rec(i, rules=FIRED1) for i in range(2, 6)]
    assert attack_redundancy(ATTACK, records)[0] == 1
    assert attack_redundancy(ATTACK, [_rec(1, valid=False)]) == (0, 0, [])


def test_minority_firing_rule_does_not_count_toward_redundancy():
    records = [_rec(1, rules=FIRED2)] + [_rec(i) for i in range(2, 6)]  # fired in 1 of 5
    assert attack_redundancy(ATTACK, records)[0] == 0


def test_build_outcome_detected_with_latent_erosion(config):
    base = [_rec(i, rules=FIRED2) for i in range(1, 6)]
    cand = [_rec(i, rules=FIRED1) for i in range(1, 6)]
    o = build_attack_outcome(ATTACK, base, cand, config)
    assert (o.d0, o.d1, o.r0, o.r1, o.rules0, o.rules1) == (True, True, 2, 1, 1, 1)
    assert o.criticality == ATTACK.criticality


def test_build_outcome_lost_attack_has_zero_candidate_redundancy(config):
    base = [_rec(i, rules=FIRED2) for i in range(1, 6)]
    cand = [_rec(i) for i in range(1, 6)]
    o = build_attack_outcome(ATTACK, base, cand, config)
    assert (o.d0, o.d1, o.r1) == (True, False, 0)


def test_build_outcome_unknown_candidate_is_none_not_false(config):
    base = [_rec(i, rules=FIRED2) for i in range(1, 6)]
    cand = [_rec(i, valid=(i == 1)) for i in range(1, 6)]  # 1 valid of 5 < ceil(0.8*5)
    o = build_attack_outcome(ATTACK, base, cand, config)
    assert o.d1 is None and o.r1 == 0


def test_inconsistent_evidence_is_an_error_not_a_guess(config):
    # Detected by 'any expected rule' in a majority, but only via a rule not in expected_rule_ids.
    stray = {"IIDE-OTHER": ["auth.lockout"]}
    records = [_rec(i, rules=stray) for i in range(1, 6)]
    with pytest.raises(InconsistentEvidenceError):
        build_attack_outcome(ATTACK, records, records, config)


# ------------------------------------------------------------------ report generator
def _outcomes():
    return [
        AttackOutcome(attack_id="a", criticality=3, d0=True, d1=False, r0=2, r1=0),
        AttackOutcome(attack_id="b", criticality=1, d0=True, d1=True, r0=2, r1=1),
        AttackOutcome(attack_id="c", criticality=2, d0=False, d1=False),
    ]


def test_report_contains_every_measure_exclusions_and_the_package_hash():
    report = build_coverage_report(_outcomes(), label="unit", note="synthetic")
    md = render_markdown(report)
    assert scoring_package_hash() in md and len(scoring_package_hash()) == 64
    assert "RC: 0.250000 = 1/4" in md
    assert "ED: 0.750000 = 3/4" in md
    assert "LEI (event-type redundancy): 0.125000 = 1/8" in md  # c_b*(2-1) / (3*2 + 1*2)
    assert "{'c': 'not detected at baseline'}" in md
    assert "RC, unit weights" in md and "LEI, independently firing rules" in md
    assert "lost (EROSION): ['a']" in md and "latent erosion: ['b']" in md


def test_report_shows_undefined_measures_with_reasons_not_numbers():
    outcomes = [AttackOutcome(attack_id="a", criticality=3, d0=True, d1=None, r0=1, r1=0)]
    md = render_markdown(build_coverage_report(outcomes, label="x"))
    assert "RC: undefined: 1 attack(s) in A0 have UNKNOWN" in md
    assert "bounds 0.0000 to 1.0000" in md
    assert "nan" not in md.lower()
    assert "A0 is empty" in render_markdown(build_coverage_report([], label="empty"))


def test_report_json_roundtrips_and_is_deterministic():
    r1 = render_json(build_coverage_report(_outcomes(), label="x"))
    r2 = render_json(build_coverage_report(list(reversed(_outcomes())), label="x"))
    assert r1 == r2
    data = json.loads(r1)
    assert data["scores"]["rc"]["numerator"] == 1 and data["scoring_package_hash"]
