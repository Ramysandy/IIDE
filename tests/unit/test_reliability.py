import math

import pytest

from iide.replay.reliability import (
    attack_detected,
    flake_rate,
    flake_within_limit,
    invalid_replay_rate,
    min_valid_replays,
    outcome_disagreement_rate,
)


class TestMinValidReplays:
    @pytest.mark.parametrize("k,expected", [(1, 1), (5, 4), (10, 8), (15, 12), (7, 6), (30, 24)])
    def test_matches_ceil_of_eighty_percent(self, k, expected):
        assert min_valid_replays(k) == expected

    def test_integer_arithmetic_agrees_with_exact_rational_ceil_for_many_k(self):
        for k in range(1, 500):
            assert min_valid_replays(k) == -(-4 * k // 5)

    @pytest.mark.parametrize("k,pct", [(0, 80), (-1, 80), (5, 0), (5, 101)])
    def test_rejects_bad_arguments(self, k, pct):
        with pytest.raises(ValueError):
            min_valid_replays(k, pct)


class TestAttackDetected:
    def test_all_replays_fire(self):
        assert attack_detected(5, 5, 5) is True

    def test_no_replays_fire(self):
        assert attack_detected(0, 5, 5) is False

    @pytest.mark.parametrize(
        "fired,valid,expected",
        [(2, 4, True), (1, 4, False), (3, 5, True), (2, 5, False), (4, 4, True)],
    )
    def test_majority_of_valid_replays_with_ceil(self, fired, valid, expected):
        # v=4: need ceil(4/2)=2 (a tie counts as detected); v=5: need 3.
        assert attack_detected(fired, valid, 5) is expected

    def test_threshold_uses_valid_not_planned_count(self):
        # k=5 planned but only 4 valid: need ceil(4/2)=2, not ceil(5/2)=3.
        assert attack_detected(2, 4, 5) is True

    @pytest.mark.parametrize("valid", [0, 1, 2, 3])
    def test_too_few_valid_replays_is_unknown_never_undetected(self, valid):
        assert attack_detected(0, valid, 5) is None
        assert attack_detected(valid, valid, 5) is None  # even if all fired

    def test_min_valid_percent_is_configurable(self):
        assert attack_detected(2, 3, 5, min_valid_percent=60) is True
        assert attack_detected(2, 3, 5, min_valid_percent=80) is None

    @pytest.mark.parametrize(
        "args", [(6, 5, 5), (1, 6, 5), (-1, 5, 5), (0, -1, 5), (0, 0, 0), (0, 0, -3)]
    )
    def test_inconsistent_counts_are_rejected(self, args):
        with pytest.raises(ValueError):
            attack_detected(*args)

    def test_non_int_counts_are_rejected_not_coerced(self):
        with pytest.raises(TypeError):
            attack_detected(1.0, 5, 5)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            attack_detected(True, 5, 5)  # type: ignore[arg-type]

    def test_matches_spec_formula_exhaustively(self):
        for k in range(1, 12):
            for v in range(0, k + 1):
                for f in range(0, v + 1):
                    got = attack_detected(f, v, k)
                    if v < math.ceil(0.8 * k - 1e-9):
                        assert got is None
                    else:
                        assert got is (f >= math.ceil(v / 2))


class TestFlakeMeasures:
    def test_perfectly_consistent_replays_have_zero_flake(self):
        assert flake_rate(5, 5, 5) == 0.0
        assert flake_rate(5, 5, 0) == 0.0

    def test_invalid_replays_and_minority_outcomes_both_count(self):
        assert flake_rate(5, 4, 4) == pytest.approx(0.2)  # one invalid replay
        assert flake_rate(5, 5, 4) == pytest.approx(0.2)  # one valid dissenter
        assert flake_rate(5, 4, 3) == pytest.approx(0.4)  # one invalid + one dissenter
        assert flake_rate(30, 30, 29) == pytest.approx(1 / 30)

    def test_no_valid_replays_is_total_flake(self):
        assert flake_rate(5, 0, 0) == 1.0

    def test_invalid_rate_and_disagreement_rate(self):
        assert invalid_replay_rate(5, 4) == pytest.approx(0.2)
        assert outcome_disagreement_rate(1, 4) == pytest.approx(0.25)
        assert outcome_disagreement_rate(4, 4) == 0.0

    def test_disagreement_undefined_without_valid_replays(self):
        assert outcome_disagreement_rate(0, 0) is None

    def test_limit_comparison_is_strict(self):
        assert flake_within_limit(0.0, 0.05)
        assert flake_within_limit(0.049, 0.05)
        assert not flake_within_limit(0.05, 0.05)
        assert not flake_within_limit(0.2, 0.05)

    @pytest.mark.parametrize("rate,limit", [(-0.1, 0.05), (1.1, 0.05), (0.1, 0.0), (0.1, 1.0)])
    def test_limit_validation(self, rate, limit):
        with pytest.raises(ValueError):
            flake_within_limit(rate, limit)

    def test_flake_inputs_are_validated(self):
        with pytest.raises(ValueError):
            flake_rate(5, 6, 0)
        with pytest.raises(ValueError):
            outcome_disagreement_rate(3, 2)
