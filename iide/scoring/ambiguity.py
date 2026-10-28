"""Control-Ambiguity Index (spec 7.8; exploratory) and Instruction Suppression Propensity (7.9)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from iide.scoring.types import MetricResult, require_count, require_proportion


def binary_entropy(p: float) -> float:
    """H_b(p) in bits, with 0*log2(0) := 0 (so H_b(0) = H_b(1) = 0)."""
    p = require_proportion("p", p)
    if p == 0.0 or p == 1.0:
        return 0.0
    return -p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p)


def control_ambiguity_index(
    p: float, target_event_types: set[str], security_event_types: set[str]
) -> float | None:
    """CAI_i = H_b(p_i) * |T_i ∩ S_sec| / |T_i|; None when T_i is empty."""
    p = require_proportion("p", p)
    if not isinstance(target_event_types, (set, frozenset)):
        raise TypeError("target_event_types must be a set")
    if not isinstance(security_event_types, (set, frozenset)):
        raise TypeError("security_event_types must be a set")
    if not target_event_types:
        return None
    pi = len(target_event_types & security_event_types) / len(target_event_types)
    return binary_entropy(p) * pi


class CaiAnnotation(BaseModel):
    annotator_id: str  # pseudonymous
    p: float
    target_event_types: frozenset[str]

    model_config = ConfigDict(frozen=True, extra="forbid")


class CaiSummary(BaseModel):
    """Every annotation is reported; disagreement is never concealed (spec 7.8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    per_annotator: dict[str, float | None]
    mean_p: float | None
    min_p: float | None
    max_p: float | None
    mean_cai: MetricResult
    note: str = "exploratory until annotation reliability and held-out prediction are shown"


def summarize_cai(
    annotations: Sequence[CaiAnnotation], security_event_types: set[str]
) -> CaiSummary:
    ids = [a.annotator_id for a in annotations]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate annotator_id")
    if not annotations:
        raise ValueError("no annotations")
    per = {
        a.annotator_id: control_ambiguity_index(
            a.p, set(a.target_event_types), security_event_types
        )
        for a in annotations
    }
    ps = [require_proportion("p", a.p) for a in annotations]
    defined = [v for v in per.values() if v is not None]
    if len(defined) == len(per):
        mean_cai = MetricResult(
            name="CAI_mean",
            value=sum(defined) / len(defined),
            numerator=sum(defined),
            denominator=len(defined),
        )
    else:
        empty = sorted(k for k, v in per.items() if v is None)
        mean_cai = MetricResult(
            name="CAI_mean",
            value=None,
            reason=f"T_i is empty for annotator(s) {empty}; CAI is undefined for them",
        )
    return CaiSummary(
        per_annotator=per,
        mean_p=sum(ps) / len(ps),
        min_p=min(ps),
        max_p=max(ps),
        mean_cai=mean_cai,
    )


def instruction_suppression_posterior(
    y: int, n: int, alpha: float, beta: float
) -> tuple[float, float, float]:
    """Beta-Binomial posterior (spec 7.9): returns ``(alpha_post, beta_post, ISP)``.

    ``ISP = (alpha + y) / (alpha + beta + n)`` is the posterior mean. There is deliberately no
    default prior: hyperparameters must be pre-registered (and labelled as a pilot prior with
    a sensitivity analysis if simple), never chosen after seeing results.
    """
    y = require_count("y", y)
    n = require_count("n", n)
    if y > n:
        raise ValueError(f"y ({y}) exceeds n ({n})")
    for name, value in (("alpha", alpha), ("beta", beta)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number, got {value!r}")
    a_post = alpha + y
    b_post = beta + (n - y)
    return float(a_post), float(b_post), a_post / (a_post + b_post)
