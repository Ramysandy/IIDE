from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from iide.config import TESTBEDS_DIR, ReplayConfig, load_replay_config
from iide.replay.runner import Testbed, load_testbed

BILLING_ROOT = TESTBEDS_DIR / "billing_api"

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


@pytest.fixture
def spec_event() -> dict:
    return copy.deepcopy(SPEC_EXAMPLE_EVENT)


@pytest.fixture(scope="session")
def config() -> ReplayConfig:
    return load_replay_config()


@pytest.fixture(scope="session")
def testbed() -> Testbed:
    return load_testbed(BILLING_ROOT)


@pytest.fixture
def testbed_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the billing_api testbed that tests may mutate."""
    dest = tmp_path / "billing_api"
    shutil.copytree(
        BILLING_ROOT,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "baseline"),
    )
    return dest


def make_event(event_type: str, target_id: str = "synthetic-account-9", **overrides) -> dict:
    event = copy.deepcopy(SPEC_EXAMPLE_EVENT)
    event["event_type"] = event_type
    event["target_id"] = target_id
    event.update(overrides)
    return event
