"""RC, ED, LEI, detection debt: spec section 9 fixture and edge cases."""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError
from scoring_fixtures import SECTION9_ROWS, outcome, section9_outcomes

from iide.scoring.coverage import (
    detection_debt,
    erosion_depth,
    latent_erosion_index,
    latent_erosion_index_result,
    retained_coverage,
    retained_coverage_result,
    score_coverage,
)
from iide.scoring.types import AttackOutcome


# ---------------------------------------------------------------- spec section 9 fixture
def test_section9_total_and_retained_criticality():
    outcomes = section9_outcomes()
    assert sum(a.criticality for a in outcomes) == 14
    assert sum(a.criticality for a in outcomes if a.d1) == 11


def test_section9_retained_coverage_and_erosion_depth():
    rc = retained_coverage_result(section9_outcomes())
    assert (rc.numerator, rc.denominator) == (11, 14)
    assert rc.value == pytest.approx(11 / 14, abs=1e-12)
    assert rc.value == pytest.approx(0.785714, abs=1e-6)
    ed = erosion_depth(rc.value)
    assert ed == pytest.approx(3 / 14, abs=1e-12)
    assert ed == pytest.approx(0.214286, abs=1e-6)


def test_section9_lei_numerator_denominator_and_value():
    lei = latent_erosion_index_result(section9_outcomes())
    assert lei.numerator == 3  # 3 * max(0, 2 - 1): brute force only
    assert lei.denominator == 20  # 3*2 + 3*1 + 2*1 + 3*2 + 2*1 + 1*1
    assert lei.value == pytest.approx(0.15, abs=1e-12)


def test_lei_numerator_excludes_the_lost_attack_explicitly():
    """Role escalation (d1=0, r0=1, r1=0) must not contribute 3*max(0, 1-0)=3 to the numerator."""
    with_lost = section9_outcomes()
    lei = latent_erosion_index_result(with_lost)
    assert lei.numerator == 3
    wrong_numerator_if_lost_row_counted = 3 + 3 * max(0, 1 - 0)
    assert lei.numerator != wrong_numerator_if_lost_row_counted
    # ...but its baseline redundancy stays in the denominator.
    assert lei.denominator == 20


def test_section9_unit_weight_sensitivity_is_reported_separately():
    scores = score_coverage(section9_outcomes())
    assert scores.rc.value == pytest.approx(11 / 14)
    assert scores.rc_unit.value == pytest.approx(5 / 6)
    assert scores.ed_unit.value == pytest.approx(1 / 6)
    assert scores.lei_unit.numerator == 1 and scores.lei_unit.denominator == 8
    assert scores.lost_attack_ids == ["role_escalation"]
    assert scores.latent_attack_ids == ["credential_bruteforce"]
    assert scores.unknown_attack_ids == [] and scores.excluded == {}


def test_rule_count_sensitivity_never_replaces_the_event_type_definition():
    # Same 6 attacks, but pretend each fired two independent rules at P0 and one at P1.
    outcomes = [
        AttackOutcome(
            attack_id=n,
            criticality=c,
            d0=True,
            d1=d1,
            r0=r0,
            r1=r1,
            rules0=2,
            rules1=1 if d1 else 0,
        )
        for n, c, r0, d1, r1 in SECTION9_ROWS
    ]
    scores = score_coverage(outcomes)
    assert scores.lei.value == pytest.approx(0.15)  # primary unchanged
    # rules variant: numerator = sum c over still-detected (3+2+3+2+1)=11 ; den = 2*14 = 28
    assert (scores.lei_rules.numerator, scores.lei_rules.denominator) == (11, 28)
    assert scores.lei_rules.name == "LEI_rules"


def test_rule_count_variant_unavailable_is_reported_not_guessed():
    result = latent_erosion_index_result(
        [outcome("a", 3, True, True)],  # rules0 / rules1 not provided
        redundancy="rules",
    )
    assert result.value is None and "unavailable" in result.reason


# ---------------------------------------------------------------- A0 and denominators
def test_attacks_outside_a0_are_not_scored_and_are_listed():
    outcomes = [
        outcome("kept", 3, True, True),
        outcome("never_detected", 3, False, False),
        outcome("baseline_unknown", 2, None, None),
    ]
    scores = score_coverage(outcomes)
    assert scores.a0_attack_ids == ["kept"]
    assert scores.excluded == {
        "never_detected": "not detected at baseline",
        "baseline_unknown": "baseline detection UNKNOWN",
    }
    assert scores.rc.value == 1.0 and scores.rc.denominator == 3


def test_empty_a0_makes_every_measure_undefined_with_a_reason():
    outcomes = [outcome("x", 3, False, False), outcome("y", 1, None, None)]
    assert retained_coverage(outcomes) is None
    assert erosion_depth(retained_coverage(outcomes)) is None
    assert latent_erosion_index(outcomes) is None
    scores = score_coverage(outcomes)
    for metric in (scores.rc, scores.ed, scores.lei, scores.rc_unit, scores.lei_rules):
        assert metric.value is None and "A0 is empty" in metric.reason
    assert score_coverage([]).rc.value is None


