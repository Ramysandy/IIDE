"""scripts/run_baseline.py end to end (writes only to a temp directory)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from conftest import BILLING_ROOT

from iide.config import REPO_ROOT
from iide.models import BaselineCoverage, ReplayRecord
from iide.replay.runner import compute_frozen_hashes, load_testbed

pytestmark = pytest.mark.integration

SCRIPT = REPO_ROOT / "scripts" / "run_baseline.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO_ROOT
    )


def test_baseline_script_writes_valid_artifacts_and_refuses_overwrite(tmp_path):
    out = tmp_path / "baseline"
    proc = _run("--testbed", "billing_api", "--output-dir", str(out))
    assert proc.returncode == 0, proc.stdout + proc.stderr

    coverage = BaselineCoverage.model_validate_json((out / "baseline_coverage.json").read_text())
    assert coverage.phase1_exit_criterion_met
    assert coverage.functional_tests.passed
    assert coverage.baseline_detected_attack_ids == ["credential_bruteforce"]
    (attack,) = coverage.attacks
    assert (attack.status, attack.fired_count, attack.valid_replays, attack.planned_k) == (
        "DETECTED",
        5,
        5,
        5,
    )
    assert attack.flake_rate == 0.0 and attack.flake_within_limit
    assert coverage.isolation["container"] is False  # honest about isolation level

    lines = (out / "baseline_replay_runs.jsonl").read_text().splitlines()
    records = [ReplayRecord.model_validate_json(line) for line in lines]
    assert len(records) == 5 and all(r.valid and r.attack_alert_fired for r in records)

    again = _run("--testbed", "billing_api", "--output-dir", str(out))
    assert again.returncode == 2 and "refusing to overwrite" in again.stderr


def test_baseline_script_rejects_negative_calibration(tmp_path):
    proc = _run("--testbed", "billing_api", "--output-dir", str(tmp_path), "--calibrate", "-1")
    assert proc.returncode == 2


def test_committed_baseline_matches_the_current_frozen_artifacts():
    """Freeze policy (spec 6.1): editing a frozen artifact after the baseline invalidates it."""
    path = BILLING_ROOT / "baseline" / "baseline_coverage.json"
    assert path.is_file(), "run `make baseline` first"
    coverage = BaselineCoverage.model_validate(json.loads(path.read_text()))
    current = compute_frozen_hashes(load_testbed(BILLING_ROOT))
    assert coverage.frozen_hashes == current, (
        "frozen artifacts changed since the baseline was recorded; "
        "a new baseline (and experiment version) is required"
    )
    assert coverage.phase1_exit_criterion_met
