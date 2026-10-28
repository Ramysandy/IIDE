"""Catalog / attack / rule / mapping consistency, telemetry contract and freeze hashes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from iide.replay.runner import (
    TestbedContractError,
    compute_frozen_hashes,
    load_testbed,
    read_events,
)
from iide.replay.sandbox import run_in_fresh_process
from iide.telemetry.inventory import contract_violations
from iide.telemetry.normalize import normalize_events
from iide.telemetry.schema import validate_event

pytestmark = pytest.mark.integration


def test_billing_testbed_is_internally_consistent(testbed):
    assert testbed.testbed_id == "billing_api"
    assert set(testbed.attacks) == {"credential_bruteforce"}
    assert testbed.detector.rule_ids == ("IIDE-BILLING-001",)


def test_emitted_telemetry_matches_schema_and_catalog_contract(testbed):
    attack = testbed.attacks["credential_bruteforce"]
    with tempfile.TemporaryDirectory() as tmp:
        sink = Path(tmp) / "events.jsonl"
        sink.touch()
        result = run_in_fresh_process(
            testbed_dir=testbed.root,
            emulation_path=testbed.emulation_path(attack),
            sink_path=sink,
            correlation_id="replay-contract-001",
            timeout_seconds=60,
            workdir=Path(tmp),
        )
        assert result.exit_code == 0, result.stderr_tail
        raw_text = sink.read_text()
        events, malformed = read_events(sink)
    assert malformed == 0 and events
    # Emitted events must already be schema-valid *without* relying on the normalizer.
    for event in events:
        assert validate_event(event) == [], event
        assert contract_violations(event, testbed.catalog) == [], event
    assert normalize_events(events) == events  # service emits canonical form
    assert {e["event_type"] for e in events} >= set(attack.required_event_types)
    assert all(e["service"] == "billing_api" for e in events)
    assert "synthetic-wrong-guess" not in raw_text  # passphrases never reach telemetry
    assert "synthetic-fixture-passphrase" not in raw_text


def _rewrite(path: Path, edit) -> None:
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data))


def test_copy_of_testbed_loads_identically(testbed_copy):
    assert load_testbed(testbed_copy).testbed_id == "billing_api"


def test_mapping_disagreeing_with_attack_is_rejected(testbed_copy):
    _rewrite(
        testbed_copy / "detection" / "mapping.json",
        lambda d: d["attacks"]["credential_bruteforce"].update(
            expected_rule_ids=["IIDE-BILLING-002"]
        ),
    )
    with pytest.raises(TestbedContractError, match="expected_rule_ids"):
        load_testbed(testbed_copy)


def test_attack_missing_from_mapping_is_rejected(testbed_copy):
    _rewrite(testbed_copy / "detection" / "mapping.json", lambda d: d["attacks"].clear())
    with pytest.raises(TestbedContractError, match="missing from mapping"):
        load_testbed(testbed_copy)


def test_rule_not_listing_the_attack_is_rejected(testbed_copy):
    pack = testbed_copy / "detection" / "rules" / "billing_rule_pack.json"
    _rewrite(pack, lambda d: d["rules"][0].update(mapped_attack_ids=["something_else"]))
    with pytest.raises(TestbedContractError, match="mapped_attack_ids"):
        load_testbed(testbed_copy)


def test_stale_catalog_dependency_is_rejected(testbed_copy):
    path = testbed_copy / "event_catalog.yaml"
    entries = yaml.safe_load(path.read_text())
    for entry in entries:
        if entry["event_type"] == "auth.lockout":
            entry["required_by_rules"] = []
    path.write_text(yaml.safe_dump(entries))
    with pytest.raises(TestbedContractError, match="required_by_rules"):
        load_testbed(testbed_copy)


def test_missing_emulation_file_is_rejected(testbed_copy):
    (testbed_copy / "attacks" / "credential_bruteforce.py").unlink()
    with pytest.raises(TestbedContractError, match="emulation file"):
        load_testbed(testbed_copy)


def test_zero_or_multiple_rule_packs_are_rejected(testbed_copy):
    rules = testbed_copy / "detection" / "rules"
    (rules / "second.json").write_text((rules / "billing_rule_pack.json").read_text())
    with pytest.raises(TestbedContractError, match="exactly one rule pack"):
        load_testbed(testbed_copy)


def test_frozen_hashes_are_stable_and_cover_expected_artifacts(testbed):
    first = compute_frozen_hashes(testbed)
    assert first == compute_frozen_hashes(testbed)
    assert set(first) == {
        "rule_pack_hash",
        "attack_set_hash",
        "telemetry_contract_hash",
        "detector_engine_hash",
        "replay_harness_hash",
        "testbed_source_hash",
    }
    assert all(len(v) == 64 for v in first.values())


def test_editing_a_rule_changes_only_the_rule_pack_hash(testbed, testbed_copy):
    before = compute_frozen_hashes(testbed)
    pack = testbed_copy / "detection" / "rules" / "billing_rule_pack.json"
    _rewrite(pack, lambda d: d["rules"][0]["detection"]["all_of"][0].update(min_count=3))
    after = compute_frozen_hashes(load_testbed(testbed_copy))
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"rule_pack_hash"}


def test_editing_app_source_changes_only_the_source_hash(testbed, testbed_copy):
    before = compute_frozen_hashes(testbed)
    service = testbed_copy / "app" / "service.py"
    service.write_text(service.read_text() + "\n# harmless edit\n")
    after = compute_frozen_hashes(load_testbed(testbed_copy))
    assert {k for k in before if before[k] != after[k]} == {"testbed_source_hash"}
