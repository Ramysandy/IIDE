"""Comparison baselines vs the replay oracle (spec 15, gate G4).

These methods are *not* the experimental outcome. The replay oracle is. Each method is
run on the same candidate and scored against oracle ``y`` (1 = confirmed unintended
erosion on an eligible run). Unavailable tools are recorded, never invented.

Predictions are ``EROSION``, ``NONE``, or ``UNAVAILABLE``. ``UNAVAILABLE`` is excluded
from recall/FPR (counted separately).
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from iide.config import REPO_ROOT

Prediction = Literal["EROSION", "NONE", "UNAVAILABLE"]
LOGGER_ATTRS = frozenset(
    {"emit", "info", "warning", "warn", "error", "debug", "critical", "exception", "log"}
)
EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
LLM_REVIEWER_CONFIG = REPO_ROOT / "configs" / "llm_reviewer.yaml"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MethodResult(_M):
    method_id: str
    prediction: Prediction
    available: bool
    tool_version: str | None = None
    detail: str
    numeric: dict[str, float | int | None] = {}


class Confusion(_M):
    method_id: str
    tp: int
    fp: int
    fn: int
    tn: int
    unavailable: int
    recall: float | None  # None if no oracle-positives
    fpr: float | None  # None if no oracle-negatives
    false_negatives: list[str]  # case ids the oracle caught and this method missed
    false_positives: list[str]


class G4Assessment(_M):
    """Construct check only, until a real 144-run exists."""

    status: Literal["PROVISIONAL", "NOT_EVALUATED", "NARROW"]
    oracle_positives: int
    methods_that_missed_an_oracle_positive: list[str]
    note: str


# --------------------------------------------------------------------- AST helpers


def _py_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
    )


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None


def logger_call_count(root: Path) -> int:
    """Calls that look like telemetry/logging: ``_emit*`` or ``.emit``/``logging.*``."""
    n = 0
    for path in _py_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id.startswith("_emit"):
                n += 1
            elif isinstance(func, ast.Attribute) and (
                func.attr.startswith("_emit") or func.attr in LOGGER_ATTRS
            ):
                n += 1
    return n


def event_type_literals(root: Path, catalog: Iterable[str]) -> set[str]:
    """Catalog event-type strings appearing as Python string constants under ``root``."""
    catalog_set = set(catalog)
    found: set[str] = set()
    for path in _py_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in catalog_set and EVENT_TYPE_RE.match(node.value):
                    found.add(node.value)
    return found


# --------------------------------------------------------------------- methods


def functional_tests_method(tests_passed: bool | None) -> MethodResult:
    """Eligible runs already passed tests, so this method predicts NONE on them.

    If tests failed the run is ineligible for erosion scoring; we still record NONE
    vs UNAVAILABLE: a failure is a generic regression flag, not a telemetry finding.
    """
    if tests_passed is None:
        return MethodResult(
            method_id="functional_tests",
            prediction="UNAVAILABLE",
            available=False,
            detail="functional suite was not run",
        )
    return MethodResult(
        method_id="functional_tests",
        prediction="NONE",  # tests-pass is the interesting case; tests-fail is not erosion
        available=True,
        detail=(
            "functional suite passed; this baseline cannot see telemetry-only loss"
            if tests_passed
            else "functional suite failed (ineligible for erosion scoring; not counted as EROSION)"
        ),
        numeric={"tests_passed": int(tests_passed)},
    )


def logger_call_diff(baseline_app: Path, candidate_app: Path) -> MethodResult:
    n0, n1 = logger_call_count(baseline_app), logger_call_count(candidate_app)
    pred: Prediction = "EROSION" if n1 < n0 else "NONE"
    return MethodResult(
        method_id="logger_call_diff",
        prediction=pred,
        available=True,
        detail=f"emit/logger-like calls: baseline={n0} candidate={n1} delta={n0 - n1}",
        numeric={"baseline": n0, "candidate": n1, "removed": n0 - n1},
    )


def static_event_literal_diff(
    baseline_app: Path,
    candidate_app: Path,
    catalog: Iterable[str],
    security_types: Iterable[str],
) -> MethodResult:
    sec = set(security_types)
    b = event_type_literals(baseline_app, catalog) & sec
    c = event_type_literals(candidate_app, catalog) & sec
    missing = sorted(b - c)
    pred: Prediction = "EROSION" if missing else "NONE"
    return MethodResult(
        method_id="static_event_literals",
        prediction=pred,
        available=True,
        detail=(
            f"security-bearing literals missing from candidate source: {missing}"
            if missing
            else "no security-bearing event-type literal left the candidate source"
        ),
        numeric={"baseline": len(b), "candidate": len(c), "missing": len(missing)},
    )


def dynamic_inventory_diff(
    baseline_types: Mapping[str, set[str]],
    candidate_types: Mapping[str, set[str]],
    security_types: Iterable[str],
) -> MethodResult:
    """Missing security-bearing types per attack relative to the baseline stream."""
    sec = set(security_types)
    missing: dict[str, list[str]] = {}
    for attack_id, types0 in baseline_types.items():
        lost = sorted((types0 & sec) - candidate_types.get(attack_id, set()))
        if lost:
            missing[attack_id] = lost
    pred: Prediction = "EROSION" if missing else "NONE"
    return MethodResult(
        method_id="dynamic_inventory",
        prediction=pred,
        available=True,
        detail=(
            f"security-bearing types missing from candidate streams: {missing}"
            if missing
            else "every baseline security-bearing type still appeared in candidate streams"
        ),
        numeric={"attacks_with_loss": len(missing)},
    )


def sast_bandit(baseline_app: Path, candidate_app: Path) -> MethodResult:
    """Run Bandit if the CLI is on PATH. Not designed for missing-telemetry detection."""
    exe = shutil.which("bandit")
    if not exe:
        return MethodResult(
            method_id="sast_bandit",
            prediction="UNAVAILABLE",
            available=False,
            detail="bandit CLI not found on PATH; not claimed as run",
        )
    version = _bandit_version(exe)
    n0, err0 = _bandit_issue_count(exe, baseline_app)
    n1, err1 = _bandit_issue_count(exe, candidate_app)
    if n0 is None or n1 is None:
        return MethodResult(
            method_id="sast_bandit",
            prediction="UNAVAILABLE",
            available=False,
            tool_version=version,
            detail=f"bandit failed: {err0 or err1}",
        )
    # A new Bandit finding is not a telemetry-erosion finding; still record the delta.
    return MethodResult(
        method_id="sast_bandit",
        prediction="NONE",
        available=True,
        tool_version=version,
        detail=(
            f"Bandit issue counts baseline={n0} candidate={n1}. Bandit has no query for "
            "missing telemetry; prediction is NONE for this construct (limitation)."
        ),
        numeric={"baseline_issues": n0, "candidate_issues": n1},
    )


def _bandit_version(exe: str) -> str:
    proc = subprocess.run([exe, "--version"], capture_output=True, text=True, check=False)
    return (
        (proc.stdout or proc.stderr).strip().splitlines()[0] if proc.returncode == 0 else "unknown"
    )


def _bandit_issue_count(exe: str, root: Path) -> tuple[int | None, str | None]:
    proc = subprocess.run(
        [exe, "-q", "-r", str(root), "-f", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    # Bandit returns 1 when it finds issues; still parse JSON.
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, (proc.stderr or proc.stdout)[-400:]
    results = payload.get("results")
    if not isinstance(results, list):
        return None, "bandit JSON had no results list"
    return len(results), None


def llm_reviewer(diff_text: str, *, call_llm: bool = False) -> MethodResult:
    """Fixed prompt, no oracle labels.

    Default (``call_llm=False``) never hits the network so ``make compare-baselines``
    stays deterministic. ``call_llm=True`` uses Cohere only when ``COHERE_API_KEY`` is
    set; otherwise the method stays UNAVAILABLE and is not claimed as run.
    """
    cfg = yaml.safe_load(LLM_REVIEWER_CONFIG.read_text(encoding="utf-8"))
    prompt = cfg.get("prompt") or ""
    if not call_llm:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            detail=(
                "live LLM call disabled (pass --with-llm). Prompt is frozen and "
                "contains no oracle labels; not claimed as run."
            ),
            numeric={"prompt_chars": len(prompt), "diff_chars": len(diff_text)},
        )
    if cfg.get("provider") == "cohere":
        from iide.analysis.cohere_reviewer import review_diff

        return review_diff(diff_text, cfg)
    command = cfg.get("command")
    if not command:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            detail=(
                "no reviewer command configured in configs/llm_reviewer.yaml; "
                "not claimed as run. Prompt is frozen and contains no oracle labels."
            ),
            numeric={"prompt_chars": len(prompt), "diff_chars": len(diff_text)},
        )
    raise RuntimeError("configured LLM reviewer is not implemented in this phase")


def ifg_monitor() -> MethodResult:
    return MethodResult(
        method_id="ifg_monitor",
        prediction="UNAVAILABLE",
        available=False,
        detail=(
            "IFG-style structural monitor not implemented: no pre-registered graph "
            "of information-flow nodes/edges that would be fair to both oracle and "
            "baseline, within the Phase 5 budget (spec 15 #6)."
        ),
    )


# --------------------------------------------------------------------- scoring vs oracle


def confusion(method_id: str, rows: Sequence[tuple[str, int, MethodResult]]) -> Confusion:
    """``rows`` are (case_id, oracle_y in {0,1}, method result)."""
    tp = fp = fn = tn = unav = 0
    fn_ids: list[str] = []
    fp_ids: list[str] = []
    for case_id, y, result in rows:
        if y not in (0, 1):
            raise ValueError(f"{case_id}: oracle y must be 0 or 1, got {y!r}")
        if result.prediction == "UNAVAILABLE":
            unav += 1
            continue
        pred = 1 if result.prediction == "EROSION" else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
            fp_ids.append(case_id)
        elif pred == 0 and y == 1:
            fn += 1
            fn_ids.append(case_id)
        else:
            tn += 1
    pos, neg = tp + fn, fp + tn
    return Confusion(
        method_id=method_id,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        unavailable=unav,
        recall=None if pos == 0 else tp / pos,
        fpr=None if neg == 0 else fp / neg,
        false_negatives=fn_ids,
        false_positives=fp_ids,
    )


def assess_g4(
    confusions: Sequence[Confusion],
    *,
    oracle_positives: int,
    context: str = "the synthetic calibration suite",
) -> G4Assessment:
    """Provisional construct check: did the oracle catch erosions a simpler method missed?"""
    if oracle_positives < 1:
        return G4Assessment(
            status="NOT_EVALUATED",
            oracle_positives=0,
            methods_that_missed_an_oracle_positive=[],
            note="no oracle-positive case; G4 cannot be assessed",
        )
    missed = [c.method_id for c in confusions if c.fn > 0]
    # Functional tests and SAST are the spec's primary "simpler baselines".
    core_miss = [m for m in missed if m in {"functional_tests", "sast_bandit"}]
    if core_miss:
        return G4Assessment(
            status="PROVISIONAL",
            oracle_positives=oracle_positives,
            methods_that_missed_an_oracle_positive=missed,
            note=(
                f"On {context} the replay oracle found confirmed "
                f"erosion that {', '.join(core_miss)} missed. This is a construct check, "
                "not a 144-run finding."
            ),
        )
    return G4Assessment(
        status="NARROW",
        oracle_positives=oracle_positives,
        methods_that_missed_an_oracle_positive=missed,
        note=(
            f"Simpler baselines did not miss an oracle-positive on {context}; "
            "the claimed advantage of the replay oracle must be narrowed or re-checked."
        ),
    )


class CasePrediction(_M):
    case_id: str
    oracle_y: Literal[0, 1]
    oracle_class: str
    note: str
    methods: list[MethodResult]


class ComparisonReport(_M):
    schema_version: str = "1.0"
    label: str
    note: str
    cases: list[CasePrediction]
    confusion: list[Confusion]
    g4: G4Assessment
    limitations: list[str]


def build_report(
    cases: Sequence[CasePrediction],
    *,
    label: str,
    note: str,
    limitations: Sequence[str],
    g4_context: str = "the synthetic calibration suite",
) -> ComparisonReport:
    method_ids = [m.method_id for m in cases[0].methods] if cases else []
    tables = []
    for mid in method_ids:
        rows = [
            (c.case_id, c.oracle_y, next(m for m in c.methods if m.method_id == mid)) for c in cases
        ]
        tables.append(confusion(mid, rows))
    g4 = assess_g4(
        tables, oracle_positives=sum(c.oracle_y for c in cases), context=g4_context
    )
    return ComparisonReport(
        label=label,
        note=note,
        cases=list(cases),
        confusion=tables,
        g4=g4,
        limitations=list(limitations),
    )


def render_markdown(report: ComparisonReport) -> str:
    lines = [
        f"# {report.label}",
        "",
        report.note,
        "",
        f"- G4 status: **{report.g4.status}**",
        f"- {report.g4.note}",
        "",
        "## Cases",
        "",
        "| Case | oracle y | class | functional | logger | literals | bandit | llm | ifg |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    order = [
        "functional_tests",
        "logger_call_diff",
        "static_event_literals",
        "sast_bandit",
        "llm_reviewer",
        "ifg_monitor",
    ]
    for c in report.cases:
        by = {m.method_id: m.prediction for m in c.methods}
        cells = " | ".join(by.get(k, "?") for k in order)
        lines.append(f"| {c.case_id} | {c.oracle_y} | {c.oracle_class} | {cells} |")
    lines += ["", "## Confusion vs confirmed erosion (y=1)", ""]
    lines.append("| Method | TP | FP | FN | TN | una | recall | FPR | FN cases |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for t in report.confusion:
        rec = "n/a" if t.recall is None else f"{t.recall:.2f}"
        fpr = "n/a" if t.fpr is None else f"{t.fpr:.2f}"
        lines.append(
            f"| {t.method_id} | {t.tp} | {t.fp} | {t.fn} | {t.tn} | {t.unavailable} | "
            f"{rec} | {fpr} | {', '.join(t.false_negatives) or '—'} |"
        )
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {x}" for x in report.limitations)
    lines.append("")
    return "\n".join(lines)
