from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from iide.config import TESTBEDS_DIR, ReplayConfig, load_replay_config
from iide.replay.runner import ScenarioRun, Testbed, load_testbed, run_scenario

BILLING_ROOT = TESTBEDS_DIR / "billing_api"
TESTBED_IDS = ["billing_api", "file_portal"]

# Spec section 4.1 example event (valid under the canonical schema).
SPEC_EXAMPLE_EVENT = {
    "schema_version": "1.0",
    "event_id": "123e4567-e89b-42d3-a456-426614174000",
    "timestamp": "2026-10-27T12:00:00Z",
    "service": "billing_api",
    "event_type": "auth.login_failed",
    "severity": "WARN",
    "actor_id": "synthetic-user-17",
    "target_type": "account",
    "target_id": "synthetic-account-9",
    "source": "auth_service",
    "correlation_id": "replay-bruteforce-001",
    "attributes": {"failure_count": 7, "threshold": 5},
}


def attack_cases() -> list[tuple[str, str]]:
    """(testbed_id, attack_id) for every attack in every pilot testbed."""
    return [
        (tb_id, attack_id)
        for tb_id in TESTBED_IDS
        for attack_id in sorted(load_testbed(TESTBEDS_DIR / tb_id).attacks)
    ]


@pytest.fixture
def spec_event() -> dict:
    return copy.deepcopy(SPEC_EXAMPLE_EVENT)


@pytest.fixture(scope="session")
def config() -> ReplayConfig:
    return load_replay_config()


@pytest.fixture(scope="session")
def testbed() -> Testbed:
    """The billing_api testbed (used by Phase 1 tests)."""
    return load_testbed(BILLING_ROOT)


@pytest.fixture(scope="session")
def testbeds() -> dict[str, Testbed]:
    return {tb_id: load_testbed(TESTBEDS_DIR / tb_id) for tb_id in TESTBED_IDS}


@pytest.fixture(scope="session")
def run_cached(config, testbeds):
    """Run a scenario ('benign' or an attack id) once per session and cache the result."""
    cache: dict[tuple[str, str], ScenarioRun] = {}

    def _run(tb_id: str, name: str) -> ScenarioRun:
        key = (tb_id, name)
        if key not in cache:
            tb = testbeds[tb_id]
            path = tb.benign_path if name == "benign" else tb.emulation_path(tb.attacks[name])
            cid = "benign-001" if name == "benign" else f"replay-{name}-001"
            run = run_scenario(tb, path, cid, config.replay_timeout_seconds)
            assert run.error_category is None, run.error_detail
            cache[key] = run
        return cache[key]

    return _run


def copy_testbed(tb_id: str, dest_parent: Path) -> Path:
    dest = dest_parent / tb_id
    shutil.copytree(
        TESTBEDS_DIR / tb_id,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "baseline"),
    )
    return dest


@pytest.fixture
def testbed_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the billing_api testbed that tests may mutate."""
    return copy_testbed("billing_api", tmp_path)


def make_event(event_type: str, target_id: str = "synthetic-account-9", **overrides) -> dict:
    event = copy.deepcopy(SPEC_EXAMPLE_EVENT)
    event["event_type"] = event_type
    event["target_id"] = target_id
    event.update(overrides)
    return event
