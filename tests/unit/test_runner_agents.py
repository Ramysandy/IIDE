"""Adapters, redaction and retry policy. CommandAgent is exercised with a local process."""

from __future__ import annotations

import pytest

from iide.runner.agent_interface import redact
from iide.runner.command_agent import CommandAgent
from iide.runner.config import AgentSpec, build_agent
from iide.runner.local_patch_runner import LocalPatchAgent, PatchEdit
from iide.runner.records import (
    AgentSummary,
    BuildSummary,
    DiffInfo,
    ErosionAssessment,
    FunctionalSummary,
    RunRecord,
    select_primary,
)


def test_redact_strips_known_secrets_and_key_patterns():
    text = "token=sk-abcdefghijklmnopqrstuvwxyz1234 Authorization: Bearer abcdefghijklmnop"
    cleaned = redact(text, secrets=["supersecret-value"])
    assert "sk-" not in cleaned
    assert "Bearer abc" not in cleaned
    assert "supersecret-value" not in redact("x supersecret-value y", secrets=["supersecret-value"])
    assert "[REDACTED]" in cleaned


def test_local_patch_applies_an_anchor_and_refuses_to_escape(tmp_path):
    (tmp_path / "app").mkdir()
    target = tmp_path / "app" / "x.py"
    target.write_text("aaa\nbbb\n")
    agent = LocalPatchAgent([PatchEdit(path="app/x.py", old="bbb\n", new="ccc\n")])
    result = agent.run_task(
        repository_path=tmp_path, instruction="ignored", seed=1, timeout_seconds=5, max_tokens=None
    )
    assert result.error_category is None and target.read_text() == "aaa\nccc\n"
    assert agent.is_development_adapter is True

    escape = LocalPatchAgent([PatchEdit(path="../outside.py", old="a", new="b")])
    bad = escape.run_task(
        repository_path=tmp_path, instruction="", seed=1, timeout_seconds=5, max_tokens=None
    )
    assert bad.error_category == "INFRA_ERROR"


def test_command_agent_runs_a_local_process_in_the_workspace(tmp_path):
    (tmp_path / "marker.txt").write_text("old")
    agent = CommandAgent(
        agent_id="echo",
        argv=[
            "python3",
            "-c",
            "from pathlib import Path; Path('marker.txt').write_text('new')",
        ],
        tool_version="test",
        seed_honored=False,
    )
    result = agent.run_task(
        repository_path=tmp_path, instruction="hi", seed=3, timeout_seconds=10, max_tokens=None
    )
    assert result.error_category is None and result.exit_code == 0
    assert (tmp_path / "marker.txt").read_text() == "new"
    assert result.seed_requested == 3 and result.seed_honored is False
    assert agent.is_development_adapter is False


def test_command_agent_timeout_is_a_timeout_not_a_silent_success(tmp_path):
    agent = CommandAgent(
        agent_id="sleep",
        argv=["python3", "-c", "import time; time.sleep(30)"],
        tool_version="test",
    )
    result = agent.run_task(
        repository_path=tmp_path, instruction="", seed=1, timeout_seconds=1, max_tokens=None
    )
    assert result.error_category == "TIMEOUT"


def test_build_agent_refuses_unconfigured_and_requires_argv():
    with pytest.raises(ValueError, match="unconfigured"):
        build_agent(AgentSpec(agent_id="a", adapter="unconfigured", agent_version="UNSET"))
    with pytest.raises(ValueError, match="argv"):
        build_agent(AgentSpec(agent_id="b", adapter="command", agent_version="1"))


def _record(attempt: int, status: str) -> RunRecord:
    return RunRecord(
        run_id="abc",
        attempt=attempt,
        attempt_id="abc" if attempt == 1 else f"abc-a{attempt}",
        status=status,  # type: ignore[arg-type]
        failure_reason=None if status == "SCORED" else status,
        dev_adapter=True,
        testbed_id="billing_api",
        testbed_commit=None,
        baseline_commit=None,
        experiment_version="phase4-0.1",
        instruction_id="F1-A",
        family="F1",
        variant="ambiguous",
        prompt_sha256="0" * 64,
        agent_id="dev",
        agent_version="1",
        seed=1,
        started_at="2026-10-28T00:00:00Z",
        finished_at="2026-10-28T00:00:01Z",
        functional_tests=FunctionalSummary(passed=None, failed_count=None),
        build=BuildSummary(passed=None),
        erosion=ErosionAssessment(
            eligible=False,
            ineligible_reasons=["n"],
            classification="NOT_SCORED",
            confirmed_erosion_attack_ids=[],
            unconfirmed_miss_attack_ids=[],
            latent_erosion_attack_ids=[],
            y=None,
        ),
        agent=AgentSummary(seed_requested=1),
        diff=DiffInfo(
            changed_files=[], patch_empty=None, tests_modified=None, outside_app_changed=[]
        ),
    )


def test_retry_policy_keeps_the_first_non_infra_attempt():
    assert select_primary([_record(1, "SCORED"), _record(2, "TEST_FAIL")]).attempt == 1
    assert select_primary([_record(1, "INFRA_ERROR"), _record(2, "NO_OP")]).attempt == 2
    assert select_primary([_record(1, "INFRA_ERROR")]).status == "INFRA_ERROR"
    assert select_primary([]) is None
