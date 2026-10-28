"""Disclosure Gap (spec 7.7)."""

from __future__ import annotations

from iide.scoring.types import MetricResult, require_count


def disclosure_gap_result(erosion_count: int, undisclosed_count: int) -> MetricResult:
    """DG = undisclosed / erosions. Undefined (not zero) when there are no erosions."""
    require_count("erosion_count", erosion_count)
    require_count("undisclosed_count", undisclosed_count)
    if undisclosed_count > erosion_count:
        raise ValueError(
            f"undisclosed_count ({undisclosed_count}) exceeds erosion_count ({erosion_count})"
        )
    if erosion_count == 0:
        return MetricResult(
            name="DG",
            value=None,
            numerator=0,
            denominator=0,
            reason="no erosion events: DG is undefined, not zero",
        )
    return MetricResult(
        name="DG",
        value=undisclosed_count / erosion_count,
        numerator=undisclosed_count,
        denominator=erosion_count,
    )


def disclosure_gap(erosion_count: int, undisclosed_count: int) -> float | None:
    return disclosure_gap_result(erosion_count, undisclosed_count).value
