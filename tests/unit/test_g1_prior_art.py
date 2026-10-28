"""G1 memo and matrix exist, and the recorded decision is explicit (spec 18 / 20).

These tests do not establish novelty. They check that the sweep artifact is complete
and that gates.yaml was not auto-set to PASSED.
"""

from __future__ import annotations

import yaml

from iide.config import REPO_ROOT
from iide.runner.config import load_gates_config

MEMO = REPO_ROOT / "docs" / "g1_prior_art.md"
MATRIX = REPO_ROOT / "docs" / "g1_matrix.yaml"

REQUIRED_WORKS = {
    "overeager",
    "snare",
    "trace_tampering",
    "wesce",
    "secdrift",
    "iac_regression",
    "ifg",
    "towards_secure_logging",
    "aspi",
    "agenttelemetry",
    "alertguardian",
    "openai_incident",
    "sigma_regression",
}
REQUIRED_HEADINGS = (
    "## Decision",
    "## Combination test",
    "## Matrix",
    "## Search log",
    "## Limitations",
    "## What a human must still do",
)


def _matrix() -> dict:
    data = yaml.safe_load(MATRIX.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_g1_memo_states_an_explicit_recommended_decision():
    text = MEMO.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"missing {heading}"
    assert "**Recommended decision: GO**" in text
    assert "does not set `configs/gates.yaml`" in text or "does **not** set" in text


def test_g1_matrix_records_go_with_no_occupying_study():
    data = _matrix()
    assert data["recommended_decision"] == "GO"
    assert data["claim_scope"] == "combination_e1_e2_e3"
    assert data["occupying_studies"] == []
    assert data["human_signoff_required"] is True
    works = {row["id"]: row for row in data["works"]}
    missing = REQUIRED_WORKS - set(works)
    assert not missing, missing
    for row in data["works"]:
        assert row["occupies_g1_gap"] is False, row["id"]
        for key in ("e1", "e2", "e3", "e4", "e5"):
            assert row[key] in {"none", "adjacent", "overlap"}, (row["id"], key, row[key])
        assert row["read_depth"] in {"full_html", "full_pdf", "abstract", "web", "news"}
    assert len(data["searches"]) >= 8
    assert data["claim_restrictions"]
    assert data["narrow_if"]


def test_g1_gate_stays_open_until_a_human_signs_off():
    gates = load_gates_config()
    assert gates.gates["G1"].status == "OPEN"
    assert "g1_prior_art" in gates.gates["G1"].description
