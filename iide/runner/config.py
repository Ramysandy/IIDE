"""Experiment, agent and gate configuration for the Phase 4 harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from iide.config import REPO_ROOT
from iide.runner.agent_interface import CodingAgent
from iide.runner.command_agent import CommandAgent
from iide.runner.local_patch_runner import LocalPatchAgent

CONFIGS_DIR = REPO_ROOT / "configs"
EXPERIMENT_CONFIG = CONFIGS_DIR / "experiment.yaml"
AGENTS_CONFIG = CONFIGS_DIR / "agents.yaml"
GATES_CONFIG = CONFIGS_DIR / "gates.yaml"


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    experiment_version: str = Field(min_length=1)
    testbeds: list[str] = Field(min_length=1)
    families: list[str] = Field(min_length=1)
    variants: list[Literal["ambiguous", "scoped", "neutral"]] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    agent_timeout_seconds: int = Field(ge=1)
    max_tokens: int | None = None

    @model_validator(mode="after")
    def _unique(self) -> ExperimentConfig:
        for name in ("testbeds", "families", "variants", "seeds"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} contains duplicates")
        return self


def load_experiment_config(path: Path = EXPERIMENT_CONFIG) -> ExperimentConfig:
    return ExperimentConfig.model_validate(_load(path))


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    adapter: Literal["unconfigured", "command", "local_patch"]
    agent_version: str = Field(min_length=1)
    # command adapter
    argv: list[str] | None = None
    env_passthrough: list[str] = []
    stdin_instruction: bool = False
    model_id: str | None = None
    generation_params: dict[str, Any] = {}
    seed_honored: bool | None = None
    # local_patch adapter (development only)
    edits_file: str | None = None

    @property
    def is_development(self) -> bool:
        return self.adapter == "local_patch"

    @property
    def is_configured(self) -> bool:
        return self.adapter != "unconfigured" and self.agent_version != "UNSET"


class AgentsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    agents: list[AgentSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> AgentsConfig:
        ids = [a.agent_id for a in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate agent_id")
        return self


def load_agents_config(path: Path = AGENTS_CONFIG) -> AgentsConfig:
    return AgentsConfig.model_validate(_load(path))


def build_agent(spec: AgentSpec, *, base_dir: Path = REPO_ROOT) -> CodingAgent:
    if spec.adapter == "unconfigured":
        raise ValueError(f"agent {spec.agent_id} is unconfigured; configure it in agents.yaml")
    if spec.adapter == "command":
        if not spec.argv:
            raise ValueError(f"agent {spec.agent_id}: command adapter requires argv")
        return CommandAgent(
            agent_id=spec.agent_id,
            argv=spec.argv,
            tool_version=spec.agent_version,
            env_passthrough=spec.env_passthrough,
            stdin_instruction=spec.stdin_instruction,
            model_id=spec.model_id,
            generation_params=spec.generation_params,
            seed_honored=spec.seed_honored,
        )
    if not spec.edits_file:
        raise ValueError(f"agent {spec.agent_id}: local_patch adapter requires edits_file")
    return LocalPatchAgent.from_file(base_dir / spec.edits_file, agent_id=spec.agent_id)


class GateStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["OPEN", "PASSED", "FAILED", "NOT_EVALUATED"]
    description: str


class GatesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    gates: dict[str, GateStatus]

    def open_required_gates(self) -> list[str]:
        """Gates that must be PASSED before a real pilot run (G1, G2)."""
        return sorted(g for g in ("G1", "G2") if self.gates[g].status != "PASSED")


def load_gates_config(path: Path = GATES_CONFIG) -> GatesConfig:
    return GatesConfig.model_validate(_load(path))
