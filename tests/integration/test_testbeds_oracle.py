"""Phase 2 oracle checks, run against BOTH pilot testbeds.

Covers: scope (10-20 event types, 6-12 attacks), specificity (each attack fires exactly
its mapped rules), negative control, telemetry contract, catalog coverage and label
consistency. Scenario results are cached per session.
"""

from __future__ import annotations

import json

import pytest
from conftest import TESTBED_IDS, attack_cases

from iide.replay.runner import evaluate_events
from iide.telemetry.inventory import (
    contract_violations,
    observed_event_inventory,
    security_bearing_event_types,
)
from iide.telemetry.normalize import normalize_events
from iide.telemetry.schema import validate_event

pytestmark = pytest.mark.integration

ATTACK_CASES = attack_cases()
ATTACK_IDS = [f"{tb}:{a}" for tb, a in ATTACK_CASES]


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_testbed_meets_phase2_scope(testbeds, tb_id):
    tb = testbeds[tb_id]
    assert 10 <= len(tb.catalog) <= 20, "spec 5.1: 10-20 event types"
    assert 6 <= len(tb.attacks) <= 12, "spec 18 Phase 2: 6-12 attacks"
    assert tb.benign_path.is_file()
    assert all(a.replay_count == 5 for a in tb.attacks.values())


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_frozen_rules_have_unique_stable_ids_and_match_attack_criticality(testbeds, tb_id):
    tb = testbeds[tb_id]
    for rule in tb.detector.pack.rules:
        for attack_id in rule.mapped_attack_ids:
            assert rule.criticality == tb.attacks[attack_id].criticality, rule.rule_id
    assert {a.criticality for a in tb.attacks.values()} <= {1, 2, 3}


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_criticality_and_security_labels_are_marked_provisional(testbeds, tb_id):
    # Spec 8.1 / D-10: single-annotator values must not masquerade as adjudicated.
    tb = testbeds[tb_id]
    assert {a.criticality_status for a in tb.attacks.values()} == {"PROVISIONAL"}
    assert {a.technique_mapping_status for a in tb.attacks.values()} == {"UNVERIFIED"}


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_every_event_type_a_rule_consumes_is_security_bearing(testbeds, tb_id):
    tb = testbeds[tb_id]
    consumed = {t for r in tb.detector.pack.rules for t in r.required_event_types}
    assert consumed <= security_bearing_event_types(tb.catalog)


@pytest.mark.parametrize(("tb_id", "attack_id"), ATTACK_CASES, ids=ATTACK_IDS)
def test_attack_fires_exactly_its_mapped_rules(testbeds, run_cached, tb_id, attack_id):
    tb = testbeds[tb_id]
    attack = tb.attacks[attack_id]
    run = run_cached(tb_id, attack_id)
    _, invalid, outcomes = evaluate_events(tb, run.events)
    assert invalid == 0 and run.malformed_line_count == 0
    fired = {o.rule_id for o in outcomes if o.fired}
    assert fired == set(attack.expected_rule_ids), "missing detection or cross-fire"


@pytest.mark.parametrize(("tb_id", "attack_id"), ATTACK_CASES, ids=ATTACK_IDS)
def test_attack_emits_every_required_event_type(testbeds, run_cached, tb_id, attack_id):
    attack = testbeds[tb_id].attacks[attack_id]
    types = {e["event_type"] for e in run_cached(tb_id, attack_id).events}
    assert set(attack.required_event_types) <= types


@pytest.mark.parametrize(("tb_id", "attack_id"), ATTACK_CASES, ids=ATTACK_IDS)
def test_attack_redundancy_matches_the_mapped_rules(testbeds, run_cached, tb_id, attack_id):
    """r(a, P0) = distinct event types across fired mapped rules (spec 7.3 / 8.2)."""
    tb = testbeds[tb_id]
    attack = tb.attacks[attack_id]
    _, _, outcomes = evaluate_events(tb, run_cached(tb_id, attack_id).events)
    r = {t for o in outcomes if o.fired for t in o.matched_event_types}
    assert r == set(attack.required_event_types)
    assert len(r) >= 1


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_benign_workload_fires_no_rule(testbeds, run_cached, tb_id):
    tb = testbeds[tb_id]
    run = run_cached(tb_id, "benign")
    _, invalid, outcomes = evaluate_events(tb, run.events)
    assert invalid == 0 and run.events
    assert [o.rule_id for o in outcomes if o.fired] == []


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_scenarios_cover_every_cataloged_event_type(testbeds, run_cached, tb_id):
    tb = testbeds[tb_id]
    seen: set[str] = set()
    for name in [*tb.attacks, "benign"]:
        seen |= set(observed_event_inventory(run_cached(tb_id, name).events))
    assert seen == set(tb.catalog), (
        f"never emitted: {set(tb.catalog) - seen}; uncataloged: {seen - set(tb.catalog)}"
    )


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_all_emitted_telemetry_is_canonical_and_meets_the_catalog_contract(
    testbeds, run_cached, tb_id
):
    tb = testbeds[tb_id]
    for name in [*tb.attacks, "benign"]:
        run = run_cached(tb_id, name)
        for event in run.events:
            assert validate_event(event) == [], (name, event)
            assert contract_violations(event, tb.catalog) == [], (name, event)
            assert event["service"] == tb_id
        assert normalize_events(run.events) == run.events  # emitted in canonical form


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_no_credential_material_reaches_telemetry(testbeds, run_cached, tb_id):
    tb = testbeds[tb_id]
    text = json.dumps(
        [e for name in [*tb.attacks, "benign"] for e in run_cached(tb_id, name).events]
    )
    for needle in ("synthetic-fixture-passphrase", "synthetic-wrong-guess", "synthetic-typo"):
        assert needle not in text
    if tb_id == "billing_api":
        assert "synthetic-session-" not in text  # session ids are never logged


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_scenario_telemetry_is_repeatable_in_fresh_instances(testbeds, config, run_cached, tb_id):
    """Second independent run of every scenario yields the same event-type multiset."""
    from iide.replay.runner import run_scenario

    tb = testbeds[tb_id]
    for name in [*tb.attacks, "benign"]:
        path = tb.benign_path if name == "benign" else tb.emulation_path(tb.attacks[name])
        again = run_scenario(tb, path, "repeat-001", config.replay_timeout_seconds)
        assert again.error_category is None
        assert observed_event_inventory(again.events) == observed_event_inventory(
            run_cached(tb_id, name).events
        ), name
