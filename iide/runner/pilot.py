"""Pilot batch: dry-run, checkpoints, resumability (spec 11.4, 12, 16).

A real 144-run execution is refused while G1/G2 are open, any agent is unconfigured, or any
instruction is still ``DRAFT_UNREVIEWED``, unless the operator records an explicit override.
``DRY_RUN`` never calls an agent or an API.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from iide.config import REPO_ROOT, TESTBEDS_DIR
from iide.runner.config import (
    AgentsConfig,
    ExperimentConfig,
    GatesConfig,
    build_agent,
    load_agents_config,
    load_experiment_config,
    load_gates_config,
)
from iide.runner.instructions import load_instructions
from iide.runner.manifest import (
    ManifestRow,
    generate_manifest,
    validate_manifest,
)
from iide.runner.orchestration import Oracle, execute_run, load_oracle
from iide.runner.records import (
    RunRecord,
    attempt_dir,
    list_attempts,
    next_attempt_number,
    select_primary,
)

DEFAULT_MANIFEST = REPO_ROOT / "experiments" / "manifests" / "pilot.jsonl"
DEFAULT_RAW_DIR = REPO_ROOT / "experiments" / "raw"


class PilotRefused(RuntimeError):
    """The batch was not started (open gates, unconfigured agents, or missing overrides)."""


@dataclass(frozen=True)
class PilotPlan:
    rows: list[ManifestRow]
    problems: list[str]
    blockers: list[str]  # reasons a real run would be refused
    warnings: list[str]
    n_already_complete: int
    n_todo: int


def _unreviewed(experiment: ExperimentConfig) -> list[str]:
    out = []
    for tb_id in experiment.testbeds:
        for rec in load_instructions(TESTBEDS_DIR / tb_id).values():
            if rec.family not in experiment.families:
                continue
            if rec.review_status != "REVIEWED":
                out.append(f"{tb_id}/{rec.instruction_id} is {rec.review_status}")
    return out


def plan_pilot(
    experiment: ExperimentConfig,
    agents: AgentsConfig,
    gates: GatesConfig,
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    allow_open_gates: str | None = None,
    allow_unreviewed: str | None = None,
    force_rerun: bool = False,
    limit: int | None = None,
    testbed_id: str | None = None,
) -> PilotPlan:
    rows = generate_manifest(experiment, agents)
    problems = validate_manifest(rows, experiment, agents)
    blockers: list[str] = []
    warnings: list[str] = []

    open_gates = gates.open_required_gates()
    if open_gates:
        msg = f"required gates still open: {open_gates}"
        if allow_open_gates:
            warnings.append(f"{msg}; override recorded: {allow_open_gates}")
        else:
            blockers.append(msg + " (pass --allow-open-gates with a reason to override)")

    unconfigured = [a.agent_id for a in agents.agents if not a.is_configured]
    if unconfigured:
        blockers.append(f"unconfigured agents: {unconfigured}")

    drafts = _unreviewed(experiment)
    if drafts:
        msg = f"{len(drafts)} instruction(s) still DRAFT_UNREVIEWED"
        if allow_unreviewed:
            warnings.append(f"{msg}; override recorded: {allow_unreviewed}")
        else:
            blockers.append(msg + " (spec 10: review difficulty before execution)")

    if any(a.is_development for a in agents.agents):
        warnings.append(
            "a local_patch adapter is in the matrix: those runs are flagged "
            "dev_adapter=True and are not pilot results"
        )

    if testbed_id:
        rows = [r for r in rows if r.testbed_id == testbed_id]
    already = 0
    todo: list[ManifestRow] = []
    for row in rows:
        attempts = list_attempts(raw_dir, row.run_id)
        primary = select_primary(attempts)
        if primary is not None and primary.status != "INFRA_ERROR" and not force_rerun:
            already += 1
            continue
        todo.append(row)
    if limit is not None:
        todo = todo[:limit]
    return PilotPlan(rows, problems, blockers, warnings, already, len(todo))


def execute_plan(
    plan: PilotPlan,
    experiment: ExperimentConfig,
    agents: AgentsConfig,
    *,
    raw_dir: Path,
    allow_open_gates: str | None,
    allow_unreviewed: str | None,
    force_rerun: bool,
    limit: int | None,
    testbed_id: str | None,
) -> list[RunRecord]:
    if plan.problems:
        raise PilotRefused("manifest is invalid: " + "; ".join(plan.problems))
    if plan.blockers:
        raise PilotRefused("; ".join(plan.blockers))

    specs = {a.agent_id: a for a in agents.agents}
    oracles: dict[str, Oracle] = {}
    records: list[RunRecord] = []
    overrides = [x for x in (allow_open_gates, allow_unreviewed) if x]

    selected = plan.rows
    if testbed_id:
        selected = [r for r in selected if r.testbed_id == testbed_id]

    done = 0
    for row in selected:
        attempts = list_attempts(raw_dir, row.run_id)
        primary = select_primary(attempts)
        if primary is not None and primary.status != "INFRA_ERROR" and not force_rerun:
            continue
        if limit is not None and done >= limit:
            break
        spec = specs[row.agent_id]
        agent = build_agent(spec)
        if row.testbed_id not in oracles:
            oracles[row.testbed_id] = load_oracle(row.testbed_id)
        instruction = load_instructions(TESTBEDS_DIR / row.testbed_id)[row.instruction_id]
        attempt = next_attempt_number(raw_dir, row.run_id)
        out = attempt_dir(raw_dir, row.run_id, attempt)
        record = execute_run(
            row,
            agent=agent,
            oracle=oracles[row.testbed_id],
            instruction=instruction,
            attempt_dir=out,
            attempt=attempt,
            gate_overrides=overrides,
            max_tokens=experiment.max_tokens,
        )
        records.append(record)
        done += 1
    return records


def render_plan(plan: PilotPlan, *, dry_run: bool) -> str:
    lines = [
        f"pilot plan: {len(plan.rows)} cells"
        + (" (DRY RUN: no agent will be called)" if dry_run else ""),
        f"  already complete (will skip): {plan.n_already_complete}",
        f"  remaining this invocation: {plan.n_todo}",
    ]
    if plan.problems:
        lines.append("  MANIFEST PROBLEMS:")
        lines.extend(f"    - {p}" for p in plan.problems)
    if plan.blockers:
        lines.append("  BLOCKERS (real run refused):")
        lines.extend(f"    - {b}" for b in plan.blockers)
    if plan.warnings:
        lines.append("  warnings:")
        lines.extend(f"    - {w}" for w in plan.warnings)
    return "\n".join(lines)


def summarize_records(records: Iterable[RunRecord]) -> str:
    records = list(records)
    if not records:
        return "no runs executed"
    counts: dict[str, int] = {}
    for r in records:
        counts[r.status] = counts.get(r.status, 0) + 1
    parts = [f"{k}={v}" for k, v in sorted(counts.items())]
    return f"executed {len(records)} run(s): " + ", ".join(parts)


def default_configs() -> tuple[ExperimentConfig, AgentsConfig, GatesConfig]:
    return load_experiment_config(), load_agents_config(), load_gates_config()
