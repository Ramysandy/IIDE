"""G4 construct check on live agent diffs (spec 15). Not a 144-run."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

from iide.analysis.comparison import (
    CasePrediction,
    ComparisonReport,
    build_report,
    functional_tests_method,
    ifg_monitor,
    llm_reviewer,
    logger_call_diff,
    sast_bandit,
    static_event_literal_diff,
)
from iide.config import TESTBEDS_DIR
from iide.replay.runner import load_testbed
from iide.runner.records import RunRecord
from iide.runner.workspace import apply_unified_diff, build_workspace
from iide.telemetry.inventory import security_bearing_event_types

LIVE_LIMITATIONS = [
    "Live F1 composer-2.5 diffs, not the 144-run matrix.",
    "functional_tests predicts NONE on every eligible run (tests already passed).",
    "logger_call_diff counts _emit*/.emit/logging.* calls; it cannot see a filtered no-op emit.",
    "static_event_literals only sees string constants; a leftover helper keeps the literal.",
    "Bandit has no missing-telemetry query; if run, it still predicts NONE for this construct.",
    "LLM reviewer is UNAVAILABLE on this path (no --with-llm).",
    "IFG monitor is UNAVAILABLE.",
    "Ineligible runs (y is None) are dropped, not scored as NONE.",
]


def _methods(
    baseline_app: Path, candidate_app: Path, catalog, security, diff: str, tests_passed: bool
):
    return [
        functional_tests_method(tests_passed),
        logger_call_diff(baseline_app, candidate_app),
        static_event_literal_diff(baseline_app, candidate_app, catalog, security),
        sast_bandit(baseline_app, candidate_app),
        llm_reviewer(diff, call_llm=False),
        ifg_monitor(),
    ]


def compare_live_attempts(items: Sequence[tuple[RunRecord, Path]]) -> ComparisonReport:
    """``items`` are (primary record, attempt directory that holds ``diff.patch``)."""
    cases: list[CasePrediction] = []
    with tempfile.TemporaryDirectory(prefix="iide-g4-live-") as tmp:
        tmp_dir = Path(tmp)
        for rec, attempt_dir in items:
            if rec.dev_adapter or not rec.erosion.eligible or rec.erosion.y is None:
                continue
            tb = load_testbed(TESTBEDS_DIR / rec.testbed_id)
            catalog = list(tb.catalog)
            security = security_bearing_event_types(tb.catalog)
            ws = tmp_dir / rec.run_id
            build_workspace(TESTBEDS_DIR / rec.testbed_id, ws)
            diff_name = rec.diff.path or "diff.patch"
            diff_file = attempt_dir / diff_name
            diff_text = diff_file.read_text(encoding="utf-8") if diff_file.is_file() else ""
            if diff_text.strip():
                apply_unified_diff(ws, diff_text)
            methods = _methods(
                TESTBEDS_DIR / rec.testbed_id / "app",
                ws / "app",
                catalog,
                security,
                diff_text,
                bool(rec.functional_tests.passed),
            )
            cases.append(
                CasePrediction(
                    case_id=f"{rec.variant}:{rec.instruction_id}",
                    oracle_y=rec.erosion.y,  # type: ignore[arg-type]
                    oracle_class=rec.erosion.classification,
                    note=f"run_id={rec.run_id} lost={rec.erosion.confirmed_erosion_attack_ids}",
                    methods=methods,
                )
            )
    return build_report(
        cases,
        label="G4 on live F1 composer-2.5 diffs (billing_api seed 1)",
        note=(
            "Construct check against replay-oracle y of live agent cells. "
            "Not a 144-run result. No LLM was called."
        ),
        limitations=LIVE_LIMITATIONS,
        g4_context="these live F1 agent diffs",
    )
