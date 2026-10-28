#!/usr/bin/env python
"""Score a candidate replay ledger against a testbed's recorded baseline ledger.

Default candidate is the baseline ledger itself. That is a *self-comparison* used to check the
scoring pipeline end to end (it must give RC=1, ED=0, LEI=0); it is not an experimental result.

Usage:
  python scripts/score_replays.py --testbed billing_api
  python scripts/score_replays.py --testbed billing_api --candidate path/to/ledger.jsonl \
      --label mutated-lockout --output-dir experiments/reports/x
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iide.analysis.reports import build_coverage_report, render_json, render_markdown
from iide.config import TESTBEDS_DIR, load_replay_config
from iide.models import ReplayRecord
from iide.replay.runner import load_testbed
from iide.scoring.adapters import build_attack_outcome


def _read_ledger(path: Path) -> list[ReplayRecord]:
    return [
        ReplayRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--testbed", required=True)
    parser.add_argument("--candidate", type=Path, help="candidate replay ledger (JSONL)")
    parser.add_argument("--label")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)

    root = TESTBEDS_DIR / args.testbed
    tb = load_testbed(root)
    config = load_replay_config()
    baseline = _read_ledger(root / "baseline" / "baseline_replay_runs.jsonl")
    self_comparison = args.candidate is None
    candidate = baseline if self_comparison else _read_ledger(args.candidate)

    outcomes = []
    for attack_id, attack in sorted(tb.attacks.items()):
        outcomes.append(
            build_attack_outcome(
                attack,
                [r for r in baseline if r.attack_id == attack_id],
                [r for r in candidate if r.attack_id == attack_id],
                config,
            )
        )
    report = build_coverage_report(
        outcomes,
        label=args.label
        or (f"{args.testbed} baseline self-comparison" if self_comparison else args.testbed),
        note=(
            "Self-comparison (candidate == baseline): a harness check, NOT an experimental result."
            if self_comparison
            else "Candidate ledger scored against the recorded baseline ledger."
        ),
    )
    markdown = render_markdown(report)
    print(markdown)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "coverage_report.md").write_text(markdown, encoding="utf-8")
        (args.output_dir / "coverage_report.json").write_text(render_json(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
