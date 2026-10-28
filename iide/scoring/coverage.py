"""RC, ED, LEI and detection debt (spec 7.1-7.3, 7.11, 8.1).

``A0`` is the set of attacks detected at baseline (``d0 is True``). Attacks outside ``A0``
are never scored for erosion (spec 7.1) and are listed as exclusions.

UNKNOWN candidate detection (``d1 is None``) for an attack in ``A0`` is neither "lost" nor
"retained": the affected measure is returned as ``None`` with a reason, and RC/ED also carry
explicit lower/upper bounds in ``details`` (DECISIONS D-26).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from iide.replay.reliability import attack_detected as attack_detected  # re-export (D-04)
from iide.scoring.types import AttackOutcome, MetricResult

Redundancy = Literal["event_types", "rules"]


def _check_unique(attacks: Sequence[AttackOutcome]) -> None:
    ids = [a.attack_id for a in attacks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate attack_id in attack outcomes")


def baseline_detected_set(attacks: Sequence[AttackOutcome]) -> list[AttackOutcome]:
    """A0 = {a : d(a, P0) = 1}."""
    _check_unique(attacks)
    return [a for a in attacks if a.d0 is True]


def _weight(a: AttackOutcome, unit_weights: bool) -> int:
    return 1 if unit_weights else a.criticality


def retained_coverage_result(
    attacks: Sequence[AttackOutcome], *, unit_weights: bool = False
) -> MetricResult:
    name = "RC_unit" if unit_weights else "RC"
    a0 = baseline_detected_set(attacks)
    if not a0:
        return MetricResult(
            name=name,
            value=None,
            denominator=0,
            reason="A0 is empty: no attack was detected at baseline (denominator 0)",
        )
    den = sum(_weight(a, unit_weights) for a in a0)
    retained = sum(_weight(a, unit_weights) for a in a0 if a.d1 is True)
    unknown = [a for a in a0 if a.d1 is None]
    if unknown:
        unknown_weight = sum(_weight(a, unit_weights) for a in unknown)
        return MetricResult(
            name=name,
            value=None,
            numerator=retained,
            denominator=den,
            reason=(
                f"{len(unknown)} attack(s) in A0 have UNKNOWN candidate detection: "
                f"{sorted(a.attack_id for a in unknown)}"
            ),
            details={
                "lower_bound": retained / den,
                "upper_bound": (retained + unknown_weight) / den,
            },
        )
    return MetricResult(name=name, value=retained / den, numerator=retained, denominator=den)


def retained_coverage(
    attacks: Sequence[AttackOutcome], *, unit_weights: bool = False
) -> float | None:
    return retained_coverage_result(attacks, unit_weights=unit_weights).value


def erosion_depth(rc: float | None) -> float | None:
    """ED = 1 - RC (spec 7.2); undefined when RC is undefined."""
    if rc is None:
        return None
    if isinstance(rc, bool) or not isinstance(rc, (int, float)) or not 0.0 <= rc <= 1.0:
        raise ValueError(f"rc must be in [0, 1] or None, got {rc!r}")
    return 1.0 - float(rc)


def erosion_depth_result(
    attacks: Sequence[AttackOutcome], *, unit_weights: bool = False
) -> MetricResult:
    rc = retained_coverage_result(attacks, unit_weights=unit_weights)
    name = "ED_unit" if unit_weights else "ED"
    if rc.value is not None:
        assert rc.numerator is not None and rc.denominator is not None
        return MetricResult(
            name=name,
            value=1.0 - rc.value,
            numerator=rc.denominator - rc.numerator,
            denominator=rc.denominator,
        )
    details = {}
    if "lower_bound" in rc.details:
        details = {
            "lower_bound": 1.0 - rc.details["upper_bound"],
            "upper_bound": 1.0 - rc.details["lower_bound"],
        }
    return MetricResult(
        name=name,
        value=None,
        numerator=None if rc.numerator is None else rc.denominator - rc.numerator,  # type: ignore[operator]
        denominator=rc.denominator,
        reason=rc.reason,
        details=details,
    )


def latent_erosion_index_result(
    attacks: Sequence[AttackOutcome],
    *,
    unit_weights: bool = False,
    redundancy: Redundancy = "event_types",
) -> MetricResult:
    """LEI (spec 7.3).

    Numerator: only attacks in A0 that are *still detected* contribute
    ``c_a * max(0, r(a,P0) - r(a,P1))``; a lost attack's redundancy is erosion (ED), not
    latent erosion. ``redundancy="rules"`` is the independently-firing-rule sensitivity
    variant; it is never substituted for the primary event-type definition.
    """
    if redundancy not in ("event_types", "rules"):
        raise ValueError(f"unknown redundancy variant: {redundancy!r}")
    name = "LEI" + ("_unit" if unit_weights else "") + ("_rules" if redundancy == "rules" else "")
    a0 = baseline_detected_set(attacks)
    if not a0:
        return MetricResult(
            name=name,
            value=None,
            denominator=0,
            reason="A0 is empty: no attack was detected at baseline (denominator 0)",
        )

    def r0(a: AttackOutcome) -> int | None:
        return a.r0 if redundancy == "event_types" else a.rules0

    def r1(a: AttackOutcome) -> int | None:
        return a.r1 if redundancy == "event_types" else a.rules1

    missing = [a.attack_id for a in a0 if r0(a) is None or (a.d1 is True and r1(a) is None)]
    if missing:
        return MetricResult(
            name=name,
            value=None,
            reason=f"redundancy variant {redundancy!r} unavailable for {sorted(missing)}",
        )
    den = sum(_weight(a, unit_weights) * r0(a) for a in a0)  # type: ignore[operator]
    unknown = [a for a in a0 if a.d1 is None]
    if unknown:
        return MetricResult(
            name=name,
            value=None,
            denominator=den,
            reason=(
                f"{len(unknown)} attack(s) in A0 have UNKNOWN candidate detection: "
                f"{sorted(a.attack_id for a in unknown)}"
            ),
        )
    num = sum(
        _weight(a, unit_weights) * max(0, r0(a) - r1(a))  # type: ignore[operator]
        for a in a0
        if a.d1 is True
    )
    return MetricResult(name=name, value=num / den, numerator=num, denominator=den)


def latent_erosion_index(
    attacks: Sequence[AttackOutcome],
    *,
    unit_weights: bool = False,
    redundancy: Redundancy = "event_types",
) -> float | None:
    return latent_erosion_index_result(
        attacks, unit_weights=unit_weights, redundancy=redundancy
    ).value


def detection_debt(ed_by_step: Sequence[float | None]) -> float | None:
    """Exploratory (spec 7.11): sum of ED_t; undefined if any step's ED is undefined."""
    if not ed_by_step:
        raise ValueError("ed_by_step is empty")
    if any(e is None for e in ed_by_step):
        return None
    for e in ed_by_step:
        if isinstance(e, bool) or not isinstance(e, (int, float)) or not 0.0 <= e <= 1.0:
            raise ValueError(f"ED values must be in [0, 1], got {e!r}")
    return float(sum(ed_by_step))  # type: ignore[arg-type]


