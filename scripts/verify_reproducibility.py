#!/usr/bin/env python3
"""Pre-pilot status report (spec 16 ``make report``). Never calls an LLM or agent.

Exit 1 if committed baselines no longer match frozen hashes. Exit 0 otherwise, even
when the 144-run is blocked (blockers are listed in the report).

Usage:
  python scripts/verify_reproducibility.py
  python scripts/verify_reproducibility.py --output-dir experiments/reports
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.analysis.status import dump_status, render_markdown  # noqa: E402
from iide.config import REPO_ROOT as ROOT  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments" / "reports")
    args = parser.parse_args(argv)
    status, code = dump_status(args.output_dir)
    print(render_markdown(status))
    return code


if __name__ == "__main__":
    sys.exit(main())
