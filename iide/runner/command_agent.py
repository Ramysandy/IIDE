"""Generic command-line agent adapter.

Runs a user-configured command with the workspace as its working directory. It is deliberately
vendor-neutral: no real agent CLI has been validated against it yet (spec 11.1: add real
adapters only after interface validation). Placeholders in ``argv``: ``{instruction}``,
``{repository}``, ``{seed}``, ``{max_tokens}``. The child gets a scrubbed environment: only
``PATH``, a private ``HOME`` and the names listed in ``env_passthrough`` (e.g. an API key
variable). Anything the agent prints is redacted before it is stored.

Isolation exception (recorded, D-03/D-31): this is process-level only. The agent runs as the
same OS user and is not prevented from reading absolute paths outside the workspace, and the
network is not blocked. The workspace itself contains no oracle artifacts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from iide.runner.agent_interface import AgentResult, redact


class CommandAgent:
    is_development_adapter = False

    def __init__(
        self,
        *,
        agent_id: str,
        argv: list[str],
        tool_version: str,
        env_passthrough: list[str] | None = None,
        stdin_instruction: bool = False,
        model_id: str | None = None,
        generation_params: dict[str, object] | None = None,
        seed_honored: bool | None = None,
    ) -> None:
        if not argv:
            raise ValueError("argv must not be empty")
        self.agent_id = agent_id
        self._argv = list(argv)
        self._tool_version = tool_version
        self._env_passthrough = list(env_passthrough or [])
        self._stdin = stdin_instruction
        self._model_id = model_id
        self._params = dict(generation_params or {})
        self._seed_honored = seed_honored

    def run_task(
        self,
        *,
        repository_path: Path,
        instruction: str,
        seed: int,
        timeout_seconds: int,
        max_tokens: int | None,
    ) -> AgentResult:
        fill = {
            "instruction": instruction,
            "repository": str(repository_path),
            "seed": str(seed),
            "max_tokens": "" if max_tokens is None else str(max_tokens),
        }
        argv = [part.format(**fill) for part in self._argv]
        # The child cwd is the agent workspace, which has no venv. Use the
        # orchestrator interpreter so ``python -m iide...`` still resolves.
        if argv and Path(argv[0]).name in {"python", "python3"}:
            argv = [sys.executable, *argv[1:]]
        secrets = [os.environ[name] for name in self._env_passthrough if name in os.environ]
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="iide-agent-home-") as home:
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home}
            env.update({n: os.environ[n] for n in self._env_passthrough if n in os.environ})
            try:
                proc = subprocess.run(
                    argv,
                    cwd=repository_path,
                    env=env,
                    input=instruction if self._stdin else None,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return self._result(
                    "", -1, start, seed, "TIMEOUT", _text(exc.stdout), _text(exc.stderr), secrets
                )
            except OSError as exc:
                return self._result(
                    f"agent could not be started: {exc}",
                    -1,
                    start,
                    seed,
                    "INFRA_ERROR",
                    "",
                    "",
                    secrets,
                )
        category = None if proc.returncode == 0 else "API_ERROR"
        return self._result(
            proc.stdout, proc.returncode, start, seed, category, proc.stdout, proc.stderr, secrets
        )

    def _result(self, summary, code, start, seed, category, out, err, secrets) -> AgentResult:
        return AgentResult(
            final_summary=redact(summary, secrets),
            exit_code=code,
            tool_version=self._tool_version,
            elapsed_seconds=time.monotonic() - start,
            stdout=redact(out, secrets),
            stderr=redact(err, secrets),
            error_category=category,
            model_id=self._model_id,
            seed_requested=seed,
            seed_honored=self._seed_honored,
            generation_params=dict(self._params),
        )


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value
