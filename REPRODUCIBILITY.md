# Reproducibility (Phase 2, experiment version `phase2-0.1`)

## Environment

- Python 3.11 or newer (developed and run on 3.13.5, macOS).
- Dependencies are declared in `pyproject.toml` with lower bounds only. They are **not pinned yet**; the
  spec asks to pin after the pilot works. The versions actually used are recorded inside
  `testbeds/<tb>/baseline/baseline_coverage.json` (`environment`).
- No secrets, network access, or LLM calls are needed.

## Setup and commands

```bash
make install                                   # venv + editable install + dev tools
make lint                                      # ruff
make test                                      # pytest (tests/) then pytest in each testbed
make test-fast                                 # skips tests that spawn replay subprocesses
make testbed-validate                          # cross-validate every testbed; print hashes
make baseline TESTBED=file_portal              # one testbed: k=5 per attack, 5 benign replays, 30 calibration replays per attack
make baseline-all                              # both testbeds (about 20 minutes)
make baseline-all FORCE=--force                # re-record (only when intentionally creating a new baseline)
```

Direct equivalents:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest testbeds/billing_api -p no:cacheprovider
.venv/bin/python -m pytest testbeds/file_portal -p no:cacheprovider
.venv/bin/python scripts/run_baseline.py --testbed billing_api --calibrate 30
```

The pytest invocations are separate on purpose: every testbed exposes a top-level package named `app`.

## Artifacts written by `make baseline`

In `testbeds/<tb>/baseline/`:

| File | Content |
|---|---|
| `baseline_replay_runs.jsonl` | One `ReplayRecord` per baseline replay (the replay ledger) |
| `baseline_coverage.json` | Per-attack detection status, set A0, per-attack flake rates, unexpected (cross-fired) rules, negative-control result, frozen hashes (incl. `benign_set_hash`), environment, isolation level, functional-test result |
| `flake_calibration_runs.jsonl`, `flake_calibration.json` | Larger replay batch used only to measure flake rate |

## Freeze policy

`baseline_coverage.json` stores hashes of the rule pack and mapping, attack set, telemetry schema and
catalog, detector engine, replay harness, and testbed source. A test
(`test_committed_baseline_matches_the_current_frozen_artifacts`) fails if any of these change after the
baseline was recorded. Fixing that requires a new baseline under a new `experiment_version` in
`configs/replay.yaml`, never an in-place edit of results.

## Known limitations

- Replays are isolated by a fresh process, not a container; outbound network is not blocked (DECISIONS D-03).
- Criticality, `security_bearing` labels and ATT&CK mappings are provisional; G2 is open (D-10, D-19).
- The Phase 1 baseline is reproducible only from git tag `phase1-baseline` (D-11).
- Timestamps and event IDs differ between runs by design; detection never depends on them.
