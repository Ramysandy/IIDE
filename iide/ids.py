"""Deterministic identifiers (spec section 12 style: truncated sha256 of joined parts)."""

from __future__ import annotations

import hashlib

_SEPARATOR = "|"


def stable_id(*parts: str, length: int = 16) -> str:
    """`sha256("|".join(parts))[:length]`.

    Parts must be non-empty strings that do not contain the separator, otherwise
    different part tuples could collide (e.g. ("a|b", "c") vs ("a", "b|c")).
    """
    if not parts:
        raise ValueError("stable_id requires at least one part")
    if not 1 <= length <= 64:
        raise ValueError("length must be between 1 and 64")
    for part in parts:
        if not isinstance(part, str):
            raise TypeError(f"id parts must be str, got {type(part).__name__}")
        if part == "":
            raise ValueError("id parts must be non-empty")
        if _SEPARATOR in part:
            raise ValueError(f"id parts must not contain {_SEPARATOR!r}: {part!r}")
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()[:length]


def replay_id(
    testbed_id: str,
    attack_id: str,
    program_ref: str,
    experiment_version: str,
    replay_index: int,
) -> str:
    """Stable identifier of one replay of `attack_id` against `program_ref`."""
    _check_replay_index(replay_index)
    return stable_id(testbed_id, attack_id, program_ref, experiment_version, str(replay_index))


def replay_correlation_id(attack_id: str, replay_index: int) -> str:
    """Correlation ID injected into replay traffic, e.g. `replay-credential_bruteforce-001`."""
    _check_replay_index(replay_index)
    if not attack_id:
        raise ValueError("attack_id must be non-empty")
    return f"replay-{attack_id}-{replay_index:03d}"


def _check_replay_index(replay_index: int) -> None:
    if isinstance(replay_index, bool) or not isinstance(replay_index, int):
        raise TypeError("replay_index must be an int")
    if replay_index < 1:
        raise ValueError("replay_index is 1-based and must be >= 1")
