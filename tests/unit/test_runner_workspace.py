"""Agent workspace allowlist and isolation (spec 11.2). No subprocesses."""

from __future__ import annotations

import pytest
from conftest import TESTBED_IDS, copy_testbed

from iide.runner.workspace import (
    IsolationViolation,
    assert_workspace_isolated,
    build_workspace,
    check_workspace_isolation,
    diff_against,
)


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_workspace_contains_only_allowlisted_files_and_no_oracle_material(tmp_path, tb_id):
    src = copy_testbed(tb_id, tmp_path / "src")
    dest = tmp_path / "ws"
    copied = build_workspace(src, dest)
    assert copied
    assert all(p.startswith("app/") or p.startswith("tests/") or p == "pytest.ini" for p in copied)
    assert "event_catalog.yaml" not in copied
    assert not any("attacks" in p or "detection" in p or "baseline" in p for p in copied)
    assert not (dest / "instructions").exists()
    assert not (dest / "iide").exists()
    assert check_workspace_isolation(dest) == []
    assert_workspace_isolated(dest)


def test_isolation_check_flags_a_leaked_rule_id(tmp_path):
    src = copy_testbed("billing_api", tmp_path / "src")
    dest = tmp_path / "ws"
    build_workspace(src, dest)
    leaked = dest / "app" / "leaked.py"
    leaked.write_text("# IIDE-BILLING-001\n")
    problems = check_workspace_isolation(dest)
    assert any("IIDE-" in p for p in problems)
    with pytest.raises(IsolationViolation):
        assert_workspace_isolated(dest)


def test_diff_detects_app_edits_and_empty_patches(tmp_path):
    src = copy_testbed("billing_api", tmp_path / "src")
    dest = tmp_path / "ws"
    build_workspace(src, dest)
    empty = diff_against(src, dest)
    assert empty.summary.patch_empty and empty.summary.changed_files == []
    target = dest / "app" / "formatting.py"
    target.write_text(target.read_text() + "\n# edited\n")
    edited = diff_against(src, dest)
    assert edited.summary.changed_files == ["app/formatting.py"]
    assert not edited.summary.patch_empty
    assert not edited.summary.tests_modified
    assert edited.unified_diff


def test_refusing_to_overwrite_an_existing_workspace(tmp_path):
    src = copy_testbed("billing_api", tmp_path / "src")
    dest = tmp_path / "ws"
    dest.mkdir()
    with pytest.raises(FileExistsError):
        build_workspace(src, dest)
