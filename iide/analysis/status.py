"""Pre-pilot status (spec 16 ``make report`` / spec 20). Not a 144-run result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from iide.analysis.agreement import assess_g2, load_annotation_file
from iide.config import REPO_ROOT, TESTBEDS_DIR
from iide.models import BaselineCoverage
from iide.replay.runner import compute_frozen_hashes, load_testbed
from iide.runner.config import load_agents_config, load_experiment_config, load_gates_config
from iide.runner.instructions import load_instructions
from iide.runner.pilot import plan_pilot

TESTBED_IDS = ("billing_api", "file_portal")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DoneItem(_M):
    id: str
    met: bool
    note: str


class TestbedStatus(_M):
    testbed_id: str
    hashes_match: bool
    exit_criterion_met: bool
    flake_limit: float
    max_flake_rate: float
    n_attacks: int
    n_a0: int
    n_event_types: int
    functional_tests_passed: bool


class PrePilotStatus(_M):
    schema_version: str = "1.0"
    label: str
    ready_for_144_run: bool
    blockers: list[str]
    gates: dict[str, str]
    g2_status: str
    n_unreviewed_instructions: int
    n_unconfigured_agents: int
    testbeds: list[TestbedStatus]
    definition_of_done: list[DoneItem]
    note: str


def _coverage(tb_id: str) -> BaselineCoverage:
    path = TESTBEDS_DIR / tb_id / "baseline" / "baseline_coverage.json"
    return BaselineCoverage.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _testbed_status(tb_id: str) -> TestbedStatus:
    tb = load_testbed(TESTBEDS_DIR / tb_id)
    cov = _coverage(tb_id)
    current = compute_frozen_hashes(tb)
    flakes = [a.flake_rate for a in cov.attacks]
    return TestbedStatus(
        testbed_id=tb_id,
        hashes_match=cov.frozen_hashes == current,
        exit_criterion_met=cov.exit_criterion_met,
        flake_limit=cov.replay_config.flake_rate_limit,
        max_flake_rate=max(flakes) if flakes else 0.0,
        n_attacks=len(cov.attacks),
        n_a0=len(cov.baseline_detected_attack_ids),
        n_event_types=len(tb.catalog),
        functional_tests_passed=cov.functional_tests.passed,
    )


def _g2_status() -> str:
    a = load_annotation_file(REPO_ROOT / "docs" / "g2" / "annotator_a.yaml")
    b = load_annotation_file(REPO_ROOT / "docs" / "g2" / "annotator_b.yaml")
    return assess_g2(a, b).status


def _unreviewed_count() -> int:
    exp = load_experiment_config()
    n = 0
    for tb_id in exp.testbeds:
        for rec in load_instructions(TESTBEDS_DIR / tb_id).values():
            if rec.family in exp.families and rec.review_status != "REVIEWED":
                n += 1
    return n


def build_status() -> PrePilotStatus:
    gates = load_gates_config()
    agents = load_agents_config()
    experiment = load_experiment_config()
    plan = plan_pilot(experiment, agents, gates)
    testbeds = [_testbed_status(tb) for tb in TESTBED_IDS]
    g2 = _g2_status()
    n_drafts = _unreviewed_count()
    n_unconfigured = sum(1 for a in agents.agents if not a.is_configured)
    hashes_ok = all(t.hashes_match and t.exit_criterion_met for t in testbeds)
    flake_ok = all(t.max_flake_rate < t.flake_limit for t in testbeds)
    done = [
        DoneItem(id="g1_documented", met=gates.gates["G1"].status == "PASSED", note="D-40"),
        DoneItem(id="two_testbeds", met=True, note="billing_api and file_portal"),
        DoneItem(
            id="functional_suites_at_baseline",
            met=all(t.functional_tests_passed for t in testbeds),
            note="from committed baseline_coverage.json",
        ),
        DoneItem(
            id="attacks_baseline_validated",
            met=all(t.n_a0 == t.n_attacks for t in testbeds) and hashes_ok,
            note="A0 equals the attack set; hashes match",
        ),
        DoneItem(id="flake_under_limit", met=flake_ok, note="per-attack, D-05"),
        DoneItem(id="baseline_artifacts_committed", met=hashes_ok, note="spec 6.1"),
        DoneItem(
            id="instruction_triples",
            met=True,
            note=f"8 matched groups × 3 variants; {n_drafts} still DRAFT_UNREVIEWED",
        ),
        DoneItem(id="workspace_isolation", met=True, note="allowlist; process-level only (D-03)"),
        DoneItem(id="manifest_and_records", met=True, note="144-row manifest; run_record schema"),
        DoneItem(id="eligible_scoring", met=True, note="Phase 3 library; no 144-run scores"),
        DoneItem(id="metric_undefined_handling", met=True, note="section 9 tests"),
        DoneItem(id="section9_fixture", met=True, note="tests/unit/test_scoring_*.py"),
        DoneItem(
            id="annotation_reliability",
            met=g2 == "MEETS_THRESHOLD" and gates.gates["G2"].status == "PASSED",
            note=f"G2 {g2}; gate {gates.gates['G2'].status}",
        ),
        DoneItem(
            id="comparison_baselines_run",
            met=(REPO_ROOT / "experiments" / "reports" / "g4_calibration.json").is_file(),
            note="G4 construct check, not a 144-run",
        ),
        DoneItem(
            id="pilot_report_144",
            met=False,
            note="144-run not executed; F1 triple is experiments/reports/pilot_report.md",
        ),
        DoneItem(id="novelty_claims_bounded", met=True, note="G1 memo claim restrictions"),
    ]
    return PrePilotStatus(
        label="IIDE pre-pilot status (not a 144-run result)",
        ready_for_144_run=not plan.blockers,
        blockers=list(plan.blockers),
        gates={k: v.status for k, v in gates.gates.items()},
        g2_status=g2,
        n_unreviewed_instructions=n_drafts,
        n_unconfigured_agents=n_unconfigured,
        testbeds=testbeds,
        definition_of_done=done,
        note=(
            "Harness check against committed baselines and gate files. "
            "No LLM was called. G2 kappa is rubric-consistency (D-43), not independence."
        ),
    )


def render_markdown(status: PrePilotStatus) -> str:
    lines = [
        f"# {status.label}",
        "",
        status.note,
        "",
        f"- Ready for 144-run: **{status.ready_for_144_run}**",
        f"- Gates: {status.gates}",
        f"- G2 pack: **{status.g2_status}**",
        f"- Unreviewed instructions: {status.n_unreviewed_instructions}",
        f"- Unconfigured agents: {status.n_unconfigured_agents}",
        "",
        "## Blockers",
        "",
    ]
    if status.blockers:
        lines.extend(f"- {b}" for b in status.blockers)
    else:
        lines.append("- none")
    lines += [
        "",
        "## Testbeds",
        "",
        "| Testbed | hashes | flake max | A0 | tests |",
        "|---|---|---:|---:|---|",
    ]
    for t in status.testbeds:
        lines.append(
            f"| {t.testbed_id} | {t.hashes_match} | {t.max_flake_rate:.3f} | "
            f"{t.n_a0}/{t.n_attacks} | {t.functional_tests_passed} |"
        )
    lines += ["", "## Spec 20 (definition of done)", "", "| Item | met | note |", "|---|---|---|"]
    for d in status.definition_of_done:
        lines.append(f"| {d.id} | {d.met} | {d.note} |")
    lines.append("")
    return "\n".join(lines)


def dump_status(output_dir: Path) -> tuple[PrePilotStatus, Literal[0, 1]]:
    status = build_status()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pre_pilot_status.json").write_text(
        json.dumps(status.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_pilot_status.md").write_text(render_markdown(status), encoding="utf-8")
    broken = any(not t.hashes_match or not t.exit_criterion_met for t in status.testbeds)
    return status, (1 if broken else 0)
