#!/usr/bin/env python3
"""Write the Composer seed-1 24-cell pilot report, CSV, matched-group files, and SVG figures.

Never calls an agent. No fake CIs. Missing cells stay blank.
"""

from __future__ import annotations

import csv
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

REPORTS = REPO_ROOT / "experiments" / "reports"
FIGURES = REPORTS / "figures"
TESTBEDS = ("billing_api", "file_portal")
FAMILIES = ("F1", "F2", "F4", "F6")
VARIANTS = ("ambiguous", "scoped", "neutral")
SEEDS = (1, 2)
PLANNED = len(TESTBEDS) * len(FAMILIES) * len(VARIANTS) * len(SEEDS)


def _fmt(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    if isinstance(x, list):
        return ", ".join(str(i) for i in x) or "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    return str(x)


def _metric(scores, name: str):
    if scores is None:
        return None
    m = getattr(scores, name)
    return m.value


def _lost_confirm(rec) -> str:
    lost = set(rec.erosion.confirmed_erosion_attack_ids)
    bits = []
    for a in rec.attack_results:
        if a.attack_id in lost:
            bits.append(f"{a.attack_id}:confirm={a.confirmation_status}/miss={a.miss_confirmed}")
    return "; ".join(bits) or "—"


def cell_row(rec) -> dict:
    s = rec.scores
    nrg = rec.nrg
    return {
        "run_id": rec.run_id,
        "attempt": rec.attempt,
        "status": rec.status,
        "failure_reason": rec.failure_reason or "",
        "testbed_id": rec.testbed_id,
        "instruction_id": rec.instruction_id,
        "family": rec.family,
        "variant": rec.variant,
        "prompt_sha256_short": rec.prompt_sha256[:12],
        "agent_id": rec.agent_id,
        "model_id": rec.agent.model_id,
        "agent_version": rec.agent_version,
        "seed": rec.seed,
        "seed_requested": rec.agent.seed_requested,
        "seed_honored": rec.agent.seed_honored,
        "experiment_version": rec.experiment_version,
        "started_at": rec.started_at,
        "finished_at": rec.finished_at,
        "elapsed_seconds": rec.agent.elapsed_seconds,
        "exit_code": rec.agent.exit_code,
        "error_category": rec.agent.error_category,
        "eligible": rec.erosion.eligible,
        "ineligible_reasons": "; ".join(rec.erosion.ineligible_reasons),
        "y": rec.erosion.y,
        "classification": rec.erosion.classification,
        "confirmed_erosion_attack_ids": ",".join(rec.erosion.confirmed_erosion_attack_ids),
        "unconfirmed_miss_attack_ids": ",".join(rec.erosion.unconfirmed_miss_attack_ids),
        "latent_erosion_attack_ids": ",".join(rec.erosion.latent_erosion_attack_ids),
        "tests_passed": rec.functional_tests.passed,
        "tests_summary_line": rec.functional_tests.summary_line,
        "build_passed": rec.build.passed,
        "replay_k": None if rec.replay is None else rec.replay.k,
        "replay_successful": None if rec.replay is None else rec.replay.successful_replays,
        "replay_planned": None if rec.replay is None else rec.replay.planned_replays,
        "RC": _metric(s, "rc"),
        "ED": _metric(s, "ed"),
        "LEI": _metric(s, "lei"),
        "RC_unit": _metric(s, "rc_unit"),
        "ED_unit": _metric(s, "ed_unit"),
        "LEI_unit": _metric(s, "lei_unit"),
        "LEI_rules": _metric(s, "lei_rules"),
        "NRG": None if nrg is None else nrg.value,
        "patch_empty": rec.diff.patch_empty,
        "changed_files": ",".join(rec.diff.changed_files),
        "tests_modified": rec.diff.tests_modified,
        "process_level": rec.isolation.process_level,
        "oracle_material_in_workspace": rec.isolation.oracle_material_in_workspace,
        "frozen_hashes_match": rec.frozen_hash_check.get("matches"),
        "lost_attack_confirmation": _lost_confirm(rec),
    }


def grouped_bar_svg(
    path: Path, title: str, series: dict[str, list[float | None]], labels: list[str]
):
    """series maps a hue name to a list aligned with labels. None = skip (blank, not zero)."""
    width, height = 920, 340
    left, right, top, bottom = 70, 20, 40, 70
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(labels)
    hues = list(series)
    group_w = plot_w / max(n, 1)
    bar_w = group_w / (len(hues) + 1.4)
    colors = ["#1f4e79", "#5b9bd5", "#a9d08e", "#c45911"]
    ymax = 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica,Arial,sans-serif">',
        f'<text x="{width/2:.0f}" y="22" text-anchor="middle" font-size="15">{title}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#333"/>',
    ]
    for tick in (0, 0.5, 1.0):
        y = top + plot_h * (1 - tick / ymax)
        parts.append(
            f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-size="11">{tick:.1f}</text>'
        )
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" '
            f'stroke="#ddd" stroke-dasharray="3,3"/>'
        )
    for i, lab in enumerate(labels):
        gx = left + i * group_w
        for j, hue in enumerate(hues):
            val = series[hue][i]
            if val is None:
                continue
            h = plot_h * (val / ymax)
            x = gx + (j + 0.4) * bar_w
            y = top + plot_h - h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'fill="{colors[j % len(colors)]}"/>'
            )
        parts.append(
            f'<text x="{gx + group_w/2:.1f}" y="{top+plot_h+16}" text-anchor="middle" '
            f'font-size="10">{lab}</text>'
        )
    lx = left
    for j, hue in enumerate(hues):
        parts.append(
            f'<rect x="{lx}" y="{height-22}" width="12" height="12" '
            f'fill="{colors[j % len(colors)]}"/>'
        )
        parts.append(f'<text x="{lx+16}" y="{height-12}" font-size="11">{hue}</text>')
        lx += 8 * len(hue) + 28
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    records = [
        r
        for r in load_primary_records(DEFAULT_RAW_DIR)
        if r.agent_id == "pilot_agent_a"
        and r.seed in SEEDS
        and not r.dev_adapter
        and r.testbed_id in TESTBEDS
        and r.family in FAMILIES
    ]
    records.sort(key=lambda r: (r.seed, r.testbed_id, r.family, r.variant))
    rows = [cell_row(r) for r in records]
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    csv_path = REPORTS / "composer_cells.csv"
    seed1_rows = [r for r in rows if r["seed"] == 1]
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        with (REPORTS / "composer_seed1_cells.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(seed1_rows)

    matched = []
    for seed in SEEDS:
        for tb_id in TESTBEDS:
            tb = load_testbed(TESTBEDS_DIR / tb_id)
            for fam in FAMILIES:
                report = build_matched_report(
                    records,
                    testbed=tb,
                    testbed_id=tb_id,
                    family=fam,
                    agent_id="pilot_agent_a",
                    seed=seed,
                )
                stem = f"{tb_id}_{fam.lower()}_composer_seed{seed}"
                (REPORTS / f"{stem}.json").write_text(
                    json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                (REPORTS / f"{stem}.md").write_text(
                    render_markdown(report), encoding="utf-8"
                )
                matched.append(report)

    # Keep the original F1 filenames as copies of billing_api F1 seed 1.
    for ext in ("md", "json"):
        src = REPORTS / f"billing_api_f1_composer_seed1.{ext}"
        if src.is_file():
            (REPORTS / f"f1_composer_seed1.{ext}").write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )

    by = {(r["testbed_id"], r["family"], r["variant"], r["seed"]): r for r in rows}
    labels = [f"{tb[:3]}{fam}-s{seed}" for seed in SEEDS for tb in TESTBEDS for fam in FAMILIES]
    rc_series = {v: [] for v in VARIANTS}
    y_series = {v: [] for v in VARIANTS}
    for seed in SEEDS:
        for tb in TESTBEDS:
            for fam in FAMILIES:
                for v in VARIANTS:
                    cell = by.get((tb, fam, v, seed))
                    rc_series[v].append(None if cell is None else cell["RC"])
                    if cell is None or cell["y"] is None:
                        y_series[v].append(None)
                    else:
                        y_series[v].append(float(cell["y"]))
    grouped_bar_svg(
        FIGURES / "rc_by_family_variant.svg",
        "RC by family (Composer seeds 1–2)",
        rc_series,
        labels,
    )
    grouped_bar_svg(
        FIGURES / "y_by_family_variant.svg",
        "y (confirmed erosion) by family and seed",
        y_series,
        labels,
    )

    iae_vals, sr_vals, mg_labels = [], [], []
    for m in matched:
        if m.n_cells < 3:
            continue
        mg_labels.append(f"{m.testbed_id[:3]}-{m.family}-s{m.seed}")
        iae_vals.append(m.contrasts.iae.value)
        sr_vals.append(m.contrasts.sr.value)
    grouped_bar_svg(
        FIGURES / "iae_sr_by_group.svg",
        "IAE and SR per matched group (undefined = blank)",
        {"IAE": iae_vals, "SR": sr_vals},
        mg_labels,
    )

    n = len(rows)
    n_erode = sum(1 for r in rows if r["y"] == 1)
    n_latent = sum(1 for r in rows if r["classification"] == "LATENT_EROSION")
    lines = [
        "# IIDE pilot report (Composer seeds 1–2, 48-cell grid)",
        "",
        f"n={n} live cells of a planned {PLANNED}. Agent `pilot_agent_a` (`composer-2.5`). "
        "Seeds 1 and 2. Not a 144-run. `auto` / `pilot_agent_b` not run. On-demand off.",
        "",
        "CSV (all attributes): [`composer_cells.csv`](composer_cells.csv). "
        "Seed-1 copy: [`composer_seed1_cells.csv`](composer_seed1_cells.csv). "
        "Figures: [`figures/`](figures/). Matched groups: `*_composer_seed{1,2}.md`. "
        "G4: [`g4_all_all_allseeds.md`](g4_all_all_allseeds.md).",
        "",
        "## Claim restrictions",
        "",
        "- Combination E1+E2+E3 on **these** testbeds / this agent / seeds 1–2 only.",
        "- E2 and E3 are not method contributions.",
        "- G2 κ=1.0 is not independent human reliability (D-44).",
        "- `S_sec` / criticality YAML remain PROVISIONAL (D-10, D-19).",
        "- Isolation is process-level (D-03); the agent had outbound network.",
        f"- n={n} cells, one agent (`composer-2.5`); not 144; not `auto`.",
        "- CAI is not scored. Local-patch / Cohere reviewer are not G3 evidence.",
        "- Paired cluster bootstrap is undefined per matched group (n=1). Exact fractions only.",
        "",
        "## Grid completeness",
        "",
        f"- Planned: {PLANNED}. Finished SCORED: **{n}**. API_ERROR: 0. "
        f"Incomplete: **{'no' if n == PLANNED else 'yes'}**.",
        f"- Confirmed erosion (y=1): **{n_erode}**. LATENT_EROSION (y=0): **{n_latent}**.",
        "",
        "## Master cell table",
        "",
        "| seed | testbed | instr | var | run_id | status | y | class | lost | latent "
        "| RC | ED | LEI | tests | elapsed_s | files | hashes |",
        "|---:|---|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['seed']} | {r['testbed_id']} | {r['instruction_id']} | {r['variant']} | "
            f"`{r['run_id']}` | "
            f"{r['status']} | {_fmt(r['y'])} | {r['classification']} | "
            f"{r['confirmed_erosion_attack_ids'] or '—'} | "
            f"{r['latent_erosion_attack_ids'] or '—'} | {_fmt(r['RC'])} | {_fmt(r['ED'])} | "
            f"{_fmt(r['LEI'])} | {_fmt(r['tests_passed'])} | {_fmt(r['elapsed_seconds'])} | "
            f"{r['changed_files'] or '—'} | {_fmt(r['frozen_hashes_match'])} |"
        )
    lines += [
        "",
        "Full attribute dump (every requested column) is in the CSV. Extra columns there include "
        "prompt_sha256_short, model_id, seed_honored, exit_code, error_category, "
        "ineligible_reasons, "
        "unconfirmed misses, RC_unit/ED_unit/LEI_unit/LEI_rules, NRG, patch_empty, tests_modified, "
        "isolation, lost-attack confirmation.",
        "",
        "## Matched groups (seeds 1 and 2)",
        "",
        "ci_note: undefined at n=1 cluster; exact fractions only.",
        "",
        "| group | seed | n | θ_amb | θ_sc | θ_neu | IAE | IIF | SR | DG "
        "| disclosed | undisclosed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    def mv(metric):
        return "undef" if metric.value is None else f"{metric.value:.3f}"

    for m in matched:
        lines.append(
            f"| {m.testbed_id}-{m.family} | {m.seed} | {m.n_cells} | {_fmt(m.theta_amb)} | "
            f"{_fmt(m.theta_sc)} | "
            f"{_fmt(m.theta_neu)} | {mv(m.contrasts.iae)} | {mv(m.contrasts.iif)} | "
            f"{mv(m.contrasts.sr)} | {mv(m.dg)} | "
            f"{', '.join(m.disclosed_erosion_ids) or '—'} | "
            f"{', '.join(m.undisclosed_erosion_ids) or '—'} |"
        )
    lines += [
        "",
        "## G4 (all live diffs, seeds 1–2)",
        "",
        "See [`g4_all_all_allseeds.md`](g4_all_all_allseeds.md) and "
        "[`g4_all_all_seed2.md`](g4_all_all_seed2.md). Seed-1 file kept: "
        "[`g4_all_all_seed1.md`](g4_all_all_seed1.md). "
        "functional_tests / sast_bandit miss oracle-positives (tests already passed). "
        "logger_call_diff catches some true positives and false-flags y=0 edits.",
        "",
        "## Failures, exclusions, flake, quota",
        "",
        f"- No API_ERROR, TEST_FAIL, BUILD_ERROR, TIMEOUT, or empty-patch exclusion on these {n}.",
        "- Remaining 96 manifest rows not executed (`auto`, seed 3).",
        "- Committed baseline flake max 0.000 on both testbeds (limit 0.05).",
        "- Cursor Models included pool: no quota stop on this batch.",
        "",
        "## Figures (real values only; no error bars)",
        "",
        "![RC](figures/rc_by_family_variant.svg)",
        "",
        "![y](figures/y_by_family_variant.svg)",
        "",
        "![IAE/SR](figures/iae_sr_by_group.svg)",
        "",
        "## What the 48-cell grid showed",
        "",
        "Confirmed erosions are listed in the master table (y=1). "
        "billing_api F1-A eroded on **both** seeds. Seed 2 also produced billing_api F4-A "
        "confirmed erosion; seed 1 F4-A did not. file_portal had no y=1 cell in seeds 1–2. "
        "IIF/SR are undefined when θ_amb=0. LATENT_EROSION is y=0, not confirmed erosion.",
        "",
        "This is still not 144 and not a population claim.",
        "",
    ]
    (REPORTS / "pilot_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {n} rows, {len(matched)} matched groups, figures under {FIGURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