class CoverageScores(BaseModel):
    """Everything the coverage family reports for one candidate program."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    a0_attack_ids: list[str]
    excluded: dict[str, str]  # attack_id -> reason it is outside A0
    lost_attack_ids: list[str]  # EROSION: d0=1, d1=0
    latent_attack_ids: list[str]  # LATENT_EROSION: still detected, r1 < r0
    unknown_attack_ids: list[str]  # d0=1, d1 UNKNOWN
    rc: MetricResult
    ed: MetricResult
    lei: MetricResult
    # Spec 8.1 and 7.3 sensitivity analyses, reported separately and never as the primary.
    rc_unit: MetricResult
    ed_unit: MetricResult
    lei_unit: MetricResult
    lei_rules: MetricResult


def score_coverage(attacks: Sequence[AttackOutcome]) -> CoverageScores:
    a0 = baseline_detected_set(attacks)
    excluded = {
        a.attack_id: ("baseline detection UNKNOWN" if a.d0 is None else "not detected at baseline")
        for a in attacks
        if a.d0 is not True
    }
    return CoverageScores(
        a0_attack_ids=sorted(a.attack_id for a in a0),
        excluded=excluded,
        lost_attack_ids=sorted(a.attack_id for a in a0 if a.d1 is False),
        latent_attack_ids=sorted(a.attack_id for a in a0 if a.d1 is True and a.r1 < a.r0),
        unknown_attack_ids=sorted(a.attack_id for a in a0 if a.d1 is None),
        rc=retained_coverage_result(attacks),
        ed=erosion_depth_result(attacks),
        lei=latent_erosion_index_result(attacks),
        rc_unit=retained_coverage_result(attacks, unit_weights=True),
        ed_unit=erosion_depth_result(attacks, unit_weights=True),
        lei_unit=latent_erosion_index_result(attacks, unit_weights=True),
        lei_rules=latent_erosion_index_result(attacks, redundancy="rules"),
    )
