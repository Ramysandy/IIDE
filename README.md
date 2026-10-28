# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Phase 5 harness plus a Phase 0 G1 memo.** The prior-art sweep is in
> [`docs/g1_prior_art.md`](docs/g1_prior_art.md) (recommended **GO** for the E1+E2+E3 combination).
> Gate **G1** is still **OPEN** until a human reviewer sets PASSED. That memo is not a novelty claim.
> A G4 construct check on scripted patches is in `experiments/reports/g4_calibration.md` and does not
> set G4 to PASSED. **No LLM has been called and no experimental result exists.** Gate **G2** is still
> open. A real 144-run is refused until G1 and G2 pass and two agent adapters are configured.
> Isolation is still process-level (Docker is not running here).

Authoritative specification: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Plan:
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Decisions: [`DECISIONS.md`](DECISIONS.md). Source
documents: [`docs/`](docs/) (G1 memo committed; proposal PDFs stay local/gitignored).

## Safety

Everything is synthetic. The toy service is driven in-process and opens no socket; attack emulations only
send synthetic requests to it and contact no external system.

## Quick start

```bash
make install          # creates .venv and installs the package with dev tools
make test             # project tests + each testbed's functional tests
make baseline-all     # records testbeds/*/baseline/* (refuses to overwrite; FORCE=--force)
make score TESTBED=billing_api   # baseline self-comparison report (a harness check, not a result)
make run-pilot DRY_RUN=1         # validate the 144-run manifest; never calls an agent
make compare-baselines           # G4 construct check on scripted patches; never calls an LLM
```

## Layout (Phase 5)

```text
configs/{replay,experiment,agents,gates}.yaml
schemas/                       telemetry, instruction and run-record JSON Schemas
testbeds/<tb>/app,tests        agent-visible program and functional tests
testbeds/<tb>/instructions     F1/F2/F4/F6 x {ambiguous,scoped,neutral} (oracle side)
testbeds/<tb>/{attacks,detection,baseline,benign}   frozen oracle; never mounted for the agent
iide/runner/                   workspace isolation, adapters, manifest, orchestration
iide/scoring/                  metrics (spec 7, 13)
iide/analysis/                 Phase 3 reports + Phase 5 comparison methods
experiments/manifests/         144-run plan (JSONL)
experiments/raw/               per-run artifacts (gitignored)
experiments/reports/           G4 calibration (construct check, not a 144-run result)
scripts/                       run_baseline.py, run_pilot.py, score_replays.py, score_runs.py, compare_baselines.py
configs/llm_reviewer.yaml      frozen LLM-diff prompt; command unset → UNAVAILABLE
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
