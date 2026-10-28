import pytest
import yaml
from conftest import BILLING_ROOT, make_event

from iide.telemetry.inventory import (
    contract_violations,
    load_event_catalog,
    observed_event_inventory,
    security_bearing_event_types,
)


@pytest.fixture(scope="module")
def catalog():
    return load_event_catalog(BILLING_ROOT / "event_catalog.yaml")


def test_catalog_marks_security_bearing_types(catalog):
    assert set(catalog) == {"auth.login_success", "auth.login_failed", "auth.lockout"}
    assert security_bearing_event_types(catalog) == {"auth.login_failed", "auth.lockout"}


def test_spec_example_event_satisfies_its_contract(catalog, spec_event):
    assert contract_violations(spec_event, catalog) == []


def test_missing_required_attribute_is_reported(catalog, spec_event):
    del spec_event["attributes"]["failure_count"]
    assert "failure_count" in " ".join(contract_violations(spec_event, catalog))


def test_none_counts_as_missing(catalog, spec_event):
    spec_event["attributes"]["failure_count"] = None
    assert contract_violations(spec_event, catalog) != []


def test_unknown_event_type_is_reported(catalog):
    assert contract_violations(make_event("auth.mystery"), catalog) != []
    assert contract_violations({}, catalog) != []


def test_inventory_counts_raw_events_per_type():
    events = [make_event("auth.login_failed")] * 3 + [make_event("auth.lockout")]
    assert observed_event_inventory(events) == {"auth.lockout": 1, "auth.login_failed": 3}


def test_duplicate_catalog_entries_are_rejected(tmp_path):
    entries = yaml.safe_load((BILLING_ROOT / "event_catalog.yaml").read_text())
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump([entries[0], entries[0]]))
    with pytest.raises(ValueError, match="duplicate"):
        load_event_catalog(path)


def test_catalog_must_be_a_list(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text("event_type: x")
    with pytest.raises(ValueError):
        load_event_catalog(path)
