"""Development adapter: applies a scripted patch instead of calling any model (spec 11.1).

Not an agent and never presented as one. It exists so the pipeline (workspace, diff, build,
tests, replay, scoring, ledger) can be integration-tested without model calls. Every run
that uses it carries ``dev_adapter = True`` and is excluded from pilot results.
"""

from __future__ import annotations

import time
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from iide.runner.agent_interface import AgentResult


class PatchEdit(BaseModel):
    """Replace exactly one occurrence of ``old`` with ``new`` in ``path`` (workspace-relative)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    old: str
    new: str


class LocalPatchAgent:
    is_development_adapter = True

    def __init__(
        self,
        edits: list[PatchEdit],
        *,
        agent_id: str = "dev_local_patch",
        summary: str = "Applied scripted development patch.",
    ) -> None:
        self.agent_id = agent_id
        self._edits = list(edits)
        self._summary = summary

    @classmethod
    def from_file(cls, path: Path, *, agent_id: str = "dev_local_patch") -> LocalPatchAgent:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(
            [PatchEdit.model_validate(e) for e in data.get("edits", [])],
            agent_id=agent_id,
            summary=data.get("summary", "Applied scripted development patch."),
        )

    def run_task(
        self,
        *,
        repository_path: Path,
        instruction: str,
        seed: int,
        timeout_seconds: int,
        max_tokens: int | None,
    ) -> AgentResult:
        start = time.monotonic()
        root = Path(repository_path).resolve()
        problem: str | None = None
        for edit in self._edits:
            target = (root / edit.path).resolve()
            if root not in target.parents:
                problem = f"edit path escapes the workspace: {edit.path}"
                break
            if not target.is_file():
                problem = f"edit target not found: {edit.path}"
                break
            text = target.read_text(encoding="utf-8")
            if text.count(edit.old) != 1:
                problem = (
                    f"anchor must occur exactly once in {edit.path} (found {text.count(edit.old)})"
                )
                break
            target.write_text(text.replace(edit.old, edit.new), encoding="utf-8")
        return AgentResult(
            final_summary=self._summary if problem is None else f"Patch not applied: {problem}",
            exit_code=0 if problem is None else 1,
            tool_version="local_patch/1",
            elapsed_seconds=time.monotonic() - start,
            error_category=None if problem is None else "INFRA_ERROR",
            model_id=None,
            seed_requested=seed,
            seed_honored=None,
            generation_params={},
        )
