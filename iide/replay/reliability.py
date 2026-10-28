"""Attack-level detection decision and replay reliability (flake) measures.

Definitions (spec 6.2, 7.1; pre-registered choices in DECISIONS.md D-04, D-05):

* k  = planned replays, v = valid completed replays, f = valid replays in which the
  mapped alert fired.
* The attack is decidable only if v >= ceil(min_valid_percent/100 * k) (default 80%).
* If decidable, d(a, P) = 1 iff f >= ceil(v/2); otherwise 0. If not decidable the
  result is UNKNOWN (None), never "undetected".
"""

from __future__ import annotations

import math


def _check_int(name: str, value: int, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")


def _check_counts(fired_count: int, valid_replays: int, planned_k: int) -> None:
    _check_int("planned_k", planned_k, 1)
    _check_int("valid_replays", valid_replays, 0)
    _check_int("fired_count", fired_count, 0)
    if valid_replays > planned_k:
        raise ValueError(f"valid_replays ({valid_replays}) exceeds planned_k ({planned_k})")
    if fired_count > valid_replays:
        raise ValueError(f"fired_count ({fired_count}) exceeds valid_replays ({valid_replays})")


def min_valid_replays(planned_k: int, min_valid_percent: int = 80) -> int:
    """ceil(min_valid_percent/100 * planned_k); the numerator is an exact int."""
    _check_int("planned_k", planned_k, 1)
    _check_int("min_valid_percent", min_valid_percent, 1)
    if min_valid_percent > 100:
        raise ValueError("min_valid_percent must be <= 100")
    return math.ceil(min_valid_percent * planned_k / 100)


def attack_detected(
    fired_count: int,
    valid_replays: int,
    planned_k: int,
    *,
    min_valid_percent: int = 80,
) -> bool | None:
    """d(a, P) as a bool, or None (UNKNOWN) when too few replays were valid."""
    _check_counts(fired_count, valid_replays, planned_k)
    if valid_replays < min_valid_replays(planned_k, min_valid_percent):
        return None
    return fired_count >= math.ceil(valid_replays / 2)


def invalid_replay_rate(planned_k: int, valid_replays: int) -> float:
    _check_counts(0, valid_replays, planned_k)
    return (planned_k - valid_replays) / planned_k


def outcome_disagreement_rate(fired_count: int, valid_replays: int) -> float | None:
    """Fraction of valid replays that disagree with the majority outcome.

    None when there are no valid replays (undefined, not zero).
    """
    _check_int("valid_replays", valid_replays, 0)
    _check_int("fired_count", fired_count, 0)
    if fired_count > valid_replays:
        raise ValueError("fired_count exceeds valid_replays")
    if valid_replays == 0:
        return None
    return min(fired_count, valid_replays - fired_count) / valid_replays


def flake_rate(planned_k: int, valid_replays: int, fired_count: int) -> float:
    """(invalid replays + valid replays in the minority outcome) / planned_k.

    A replay "flakes" if it failed to complete or disagrees with the majority of
    valid replays. With no valid replays every replay is a flake (rate 1.0).
    """
    _check_counts(fired_count, valid_replays, planned_k)
    minority = min(fired_count, valid_replays - fired_count)
    return ((planned_k - valid_replays) + minority) / planned_k


def flake_within_limit(rate: float, limit: float) -> bool:
    """Strict comparison: the pilot requires a flake rate *below* the limit."""
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be in [0, 1]")
    if not 0.0 < limit < 1.0:
        raise ValueError("limit must be in (0, 1)")
    return rate < limit
