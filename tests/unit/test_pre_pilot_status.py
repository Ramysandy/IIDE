"""Pre-pilot status report. Not a 144-run result."""

from __future__ import annotations

import os
import subprocess
import sys

from iide.analysis.status import build_status
from iide.config import REPO_ROOT


def test_pre_pilot_status_is_blocked_and_honest(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    status = build_status()
    assert status.ready_for_144_run is False
    assert status.gates["G1"] == "PASSED"
    assert status.gates["G2"] == "PASSED"
    assert status.gates["G3"] == "PASSED"
    assert status.gates["G4"] == "PASSED"
    assert status.g2_status == "MEETS_THRESHOLD"
    assert status.n_unconfigured_agents == 0
    assert status.n_unreviewed_instructions == 0
    assert status.blockers
    assert any("CURSOR_API_KEY" in b for b in status.blockers)
    assert all(t.hashes_match and t.exit_criterion_met for t in status.testbeds)
    assert all(t.max_flake_rate == 0.0 for t in status.testbeds)
    by_id = {d.id: d for d in status.definition_of_done}
    assert by_id["g1_documented"].met is True
    assert by_id["annotation_reliability"].met is True
    assert by_id["pilot_report_144"].met is False


def test_verify_reproducibility_script_writes_a_report(tmp_path):
    env = os.environ.copy()
    env.pop("CURSOR_API_KEY", None)
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_reproducibility.py"),
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Ready for 144-run: **False**" in proc.stdout
    assert (tmp_path / "pre_pilot_status.json").is_file()
    assert (tmp_path / "pre_pilot_status.md").is_file()
