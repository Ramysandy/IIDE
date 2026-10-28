#!/usr/bin/env python3
"""Record the frozen baseline for a testbed (spec 6.1 steps 5-8).

Runs the testbed's functional tests, replays every attack k times (k = the attack's
`replay_count`) in fresh instances, replays the benign workload as a negative control,
runs a larger per-attack flake calibration (default: `min_calibration_replays` from
configs/replay.yaml) and writes, into <output-dir>:

  baseline_replay_runs.jsonl    one record per baseline replay (the replay ledger)
  baseline_coverage.json        summary, A0, hashes, environment, negative control
  flake_calibration_runs.jsonl  calibration replays (unless --calibrate 0)
  flake_calibration.json        calibration summary   (unless --calibrate 0)

Refuses to overwrite existing artifacts without --force. Exit code 0 only if the exit
criterion holds: functional tests pass; every attack DETECTED; no rule fires that is not
mapped to the attack (cross-fire); flake rate below the limit per attack (baseline and
calibration); calibration of at least `min_calibration_replays`; the benign workload
fires no rule; baseline telemetry is schema-valid.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.config import TESTBEDS_DIR, load_replay_config  # noqa: E402
from iide.models import AttackBaseline, BaselineCoverage, ReplayRecord  # noqa: E402
from iide.replay.runner import (  # noqa: E402
    compute_frozen_hashes,
    load_testbed,
    run_attack_replays,
    run_benign_replays,
    run_functional_tests,
    summarize_attack,
)

NEGATIVE_CONTROL_REPLAYS = 5
_PACKAGES = ("fastapi", "starlette", "httpx", "pydantic", "jsonschema", "PyYAML", "pytest")


def _git_commit() -> tuple[str | None, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        return None, f"git unavailable: {exc}"
    if proc.returncode != 0:
        return None, "project is not a git repository; no commit to record"
    return proc.stdout.strip(), "git rev-parse HEAD (working tree may contain uncommitted edits)"


def _environment() -> dict:
    versions = {}
    for name in _PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": versions,
    }


_ISOLATION = {
    "level": (
        "fresh Python subprocess per replay (python -I -B), scrubbed env, own temp dir and sink"
    ),
    "container": False,
    "network_blocked": False,
    "service_binds_socket": False,
    "note": "App is driven in-process via a test client. See DECISIONS.md D-03.",
}


def _write_jsonl(path: Path, records: list[ReplayRecord]) -> None:
    path.write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")


def _write_json(path: Path, payload: str) -> None:
    path.write_text(payload.rstrip("\n") + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--testbed", required=True, help="directory name under testbeds/")
    parser.add_argument("--output-dir", type=Path, help="default: testbeds/<testbed>/baseline")
    parser.add_argument("--config", type=Path, help="default: configs/replay.yaml")
    parser.add_argument(
        "--calibrate",
        type=int,
        default=None,
        metavar="N",
        help="calibration replays per attack (default: min_calibration_replays; "
        "0 skips calibration and fails the criterion)",
    )
    parser.add_argument("--force", action="store_true", help="overwrite existing artifacts")
    args = parser.parse_args(argv)

    root = TESTBEDS_DIR / args.testbed
    out_dir = args.output_dir or root / "baseline"
    if args.calibrate is not None and args.calibrate < 0:
        print("error: --calibrate must be >= 0", file=sys.stderr)
        return 2
    config = load_replay_config(args.config)
    calibrate = config.min_calibration_replays if args.calibrate is None else args.calibrate

    targets = [out_dir / "baseline_coverage.json", out_dir / "baseline_replay_runs.jsonl"]
    if calibrate:
        targets += [out_dir / "flake_calibration.json", out_dir / "flake_calibration_runs.jsonl"]
    existing = [p for p in targets if p.exists()]
    if existing and not args.force:
        print("error: refusing to overwrite (use --force):", file=sys.stderr)
        for p in existing:
            print(f"  {p}", file=sys.stderr)
        return 2

    tb = load_testbed(root)
    hashes_before = compute_frozen_hashes(tb)

    print(f"[baseline] testbed={tb.testbed_id} experiment={config.experiment_version}")
    functional = run_functional_tests(tb)
    print(
        f"[baseline] functional tests: {'PASS' if functional.passed else 'FAIL'} "
        f"({functional.summary_line})"
    )

    records: list[ReplayRecord] = []
    baselines: list[AttackBaseline] = []
    for attack_id in sorted(tb.attacks):
        attack = tb.attacks[attack_id]
        attack_records = run_attack_replays(tb, attack_id, config)
        records += attack_records
        summary = summarize_attack(attack, attack_records, config)
        baselines.append(summary)
        print(
            f"[baseline] {attack_id}: {summary.status} fired={summary.fired_count}/"
            f"{summary.valid_replays} valid of k={summary.planned_k} "
            f"flake_rate={summary.flake_rate:.3f} "
            f"unexpected_rules={summary.unexpected_fired_rule_ids}"
        )

    negative = run_benign_replays(tb, config, NEGATIVE_CONTROL_REPLAYS)
    print(
        f"[baseline] negative control: valid={negative.valid_replays}/{negative.replays} "
        f"fired_rules={negative.fired_rule_ids} events={negative.raw_event_counts}"
    )

    calibration: list[AttackBaseline] = []
    calibration_records: list[ReplayRecord] = []
    for attack_id in sorted(tb.attacks) if calibrate else []:
        recs = run_attack_replays(
            tb, attack_id, config, planned_k=calibrate, program_ref="baseline-calibration"
        )
        calibration_records += recs
        s = summarize_attack(tb.attacks[attack_id], recs, config)
        calibration.append(s)
        print(
            f"[calibrate] {attack_id}: n={s.planned_k} valid={s.valid_replays} "
            f"fired={s.fired_count} flake_rate={s.flake_rate:.4f} "
            f"within_limit={s.flake_within_limit}"
        )

    hashes_after = compute_frozen_hashes(tb)
    notes: list[str] = []
    if hashes_before != hashes_after:
        notes.append("frozen artifacts changed during the baseline run")
    if not functional.passed:
        notes.append("baseline functional tests failed")
    for b in baselines:
        if b.status != "DETECTED":
            notes.append(f"attack {b.attack_id} is {b.status} at baseline")
        if b.unexpected_fired_rule_ids:
            notes.append(f"attack {b.attack_id} also fired {b.unexpected_fired_rule_ids}")
        if not b.flake_within_limit:
            notes.append(
                f"attack {b.attack_id} flake rate {b.flake_rate:.3f} >= limit {b.flake_limit}"
            )
    if calibrate < config.min_calibration_replays:
        notes.append(
            f"calibration of {calibrate} replays per attack is below the required "
            f"{config.min_calibration_replays}"
        )
    for c in calibration:
        if c.status != "DETECTED":
            notes.append(f"calibration: attack {c.attack_id} is {c.status}")
        if not c.flake_within_limit:
            notes.append(
                f"calibration: attack {c.attack_id} flake rate {c.flake_rate:.4f} "
                f">= limit {c.flake_limit}"
            )
    if negative.fired_rule_ids:
        notes.append(f"benign workload fired rules {negative.fired_rule_ids}")
    if negative.valid_replays != negative.replays:
        notes.append("some negative-control replays were invalid")
    if negative.schema_invalid_event_count or any(
        r.schema_invalid_event_count or r.malformed_line_count for r in records
    ):
        notes.append("baseline replays produced schema-invalid or malformed events")
    ok = not notes
    commit, commit_note = _git_commit()

    coverage = BaselineCoverage(
        experiment_version=config.experiment_version,
        testbed_id=tb.testbed_id,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        git_commit=commit,
        git_commit_note=commit_note,
        frozen_hashes=hashes_after,
        replay_config=config,
        environment=_environment(),
        isolation=_ISOLATION,
        functional_tests=functional,
        attacks=baselines,
        calibration_replays_per_attack=calibrate,
        negative_control=negative,
        baseline_detected_attack_ids=[b.attack_id for b in baselines if b.status == "DETECTED"],
        exit_criterion_met=ok,
        exit_criterion_notes=notes or ["all baseline checks passed"],
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "baseline_replay_runs.jsonl", records)
    _write_json(out_dir / "baseline_coverage.json", coverage.model_dump_json(indent=2))
    if calibrate:
        _write_jsonl(out_dir / "flake_calibration_runs.jsonl", calibration_records)
        _write_json(
            out_dir / "flake_calibration.json",
            json.dumps(
                {
                    "schema_version": "1.0",
                    "experiment_version": config.experiment_version,
                    "testbed_id": tb.testbed_id,
                    "replays_per_attack": calibrate,
                    "attacks": [c.model_dump(mode="json") for c in calibration],
                },
                indent=2,
            ),
        )
    print(f"[baseline] wrote artifacts to {out_dir}")
    print(f"[baseline] exit criterion: {'MET' if ok else 'NOT MET'}")
    for n in notes:
        print(f"  - {n}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
