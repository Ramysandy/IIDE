"""Shared scoring types (spec 7, 13).

Conventions used by every scoring function:

* An undefined measure is ``None`` plus a human-readable reason; never NaN and never a
  fabricated zero (spec 7).
* Inputs are validated and never silently coerced. ``bool`` is not accepted where a number
  is expected.
* ``theta`` values are *empirical proportions* (y/n over eligible cells), not posterior
  probabilities.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class MetricResult(BaseModel):
    """A measure with its exact numerator/denominator and, when undefined, the reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value: float | None
    numerator: float | None = None
    denominator: float | None = None
    reason: str | None = None  # set iff value is None
    details: dict[str, Any] = {}

    @model_validator(mode="after")
    def _reason_iff_undefined(self) -> MetricResult:
        if (self.value is None) != (self.reason is not None):
            raise ValueError("reason must be present exactly when value is None")
        if self.value is not None and not math.isfinite(self.value):
            raise ValueError("value must be finite")
        return self


class AttackOutcome(BaseModel):
    """One attack scored against baseline P0 and candidate P1 (spec 7.1, 7.3).

    ``d0``/``d1`` are True (detected), False (decided, not detected) or None (UNKNOWN).
    ``r0``/``r1`` are redundancy in *event types*: ``r(a, P)`` = distinct event types that
    participate in at least one fired expected rule (spec 8.2). ``rules0``/``rules1`` are the
    number of independently firing rules (the spec 7.3 sensitivity variant).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    attack_id: str
    criticality: Literal[1, 2, 3]
    d0: bool | None
    d1: bool | None
    r0: int = 0
    r1: int = 0
    rules0: int | None = None
    rules1: int | None = None

    @model_validator(mode="after")
    def _consistent(self) -> AttackOutcome:
        for name in ("r0", "r1", "rules0", "rules1"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.d0 is True and self.r0 < 1:
            raise ValueError("a detected attack must have r0 >= 1")
        if self.d1 is True and self.r1 < 1:
            raise ValueError("a detected attack must have r1 >= 1")
        if self.d0 is True and self.rules0 is not None and self.rules0 < 1:
            raise ValueError("a detected attack must have rules0 >= 1")
        if self.d1 is True and self.rules1 is not None and self.rules1 < 1:
            raise ValueError("a detected attack must have rules1 >= 1")
        return self


def require_proportion(name: str, value: float) -> float:
    """Validate a probability/proportion in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}")
    return float(value)


def require_count(name: str, value: int, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value
