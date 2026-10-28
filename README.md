# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Phase 3 (scoring library) on top of the Phase 2 testbeds.** `billing_api` and `file_portal`
> (frozen rule packs, benign controls, baselines) plus `iide/scoring/` (RC, ED, LEI, IAE, IIF, SR, DG, CAI,
> ISP, NRG, Pareto frontier) verified against the spec section 9 worked example. There is no agent runner
> and no experimental result yet. Gate **G2** (inter-annotator kappa >= 0.6) is **not met**: criticality
> weights, `security_bearing` labels and ATT&CK mappings are provisional single-annotator values. The
> research gap has **not** been verified as novel; the Phase 0 prior-art gate (G1) is still open.

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
```

## Layout (Phase 3)

```text
configs/replay.yaml            frozen replay settings (k policy, flake limit, timeout)
schemas/                       canonical telemetry event JSON Schema
testbeds/billing_api/          billing/auth API: service, catalog, attacks, benign workload, rules, baseline
testbeds/file_portal/          file portal: same layout
iide/                          oracle side: schema, normalizer, detector, replay, reliability, hashing
iide/scoring/                  metrics (spec 7, 13); iide/analysis/reports.py report generator
scripts/                       run_baseline.py, validate_testbed.py
tests/                         unit, integration, fixtures
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
