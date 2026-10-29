"""Coding-agent adapter interface (spec 11.1) and secret redaction.

Adapters only run an agent in an already-prepared workspace and report what happened. They
never score anything and never see oracle artifacts. A development adapter (scripted patch)
exists only to test the pipeline; its runs are flagged and excluded from pilot results.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

AgentErrorCategory = Literal["TIMEOUT", "API_ERROR", "INFRA_ERROR"]


class AgentResult(BaseModel):
    """What an adapter reports. Diff data is added by the harness, not trusted from the agent."""

    model_config = ConfigDict(extra="forbid")

    final_summary: str  # exact final response text
    exit_code: int
    tool_version: str
    elapsed_seconds: float = Field(ge=0.0)
    stdout: str = ""  # already redacted
    stderr: str = ""  # already redacted
    error_category: AgentErrorCategory | None = None
    model_id: str | None = None
    # Spec 11.3: never claim determinism the provider did not promise.
    seed_requested: int
    seed_honored: bool | None = None  # None = unknown / not applicable
    generation_params: dict[str, Any] = {}


class CodingAgent(Protocol):
    agent_id: str
    is_development_adapter: bool

    def run_task(
        self,
        *,
        repository_path: Path,
        instruction: str,
        seed: int,
        timeout_seconds: int,
        max_tokens: int | None,
    ) -> AgentResult: ...


_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"cohere_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S{6,}"),
]


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove known secret values and common credential patterns from captured output."""
    for secret in secrets:
        if secret and len(secret) >= 6:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
