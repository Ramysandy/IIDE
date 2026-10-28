import pytest

from iide.telemetry.schema import TelemetryValidationError, require_valid_event, validate_event


def test_spec_example_event_is_valid(spec_event):
    assert validate_event(spec_event) == []
    require_valid_event(spec_event)  # does not raise


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "event_id",
        "timestamp",
        "service",
        "event_type",
        "severity",
        "actor_id",
        "target_type",
        "target_id",
        "source",
        "correlation_id",
        "attributes",
    ],
)
def test_every_field_is_required(spec_event, field):
    del spec_event[field]
    errors = validate_event(spec_event)
    assert errors and field in " ".join(errors)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "2.0"),
        ("event_id", "not-a-uuid"),
        ("timestamp", "2026-10-27 12:00:00"),
        ("timestamp", "2026-10-27T12:00:00+00:00"),  # normalized form must use Z
        ("event_type", "AuthLoginFailed"),
        ("event_type", "auth"),
        ("severity", "warn"),
        ("severity", "FATAL"),
        ("actor_id", ""),
        ("attributes", []),
    ],
)
def test_invalid_values_are_rejected(spec_event, field, value):
    spec_event[field] = value
    assert validate_event(spec_event) != []


def test_unknown_top_level_fields_are_rejected(spec_event):
    spec_event["extra"] = 1
    assert validate_event(spec_event) != []


@pytest.mark.parametrize(
    "key",
    ["password", "passphrase", "api_key", "API-KEY", "access_token", "client_secret", "credential"],
)
def test_secret_like_attribute_names_are_rejected(spec_event, key):
    spec_event["attributes"][key] = "x"
    errors = validate_event(spec_event)
    assert errors and "attributes" in " ".join(errors)


def test_non_object_event_is_reported_not_raised():
    assert validate_event("nope")  # type: ignore[arg-type]


def test_require_valid_event_raises_with_details(spec_event):
    spec_event["severity"] = "nope"
    with pytest.raises(TelemetryValidationError, match="severity"):
        require_valid_event(spec_event)


def test_fractional_seconds_are_accepted(spec_event):
    spec_event["timestamp"] = "2026-10-27T12:00:00.123456Z"
    assert validate_event(spec_event) == []
