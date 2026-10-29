#!/usr/bin/env python3
"""G4 construct check on live agent diffs (spec 15). Never calls an LLM. Not a 144-run.

Usage:
  python scripts/compare_live.py
  python scripts/compare_live.py --testbed billing_api --family F1 --agent pilot_agent_a --seed 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.analysis.comparison import render_markdown  # noqa: E402
from iide.analysis.live_g4 import compare_live_attempts  # noqa: E402
from iide.runner.pilot import DEFAULT_RAW_DIR  # noqa: E402
from iide.runner.records import attempt_dir, load_primary_records  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--testbed", default="billing_api")
    parser.add_argument("--family", default="F1")
    parser.add_argument("--agent", default="pilot_agent_a")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "experiments" / "reports")
    args = parser.parse_args(argv)

    records = [
        r
        for r in load_primary_records(args.raw_dir)
        if r.testbed_id == args.testbed
        and r.family == args.family
        and r.agent_id == args.agent
        and r.seed == args.seed
        and not r.dev_adapter
    ]
    items = [(r, attempt_dir(args.raw_dir, r.run_id, r.attempt)) for r in records]
    report = compare_live_attempts(items)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    md = render_markdown(report)
    (args.output_dir / "g4_f1_live.md").write_text(md, encoding="utf-8")
    (args.output_dir / "g4_f1_live.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(md)
    return 0 if report.cases else 2


if __name__ == "__main__":
    sys.exit(main())
