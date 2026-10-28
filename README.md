# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Phase 4 (agent harness) on top of the Phase 2 testbeds and Phase 3 scoring library.** The
> 144-run manifest is generated and validated. A local-patch development adapter exercises the pipeline.
> **No LLM has been called and no experimental result exists.** Gate **G2** (kappa >= 0.6) is **not met**;
> gate **G1** (prior-art) is still open. A real 144-run execution is refused until both gates pass and two
> agent adapters are configured. Isolation is still process-level (Docker is not running here).

Authoritative specification: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Plan:
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Decisions: [`DECISIONS.md`](DECISIONS.md). Source
documents: [`docs/`](docs/).

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
```

## Layout (Phase 4)

```text
configs/{replay,experiment,agents,gates}.yaml
schemas/                       telemetry, instruction and run-record JSON Schemas
testbeds/<tb>/app,tests        agent-visible program and functional tests
testbeds/<tb>/instructions     F1/F2/F4/F6 x {ambiguous,scoped,neutral} (oracle side)
testbeds/<tb>/{attacks,detection,baseline,benign}   frozen oracle; never mounted for the agent
iide/runner/                   workspace isolation, adapters, manifest, orchestration
iide/scoring/                  metrics (spec 7, 13)
experiments/manifests/         144-run plan (JSONL)
experiments/raw/               per-run artifacts (gitignored)
scripts/                       run_baseline.py, run_pilot.py, score_replays.py, score_runs.py
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
