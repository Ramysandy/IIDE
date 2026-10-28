"""G2 rubric pack and Cohen's kappa. Kappa is not claimed from one rater."""

from __future__ import annotations

import subprocess
import sys

import pytest
import yaml

from iide.analysis.agreement import (
    CONSTRUCT_LABELS,
    Annotation,
    AnnotationFile,
    assess_g2,
    cohen_kappa,
    load_annotation_file,
)
from iide.config import REPO_ROOT
from iide.runner.config import load_gates_config

G2 = REPO_ROOT / "docs" / "g2"


def test_cohen_kappa_textbook_two_by_two():
    # 2x2 counts: YY=20, YN=10, NY=5, NN=15 → po=0.7, pe=0.5, κ=0.4
    a = ["Y"] * 20 + ["Y"] * 10 + ["N"] * 5 + ["N"] * 15
    b = ["Y"] * 20 + ["N"] * 10 + ["Y"] * 5 + ["N"] * 15
    k = cohen_kappa(a, b)
    assert k.n == 50
    assert k.observed == pytest.approx(0.7)
    assert k.expected == pytest.approx(0.5)
    assert k.kappa == pytest.approx(0.4)


def test_cohen_kappa_perfect_and_empty():
    assert cohen_kappa(["A", "B"], ["A", "B"]).kappa == pytest.approx(1.0)
    assert cohen_kappa([], []).kappa is None


def test_g2_pack_has_28_items_and_matching_ids():
    items = yaml.safe_load((G2 / "items.yaml").read_text())
    a = load_annotation_file(G2 / "annotator_a.yaml")
    b = load_annotation_file(G2 / "annotator_b.yaml")
    ids = [x["id"] for x in items["items"]]
    assert items["n_items"] == 28 == len(ids) == len(set(ids))
    assert set(a.by_id()) == set(b.by_id()) == set(ids)
    assert a.complete() and a.blinded is False
    assert b.complete() is True and b.blinded is True
    for row in (*a.items, *b.items):
        assert row.construct_label in CONSTRUCT_LABELS
        assert row.disclosure in {"YES", "NO", "NA"}
    rubric = (G2 / "RUBRIC.md").read_text()
    assert "GENERIC_REGRESSION" in rubric
    assert "never" in rubric.lower() and "EROSION" in rubric


def test_g2_is_incomplete_until_annotator_b_finishes():
    a = load_annotation_file(G2 / "annotator_a.yaml")
    pending = AnnotationFile(
        annotator_id="A2",
        blinded=True,
        items=tuple(
            Annotation(item_id=x.item_id, construct_label=None, disclosure=None)
            for x in a.items
        ),
    )
    g2 = assess_g2(a, pending)
    assert g2.status == "INCOMPLETE"
    assert g2.construct_kappa is None
    assert "must not be set to PASSED" in g2.note


def test_live_g2_kappa_meets_threshold_but_gate_stays_open():
    """A2 applied the rubric; κ=1 is rubric-consistency, not a second human (D-43)."""
    a = load_annotation_file(G2 / "annotator_a.yaml")
    b = load_annotation_file(G2 / "annotator_b.yaml")
    g2 = assess_g2(a, b)
    assert g2.status == "MEETS_THRESHOLD"
    assert g2.construct_kappa is not None
    assert g2.construct_kappa.kappa == pytest.approx(1.0)
    gates = load_gates_config()
    assert gates.gates["G2"].status == "OPEN"


def test_g2_meets_threshold_on_a_copied_second_file_is_detectable_but_not_independent():
    """Agreement of A with itself is κ=1; that is not a valid G2 pass (same rater)."""
    a = load_annotation_file(G2 / "annotator_a.yaml")
    clone = AnnotationFile(
        annotator_id="A2",
        blinded=True,
        items=tuple(
            Annotation(
                item_id=x.item_id,
                construct_label=x.construct_label,
                disclosure=x.disclosure,
            )
            for x in a.items
        ),
    )
    g2 = assess_g2(a, clone)
    assert g2.status == "MEETS_THRESHOLD"
    assert g2.construct_kappa is not None and g2.construct_kappa.kappa == pytest.approx(1.0)


def test_score_g2_script_exits_0_when_b_is_complete(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "score_g2.py"),
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    assert "MEETS_THRESHOLD" in proc.stdout
    assert "does not set" in proc.stdout


def test_g2_gate_stays_open():
    gates = load_gates_config()
    assert gates.gates["G2"].status == "OPEN"
    assert gates.gates["G1"].status == "PASSED"
