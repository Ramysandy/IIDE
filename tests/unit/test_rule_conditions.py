"""`where` conditions in the JSON-rule engine, and catalog security-basis validation."""

from __future__ import annotations

import pytest
from conftest import make_event
from pydantic import ValidationError

from iide.detection.json_rules import Condition, JsonRuleDetector, RulePack
from iide.telemetry.inventory import CatalogEntry


def pack(*clauses, group_by="target_id") -> JsonRuleDetector:
    rule = {
        "rule_id": "IIDE-TEST-001",
        "title": "t",
        "rule_version": "1",
        "criticality": 1,
        "mapped_attack_ids": ["a"],
        "required_event_types": [c["event_type"] for c in clauses],
        "detection": {"group_by": group_by, "all_of": list(clauses)},
    }
    return JsonRuleDetector(
        RulePack.model_validate(
            {
                "schema_version": "1.0",
                "format": "iide-json-rules-v1",
                "description": "test",
                "rule_pack_id": "p",
                "rule_pack_version": "1",
                "rules": [rule],
            }
        )
    )


def fires(detector, events) -> bool:
    (result,) = detector.evaluate(events)
    return result.fired


def role_event(new_role, target="synthetic-account-3"):
    return make_event(
        "auth.role_changed", target, attributes={"previous_role": "viewer", "new_role": new_role}
    )


ADMIN_RULE = {
    "event_type": "auth.role_changed",
    "min_count": 1,
    "where": {"new_role": {"eq": "admin"}},
}


def test_eq_condition_matches_only_the_given_value():
    d = pack(ADMIN_RULE)
    assert fires(d, [role_event("admin")])
    assert not fires(d, [role_event("analyst")])


def test_where_filtered_events_do_not_count_toward_min_count():
    clause = {**ADMIN_RULE, "min_count": 2}
    d = pack(clause)
    assert not fires(d, [role_event("admin"), role_event("analyst"), role_event("viewer")])
    assert fires(d, [role_event("admin"), role_event("analyst"), role_event("admin")])


def test_missing_field_never_matches():
    d = pack(ADMIN_RULE)
    event = make_event("auth.role_changed", attributes={"previous_role": "viewer"})
    assert not fires(d, [event])


def test_eq_is_type_strict_so_true_is_not_one():
    d_true = pack({"event_type": "x.y", "min_count": 1, "where": {"flag": {"eq": True}}})
    assert fires(d_true, [make_event("x.y", attributes={"flag": True})])
    assert not fires(d_true, [make_event("x.y", attributes={"flag": 1})])
    assert not fires(d_true, [make_event("x.y", attributes={"flag": "true"})])


def test_gte_requires_real_numbers_and_is_inclusive():
    d = pack({"event_type": "x.y", "min_count": 1, "where": {"n": {"gte": 10}}})
    assert fires(d, [make_event("x.y", attributes={"n": 10})])
    assert fires(d, [make_event("x.y", attributes={"n": 10.5})])
    assert not fires(d, [make_event("x.y", attributes={"n": 9})])
    assert not fires(d, [make_event("x.y", attributes={"n": True})])  # bool is not a number
    assert not fires(d, [make_event("x.y", attributes={"n": "99"})])


def test_top_level_fields_are_looked_up_before_attributes():
    d = pack({"event_type": "x.y", "min_count": 1, "where": {"severity": {"eq": "ERROR"}}})
    assert fires(d, [make_event("x.y", severity="ERROR")])
    assert not fires(d, [make_event("x.y", severity="WARN")])


def test_every_where_condition_must_hold():
    d = pack(
        {
            "event_type": "x.y",
            "min_count": 1,
            "where": {"a": {"eq": 1}, "b": {"gte": 5}},
        }
    )
    assert fires(d, [make_event("x.y", attributes={"a": 1, "b": 5})])
    assert not fires(d, [make_event("x.y", attributes={"a": 1, "b": 4})])
    assert not fires(d, [make_event("x.y", attributes={"a": 2, "b": 5})])


def test_where_is_applied_per_clause_in_a_multi_clause_rule():
    d = pack(
        {"event_type": "approval.requested", "min_count": 1},
        {
            "event_type": "approval.completed",
            "min_count": 1,
            "where": {"self_approved": {"eq": True}},
        },
    )
    requested = make_event("approval.requested", "ap-1")
    own = make_event("approval.completed", "ap-1", attributes={"self_approved": True})
    other = make_event("approval.completed", "ap-1", attributes={"self_approved": False})
    assert fires(d, [requested, own])
    assert not fires(d, [requested, other])
    assert not fires(d, [own])


@pytest.mark.parametrize(
    "condition",
    [{}, {"eq": 1, "gte": 1}, {"eq": None}, {"gte": "5"}, {"gte": True}, {"lt": 3}, {"eq": [1]}],
    ids=["empty", "both", "null", "string-gte", "bool-gte", "unknown-op", "list"],
)
def test_invalid_conditions_are_rejected(condition):
    with pytest.raises(ValidationError):
        Condition.model_validate(condition)


@pytest.mark.parametrize(
    "where",
    [{"Bad Field": {"eq": 1}}, {"x": 1}, {"x": {"eq": 1, "gte": 1}}, {"": {"eq": 1}}],
    ids=["bad-name", "bare-value", "two-operators", "empty-name"],
)
def test_invalid_where_clauses_are_rejected_by_the_pack_schema(where):
    with pytest.raises(ValidationError):
        pack({"event_type": "x.y", "min_count": 1, "where": where})


# --------------------------------------------------------------- catalog basis


def entry(**overrides):
    base = dict(
        event_type="a.b",
        description="d",
        owning_module="m",
        security_bearing=True,
        security_basis="rule_dependency",
        required_fields=["actor_id"],
        required_by_attacks=[],
        required_by_rules=["IIDE-X-001"],
        benign_absence_expected=False,
        criticality_rationale="r",
    )
    base.update(overrides)
    return base


def test_valid_catalog_entries_are_accepted():
    CatalogEntry.model_validate(entry())
    CatalogEntry.model_validate(entry(security_basis="audit_category", required_by_rules=[]))
    CatalogEntry.model_validate(
        entry(security_bearing=False, security_basis="none", required_by_rules=[])
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"security_bearing": False, "security_basis": "none"},  # consumed by a rule
        {"security_basis": "audit_category"},  # consumed by a rule but basis differs
        {"security_bearing": False, "required_by_rules": []},  # bearing disagrees with basis
        {"security_basis": "none", "required_by_rules": []},  # bearing disagrees with basis
        {"security_basis": "vibes"},
    ],
)
def test_inconsistent_security_basis_is_rejected(overrides):
    with pytest.raises(ValidationError):
        CatalogEntry.model_validate(entry(**overrides))