def test_unknown_candidate_detection_is_never_counted_as_lost_or_retained():
    outcomes = [
        outcome("kept", 3, True, True),
        outcome("lost", 1, True, False),
        outcome("unsure", 2, True, None),
    ]
    rc = retained_coverage_result(outcomes)
    assert rc.value is None and "unsure" in rc.reason
    assert rc.details == {"lower_bound": pytest.approx(3 / 6), "upper_bound": pytest.approx(5 / 6)}
    scores = score_coverage(outcomes)
    assert scores.ed.value is None
    assert scores.ed.details == {
        "lower_bound": pytest.approx(1 / 6),
        "upper_bound": pytest.approx(3 / 6),
    }
    assert scores.lei.value is None and "UNKNOWN" in scores.lei.reason
    assert scores.unknown_attack_ids == ["unsure"] and scores.lost_attack_ids == ["lost"]


def test_duplicate_attack_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate attack_id"):
        retained_coverage([outcome("a", 1, True, True), outcome("a", 2, True, True)])


# ---------------------------------------------------------------- boundary behaviour
def test_no_erosion_and_total_erosion_boundaries():
    same = [outcome("a", 3, True, True, 2, 2), outcome("b", 1, True, True, 1, 1)]
    assert retained_coverage(same) == 1.0 and erosion_depth(1.0) == 0.0
    assert latent_erosion_index(same) == 0.0
    gone = [outcome("a", 3, True, False, 2), outcome("b", 1, True, False, 1)]
    assert retained_coverage(gone) == 0.0 and erosion_depth(0.0) == 1.0
    assert latent_erosion_index(gone) == 0.0  # nothing still detected -> numerator 0


def test_gained_redundancy_does_not_offset_lost_redundancy():
    outcomes = [outcome("a", 1, True, True, 1, 3), outcome("b", 1, True, True, 3, 1)]
    lei = latent_erosion_index_result(outcomes)
    assert lei.numerator == 2  # max(0, 1-3)=0 for a; max(0, 3-1)=2 for b


def test_erosion_depth_validates_input():
    for bad in (-0.1, 1.1, True, "0.5"):
        with pytest.raises(ValueError):
            erosion_depth(bad)


def test_attack_outcome_validation():
    with pytest.raises(ValidationError):
        AttackOutcome(attack_id="a", criticality=4, d0=True, d1=True, r0=1, r1=1)
    with pytest.raises(ValidationError):
        AttackOutcome(attack_id="a", criticality=2, d0=True, d1=True, r0=0, r1=1)
    with pytest.raises(ValidationError):
        AttackOutcome(attack_id="a", criticality=2, d0=True, d1=True, r0=1, r1=0)
    with pytest.raises(ValidationError):
        AttackOutcome(attack_id="a", criticality=2, d0=True, d1=False, r0=-1, r1=0)


# ---------------------------------------------------------------- randomized property checks
def _random_outcomes(rng: random.Random):
    out = []
    for i in range(rng.randint(1, 12)):
        d0 = rng.random() < 0.8
        d1 = rng.choice([True, False]) if d0 else rng.choice([True, False])
        r0 = rng.randint(1, 4)
        r1 = rng.randint(1, 4)
        out.append(outcome(f"a{i}", rng.choice([1, 2, 3]), d0, d1, r0, r1))
    return out


def test_property_rc_ed_lei_are_in_range_and_rc_plus_ed_is_one():
    rng = random.Random(20260427)
    for _ in range(500):
        outcomes = _random_outcomes(rng)
        rc = retained_coverage(outcomes)
        lei = latent_erosion_index(outcomes)
        if rc is None:
            assert not any(a.d0 for a in outcomes) and lei is None
            continue
        assert 0.0 <= rc <= 1.0
        assert erosion_depth(rc) == pytest.approx(1.0 - rc)
        assert lei is not None and 0.0 <= lei <= 1.0


def test_property_weights_scale_invariance_and_order_invariance():
    rng = random.Random(7)
    for _ in range(100):
        outcomes = _random_outcomes(rng)
        shuffled = outcomes[:]
        rng.shuffle(shuffled)
        assert retained_coverage(outcomes) == retained_coverage(shuffled)
        assert latent_erosion_index(outcomes) == latent_erosion_index(shuffled)


# ---------------------------------------------------------------- detection debt
def test_detection_debt_sums_steps_and_propagates_undefined():
    assert detection_debt([0.25, 0.5]) == pytest.approx(0.75)
    assert detection_debt([0.25, None]) is None
    with pytest.raises(ValueError):
        detection_debt([])
    with pytest.raises(ValueError):
        detection_debt([1.5])
