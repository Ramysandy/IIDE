"""Blinded S_sec / criticality / instruction worksheets. Does not set REVIEWED."""

from __future__ import annotations

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
    assert all(row["label"] is None for row in b_sec["items"])
    b_crit = _load("criticality", "annotator_b.yaml")
    assert all(row["criticality"] is None for row in b_crit["items"])
    b_ins = _load("instructions", "annotator_b.yaml")
    assert all(row["difficulty"] is None for row in b_ins["items"])
    a_sec = _load("s_sec", "annotator_a.yaml")
    assert a_sec["blinded"] is False
    assert {row["label"] for row in a_sec["items"]} <= {"SECURITY", "NOT_SECURITY"}
    assert (REVIEWS / "instructions" / "annotator_a.yaml").is_file() is False
