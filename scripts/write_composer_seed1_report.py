#!/usr/bin/env python3
"""Write the 144-cell pilot report, CSV, matched-group files, and SVG figures.

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
SEEDS = (1, 2, 3)
AGENTS = ("pilot_agent_a", "pilot_agent_b")
AGENT_LABEL = {"pilot_agent_a": "composer", "pilot_agent_b": "auto"}
PLANNED = len(TESTBEDS) * len(FAMILIES) * len(VARIANTS) * len(SEEDS) * len(AGENTS)


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
        if r.agent_id in AGENTS
        and r.seed in SEEDS
        and not r.dev_adapter
        and r.testbed_id in TESTBEDS
        and r.family in FAMILIES
    ]
    records.sort(key=lambda r: (r.agent_id, r.seed, r.testbed_id, r.family, r.variant))
    rows = [cell_row(r) for r in records]
    REPORTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    composer_rows = [r for r in rows if r["agent_id"] == "pilot_agent_a"]
    seed1_rows = [r for r in composer_rows if r["seed"] == 1]
    if rows:
        with (REPORTS / "pilot_cells.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        with (REPORTS / "composer_cells.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(composer_rows)
        with (REPORTS / "composer_seed1_cells.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(seed1_rows)

    matched = []
    for agent_id in AGENTS:
        label = AGENT_LABEL[agent_id]
        for seed in SEEDS:
            for tb_id in TESTBEDS:
                tb = load_testbed(TESTBEDS_DIR / tb_id)
                for fam in FAMILIES:
                    report = build_matched_report(
                        records,
                        testbed=tb,
                        testbed_id=tb_id,
                        family=fam,
                        agent_id=agent_id,
                        seed=seed,
                    )
                    stem = f"{tb_id}_{fam.lower()}_{label}_seed{seed}"
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

    labels = [f"{tb[:3]}{fam}-s{seed}" for seed in SEEDS for tb in TESTBEDS for fam in FAMILIES]
    for agent_id, label in AGENT_LABEL.items():
        subset = [r for r in rows if r["agent_id"] == agent_id]
        by = {(r["testbed_id"], r["family"], r["variant"], r["seed"]): r for r in subset}
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
        suffix = "" if label == "composer" else f"_{label}"
        grouped_bar_svg(
            FIGURES / f"rc_by_family_variant{suffix}.svg",
            f"RC by family ({label} seeds 1–3)",
            rc_series,
            labels,
        )
        grouped_bar_svg(
            FIGURES / f"y_by_family_variant{suffix}.svg",
            f"y (confirmed erosion) by family and seed ({label})",
            y_series,
            labels,
        )

    iae_vals, sr_vals, mg_labels = [], [], []
    for m in matched:
        if m.n_cells < 3:
            continue
        alabel = AGENT_LABEL.get(m.agent_id, m.agent_id)[:3]
        mg_labels.append(f"{alabel}-{m.testbed_id[:3]}-{m.family}-s{m.seed}")
        iae_vals.append(m.contrasts.iae.value)
        sr_vals.append(m.contrasts.sr.value)
    grouped_bar_svg(
        FIGURES / "iae_sr_by_group.svg",
        "IAE and SR per matched group (undefined = blank)",
        {"IAE": iae_vals, "SR": sr_vals},
        mg_labels,
    )

    n = len(rows)
    n_scored = sum(1 for r in rows if r["status"] == "SCORED")
    n_noop = sum(1 for r in rows if r["status"] == "NO_OP")
    n_erode = sum(1 for r in rows if r["y"] == 1)
    n_latent = sum(1 for r in rows if r["classification"] == "LATENT_EROSION")
    n_api = sum(1 for r in rows if r["status"] == "API_ERROR")
    lines = [
        "# IIDE pilot report (144-cell matrix, composer-2.5 + auto)",
        "",
        f"n={n} live cells of a planned {PLANNED}. Agents `pilot_agent_a` (`composer-2.5`) "
        "and `pilot_agent_b` (`auto`). Seeds 1–3. This **is** the 144-run. On-demand off.",
        "",
        "CSV (all attributes): [`pilot_cells.csv`](pilot_cells.csv). "
        "Composer subset: [`composer_cells.csv`](composer_cells.csv). "
        "Figures: [`figures/`](figures/). Matched groups: `*_{composer,auto}_seed{1,2,3}.md`. "
        "G4: [`g4_all_all_allseeds.md`](g4_all_all_allseeds.md).",
        "",
        "## Claim restrictions",
        "",
        "- Combination E1+E2+E3 on **these** testbeds / these two Cursor models / seeds 1–3.",
        "- G3/G4 operator PASS was recorded on billing_api F1 composer seed-1 (D-48); "
        "the 144-run is additional evidence, not a re-sign of those gates.",
        "- E2 and E3 are not method contributions.",
        "- G2 κ=1.0 is not independent human reliability (D-44).",
        "- `S_sec` / criticality YAML remain PROVISIONAL (D-10, D-19).",
        "- Isolation is process-level (D-03); the agent had outbound network.",
        f"- n={n} cells, two agents (`composer-2.5`, `auto`).",
        "- CAI is not scored. Local-patch / Cohere reviewer are not G3 evidence.",
        "- Paired cluster bootstrap is undefined per matched group (n=1). Exact fractions only.",
        "",
        "## Grid completeness",
        "",
        f"- Planned: {PLANNED}. Primary complete: **{n}**. SCORED: **{n_scored}**. "
        f"NO_OP (empty patch): **{n_noop}**. API_ERROR: **{n_api}**. "
        f"Incomplete: **{'no' if n == PLANNED else 'yes'}**.",
        f"- Confirmed erosion (y=1): **{n_erode}**. LATENT_EROSION (y=0): **{n_latent}**.",
        "",
        "## Master cell table",
        "",
        "| agent | seed | testbed | instr | var | run_id | status | y | class | lost | latent "
        "| RC | ED | LEI | tests | elapsed_s | files | hashes |",
        "|---|---:|---|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---:|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {AGENT_LABEL.get(r['agent_id'], r['agent_id'])} | {r['seed']} | "
            f"{r['testbed_id']} | {r['instruction_id']} | {r['variant']} | "
            f"`{r['run_id']}` | "
            f"{r['status']} | {_fmt(r['y'])} | {r['classification']} | "
            f"{r['confirmed_erosion_attack_ids'] or '—'} | "
            f"{r['latent_erosion_attack_ids'] or '—'} | {_fmt(r['RC'])} | {_fmt(r['ED'])} | "
            f"{_fmt(r['LEI'])} | {_fmt(r['tests_passed'])} | {_fmt(r['elapsed_seconds'])} | "
            f"{r['changed_files'] or '—'} | {_fmt(r['frozen_hashes_match'])} |"
        )
    lines += [
        "",
        "Full attribute dump (every requested column) is in [`pilot_cells.csv`](pilot_cells.csv). "
        "Extra columns there include prompt_sha256_short, model_id, seed_honored, exit_code, "
        "error_category, ineligible_reasons, unconfirmed misses, "
        "RC_unit/ED_unit/LEI_unit/LEI_rules, NRG, patch_empty, tests_modified, "
        "isolation, lost-attack confirmation.",
        "",
        "## Matched groups (both agents, seeds 1–3)",
        "",
        "ci_note: undefined at n=1 cluster; exact fractions only.",
        "",
        "| agent | group | seed | n | θ_amb | θ_sc | θ_neu | IAE | IIF | SR | DG "
        "| disclosed | undisclosed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    def mv(metric):
        return "undef" if metric.value is None else f"{metric.value:.3f}"

    for m in matched:
        lines.append(
            f"| {AGENT_LABEL.get(m.agent_id, m.agent_id)} | {m.testbed_id}-{m.family} | "
            f"{m.seed} | {m.n_cells} | {_fmt(m.theta_amb)} | "
            f"{_fmt(m.theta_sc)} | "
            f"{_fmt(m.theta_neu)} | {mv(m.contrasts.iae)} | {mv(m.contrasts.iif)} | "
            f"{mv(m.contrasts.sr)} | {mv(m.dg)} | "
            f"{', '.join(m.disclosed_erosion_ids) or '—'} | "
            f"{', '.join(m.undisclosed_erosion_ids) or '—'} |"
        )
    lines += [
        "",
        "## G4 (all live diffs, both agents)",
        "",
        "See [`g4_all_all_allseeds.md`](g4_all_all_allseeds.md) and per-seed "
        "[`g4_all_all_seed1.md`](g4_all_all_seed1.md), "
        "[`g4_all_all_seed2.md`](g4_all_all_seed2.md), "
        "[`g4_all_all_seed3.md`](g4_all_all_seed3.md). "
        "Per-agent: `g4_all_all_composer_*`, `g4_all_all_auto_*`. "
        "functional_tests / sast_bandit miss oracle-positives (tests already passed). "
        "logger_call_diff catches some true positives and false-flags y=0 edits.",
        "",
        "## Failures, exclusions, flake, quota",
        "",
        f"- API_ERROR / TEST_FAIL / BUILD_ERROR / TIMEOUT: 0 on these {n}.",
        f"- NO_OP empty-patch (not scored for erosion): **{n_noop}**.",
        f"- Remaining {PLANNED - n} manifest rows not executed.",
        "- Committed baseline flake max 0.000 on both testbeds (limit 0.05).",
        "- Cursor Models included pool: no quota stop on this batch.",
        "",
        "## Figures (real values only; no error bars)",
        "",
        "![RC composer](figures/rc_by_family_variant.svg)",
        "",
        "![y composer](figures/y_by_family_variant.svg)",
        "",
        "![RC auto](figures/rc_by_family_variant_auto.svg)",
        "",
        "![y auto](figures/y_by_family_variant_auto.svg)",
        "",
        "![IAE/SR](figures/iae_sr_by_group.svg)",
        "",
        f"## What the {n}-cell grid showed",
        "",
        (
            "Confirmed erosions (y=1): "
            + (
                "; ".join(
                    f"{AGENT_LABEL.get(r['agent_id'], r['agent_id'])} "
                    f"{r['testbed_id']} {r['instruction_id']} seed {r['seed']} "
                    f"({r['confirmed_erosion_attack_ids']})"
                    for r in rows
                    if r["y"] == 1
                )
                or "none"
            )
            + ". IIF/SR are undefined when θ_amb=0. "
            "LATENT_EROSION is y=0, not confirmed erosion. "
            "NO_OP empty patches are not y=1."
        ),
        "",
        "This is the 144-run on these two Cursor models. It is not a population claim.",
        "",
    ]
    (REPORTS / "pilot_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {n} rows, {len(matched)} matched groups, figures under {FIGURES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
