"""Agent workspace construction, isolation checks and diff collection (spec 11.2).

The agent sees only the files of an explicit allowlist (``app/**/*.py``, ``tests/**/*.py``,
``pytest.ini``). Attacks, benign workloads, detection rules, mapping, event catalog,
instructions, baseline artifacts, scoring code and previous runs are never copied.
"""

from __future__ import annotations

import difflib
import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict

WORKSPACE_ALLOWLIST = ("app/**/*.py", "tests/**/*.py", "pytest.ini")
EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".git"}
# Names that must never appear in an agent workspace (relative path components).
FORBIDDEN_PATH_PARTS = (
    "attacks",
    "benign",
    "detection",
    "baseline",
    "instructions",
    "event_catalog.yaml",
    "baseline_coverage.json",
    "mapping.json",
)
# Strings that must never appear in workspace file contents.
FORBIDDEN_CONTENT = (
    "IIDE-",
    "baseline_coverage",
    "rule_pack",
    "required_by_rules",
    "required_by_attacks",
)


class IsolationViolation(RuntimeError):
    """Oracle material was found in an agent workspace."""


def _files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and not (set(p.relative_to(root).parts) & EXCLUDED_DIRS)
    )


def build_workspace(testbed_root: Path, dest: Path) -> list[str]:
    """Copy only allowlisted files into a fresh ``dest``; return their relative paths."""
    if dest.exists():
        raise FileExistsError(f"workspace already exists: {dest}")
    dest.mkdir(parents=True)
    copied: list[str] = []
    for pattern in WORKSPACE_ALLOWLIST:
        for src in sorted(testbed_root.glob(pattern)):
            if not src.is_file() or set(src.relative_to(testbed_root).parts) & EXCLUDED_DIRS:
                continue
            rel = src.relative_to(testbed_root)
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            copied.append(rel.as_posix())
    return sorted(set(copied))


def check_workspace_isolation(workspace: Path) -> list[str]:
    """Return a list of violations (empty = clean). Checked before and after the agent runs."""
    problems: list[str] = []
    for path in _files(workspace):
        rel = path.relative_to(workspace)
        for part in rel.parts:
            if part in FORBIDDEN_PATH_PARTS:
                problems.append(f"forbidden path component {part!r}: {rel.as_posix()}")
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in FORBIDDEN_CONTENT:
            if needle in text:
                problems.append(f"forbidden content {needle!r} in {rel.as_posix()}")
    return problems


def assert_workspace_isolated(workspace: Path) -> None:
    problems = check_workspace_isolation(workspace)
    if problems:
        raise IsolationViolation("; ".join(problems))


class DiffSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    changed_files: list[str]
    patch_empty: bool
    diff_sha256: str
    tests_modified: bool
    outside_app_changed: list[str]  # changed files that are not under app/ (not scored)


@dataclass(frozen=True)
class DiffResult:
    summary: DiffSummary
    unified_diff: str


def diff_against(original_root: Path, workspace: Path) -> DiffResult:
    """Unified diff of the workspace against the original allowlisted files."""
    original = {
        p.relative_to(original_root).as_posix(): p for p in allowlisted_files(original_root)
    }
    current = {p.relative_to(workspace).as_posix(): p for p in _files(workspace)}
    changed: list[str] = []
    chunks: list[str] = []
    for rel in sorted(set(original) | set(current)):
        before = (
            original[rel].read_text(encoding="utf-8").splitlines(keepends=True)
            if rel in original
            else []
        )
        after = (
            current[rel].read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            if rel in current
            else []
        )
        if before == after and (rel in original) == (rel in current):
            continue
        changed.append(rel)
        chunks.extend(
            difflib.unified_diff(
                before,
                after,
                fromfile=f"a/{rel}" if rel in original else "/dev/null",
                tofile=f"b/{rel}" if rel in current else "/dev/null",
            )
        )
    text = "".join(chunks)
    summary = DiffSummary(
        changed_files=changed,
        patch_empty=not changed,
        diff_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        tests_modified=any(c.startswith("tests/") or c == "pytest.ini" for c in changed),
        outside_app_changed=[c for c in changed if not c.startswith("app/")],
    )
    return DiffResult(summary, text)


def allowlisted_files(root: Path) -> list[Path]:
    out: dict[str, Path] = {}
    for pattern in WORKSPACE_ALLOWLIST:
        for p in root.glob(pattern):
            if p.is_file() and not (set(p.relative_to(root).parts) & EXCLUDED_DIRS):
                out[p.relative_to(root).as_posix()] = p
    return [out[k] for k in sorted(out)]


def apply_unified_diff(workspace: Path, diff_text: str) -> None:
    """Apply a ``a/`` ``b/`` unified diff produced by ``diff_against`` onto ``workspace``."""
    if not (diff_text or "").strip():
        return
    proc = subprocess.run(
        ["patch", "-p1", "--forward", "--batch"],
        cwd=workspace,
        input=diff_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise ValueError(f"patch failed: {detail}")


def build_candidate_root(oracle_root: Path, workspace: Path, dest: Path) -> Path:
    """Oracle testbed with ONLY ``app/`` replaced by the agent's version.

    Frozen tests, attacks, rules and catalog come from the oracle copy, never from the
    workspace, so an agent cannot change what is measured by editing tests.
    """
    shutil.copytree(
        oracle_root,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "baseline", "instructions"),
    )
    shutil.rmtree(dest / "app")
    shutil.copytree(workspace / "app", dest / "app", ignore=shutil.ignore_patterns("__pycache__"))
    return dest
