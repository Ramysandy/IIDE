#!/usr/bin/env python3
"""Compare simpler baselines against the replay oracle on the calibration fixtures (spec 15).

This is a construct check, not a 144-run result. It never calls an LLM. Bandit is run only
if the CLI is on PATH.

Usage:
  python scripts/compare_baselines.py
  python scripts/compare_baselines.py --output-dir experiments/reports
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.analysis.comparison import (  # noqa: E402
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
from iide.analysis.fixtures import CALIBRATION_CASES, materialise  # noqa: E402
from iide.config import TESTBEDS_DIR  # noqa: E402
from iide.replay.runner import load_testbed  # noqa: E402
from iide.telemetry.inventory import security_bearing_event_types  # noqa: E402

LIMITATIONS = [
    "Calibration fixtures are scripted patches, not agent runs. G4 is PROVISIONAL.",
    "functional_tests predicts NONE on every eligible run (tests already passed).",
    "logger_call_diff counts _emit*/.emit/logging.* calls; it cannot see a filtered no-op emit.",
    "static_event_literals only sees string constants; a leftover helper keeps the literal.",
    "dynamic_inventory is optional and uses one replay per attack, not the k=5 oracle.",
    "Bandit has no missing-telemetry query; if run, it still predicts NONE for this construct.",
    "CodeQL is recorded only if the codeql CLI is on PATH; it was not, and is not claimed as run.",
    "LLM reviewer and IFG monitor are UNAVAILABLE (not configured / not in budget).",
    "Latent erosion (y=0) is an oracle-negative; flagging it is a false positive vs EROSION.",
]


def _source_methods(
    baseline_app: Path, candidate_app: Path, catalog, security, diff: str, tests_passed: bool
):
    return [
        functional_tests_method(tests_passed),
        logger_call_diff(baseline_app, candidate_app),
        static_event_literal_diff(baseline_app, candidate_app, catalog, security),
        sast_bandit(baseline_app, candidate_app),
        llm_reviewer(diff),
        ifg_monitor(),
    ]


def run_calibration() -> ComparisonReport:
    cases: list[CasePrediction] = []
    with tempfile.TemporaryDirectory(prefix="iide-g4-") as tmp:
        tmp_dir = Path(tmp)
        for spec in CALIBRATION_CASES:
            tb = load_testbed(TESTBEDS_DIR / spec.testbed_id)
            catalog = list(tb.catalog)
            security = security_bearing_event_types(tb.catalog)
            baseline_app, candidate_app, diff = materialise(spec, tmp_dir / spec.case_id)
            methods = _source_methods(
                baseline_app, candidate_app, catalog, security, diff, spec.tests_passed
            )
            cases.append(
                CasePrediction(
                    case_id=spec.case_id,
                    oracle_y=spec.oracle_y,  # type: ignore[arg-type]
                    oracle_class=spec.oracle_class,
                    note=spec.note,
                    methods=methods,
                )
            )
    return build_report(
        cases,
        label="Phase 5 calibration suite (billing_api scripted patches)",
        note=(
            "Construct check against the replay-oracle labels of four scripted patches. "
            "Not a 144-run result. No LLM was called."
        ),
        limitations=LIMITATIONS,
    )


def render_markdown(report: ComparisonReport) -> str:
    lines = [
        f"# {report.label}",
        "",
        report.note,
        "",
        f"- G4 status: **{report.g4.status}**",
        f"- {report.g4.note}",
        "",
        "## Cases",
        "",
        "| Case | oracle y | class | functional | logger | literals | bandit | llm | ifg |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    order = [
        "functional_tests",
        "logger_call_diff",
        "static_event_literals",
        "sast_bandit",
        "llm_reviewer",
        "ifg_monitor",
    ]
    for c in report.cases:
        by = {m.method_id: m.prediction for m in c.methods}
        cells = " | ".join(by.get(k, "?") for k in order)
        lines.append(f"| {c.case_id} | {c.oracle_y} | {c.oracle_class} | {cells} |")
    lines += ["", "## Confusion vs confirmed erosion (y=1)", ""]
    lines.append("| Method | TP | FP | FN | TN | una | recall | FPR | FN cases |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for t in report.confusion:
        rec = "n/a" if t.recall is None else f"{t.recall:.2f}"
        fpr = "n/a" if t.fpr is None else f"{t.fpr:.2f}"
        lines.append(
            f"| {t.method_id} | {t.tp} | {t.fp} | {t.fn} | {t.tn} | {t.unavailable} | "
            f"{rec} | {fpr} | {', '.join(t.false_negatives) or '—'} |"
        )
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {x}" for x in report.limitations)
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "experiments" / "reports")
    args = parser.parse_args(argv)

    report = run_calibration()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    md = render_markdown(report)
    (args.output_dir / "g4_calibration.md").write_text(md, encoding="utf-8")
    (args.output_dir / "g4_calibration.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
