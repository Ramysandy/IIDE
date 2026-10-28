import copy

import pytest

from iide.telemetry.normalize import normalize_event, normalize_events, normalize_timestamp
from iide.telemetry.schema import validate_event


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-10-27T12:00:00Z", "2026-10-27T12:00:00Z"),
        ("2026-10-27T12:00:00+00:00", "2026-10-27T12:00:00Z"),
        ("2026-10-27T08:00:00-04:00", "2026-10-27T12:00:00Z"),
        ("2026-10-27T12:00:00.5Z", "2026-10-27T12:00:00.500000Z"),
    ],
)
def test_aware_timestamps_become_utc_z(raw, expected):
    assert normalize_timestamp(raw) == expected


@pytest.mark.parametrize("raw", ["2026-10-27T12:00:00", "garbage", "", 12345, None])
def test_unnormalizable_timestamps_are_left_unchanged(raw):
    assert normalize_timestamp(raw) == raw


def test_severity_is_stripped_and_uppercased(spec_event):
    spec_event["severity"] = " warn "
    assert normalize_event(spec_event)["severity"] == "WARN"


def test_normalization_makes_cosmetic_drift_schema_valid(spec_event):
    spec_event["severity"] = "warn"
    spec_event["timestamp"] = "2026-10-27T08:00:00-04:00"
    assert validate_event(spec_event) != []
    assert validate_event(normalize_event(spec_event)) == []


def test_normalizer_never_touches_event_type_or_mutates_input(spec_event):
    spec_event["event_type"] = "Auth.Login_Failed"
    before = copy.deepcopy(spec_event)
    out = normalize_event(spec_event)
    assert out["event_type"] == "Auth.Login_Failed"  # semantic identity is not rewritten
    assert spec_event == before


def test_normalize_events_preserves_order(spec_event):
    a, b = copy.deepcopy(spec_event), copy.deepcopy(spec_event)
    a["actor_id"], b["actor_id"] = "first", "second"
    assert [e["actor_id"] for e in normalize_events([a, b])] == ["first", "second"]
