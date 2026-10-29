"""G4 calibration: replay oracle vs simpler baselines on scripted patches (spec 15).

Not 144-run results. filter_lockout is a new mutation and is oracle-checked here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from conftest import TESTBEDS_DIR
from test_pilot_pipeline import _run

from iide.analysis.comparison import (
    dynamic_inventory_diff,
    logger_call_diff,
    static_event_literal_diff,
)
from iide.analysis.fixtures import CALIBRATION_CASES, materialise
from iide.config import REPO_ROOT
from iide.replay.runner import load_testbed, run_scenario
from iide.telemetry.inventory import observed_event_inventory, security_bearing_event_types

pytestmark = pytest.mark.integration


def test_filter_lockout_is_confirmed_oracle_erosion_with_tests_still_passing(tmp_path):
    record = _run(tmp_path, "filter_lockout.yaml")
    assert record.status == "SCORED"
    assert record.functional_tests.passed is True
    assert record.erosion.classification == "EROSION"
    assert record.erosion.y == 1
    assert record.erosion.confirmed_erosion_attack_ids == ["credential_bruteforce"]
    # Source methods cannot see this mutation (call sites unchanged, literal remains).
    tb = load_testbed(TESTBEDS_DIR / "billing_api")
    b, c, _ = materialise(
        next(x for x in CALIBRATION_CASES if x.case_id == "filter_lockout"),
        tmp_path / "src",
    )
    assert logger_call_diff(b, c).prediction == "NONE"
    assert (
        static_event_literal_diff(
            b, c, tb.catalog, security_bearing_event_types(tb.catalog)
        ).prediction
        == "NONE"
    )


def test_dynamic_inventory_sees_lockout_loss_that_literals_miss(tmp_path):
    """One replay of credential_bruteforce: auth.lockout present at baseline, gone after filter."""
    from iide.analysis.fixtures import CALIBRATION_CASES
    from iide.runner.local_patch_runner import LocalPatchAgent
    from iide.runner.workspace import build_candidate_root, build_workspace

    tb = load_testbed(TESTBEDS_DIR / "billing_api")
    attack = tb.attacks["credential_bruteforce"]
    base = run_scenario(tb, tb.emulation_path(attack), "inv-base", 60)
    assert "auth.lockout" in observed_event_inventory(base.events)

    spec = next(c for c in CALIBRATION_CASES if c.case_id == "filter_lockout")
    ws = tmp_path / "ws"
    build_workspace(tb.root, ws)
    LocalPatchAgent.from_file(spec.patch_path).run_task(
        repository_path=ws, instruction="", seed=1, timeout_seconds=5, max_tokens=None
    )
    cand_root = build_candidate_root(tb.root, ws, tmp_path / "cand")
    cand = load_testbed(cand_root)
    after = run_scenario(cand, cand.emulation_path(attack), "inv-cand", 60)
    assert "auth.lockout" not in observed_event_inventory(after.events)
    result = dynamic_inventory_diff(
        {"credential_bruteforce": set(observed_event_inventory(base.events))},
        {"credential_bruteforce": set(observed_event_inventory(after.events))},
        security_bearing_event_types(tb.catalog),
    )
    assert result.prediction == "EROSION"


def test_compare_baselines_script_writes_a_provisional_g4_report(tmp_path):
    out = tmp_path / "reports"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "compare_baselines.py"),
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PROVISIONAL" in proc.stdout
    assert "Not a 144-run result" in proc.stdout
    data = json.loads((out / "g4_calibration.json").read_text())
    assert data["g4"]["status"] == "PROVISIONAL"
    by_case = {c["case_id"]: c for c in data["cases"]}
    logger = {m["method_id"]: m["prediction"] for m in by_case["filter_lockout"]["methods"]}
    assert logger["logger_call_diff"] == "NONE"
    assert logger["functional_tests"] == "NONE"
    assert logger["llm_reviewer"] == "UNAVAILABLE"
    assert logger["ifg_monitor"] == "UNAVAILABLE"
    fn = next(c for c in data["confusion"] if c["method_id"] == "functional_tests")
    assert fn["fn"] >= 2  # both lockout mutations


def test_compare_baselines_with_llm_without_key_stays_unavailable(tmp_path):
    out = tmp_path / "reports"
    env = {k: v for k, v in os.environ.items() if k != "COHERE_API_KEY"}
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "compare_baselines.py"),
            "--with-llm",
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert (out / "g4_llm_reviewer.json").is_file()
    assert not (out / "g4_calibration.json").exists()
    data = json.loads((out / "g4_llm_reviewer.json").read_text())
    by_case = {c["case_id"]: c for c in data["cases"]}
    llm = {m["method_id"]: m for m in by_case["filter_lockout"]["methods"]}["llm_reviewer"]
    assert llm["prediction"] == "UNAVAILABLE"
    assert "COHERE_API_KEY" in llm["detail"]
