"""Fresh-process isolation for one replay, plus the standalone worker it launches.

Isolation level in Phase 1 (honest scope, see DECISIONS.md D-03): every replay runs in
a brand-new Python process (`python -I -B`) with a scrubbed environment, its own
temporary working directory and its own event sink file, so no state (lockout
counters, module globals, event sink) can leak between replays. The toy app is driven
in-process through a test client, so it opens no socket. This is NOT container
isolation and it does not block outbound network access by itself.

The worker half of this file imports nothing from the `iide` package and is handed
only: the testbed directory (for `app/`), one emulation file, a sink path and a
correlation ID. It never loads rules, mappings or baseline artifacts. Note that the
development venv installs `iide` in editable mode, so it is *importable* in the
worker's interpreter; keeping oracle artifacts out of the agent's workspace is a
separate Phase 4 mechanism (spec 11.2) and is not provided by this module.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

_STDERR_TAIL_CHARS = 2000


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None  # None when the process was killed on timeout
    timed_out: bool
    stderr_tail: str
    elapsed_seconds: float


def run_in_fresh_process(
    *,
    testbed_dir: Path,
    emulation_path: Path,
    sink_path: Path,
    correlation_id: str,
    timeout_seconds: int,
    workdir: Path,
) -> SandboxResult:
    cmd = [
        sys.executable,
        "-I",  # isolated mode: ignore PYTHON* env vars, user site, cwd on sys.path
        "-B",  # never write bytecode into the testbed or attacks directories
        str(Path(__file__).resolve()),
        "--testbed-dir",
        str(testbed_dir),
        "--emulation",
        str(emulation_path),
        "--sink",
        str(sink_path),
        "--correlation-id",
        correlation_id,
    ]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(workdir), "TMPDIR": str(workdir)}
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return SandboxResult(None, True, stderr[-_STDERR_TAIL_CHARS:], time.monotonic() - start)
    return SandboxResult(
        proc.returncode, False, proc.stderr[-_STDERR_TAIL_CHARS:], time.monotonic() - start
    )


# --------------------------------------------------------------------------- worker


class _JsonlSink:
    """Oracle-owned sink: the harness, not the code under test, collects events."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def emit(self, event: dict) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")


def _worker_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IIDE replay worker (internal).")
    parser.add_argument("--testbed-dir", required=True)
    parser.add_argument("--emulation", required=True)
    parser.add_argument("--sink", required=True)
    parser.add_argument("--correlation-id", required=True)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(args.testbed_dir).resolve()))
    # Emulations may import a sibling helper (e.g. attacks/emu_common.py).
    sys.path.insert(1, str(Path(args.emulation).resolve().parent))
    try:
        from app.main import create_app
        from fastapi.testclient import TestClient

        spec = importlib.util.spec_from_file_location("iide_emulation", args.emulation)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load emulation from {args.emulation}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        client = TestClient(create_app(sink=_JsonlSink(Path(args.sink))))
        module.emulate(client, correlation_id=args.correlation_id)
    except BaseException:
        traceback.print_exc()
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(_worker_main())
