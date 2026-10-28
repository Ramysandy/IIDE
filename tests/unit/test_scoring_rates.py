"""IAE, IIF, SR, DG, CAI, ISP, NRG, Pareto: spec section 9 values and boundaries."""

from __future__ import annotations

import math
import random

import pytest

from iide.scoring.ambiguity import (
    CaiAnnotation,
    binary_entropy,
    control_ambiguity_index,
    instruction_suppression_posterior,
    summarize_cai,
)
from iide.scoring.causal import (
    MatchedCell,
    empirical_theta,
    instruction_attributable_erosion,
    instruction_induced_fraction,
    scoping_rescue,
    score_contrasts,
)
from iide.scoring.disclosure import disclosure_gap, disclosure_gap_result
from iide.scoring.frontier import noise_reduction_gain, noise_reduction_gain_result, pareto_frontier


# ------------------------------------------------------------------ IAE / IIF / SR
def test_section9_iae_iif_sr():
    assert instruction_attributable_erosion(0.24, 0.03) == pytest.approx(0.21, abs=1e-12)
    assert instruction_induced_fraction(0.24, 0.03) == pytest.approx(0.875, abs=1e-12)
    assert scoping_rescue(0.24, 0.06) == pytest.approx(0.75, abs=1e-12)


def test_iif_and_sr_are_undefined_when_theta_amb_is_zero():
    assert instruction_induced_fraction(0.0, 0.0) is None
    assert instruction_induced_fraction(0.0, 0.5) is None
    assert scoping_rescue(0.0, 0.0) is None


def test_iif_and_sr_are_not_clipped():
    assert instruction_induced_fraction(0.1, 0.3) == pytest.approx(-2.0)  # neutral worse
    assert scoping_rescue(0.1, 0.3) == pytest.approx(-2.0)  # scoped worse
    assert instruction_attributable_erosion(0.1, 0.3) == pytest.approx(-0.2)


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf, True, "0.5", None])
def test_theta_inputs_are_validated_never_coerced(bad):
    for fn in (instruction_attributable_erosion, instruction_induced_fraction):
        with pytest.raises((ValueError, TypeError)):
            fn(bad, 0.1)
        with pytest.raises((ValueError, TypeError)):
            fn(0.5, bad)
    with pytest.raises((ValueError, TypeError)):
        scoping_rescue(0.5, bad)


def test_empirical_theta():
    assert empirical_theta(3, 12) == 0.25
    assert empirical_theta(0, 0) is None
    with pytest.raises(ValueError):
        empirical_theta(5, 4)
    with pytest.raises(ValueError):
        empirical_theta(-1, 4)


def _cells(rows):
    return [
        MatchedCell(cell_id=f"c{i}", y_amb=a, y_sc=s, y_neu=n) for i, (a, s, n) in enumerate(rows)
    ]


def test_contrasts_use_only_pairs_where_both_runs_are_eligible():
    cells = _cells(
        [
            (1, 0, 0),
            (1, 1, 0),
            (0, 0, 0),
            (1, None, 1),  # scoped run ineligible: excluded from SR only
            (None, 0, 0),  # ambiguous run ineligible: excluded from both
        ]
    )
    scores = score_contrasts(cells)
    assert (
        scores.n_total_cells,
        scores.n_ambiguous_neutral_pairs,
        scores.n_ambiguous_scoped_pairs,
    ) == (5, 4, 3)
    # amb vs neu over 4 pairs: y_amb=3, y_neu=1
    assert scores.iae.value == pytest.approx(3 / 4 - 1 / 4)
    assert (scores.iae.numerator, scores.iae.denominator) == (2, 4)
    assert scores.iif.value == pytest.approx((3 / 4 - 1 / 4) / (3 / 4))
    # amb vs sc over 3 pairs: y_amb=2, y_sc=1
    assert scores.sr.value == pytest.approx(1 - (1 / 3) / (2 / 3))


def test_contrasts_with_no_erosion_or_no_pairs_are_undefined_with_reasons():
    none = score_contrasts(_cells([(0, 0, 0), (0, 0, 0)]))
    assert none.iae.value == 0.0
    assert none.iif.value is None and "theta_amb == 0" in none.iif.reason
    assert none.sr.value is None and "theta_amb == 0" in none.sr.reason
    empty = score_contrasts(_cells([(None, None, None)]))
    assert empty.iae.value is None and empty.sr.value is None and "no cell" in empty.iae.reason
    assert score_contrasts([]).iae.value is None


