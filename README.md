# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Phase 5 harness plus G1 PASSED.** The prior-art sweep is in
> [`docs/g1_prior_art.md`](docs/g1_prior_art.md) (recommended **GO** for the E1+E2+E3 combination).
> That memo is not a novelty claim. Gate **G2** is still **OPEN**: 28 construct vignettes are in
> [`docs/g2/`](docs/g2/); a second independent annotator has not labelled them. Human worksheets for
> `S_sec`, criticality, and instruction review are in [`docs/reviews/`](docs/reviews/) and are also
> unlabelled by A2. `make report` writes a pre-pilot status file, not a 144-run result. A G4
> construct check on scripted patches is in `experiments/reports/g4_calibration.md` and does not set
> G4 to PASSED. **No LLM has been called and no experimental result exists.** A real 144-run is
> refused until G2 passes, instructions are REVIEWED, and two agent adapters are configured.
> Isolation is still process-level.

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
make g2-agreement                # G2 kappa; exits 2 until annotator_b.yaml is filled
make report                      # pre-pilot status; exit 1 only on frozen-hash drift
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
experiments/reports/           G4 calibration + pre-pilot status (not 144-run results)
docs/g2/                       G2 construct pack (rubric, 28 vignettes, A1 labels; A2 pending)
docs/reviews/                  S_sec, criticality, instruction worksheets (A2 pending)
scripts/                       run_baseline.py, run_pilot.py, score_replays.py, score_runs.py, compare_baselines.py, score_g2.py, verify_reproducibility.py, export_review_packs.py
configs/llm_reviewer.yaml      frozen LLM-diff prompt; command unset → UNAVAILABLE
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
