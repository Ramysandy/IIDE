"""Coverage report generator (spec 13, Phase 3).

Reports every measure with its exact numerator/denominator, every undefined value with its
reason, exclusions, sensitivity variants and the scoring-package hash. It adds no
interpretation: a report from a self-comparison (candidate == baseline) is a harness check,
not a result, and says so.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from iide.config import REPO_ROOT
from iide.hashing import hash_patterns
from iide.scoring.coverage import CoverageScores, score_coverage
from iide.scoring.types import AttackOutcome, MetricResult


def scoring_package_hash() -> str:
    """Spec 17: hash of the scoring code that produced a report."""
    return hash_patterns(REPO_ROOT, ["iide/scoring/*.py"])


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    label: str
    note: str
    scoring_package_hash: str
    attacks: list[AttackOutcome]
    scores: CoverageScores


def build_coverage_report(
    outcomes: Sequence[AttackOutcome], *, label: str, note: str = ""
) -> CoverageReport:
    return CoverageReport(
        label=label,
        note=note,
        scoring_package_hash=scoring_package_hash(),
        attacks=sorted(outcomes, key=lambda a: a.attack_id),
        scores=score_coverage(outcomes),
    )


def _fmt(result: MetricResult) -> str:
    if result.value is None:
        bounds = ""
        if "lower_bound" in result.details:
            bounds = (
                f" (bounds {result.details['lower_bound']:.4f} to "
                f"{result.details['upper_bound']:.4f})"
            )
        return f"undefined: {result.reason}{bounds}"
    num = "" if result.numerator is None else f" = {result.numerator:g}/{result.denominator:g}"
    return f"{result.value:.6f}{num}"


def _state(flag: bool | None) -> str:
    return "UNKNOWN" if flag is None else ("1" if flag else "0")


def render_markdown(report: CoverageReport) -> str:
    s = report.scores
    lines = [
        f"# Coverage report: {report.label}",
        "",
        report.note or "No note.",
        "",
        f"- scoring package hash: `{report.scoring_package_hash}`",
        f"- A0 (baseline-detected): {s.a0_attack_ids or 'empty'}",
        f"- excluded from scoring: {s.excluded or 'none'}",
        f"- lost (EROSION): {s.lost_attack_ids or 'none'}",
        f"- latent erosion: {s.latent_attack_ids or 'none'}",
        f"- UNKNOWN candidate detection: {s.unknown_attack_ids or 'none'}",
        "",
        "| Attack | c_a | d(P0) | r(P0) | d(P1) | r(P1) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for a in report.attacks:
        cells = [a.attack_id, a.criticality, _state(a.d0), a.r0, _state(a.d1), a.r1]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    lines += [
        "",
        "## Primary measures",
        "",
        f"- RC: {_fmt(s.rc)}",
        f"- ED: {_fmt(s.ed)}",
        f"- LEI (event-type redundancy): {_fmt(s.lei)}",
        "",
        "## Sensitivity variants (reported separately, never substituted)",
        "",
        f"- RC, unit weights: {_fmt(s.rc_unit)}",
        f"- ED, unit weights: {_fmt(s.ed_unit)}",
        f"- LEI, unit weights: {_fmt(s.lei_unit)}",
        f"- LEI, independently firing rules: {_fmt(s.lei_rules)}",
        "",
    ]
    return "\n".join(lines)


def render_json(report: CoverageReport) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
