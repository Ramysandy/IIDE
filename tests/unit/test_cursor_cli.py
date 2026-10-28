"""Cursor command-adapter frontend. Does not call the Cursor API."""

from __future__ import annotations

import io
import sys

from iide.runner.cursor_cli import main


def test_cursor_cli_exits_1_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO("reduce alert noise"))
    assert main(["--model", "composer-2.5"]) == 1


def test_cursor_cli_exits_1_on_empty_instruction(monkeypatch):
    monkeypatch.setenv("CURSOR_API_KEY", "cursor_test_placeholder_not_a_real_key")
    monkeypatch.setattr(sys, "stdin", io.StringIO("   "))
    assert main(["--model", "composer-2.5"]) == 1
