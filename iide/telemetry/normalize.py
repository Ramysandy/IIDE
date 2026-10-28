"""Frozen, deliberately conservative event normalizer (spec 4.1, 6.2 step 5).

Only cosmetic representation differences are normalized:

* `timestamp`: any timezone-aware ISO-8601 string becomes UTC with a `Z` suffix.
  Naive timestamps are left unchanged (assuming UTC would hide a real defect).
* `severity`: surrounding whitespace is stripped and the value upper-cased.

`event_type` and every other field are left untouched: `event_type` is the stable
semantic identity and must never be rewritten. Anything this normalizer cannot make
canonical is left as-is so schema validation reports it (strict mode).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any


def normalize_timestamp(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return value
    if parsed.tzinfo is None:
        return value
    return parsed.astimezone(UTC).replace(tzinfo=None).isoformat() + "Z"


def normalize_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalized shallow copy; the input is not mutated."""
    out = dict(event)
    if "timestamp" in out:
        out["timestamp"] = normalize_timestamp(out["timestamp"])
    severity = out.get("severity")
    if isinstance(severity, str):
        out["severity"] = severity.strip().upper()
    return out


def normalize_events(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_event(e) for e in events]
