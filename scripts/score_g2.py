#!/usr/bin/env python3
"""Score G2 annotator files. Never writes configs/gates.yaml.

Usage:
  python scripts/score_g2.py
  python scripts/score_g2.py --a docs/g2/annotator_a.yaml --b docs/g2/annotator_b.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.analysis.agreement import assess_g2, load_annotation_file  # noqa: E402
from iide.config import REPO_ROOT as ROOT  # noqa: E402

DEFAULT_A = ROOT / "docs" / "g2" / "annotator_a.yaml"
DEFAULT_B = ROOT / "docs" / "g2" / "annotator_b.yaml"
DEFAULT_OUT = ROOT / "experiments" / "reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", type=Path, default=DEFAULT_A)
    parser.add_argument("--b", type=Path, default=DEFAULT_B)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--threshold", type=float, default=0.6)
    args = parser.parse_args(argv)

    a_file = load_annotation_file(args.a)
    b_file = load_annotation_file(args.b)
    report = assess_g2(a_file, b_file, threshold=args.threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json")
    (args.output_dir / "g2_agreement.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md = [
        "# G2 agreement",
        "",
        f"- status: **{report.status}**",
        f"- items: {report.n_items}; B labelled: {report.n_labelled_b}",
        f"- {report.note}",
        "",
        "This script does not set `configs/gates.yaml`.",
        "Numeric κ>=0.6 is not a G2 pass if B is the same rater or the fixture author.",
        "",
    ]
    (args.output_dir / "g2_agreement.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    return 0 if report.status != "INCOMPLETE" else 2


if __name__ == "__main__":
    sys.exit(main())
