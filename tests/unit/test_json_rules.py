import copy
import json
import uuid

import pytest
from conftest import BILLING_ROOT, make_event
from pydantic import ValidationError

from iide.detection.json_rules import JsonRuleDetector, RulePack

PACK_PATH = BILLING_ROOT / "detection" / "rules" / "billing_rule_pack.json"
RULE_ID = "IIDE-BILLING-001"


@pytest.fixture(scope="module")
def detector():
    return JsonRuleDetector.from_file(PACK_PATH)


def _result(detector, events):
    (result,) = [r for r in detector.evaluate(events) if r.rule_id == RULE_ID]
    return result


def _bruteforce_events(target="synthetic-account-9", failures=6, lockout=True):
    events = [make_event("auth.login_failed", target) for _ in range(failures)]
    if lockout:
        events.append(make_event("auth.lockout", target))
    return events


def test_rule_fires_on_bruteforce_pattern_and_reports_matched_types(detector):
    result = _result(detector, _bruteforce_events())
    assert result.fired
    assert result.matched_event_types == ("auth.lockout", "auth.login_failed")


def test_rule_fires_at_exactly_the_threshold(detector):
    assert _result(detector, _bruteforce_events(failures=5)).fired


def test_rule_is_silent_below_threshold(detector):
    result = _result(detector, _bruteforce_events(failures=4))
    assert not result.fired and result.matched_event_types == ()


def test_rule_is_silent_without_lockout_corroboration(detector):
    assert not _result(detector, _bruteforce_events(lockout=False)).fired


def test_rule_is_silent_on_lockout_alone(detector):
    assert not _result(detector, [make_event("auth.lockout")]).fired


def test_rule_is_silent_on_empty_stream(detector):
    assert not _result(detector, []).fired


def test_events_are_grouped_by_target_not_pooled(detector):
    events = [make_event("auth.login_failed", "synthetic-account-1") for _ in range(3)]
    events += [make_event("auth.login_failed", "synthetic-account-2") for _ in range(3)]
    events += [make_event("auth.lockout", "synthetic-account-1")]
    assert not _result(detector, events).fired


def test_duplicate_events_do_not_inflate_redundancy(detector):
    result = _result(detector, _bruteforce_events(failures=50))
    assert len(result.matched_event_types) == 2


def test_result_does_not_depend_on_random_ids_or_timestamps(detector):
    events = _bruteforce_events()
    reshuffled = copy.deepcopy(events)
    for i, e in enumerate(reshuffled):
        e["event_id"] = str(uuid.uuid4())
        e["timestamp"] = f"2030-01-01T00:00:{i:02d}Z"
    assert detector.evaluate(events) == detector.evaluate(reshuffled)


def test_malformed_events_are_ignored_not_fatal(detector):
    events = _bruteforce_events() + [{"event_type": 5}, {}, {"target_id": None}]
    assert _result(detector, events).fired


def test_rule_hash_is_stable_and_content_sensitive(detector):
    first = detector.rule_hash(RULE_ID)
    assert first == detector.rule_hash(RULE_ID)
    data = json.loads(PACK_PATH.read_text())
    data["rules"][0]["detection"]["all_of"][0]["min_count"] = 6
    assert JsonRuleDetector(RulePack.model_validate(data)).rule_hash(RULE_ID) != first


def test_unknown_rule_id_raises(detector):
    with pytest.raises(KeyError):
        detector.rule("IIDE-NOPE-999")


def _pack():
    return json.loads(PACK_PATH.read_text())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["rules"].append(copy.deepcopy(d["rules"][0])),  # duplicate rule_id
        lambda d: d["rules"][0].update(required_event_types=["auth.lockout"]),  # mismatch
        lambda d: d["rules"][0]["detection"]["all_of"].append(
            {"event_type": "auth.lockout", "min_count": 2}  # duplicate clause type
        ),
        lambda d: d["rules"][0]["detection"]["all_of"][0].update(min_count=0),
        lambda d: d["rules"][0]["detection"].update(group_by="severity"),
        lambda d: d["rules"][0].update(criticality=4),
        lambda d: d["rules"][0].update(rule_id="bad-id"),
        lambda d: d.update(format="sigma"),
        lambda d: d.update(rules=[]),
        lambda d: d.update(surprise=True),
    ],
    ids=[
        "duplicate-rule",
        "types-mismatch",
        "duplicate-clause",
        "min-count-zero",
        "bad-group-by",
        "bad-criticality",
        "bad-rule-id",
        "wrong-format",
        "no-rules",
        "extra-field",
    ],
)
def test_invalid_rule_packs_are_rejected(mutate):
    data = _pack()
    mutate(data)
    with pytest.raises(ValidationError):
        RulePack.model_validate(data)
