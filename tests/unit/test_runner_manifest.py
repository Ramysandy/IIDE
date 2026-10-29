"""144-run manifest generation and validation (spec 11.4, 12)."""

from __future__ import annotations

from iide.ids import stable_id
from iide.runner.config import load_agents_config, load_experiment_config, load_gates_config
from iide.runner.manifest import (
    generate_manifest,
    read_manifest,
    run_id_for,
    validate_manifest,
    write_manifest,
)
from iide.runner.pilot import CellFilter, plan_pilot


def test_experiment_matrix_is_exactly_the_144_run_pilot():
    exp = load_experiment_config()
    agents = load_agents_config()
    assert exp.testbeds == ["billing_api", "file_portal"]
    assert exp.families == ["F1", "F2", "F4", "F6"]
    assert list(exp.variants) == ["ambiguous", "scoped", "neutral"]
    assert exp.seeds == [1, 2, 3]
    assert len(agents.agents) == 2
    assert {a.adapter for a in agents.agents} == {"command"}
    assert all(a.is_configured for a in agents.agents)
    assert 2 * 4 * 3 * 2 * 3 == 144


def test_generated_manifest_has_144_unique_cells_and_stable_ids():
    exp = load_experiment_config()
    agents = load_agents_config()
    rows = generate_manifest(exp, agents, created_at="2026-10-28T00:00:00Z")
    assert len(rows) == 144
    assert validate_manifest(rows, exp, agents) == []
    ids = [r.run_id for r in rows]
    assert len(set(ids)) == 144
    row = rows[0]
    assert row.run_id == run_id_for(
        row.testbed_id,
        row.instruction_id,
        row.agent_id,
        row.seed,
        row.experiment_version,
        row.variant,
    )
    assert row.run_id == stable_id(
        row.testbed_id,
        row.instruction_id,
        row.variant,
        row.agent_id,
        str(row.seed),
        row.experiment_version,
    )
    assert row.instruction_set_hash
    assert row.detector_hash and row.attack_set_hash


def test_manifest_roundtrip(tmp_path):
    exp = load_experiment_config()
    agents = load_agents_config()
    rows = generate_manifest(exp, agents, created_at="2026-10-28T00:00:00Z")
    path = tmp_path / "pilot.jsonl"
    write_manifest(rows, path)
    assert read_manifest(path) == rows


def test_dry_run_plan_reports_missing_cursor_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    plan = plan_pilot(
        load_experiment_config(), load_agents_config(), load_gates_config(), raw_dir=tmp_path
    )
    assert plan.problems == []
    assert not any("open" in b for b in plan.blockers)
    assert not any("unconfigured" in b for b in plan.blockers)
    assert any("CURSOR_API_KEY" in b for b in plan.blockers)
    assert not any("DRAFT_UNREVIEWED" in b for b in plan.blockers)
    assert plan.n_todo == 144
    assert len(plan.rows) == 144
    assert plan.todo_rows[0].agent_id in {"pilot_agent_a", "pilot_agent_b"}


def test_cell_filter_selects_f1_scoped_agent_a_seed_1_only(tmp_path, monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    filt = CellFilter(
        testbed_id="billing_api",
        family="F1",
        variant="scoped",
        agent_id="pilot_agent_a",
        seed=1,
    )
    plan = plan_pilot(
        load_experiment_config(),
        load_agents_config(),
        load_gates_config(),
        raw_dir=tmp_path,
        cell_filter=filt,
    )
    assert len(plan.rows) == 144
    assert plan.n_todo == 1
    row = plan.todo_rows[0]
    assert row.testbed_id == "billing_api"
    assert row.family == "F1"
    assert row.variant == "scoped"
    assert row.instruction_id == "F1-S"
    assert row.agent_id == "pilot_agent_a"
    assert row.seed == 1
    assert row.agent_id != "pilot_agent_b"
    assert plan.cell_filter.label() == (
        "testbed=billing_api, family=F1, variant=scoped, agent=pilot_agent_a, seed=1"
    )
