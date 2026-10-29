# Reproducibility (Phase 5 on experiment version `phase4-0.1`)

## Environment

- Python 3.11 or newer (developed and run on 3.13.5, macOS).
- Dependencies are declared in `pyproject.toml` with lower bounds only. They are **not pinned yet**; the
  spec asks to pin after the pilot works. The versions actually used are recorded inside
  `testbeds/<tb>/baseline/baseline_coverage.json` (`environment`).
- No secrets, network access, or LLM calls are needed for tests, baselines, `make run-pilot DRY_RUN=1`,
  or default `make compare-baselines`. Optional `make compare-baselines WITH_LLM=1` needs
  `COHERE_API_KEY` (never committed) and makes four Chat calls (D-47). A real 144-run needs
  `CURSOR_API_KEY` (never committed) and `pip install 'iide[agents]'` (D-45). Bandit is used
  only if the `bandit` CLI is on PATH; CodeQL is not claimed unless the `codeql` CLI is present.

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
make score TESTBED=file_portal                 # score a ledger vs the baseline; default is a self-comparison check
make manifest-pilot                            # write experiments/manifests/pilot.jsonl (144 rows)
make run-pilot DRY_RUN=1                       # validate the 144-run plan; never calls an agent
make score-runs                                # list primary attempts under experiments/raw/ (if any)
make score-matched                             # IAE/IIF/SR/DG on billing_api F1 composer seed 1
make compare-baselines                         # G4 construct check; writes experiments/reports/g4_calibration.{md,json}
make compare-live                              # G4 on live F1 diffs; writes experiments/reports/g4_f1_live.{md,json}
make compare-baselines WITH_LLM=1              # four Cohere calls if COHERE_API_KEY is set; writes g4_llm_reviewer.{md,json}
make g2-agreement                              # G2 kappa; exits 2 if annotator_b.yaml is incomplete; does not set gates.yaml
make report                                    # harness check (pre_pilot_status); points at experiments/reports/pilot_report.md
make export-reviews                            # blinded A2 worksheets under docs/reviews/; does not fill B or set REVIEWED
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

## Scoring

`scripts/score_replays.py --testbed T [--candidate ledger.jsonl] [--output-dir D]` scores a replay ledger
against `testbeds/T/baseline/baseline_replay_runs.jsonl` and writes `coverage_report.{md,json}`. Without
`--candidate` it compares the baseline with itself (RC=1, ED=0, LEI=0), which checks the pipeline and is
not a result. Every report carries `scoring_package_hash` (hash of `iide/scoring/*.py`). The scoring code
is outside the frozen replay hashes, so it does not invalidate the baselines.

## Comparison baselines (Phase 5 / G4)

`scripts/compare_baselines.py` (Make: `compare-baselines`) applies four scripted patches to
`billing_api` and scores simpler methods against the replay-oracle labels of those patches. Default
path never calls an LLM. `--with-llm` calls Cohere `command-r7b-12-2024` on those four diffs only
when `COHERE_API_KEY` is set, and writes a separate report so the deterministic calibration file is
not overwritten. Output:

| File | Content |
|---|---|
| `experiments/reports/g4_calibration.md` | Human-readable confusion table and G4 construct-check note (no LLM) |
| `experiments/reports/g4_calibration.json` | Same payload (`schema_version` 1.0) |
| `experiments/reports/g4_llm_reviewer.md` | Same table after `--with-llm` (Cohere; not a 144-run) |
| `experiments/reports/g4_llm_reviewer.json` | Same payload; `llm_reviewer.detail` is redacted |
| `experiments/reports/g4_f1_live.md` | G4 on the three live F1 composer diffs (no LLM) |
| `experiments/reports/f1_composer_seed1.md` | IAE/IIF/SR/DG on billing_api-F1 seed 1 (no CIs) |
| `experiments/reports/pilot_report.md` | Paper-facing F1 pilot report (not 144) |

Scripted calibration is a **construct check**, not a 144-run finding. Regenerating
`g4_calibration.*` overwrites the previous derived files; the labels live in
`iide/analysis/fixtures.py`. Live F1 diffs are scored by `scripts/compare_live.py`
(`make compare-live`) into `g4_f1_live.{md,json}`. Operator set G4 PASSED on those
live diffs only (D-48); the analysis module still labels the construct check
`PROVISIONAL`. The 144-run was not executed.

## Freeze policy

`baseline_coverage.json` stores hashes of the rule pack and mapping, attack set, telemetry schema and
catalog, detector engine, replay harness, and testbed source. A test
(`test_committed_baseline_matches_the_current_frozen_artifacts`) fails if any of these change after the
baseline was recorded. Fixing that requires a new baseline under a new `experiment_version` in
`configs/replay.yaml`, never an in-place edit of results.

## Known limitations

- Replays and agent runs are isolated by a fresh process, not a container; outbound network is not blocked (D-03, D-31).
- Criticality, `security_bearing` labels and ATT&CK mappings are provisional (D-10, D-19).
- In-matrix instructions are REVIEWED (D-44). The 144-run has not been executed (D-35). The F1 composer seed-1 triple has (D-48).
- G4 scripted calibration is D-38/D-39. G4 on the three live F1 diffs is D-48 (`gates.yaml` PASSED for those diffs only).
- G1 sweep is in `docs/g1_prior_art.md` (D-40). Recommended GO; operator set G1 PASSED 2026-10-28.
- G2 construct pack is `docs/g2/` (D-41–D-44). A2 is filled; construct κ = 1.000; operator set G2 PASSED with the restriction that this is not independent human reliability. `S_sec` and criticality catalog/attack YAML remain provisional.
- `make report` is a harness check (D-42). The paper-facing pilot report is `experiments/reports/pilot_report.md`.
- Cursor command adapters are configured (D-45). Three live `composer-2.5` cells exist; `auto` was not called. A 144-run still needs `CURSOR_API_KEY`.
- Cell-filtered live example (restores `pilot.jsonl` timestamps after; never commit the key):
  `python scripts/run_pilot.py --testbed billing_api --family F1 --variant scoped --agent pilot_agent_a --seed 1`
- Optional Cohere LLM reviewer is D-47. It is not a coding agent and does not replace Cursor.
- Phase 1 is reproducible from tag `phase1-baseline`; Phase 2 from `phase2-baseline`; Phase 3 from `phase3-scoring`; Phase 4 from `phase4-harness`; Phase 5 from `phase5-baselines`.
- Timestamps and event IDs differ between runs by design; detection never depends on them.
