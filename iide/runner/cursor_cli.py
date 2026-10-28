"""Cursor SDK frontend for the command adapter (spec 11.1).

Runs in the prepared agent workspace (cwd). Reads the instruction from stdin.
Does not score, does not touch oracle artifacts, and does not print API keys.

Install: ``pip install 'iide[agents]'`` then set ``CURSOR_API_KEY``.
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="Cursor model id, e.g. composer-2.5")
    args = parser.parse_args(argv)
    instruction = sys.stdin.read()
    if not instruction.strip():
        print("empty instruction on stdin", file=sys.stderr)
        return 1
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not key:
        print("CURSOR_API_KEY is not set", file=sys.stderr)
        return 1
    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError:
        print("cursor-sdk is not installed; pip install 'iide[agents]'", file=sys.stderr)
        return 1
    try:
        result = Agent.prompt(
            instruction,
            AgentOptions(
                api_key=key,
                model=args.model,
                local=LocalAgentOptions(cwd=os.getcwd()),
            ),
        )
    except Exception as exc:  # CursorAgentError and startup failures
        print(f"startup failed: {exc}", file=sys.stderr)
        return 1
    status = getattr(result, "status", None)
    text = getattr(result, "result", None) or getattr(result, "text", None) or str(result)
    sys.stdout.write(str(text))
    if status == "error":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
