import copy
from pathlib import Path

import pytest
import yaml
from conftest import BILLING_ROOT
from pydantic import ValidationError

from iide.config import DEFAULT_REPLAY_CONFIG, load_replay_config
from iide.detection.interface import load_attack_mapping
from iide.models import ReplayRecord, load_attack_definition

ATTACK_YAML = BILLING_ROOT / "attacks" / "credential_bruteforce.yaml"


def test_default_replay_config_values_are_the_preregistered_ones(config):
    assert config.min_valid_percent == 80
    assert config.flake_rate_limit == 0.05
    assert config.min_calibration_replays == 30  # D-05 amendment
    assert config.experiment_version == "phase2-0.1"
    assert config.attack_alert_aggregation == "any_expected_rule"


@pytest.mark.parametrize(
    "key,value",
    [
        ("min_valid_percent", 0),
        ("min_valid_percent", 101),
        ("flake_rate_limit", 0),
        ("flake_rate_limit", 1.5),
        ("replay_timeout_seconds", 0),
        ("attack_alert_aggregation", "all_expected_rules"),
        ("schema_version", "9.9"),
    ],
)
def test_invalid_config_values_are_rejected(tmp_path, key, value):
    data = yaml.safe_load(DEFAULT_REPLAY_CONFIG.read_text())
    data[key] = value
    path = tmp_path / "replay.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError):
        load_replay_config(path)


def test_unknown_config_keys_and_non_mapping_are_rejected(tmp_path):
    data = yaml.safe_load(DEFAULT_REPLAY_CONFIG.read_text())
    data["surprise"] = 1
    path = tmp_path / "replay.yaml"
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError):
        load_replay_config(path)
    path.write_text("- a\n- b\n")
    with pytest.raises(ValueError):
        load_replay_config(path)


def test_config_is_frozen(config):
    with pytest.raises(ValidationError):
        config.min_valid_percent = 50  # type: ignore[misc]


def test_attack_definition_matches_spec_section_4_3():
    attack = load_attack_definition(ATTACK_YAML)
    assert attack.id == "credential_bruteforce"
    assert attack.technique_id == "T1110"
    assert attack.criticality == 3
    assert attack.criticality_status == "PROVISIONAL"  # not yet double-annotated
    assert attack.required_event_types == ["auth.login_failed", "auth.lockout"]
    assert attack.expected_rule_ids == ["IIDE-BILLING-001"]
    assert attack.replay_count == 5
    assert attack.technique_mapping_status == "UNVERIFIED"  # must not claim verification


@pytest.mark.parametrize(
    "key,value",
    [
        ("criticality", 0),
        ("criticality", 4),
        ("replay_count", 0),
        ("id", "Bad-Id"),
        ("required_event_types", []),
        ("technique_mapping_status", "MAYBE"),
        ("criticality_status", "FINAL"),
    ],
)
def test_invalid_attack_definitions_are_rejected(tmp_path, key, value):
    data = yaml.safe_load(ATTACK_YAML.read_text())
    data[key] = value
    path = Path(tmp_path / "a.yaml")
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError):
        load_attack_definition(path)


def test_attack_mapping_loads():
    mapping = load_attack_mapping(BILLING_ROOT / "detection" / "mapping.json")
    assert mapping.attacks["credential_bruteforce"].expected_rule_ids == ["IIDE-BILLING-001"]


def test_replay_record_rejects_unknown_fields_and_bad_index():
    base = dict(
        replay_id="x",
        testbed_id="t",
        attack_id="a",
        program_ref="p",
        replay_index=1,
        correlation_id="c",
        started_at="2026-10-27T12:00:00Z",
        elapsed_seconds=0.1,
        valid=True,
    )
    ReplayRecord(**base)
    with pytest.raises(ValidationError):
        ReplayRecord(**{**copy.deepcopy(base), "replay_index": 0})
    with pytest.raises(ValidationError):
        ReplayRecord(**base, surprise=1)
    with pytest.raises(ValidationError):
        ReplayRecord(**{**base, "error_category": "ATTACK_FAILED"})
