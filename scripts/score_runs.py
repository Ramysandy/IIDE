#!/usr/bin/env python3
"""Summarise primary attempts under experiments/raw (spec 13/16).

Development-adapter runs are listed but counted separately: they are not pilot results.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.runner.pilot import DEFAULT_RAW_DIR  # noqa: E402
from iide.runner.records import RunRecord, select_primary  # noqa: E402


def _load_primaries(raw_dir: Path) -> list[RunRecord]:
    out = []
    if not raw_dir.is_dir():
        return out
    for run_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        attempts = []
        for d in sorted(run_dir.glob("attempt-*")):
            path = d / "run_record.json"
            if path.is_file():
                attempts.append(RunRecord.model_validate_json(path.read_text(encoding="utf-8")))
        primary = select_primary(attempts)
        if primary is not None:
            out.append(primary)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    records = _load_primaries(args.raw_dir)
    if args.json:
        print(json.dumps([r.model_dump(mode="json") for r in records], indent=2, sort_keys=True))
        return 0

    print(f"primary attempts: {len(records)}")
    if not records:
        return 0
    print(
        f"{'run_id':<16} {'tb':<12} {'instr':<6} {'var':<10} {'agent':<16} "
        f"{'status':<12} {'y':<4} {'dev':<3} RC"
    )
    for r in records:
        rc = None if r.scores is None else r.scores.rc.value
        rc_s = "n/a" if rc is None else f"{rc:.3f}"
        y = "-" if r.erosion.y is None else str(r.erosion.y)
        print(
            f"{r.run_id:<16} {r.testbed_id:<12} {r.instruction_id:<6} {r.variant:<10} "
            f"{r.agent_id:<16} {r.status:<12} {y:<4} {'Y' if r.dev_adapter else 'N':<3} {rc_s}"
        )
    n_dev = sum(1 for r in records if r.dev_adapter)
    n_pilot = len(records) - n_dev
    print(f"of which development-adapter: {n_dev}; candidate pilot results: {n_pilot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
