"""Typed experiment configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY_CONFIG = REPO_ROOT / "configs" / "replay.yaml"
DEFAULT_TELEMETRY_SCHEMA = REPO_ROOT / "schemas" / "telemetry_event.schema.json"
TESTBEDS_DIR = REPO_ROOT / "testbeds"


class ReplayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    experiment_version: str = Field(min_length=1)
    min_valid_percent: int = Field(ge=1, le=100)
    flake_rate_limit: float = Field(gt=0.0, lt=1.0)
    replay_timeout_seconds: int = Field(ge=1)
    attack_alert_aggregation: Literal["any_expected_rule"]


def load_replay_config(path: Path | None = None) -> ReplayConfig:
    path = path or DEFAULT_REPLAY_CONFIG
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return ReplayConfig.model_validate(data)
