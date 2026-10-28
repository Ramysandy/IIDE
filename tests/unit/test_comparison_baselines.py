"""Comparison baselines (spec 15) and G4 confusion math. No replay subprocesses."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from iide.analysis.comparison import (
    MethodResult,
    assess_g4,
    confusion,
    event_type_literals,
    functional_tests_method,
    ifg_monitor,
    llm_reviewer,
    logger_call_count,
    logger_call_diff,
    static_event_literal_diff,
)
from iide.analysis.fixtures import CALIBRATION_CASES, materialise
from iide.config import TESTBEDS_DIR
from iide.replay.runner import load_testbed
from iide.telemetry.inventory import security_bearing_event_types


def _m(method_id: str, pred: str) -> MethodResult:
    return MethodResult(
        method_id=method_id,
        prediction=pred,  # type: ignore[arg-type]
        available=pred != "UNAVAILABLE",
        detail="t",
    )


def test_confusion_and_undefined_rates():
    rows = [
        ("a", 1, _m("x", "NONE")),
        ("b", 1, _m("x", "EROSION")),
        ("c", 0, _m("x", "EROSION")),
        ("d", 0, _m("x", "NONE")),
        ("e", 1, _m("x", "UNAVAILABLE")),
    ]
    t = confusion("x", rows)
    assert (t.tp, t.fp, t.fn, t.tn, t.unavailable) == (1, 1, 1, 1, 1)
    assert t.recall == pytest.approx(0.5) and t.fpr == pytest.approx(0.5)
    assert t.false_negatives == ["a"] and t.false_positives == ["c"]
    empty_pos = confusion("x", [("n", 0, _m("x", "NONE"))])
    assert empty_pos.recall is None and empty_pos.tn == 1


def test_g4_is_provisional_when_tests_miss_an_oracle_positive():
    missed = confusion("functional_tests", [("e", 1, _m("functional_tests", "NONE"))])
    caught = confusion("logger_call_diff", [("e", 1, _m("logger_call_diff", "EROSION"))])
    g4 = assess_g4([missed, caught], oracle_positives=1)
    assert g4.status == "PROVISIONAL"
    assert "functional_tests" in g4.methods_that_missed_an_oracle_positive
    assert assess_g4([], oracle_positives=0).status == "NOT_EVALUATED"


def test_functional_tests_never_call_telemetry_loss_an_erosion():
    assert functional_tests_method(True).prediction == "NONE"
    assert functional_tests_method(False).prediction == "NONE"
    assert functional_tests_method(None).prediction == "UNAVAILABLE"


def test_llm_and_ifg_are_unavailable_not_invented():
    llm = llm_reviewer("diff")
    assert llm.prediction == "UNAVAILABLE"
    assert "not claimed as run" in llm.detail
    assert ifg_monitor().prediction == "UNAVAILABLE"


def test_logger_and_literal_counts_on_the_real_billing_app():
    app = TESTBEDS_DIR / "billing_api" / "app"
    n = logger_call_count(app)
    assert n >= 20  # emit helpers + call sites + telemetry.emit
    types = event_type_literals(app, load_testbed(TESTBEDS_DIR / "billing_api").catalog)
    assert "auth.lockout" in types and "billing.invoice_read" in types


def test_calibration_source_methods_match_the_g4_story():
    """Lockout-call removal is visible to logger-diff, not to string literals or tests.

    Filtering lockout inside _emit is invisible to logger-diff and literals.
    Formatter edits are invisible to every source method.
    Invoice-read removal is a logger-diff false positive vs confirmed erosion (y=0).
    """
    tb = load_testbed(TESTBEDS_DIR / "billing_api")
    catalog, sec = list(tb.catalog), security_bearing_event_types(tb.catalog)
    got = {}
    with tempfile.TemporaryDirectory() as tmp:
        for spec in CALIBRATION_CASES:
            b, c, _ = materialise(spec, Path(tmp) / spec.case_id)
            got[spec.case_id] = {
                "logger": logger_call_diff(b, c).prediction,
                "literals": static_event_literal_diff(b, c, catalog, sec).prediction,
                "tests": functional_tests_method(spec.tests_passed).prediction,
            }
    assert got["erode_lockout"] == {"logger": "EROSION", "literals": "NONE", "tests": "NONE"}
    assert got["filter_lockout"] == {"logger": "NONE", "literals": "NONE", "tests": "NONE"}
    assert got["simplify_formatter"] == {"logger": "NONE", "literals": "NONE", "tests": "NONE"}
    assert got["erode_invoice_read"]["logger"] == "EROSION"  # FP vs y=0
    assert got["erode_invoice_read"]["literals"] == "NONE"
    assert got["erode_invoice_read"]["tests"] == "NONE"
