#!/usr/bin/env python3
"""Compare simpler baselines against the replay oracle on the calibration fixtures (spec 15).

This is a construct check, not a 144-run result. Default path never calls an LLM. Bandit is
run only if the CLI is on PATH. ``--with-llm`` calls Cohere on the four diffs when
``COHERE_API_KEY`` is set (never committed); trial keys should not be used for a 144-run.

Usage:
  python scripts/compare_baselines.py
  python scripts/compare_baselines.py --output-dir experiments/reports
  python scripts/compare_baselines.py --with-llm
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
    render_markdown,
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
    "IFG monitor is UNAVAILABLE (not implemented in this budget).",
    "Latent erosion (y=0) is an oracle-negative; flagging it is a false positive vs EROSION.",
]

LLM_OFF_LIMIT = (
    "LLM reviewer is UNAVAILABLE unless --with-llm and COHERE_API_KEY are both set; "
    "not claimed as run on the default path."
)
LLM_ON_LIMIT = (
    "LLM reviewer is Cohere command-r7b-12-2024 on four scripted diffs (trial-safe). "
    "Not a 144-run. seed_honored is not claimed. UNKNOWN/unparseable maps to UNAVAILABLE."
)


def _source_methods(
    baseline_app: Path,
    candidate_app: Path,
    catalog,
    security,
    diff: str,
    tests_passed: bool,
    *,
    call_llm: bool,
):
    return [
        functional_tests_method(tests_passed),
        logger_call_diff(baseline_app, candidate_app),
        static_event_literal_diff(baseline_app, candidate_app, catalog, security),
        sast_bandit(baseline_app, candidate_app),
        llm_reviewer(diff, call_llm=call_llm),
        ifg_monitor(),
    ]


def run_calibration(*, call_llm: bool = False) -> ComparisonReport:
    cases: list[CasePrediction] = []
    with tempfile.TemporaryDirectory(prefix="iide-g4-") as tmp:
        tmp_dir = Path(tmp)
        for spec in CALIBRATION_CASES:
            tb = load_testbed(TESTBEDS_DIR / spec.testbed_id)
            catalog = list(tb.catalog)
            security = security_bearing_event_types(tb.catalog)
            baseline_app, candidate_app, diff = materialise(spec, tmp_dir / spec.case_id)
            methods = _source_methods(
                baseline_app,
                candidate_app,
                catalog,
                security,
                diff,
                spec.tests_passed,
                call_llm=call_llm,
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
    if call_llm:
        note = (
            "Construct check against the replay-oracle labels of four scripted patches. "
            "Not a 144-run result. Cohere command-r7b-12-2024 was requested for the "
            "LLM reviewer (four HTTP calls at most)."
        )
        limits = [*LIMITATIONS, LLM_ON_LIMIT]
    else:
        note = (
            "Construct check against the replay-oracle labels of four scripted patches. "
            "Not a 144-run result. No LLM was called."
        )
        limits = [*LIMITATIONS, LLM_OFF_LIMIT]
    return build_report(
        cases,
        label="Phase 5 calibration suite (billing_api scripted patches)",
        note=note,
        limitations=limits,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "experiments" / "reports")
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Call Cohere on the four calibration diffs if COHERE_API_KEY is set. "
        "Writes g4_llm_reviewer.{md,json}; does not overwrite g4_calibration.",
    )
    args = parser.parse_args(argv)

    report = run_calibration(call_llm=args.with_llm)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = "g4_llm_reviewer" if args.with_llm else "g4_calibration"
    md = render_markdown(report)
    (args.output_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
