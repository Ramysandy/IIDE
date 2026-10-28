"""scripts/run_baseline.py end to end (writes only to a temp directory)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from conftest import TESTBED_IDS

from iide.config import REPO_ROOT, TESTBEDS_DIR
from iide.models import BaselineCoverage, ReplayRecord
from iide.replay.runner import compute_frozen_hashes, load_testbed

pytestmark = pytest.mark.integration

SCRIPT = REPO_ROOT / "scripts" / "run_baseline.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=REPO_ROOT
    )


def test_baseline_script_writes_valid_artifacts_and_refuses_overwrite(tmp_path):
    """Fast path: --calibrate 0 skips calibration, so the exit criterion must NOT be met."""
    out = tmp_path / "baseline"
    proc = _run("--testbed", "file_portal", "--output-dir", str(out), "--calibrate", "0")
    assert proc.returncode == 1, proc.stdout + proc.stderr  # incomplete evidence, honestly
    assert "calibration" in (proc.stdout + proc.stderr).lower()

    coverage = BaselineCoverage.model_validate_json((out / "baseline_coverage.json").read_text())
    assert not coverage.exit_criterion_met
    assert coverage.functional_tests.passed
    assert len(coverage.attacks) == 6 and len(coverage.baseline_detected_attack_ids) == 6
    assert coverage.calibration_replays_per_attack == 0
    for attack in coverage.attacks:
        assert (attack.status, attack.fired_count, attack.valid_replays, attack.planned_k) == (
            "DETECTED",
            5,
            5,
            5,
        )
        assert attack.flake_rate == 0.0 and attack.flake_within_limit
        assert attack.unexpected_fired_rule_ids == []
    assert coverage.negative_control.fired_rule_ids == []
    assert coverage.negative_control.valid_replays == coverage.negative_control.replays
    assert coverage.isolation["container"] is False  # honest about isolation level
    assert "benign_set_hash" in coverage.frozen_hashes

    lines = (out / "baseline_replay_runs.jsonl").read_text().splitlines()
    records = [ReplayRecord.model_validate_json(line) for line in lines]
    assert len(records) == 30 and all(r.valid and r.attack_alert_fired for r in records)
    assert not (out / "flake_calibration.json").exists()

    again = _run("--testbed", "file_portal", "--output-dir", str(out), "--calibrate", "0")
    assert again.returncode == 2 and "refusing to overwrite" in again.stderr


def test_baseline_script_rejects_negative_calibration(tmp_path):
    proc = _run("--testbed", "billing_api", "--output-dir", str(tmp_path), "--calibrate", "-1")
    assert proc.returncode == 2


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_committed_baseline_matches_the_current_frozen_artifacts(tb_id):
    """Freeze policy (spec 6.1): editing a frozen artifact after the baseline invalidates it."""
    root = TESTBEDS_DIR / tb_id
    path = root / "baseline" / "baseline_coverage.json"
    assert path.is_file(), "run `make baseline-all` first"
    coverage = BaselineCoverage.model_validate(json.loads(path.read_text()))
    current = compute_frozen_hashes(load_testbed(root))
    assert coverage.frozen_hashes == current, (
        "frozen artifacts changed since the baseline was recorded; "
        "a new baseline (and experiment version) is required"
    )
    assert coverage.exit_criterion_met
    assert coverage.experiment_version == "phase2-0.1"
    assert coverage.calibration_replays_per_attack >= 30
