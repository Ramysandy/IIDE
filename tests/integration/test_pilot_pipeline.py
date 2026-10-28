"""End-to-end harness checks using the development adapter (spec 11).

These runs are flagged ``dev_adapter=True``. They exercise the pipeline; they are not
pilot results and they do not call any model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from conftest import TESTBEDS_DIR

from iide.config import REPO_ROOT
from iide.runner.config import load_agents_config, load_experiment_config
from iide.runner.instructions import load_instructions
from iide.runner.local_patch_runner import LocalPatchAgent
from iide.runner.manifest import generate_manifest
from iide.runner.orchestration import execute_run, load_oracle

pytestmark = pytest.mark.integration

PATCHES = REPO_ROOT / "tests" / "fixtures" / "local_patches"


def _row(instruction_id="F1-A", variant="ambiguous", seed=1):
    exp = load_experiment_config()
    rows = generate_manifest(exp, load_agents_config(), created_at="2026-10-28T00:00:00Z")
    return next(
        r
        for r in rows
        if r.testbed_id == "billing_api"
        and r.instruction_id == instruction_id
        and r.variant == variant
        and r.seed == seed
        and r.agent_id == "pilot_agent_a"
    )


def _run(tmp_path, patch_name, instruction_id="F1-A", variant="ambiguous"):
    oracle = load_oracle("billing_api")
    agent = LocalPatchAgent.from_file(PATCHES / patch_name)
    rec = load_instructions(TESTBEDS_DIR / "billing_api")[instruction_id]
    out = tmp_path / "attempt-1"
    return execute_run(
        _row(instruction_id, variant),
        agent=agent,
        oracle=oracle,
        instruction=rec,
        attempt_dir=out,
        attempt=1,
        gate_overrides=["harness integration test"],
    )


def test_empty_patch_is_no_op(tmp_path):
    record = _run(tmp_path, "empty.yaml")
    assert record.status == "NO_OP" and record.dev_adapter
    assert record.erosion.classification == "NOT_SCORED"
    assert record.diff.patch_empty
    assert (tmp_path / "attempt-1" / "run_record.json").is_file()
    assert (tmp_path / "attempt-1" / "diff.patch").is_file()


def test_syntax_error_is_build_error(tmp_path):
    record = _run(tmp_path, "syntax_error.yaml")
    assert record.status == "BUILD_ERROR"
    assert record.build.passed is False
    assert record.erosion.y is None


def test_status_change_is_test_fail_not_erosion(tmp_path):
    record = _run(tmp_path, "break_status.yaml")
    assert record.status == "TEST_FAIL"
    assert record.functional_tests.passed is False
    assert record.erosion.classification == "NOT_SCORED"


def test_formatter_edit_is_scored_with_no_erosion(tmp_path):
    record = _run(tmp_path, "simplify_formatter.yaml", instruction_id="F1-N", variant="neutral")
    assert record.status == "SCORED"
    assert record.erosion.classification == "NONE"
    assert record.erosion.y == 0
    assert record.erosion.eligible
    assert record.scores is not None and record.scores.rc.value == 1.0
    assert record.scores.lei.value == 0.0
    assert "app/formatting.py" in record.diff.changed_files
    assert record.isolation.oracle_material_in_workspace is False
    assert record.isolation.container is False  # honest: process-level only


def test_lockout_removal_is_confirmed_erosion(tmp_path):
    record = _run(tmp_path, "erode_lockout.yaml")
    assert record.status == "SCORED"
    assert record.dev_adapter is True
    assert record.erosion.classification == "EROSION"
    assert record.erosion.y == 1
    assert record.erosion.confirmed_erosion_attack_ids == ["credential_bruteforce"]
    assert record.erosion.unconfirmed_miss_attack_ids == []
    assert record.scores is not None
    assert (record.scores.rc.numerator, record.scores.rc.denominator) == (11, 14)
    missed = next(a for a in record.attack_results if a.attack_id == "credential_bruteforce")
    assert missed.miss_confirmed is True
    dumped = json.loads((tmp_path / "attempt-1" / "run_record.json").read_text())
    assert dumped["status"] == "SCORED" and dumped["dev_adapter"] is True


def test_run_pilot_dry_run_writes_the_manifest_and_calls_no_agent(tmp_path):
    manifest = tmp_path / "pilot.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_pilot.py"),
            "--dry-run",
            "--manifest",
            str(manifest),
            "--raw-dir",
            str(tmp_path / "raw"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "DRY RUN" in proc.stdout
    assert "144 cells" in proc.stdout
    assert "BLOCKERS" in proc.stdout
    lines = [ln for ln in manifest.read_text().splitlines() if ln.strip()]
    assert len(lines) == 144


def test_real_pilot_refuses_while_cursor_api_key_is_missing(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "CURSOR_API_KEY"}
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_pilot.py"),
            "--manifest",
            str(tmp_path / "m.jsonl"),
            "--raw-dir",
            str(tmp_path / "raw"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert proc.returncode == 2
    assert "refusing to start the pilot" in proc.stderr
    assert "CURSOR_API_KEY" in proc.stderr or "CURSOR_API_KEY" in proc.stdout
