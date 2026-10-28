"""Scoring on real replay ledgers: committed baselines and the Phase 2 mutation fixtures.

These are harness checks on throwaway mutants. They are not findings about any agent.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from conftest import TESTBED_IDS, copy_testbed
from test_telemetry_removal import remove_emit_call

from iide.config import REPO_ROOT, TESTBEDS_DIR
from iide.models import ReplayRecord
from iide.replay.runner import load_testbed, run_attack_replays
from iide.scoring.adapters import build_attack_outcome
from iide.scoring.coverage import score_coverage

pytestmark = pytest.mark.integration


def _ledger(tb_id):
    path = TESTBEDS_DIR / tb_id / "baseline" / "baseline_replay_runs.jsonl"
    return [ReplayRecord.model_validate_json(x) for x in path.read_text().splitlines() if x]


def _outcomes(tb, baseline, candidate, config):
    return [
        build_attack_outcome(
            attack,
            [r for r in baseline if r.attack_id == aid],
            [r for r in candidate if r.attack_id == aid],
            config,
        )
        for aid, attack in sorted(tb.attacks.items())
    ]


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_baseline_self_comparison_gives_no_erosion(testbeds, config, tb_id):
    base = _ledger(tb_id)
    scores = score_coverage(_outcomes(testbeds[tb_id], base, base, config))
    assert len(scores.a0_attack_ids) == 6 and scores.excluded == {}
    assert (scores.rc.value, scores.ed.value, scores.lei.value) == (1.0, 0.0, 0.0)
    assert scores.lost_attack_ids == [] and scores.latent_attack_ids == []
    assert scores.rc_unit.value == 1.0 and scores.lei_rules.value == 0.0


def test_lockout_removal_mutant_scores_as_erosion_with_expected_rc(testbed, config, tmp_path):
    root = copy_testbed("billing_api", tmp_path)
    remove_emit_call(root, "_emit_lockout")
    mutant = load_testbed(root)
    candidate = run_attack_replays(mutant, "credential_bruteforce", config, program_ref="mutated")
    others = [r for r in _ledger("billing_api") if r.attack_id != "credential_bruteforce"]
    scores = score_coverage(_outcomes(testbed, _ledger("billing_api"), candidate + others, config))
    # billing criticalities: 3+3+2+3+2+1 = 14; the lost attack has c=3 => RC = 11/14
    assert scores.lost_attack_ids == ["credential_bruteforce"]
    assert (scores.rc.numerator, scores.rc.denominator) == (11, 14)
    assert scores.ed.value == pytest.approx(3 / 14)
    assert scores.latent_attack_ids == []


def test_invoice_read_removal_mutant_scores_as_latent_erosion(testbed, config, tmp_path):
    root = copy_testbed("billing_api", tmp_path)
    remove_emit_call(root, "_emit_invoice_read")
    mutant = load_testbed(root)
    candidate = run_attack_replays(mutant, "bulk_invoice_export", config, program_ref="mutated")
    others = [r for r in _ledger("billing_api") if r.attack_id != "bulk_invoice_export"]
    scores = score_coverage(_outcomes(testbed, _ledger("billing_api"), candidate + others, config))
    assert scores.lost_attack_ids == [] and scores.latent_attack_ids == ["bulk_invoice_export"]
    assert scores.rc.value == 1.0 and scores.ed.value == 0.0  # still detected
    assert scores.lei.numerator == 3 and scores.lei.value > 0  # c=3, r 2 -> 1
    assert scores.lei_unit.numerator == 1


def test_score_replays_script_self_comparison_is_labelled_not_a_result(tmp_path):
    out = tmp_path / "report"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "score_replays.py"),
            "--testbed",
            "file_portal",
            "--output-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "NOT an experimental result" in proc.stdout
    assert "RC: 1.000000 = 14/14" in proc.stdout or "RC: 1.000000" in proc.stdout
    assert (out / "coverage_report.md").is_file() and (out / "coverage_report.json").is_file()
