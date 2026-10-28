#!/usr/bin/env python3
"""Generate the 144-run pilot manifest and optionally execute it (spec 11.4, 12, 16).

DRY_RUN never calls an agent, an LLM, or any network API: it validates the manifest and
prints the run plan. A real execution is refused while G1/G2 are open or agents are
unconfigured, unless an override reason is recorded.

Usage:
  python scripts/run_pilot.py --dry-run
  python scripts/run_pilot.py --manifest-only
  python scripts/run_pilot.py --allow-open-gates "reason" --allow-unreviewed "reason"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.runner.manifest import write_manifest  # noqa: E402
from iide.runner.pilot import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_RAW_DIR,
    PilotRefused,
    default_configs,
    execute_plan,
    plan_pilot,
    render_plan,
    summarize_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the manifest and print the plan; never call an agent",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="write experiments/manifests/pilot.jsonl and exit",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--testbed", help="restrict to one testbed id")
    parser.add_argument("--limit", type=int, help="execute at most N remaining cells")
    parser.add_argument(
        "--force-rerun",
        action="store_true",
        help="create a new attempt even when a completed run already exists",
    )
    parser.add_argument(
        "--allow-open-gates",
        metavar="REASON",
        help="record a reason and run despite G1/G2 still being OPEN",
    )
    parser.add_argument(
        "--allow-unreviewed",
        metavar="REASON",
        help="record a reason and run despite DRAFT_UNREVIEWED instructions",
    )
    args = parser.parse_args(argv)

    experiment, agents, gates = default_configs()
    try:
        plan = plan_pilot(
            experiment,
            agents,
            gates,
            raw_dir=args.raw_dir,
            allow_open_gates=args.allow_open_gates,
            allow_unreviewed=args.allow_unreviewed,
            force_rerun=args.force_rerun,
            limit=args.limit,
            testbed_id=args.testbed,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    write_manifest(plan.rows, args.manifest)
    print(f"wrote {len(plan.rows)} rows to {args.manifest}")
    print(render_plan(plan, dry_run=args.dry_run or args.manifest_only))

    if plan.problems:
        return 2
    if args.dry_run or args.manifest_only:
        return 0

    try:
        records = execute_plan(
            plan,
            experiment,
            agents,
            raw_dir=args.raw_dir,
            allow_open_gates=args.allow_open_gates,
            allow_unreviewed=args.allow_unreviewed,
            force_rerun=args.force_rerun,
            limit=args.limit,
            testbed_id=args.testbed,
        )
    except PilotRefused as exc:
        print(f"refusing to start the pilot: {exc}", file=sys.stderr)
        return 2
    print(summarize_records(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