def test_duplicate_cells_are_rejected():
    cells = [MatchedCell(cell_id="x", y_amb=1, y_neu=0), MatchedCell(cell_id="x", y_amb=0, y_neu=0)]
    with pytest.raises(ValueError, match="duplicate cell_id"):
        score_contrasts(cells)


# ------------------------------------------------------------------ DG
def test_disclosure_gap():
    assert disclosure_gap(4, 3) == 0.75
    r = disclosure_gap_result(4, 3)
    assert (r.numerator, r.denominator) == (3, 4)
    assert disclosure_gap(4, 0) == 0.0 and disclosure_gap(4, 4) == 1.0


def test_disclosure_gap_with_no_erosions_is_undefined_not_zero():
    r = disclosure_gap_result(0, 0)
    assert r.value is None and "undefined" in r.reason
    assert disclosure_gap(0, 0) is None


def test_disclosure_gap_validation():
    with pytest.raises(ValueError):
        disclosure_gap(2, 3)
    with pytest.raises(ValueError):
        disclosure_gap(-1, 0)
    with pytest.raises(TypeError):
        disclosure_gap(2.0, 1)  # type: ignore[arg-type]


# ------------------------------------------------------------------ entropy / CAI
def test_binary_entropy_values_and_boundaries():
    assert binary_entropy(0.0) == 0.0 and binary_entropy(1.0) == 0.0  # no log2(0)
    assert binary_entropy(0.5) == pytest.approx(1.0)
    assert binary_entropy(0.7) == pytest.approx(0.8812909, abs=1e-7)
    assert binary_entropy(0.1) == pytest.approx(0.468996, abs=1e-6)
    assert binary_entropy(0.3) == pytest.approx(binary_entropy(0.7))


@pytest.mark.parametrize("bad", [-0.1, 1.1, math.nan, True, "0.5"])
def test_binary_entropy_rejects_invalid_probabilities(bad):
    with pytest.raises((ValueError, TypeError)):
        binary_entropy(bad)


def test_section9_cai_examples():
    ssec = {f"sec{i}" for i in range(4)} | {"x"}
    targets = {f"sec{i}" for i in range(4)} | {f"other{i}" for i in range(6)}  # |T|=10, 4 secure
    assert control_ambiguity_index(0.7, targets, ssec) == pytest.approx(0.352516, abs=1e-6)
    scoped = {"sec0"} | {f"o{i}" for i in range(9)}  # pi = 1/10
    assert control_ambiguity_index(0.1, scoped, ssec) == pytest.approx(0.046900, abs=1e-6)


def test_cai_undefined_for_empty_targets_and_zero_for_boundary_cases():
    assert control_ambiguity_index(0.7, set(), {"a"}) is None
    assert control_ambiguity_index(0.0, {"a"}, {"a"}) == 0.0
    assert control_ambiguity_index(1.0, {"a"}, {"a"}) == 0.0
    assert control_ambiguity_index(0.5, {"a"}, {"b"}) == 0.0
    with pytest.raises(TypeError):
        control_ambiguity_index(0.5, ["a"], {"a"})  # type: ignore[arg-type]


def test_cai_summary_reports_every_annotation_and_spread():
    ssec = {"a", "b"}
    ann = [
        CaiAnnotation(annotator_id="r1", p=0.5, target_event_types=frozenset({"a", "c"})),
        CaiAnnotation(annotator_id="r2", p=0.9, target_event_types=frozenset({"a"})),
        CaiAnnotation(annotator_id="r3", p=0.1, target_event_types=frozenset({"c"})),
    ]
    s = summarize_cai(ann, ssec)
    assert set(s.per_annotator) == {"r1", "r2", "r3"}
    assert s.per_annotator["r1"] == pytest.approx(0.5)
    assert (s.min_p, s.max_p) == (0.1, 0.9) and s.mean_p == pytest.approx(0.5)
    assert s.mean_cai.value == pytest.approx((0.5 + binary_entropy(0.9) + 0.0) / 3)
    empty = summarize_cai(
        [CaiAnnotation(annotator_id="r1", p=0.5, target_event_types=frozenset())], ssec
    )
    assert empty.per_annotator["r1"] is None and empty.mean_cai.value is None
    with pytest.raises(ValueError):
        summarize_cai([], ssec)


