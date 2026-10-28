"""Noise Reduction Gain and the (NRG, RC) Pareto frontier (spec 7.10)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from iide.scoring.types import MetricResult, require_count


def noise_reduction_gain_result(v0: int, v1: int) -> MetricResult:
    """NRG = 1 - V1/V0 over a fixed benign workload. Undefined when V0 = 0.

    Not clipped: V1 > V0 gives a negative gain, which is information, not an error.
    """
    require_count("v0", v0)
    require_count("v1", v1)
    if v0 == 0:
        return MetricResult(
            name="NRG", value=None, numerator=v1, denominator=0, reason="V0 = 0: NRG is undefined"
        )
    return MetricResult(name="NRG", value=1.0 - v1 / v0, numerator=v0 - v1, denominator=v0)


def noise_reduction_gain(v0: int, v1: int) -> float | None:
    return noise_reduction_gain_result(v0, v1).value


def pareto_frontier(points: Sequence[tuple[float, float]]) -> list[bool]:
    """``True`` for non-dominated points of ``(NRG, RC)``; both axes are maximised.

    A point is dominated if another point has both coordinates >= and at least one strictly >.
    Identical points do not dominate each other. Callers must pass valid observed points only
    (spec 7.10); non-finite coordinates are rejected rather than silently dropped.
    """
    for i, p in enumerate(points):
        if len(p) != 2:
            raise ValueError(f"point {i} must be a pair")
        for v in p:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"point {i} has a non-finite or non-numeric coordinate: {p!r}")
    flags = []
    for i, (x, y) in enumerate(points):
        dominated = any(
            j != i and x2 >= x and y2 >= y and (x2 > x or y2 > y)
            for j, (x2, y2) in enumerate(points)
        )
        flags.append(not dominated)
    return flags
