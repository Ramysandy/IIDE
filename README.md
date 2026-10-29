# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Composer 48-cell grid (seeds 1–2); G1–G4 PASSED (operator, restricted).**
> Live results: 48/48 `SCORED`, 4 confirmed erosions; not 144; not `auto`. Writeup:
> [`experiments/reports/pilot_report.md`](experiments/reports/pilot_report.md),
> [`composer_cells.csv`](experiments/reports/composer_cells.csv),
> [`figures/`](experiments/reports/figures/). The prior-art sweep is in
> [`docs/g1_prior_art.md`](docs/g1_prior_art.md) (recommended **GO** for E1+E2+E3).
> That memo is not a novelty claim. Gate **G2** is **PASSED** with D-44: construct
> κ = 1.000 is not independent human reliability. **G3**/**G4** operator PASS was
> recorded on the billing_api F1 seed-1 triple (D-48); the 48-cell grid is extra
> evidence on the same agent, not a 144-run. Isolation is process-level.
> `CURSOR_API_KEY` is never committed (D-45).

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
make score-matched               # IAE/IIF/SR/DG on billing_api F1 composer seed 1
make compare-baselines           # G4 construct check on scripted patches; never calls an LLM
make compare-live                # G4 on the three live F1 diffs; never calls an LLM
make compare-baselines WITH_LLM=1  # four Cohere calls if COHERE_API_KEY is set (D-47)
make g2-agreement                # G2 kappa; exits 2 until annotator_b.yaml is filled
make report                      # harness check (pre_pilot_status) + pointer to pilot_report.md
```

## Layout

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
experiments/reports/           48-cell pilot_report, composer_cells.csv, figures, G4 live + calibration
docs/paper/                    restricted paper skeleton (methods / results / limitations)
docs/g2/                       G2 construct pack (rubric, 28 vignettes, A1 labels; A2 pending)
docs/reviews/                  S_sec, criticality, instruction worksheets (A2 pending)
scripts/                       run_baseline.py, run_pilot.py, score_replays.py, score_runs.py, score_matched_group.py, compare_baselines.py, compare_live.py, score_g2.py, verify_reproducibility.py, export_review_packs.py
configs/llm_reviewer.yaml      frozen LLM-diff prompt; live Cohere only with --with-llm
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