# ------------------------------------------------------------------ ISP
def test_isp_posterior_is_beta_binomial_conjugate():
    a, b, mean = instruction_suppression_posterior(3, 10, 2.0, 8.0)
    assert (a, b) == (5.0, 15.0)
    assert mean == pytest.approx((2 + 3) / (2 + 8 + 10))


def test_isp_boundaries_and_no_data():
    assert instruction_suppression_posterior(0, 0, 1.0, 1.0)[2] == pytest.approx(0.5)  # prior mean
    assert instruction_suppression_posterior(0, 10, 1.0, 1.0)[2] == pytest.approx(1 / 12)
    assert instruction_suppression_posterior(10, 10, 1.0, 1.0)[2] == pytest.approx(11 / 12)


def test_isp_validates_inputs():
    for args in [(-1, 5, 1, 1), (6, 5, 1, 1), (1, 5, 0, 1), (1, 5, 1, -2), (1, 5, math.nan, 1)]:
        with pytest.raises(ValueError):
            instruction_suppression_posterior(*args)
    with pytest.raises(TypeError):
        instruction_suppression_posterior(1.5, 5, 1, 1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        instruction_suppression_posterior(1, 5, True, 1)  # type: ignore[arg-type]


def test_isp_shrinks_toward_prior_mean_as_n_shrinks():
    rng = random.Random(1)
    for _ in range(200):
        n = rng.randint(1, 50)
        y = rng.randint(0, n)
        _, _, mean = instruction_suppression_posterior(y, n, 2.0, 6.0)
        lo, hi = sorted((y / n, 2 / 8))
        assert lo - 1e-12 <= mean <= hi + 1e-12


# ------------------------------------------------------------------ NRG / Pareto
def test_section9_nrg():
    assert noise_reduction_gain(1000, 280) == pytest.approx(0.72, abs=1e-12)


def test_nrg_edge_cases():
    assert noise_reduction_gain(1000, 1000) == 0.0
    assert noise_reduction_gain(1000, 0) == 1.0
    assert noise_reduction_gain(100, 150) == pytest.approx(-0.5)  # noise increased: not clipped
    r = noise_reduction_gain_result(0, 0)
    assert r.value is None and "V0 = 0" in r.reason
    with pytest.raises(ValueError):
        noise_reduction_gain(-1, 0)
    with pytest.raises(TypeError):
        noise_reduction_gain(10.0, 5)  # type: ignore[arg-type]


def test_pareto_frontier_basic():
    pts = [(0.72, 0.786), (0.5, 0.9), (0.1, 1.0), (0.4, 0.5), (0.72, 0.5)]
    assert pareto_frontier(pts) == [True, True, True, False, False]


def test_pareto_ties_and_degenerate_inputs():
    assert pareto_frontier([]) == []
    assert pareto_frontier([(0.5, 0.5)]) == [True]
    assert pareto_frontier([(0.5, 0.5), (0.5, 0.5)]) == [
        True,
        True,
    ]  # equal points: neither dominates
    assert pareto_frontier([(0.5, 0.5), (0.5, 0.6)]) == [False, True]
    assert pareto_frontier([(0.5, 0.5), (0.6, 0.5)]) == [False, True]
    for bad in ([(math.nan, 0.5)], [(0.5, math.inf)], [(True, 0.5)], [(0.5,)]):
        with pytest.raises(ValueError):
            pareto_frontier(bad)  # type: ignore[arg-type]


def test_property_frontier_is_nonempty_and_every_dominated_point_has_a_dominator_on_it():
    rng = random.Random(3)
    for _ in range(200):
        pts = [(rng.randint(0, 5) / 5, rng.randint(0, 5) / 5) for _ in range(rng.randint(1, 15))]
        flags = pareto_frontier(pts)
        assert any(flags)
        front = [p for p, f in zip(pts, flags, strict=True) if f]
        for p, f in zip(pts, flags, strict=True):
            if not f:
                assert any(q[0] >= p[0] and q[1] >= p[1] and q != p for q in front)
