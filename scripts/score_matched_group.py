#!/usr/bin/env python3
"""Score IAE/IIF/SR/DG on one matched wording triple (spec 7.4–7.7).

n=1 cluster: no bootstrap intervals. Not a 144-run.

Usage:
  python scripts/score_matched_group.py
  python scripts/score_matched_group.py --testbed billing_api --family F1 \\
      --agent pilot_agent_a --seed 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.analysis.matched import build_matched_report, render_markdown  # noqa: E402
from iide.config import TESTBEDS_DIR  # noqa: E402
from iide.replay.runner import load_testbed  # noqa: E402
from iide.runner.pilot import DEFAULT_RAW_DIR  # noqa: E402
from iide.runner.records import load_primary_records  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--testbed", default="billing_api")
    parser.add_argument("--family", default="F1")
    parser.add_argument("--agent", default="pilot_agent_a")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "experiments" / "reports")
    args = parser.parse_args(argv)

    records = load_primary_records(args.raw_dir)
    tb = load_testbed(TESTBEDS_DIR / args.testbed)
    report = build_matched_report(
        records,
        testbed=tb,
        testbed_id=args.testbed,
        family=args.family,
        agent_id=args.agent,
        seed=args.seed,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.testbed}_{args.family.lower()}_composer_seed{args.seed}"
    md = render_markdown(report)
    (args.output_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    (args.output_dir / f"{stem}.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(md)
    return 0 if report.n_cells else 2


if __name__ == "__main__":
    sys.exit(main())
