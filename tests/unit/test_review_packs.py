"""Blinded S_sec / criticality / instruction worksheets. Does not set REVIEWED."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

import yaml

from iide.config import REPO_ROOT, TESTBEDS_DIR
from iide.replay.runner import load_testbed
from iide.runner.config import load_experiment_config
from iide.runner.instructions import load_instructions

REVIEWS = REPO_ROOT / "docs" / "reviews"


def _load(pack: str, name: str) -> dict[str, Any]:
    return yaml.safe_load((REVIEWS / pack / name).read_text(encoding="utf-8"))


def test_review_packs_are_blinded_and_complete():
    exp = load_experiment_config()
    n_events = sum(len(load_testbed(TESTBEDS_DIR / tb).catalog) for tb in exp.testbeds)
    n_attacks = sum(len(load_testbed(TESTBEDS_DIR / tb).attacks) for tb in exp.testbeds)
    n_instr = 0
    for tb in exp.testbeds:
        n_instr += sum(
            1
            for r in load_instructions(TESTBEDS_DIR / tb).values()
            if r.family in exp.families
        )
    s_sec = _load("s_sec", "items.yaml")
    crit = _load("criticality", "items.yaml")
    instr = _load("instructions", "items.yaml")
    assert len(s_sec["items"]) == n_events
    assert len(crit["items"]) == n_attacks
    assert len(instr["items"]) == n_instr == 24
    for item in s_sec["items"]:
        assert "security_bearing" not in item
        assert "security_basis" not in item
    for item in crit["items"]:
        assert "criticality" not in item
    b_sec = _load("s_sec", "annotator_b.yaml")
    assert b_sec["blinded"] is True
    assert {row["label"] for row in b_sec["items"]} <= {"SECURITY", "NOT_SECURITY"}
    assert all(row["label"] is not None for row in b_sec["items"])
    b_crit = _load("criticality", "annotator_b.yaml")
    assert {row["criticality"] for row in b_crit["items"]} <= {1, 2, 3}
    b_ins = _load("instructions", "annotator_b.yaml")
    assert {row["difficulty"] for row in b_ins["items"]} <= {1, 2, 3, 4, 5}
    assert {row["scope_similarity"] for row in b_ins["items"]} <= {"MATCHED", "UNMATCHED"}
    a_sec = _load("s_sec", "annotator_a.yaml")
    assert a_sec["blinded"] is False
    assert {row["label"] for row in a_sec["items"]} <= {"SECURITY", "NOT_SECURITY"}
    assert (REVIEWS / "instructions" / "annotator_a.yaml").is_file() is False
    for rec in load_instructions(TESTBEDS_DIR / "billing_api").values():
        if rec.family in exp.families:
            assert rec.review_status == "REVIEWED"


def test_export_review_packs_refuses_to_overwrite_completed_b():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "export_review_packs.py")],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "already has labels" in proc.stderr + proc.stdout
