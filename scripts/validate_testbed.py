#!/usr/bin/env python3
"""Load a testbed and cross-validate catalog, attacks, rules and mapping.

Exit code 0 if consistent, 1 otherwise. Prints the frozen-artifact hashes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.config import TESTBEDS_DIR  # noqa: E402
from iide.replay.runner import TestbedContractError, compute_frozen_hashes, load_testbed  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--testbed", required=True, help="directory name under testbeds/")
    args = parser.parse_args(argv)

    root = TESTBEDS_DIR / args.testbed
    if not root.is_dir():
        print(f"error: no such testbed directory: {root}", file=sys.stderr)
        return 1
    try:
        tb = load_testbed(root)
    except (TestbedContractError, ValueError, OSError) as exc:
        print(f"INVALID testbed {args.testbed}: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK testbed={tb.testbed_id} attacks={len(tb.attacks)} "
        f"rules={len(tb.detector.rule_ids)} event_types={len(tb.catalog)}"
    )
    print(json.dumps(compute_frozen_hashes(tb), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
