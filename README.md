# IIDE: Instruction-Induced Detection Erosion

A reproducible research harness for measuring whether ordinary maintenance instructions cause a coding
agent to remove or degrade security telemetry that a frozen detection pipeline relies on, even when
functional tests still pass.

> **Status: Phase 1 only (minimal vertical slice).** One toy endpoint, one safe synthetic attack, one frozen
> rule, fresh-instance replay and a baseline result. There is no agent runner, no scoring library, no second
> testbed and no experimental result yet. The research gap has **not** been verified as novel; the Phase 0
> prior-art gate (G1) is still open.

Authoritative specification: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Plan:
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md). Decisions: [`DECISIONS.md`](DECISIONS.md). Source
documents: [`docs/`](docs/).

## Safety

Everything is synthetic. The toy service is driven in-process and opens no socket; attack emulations only
send synthetic requests to it and contact no external system.

## Quick start

```bash
make install          # creates .venv and installs the package with dev tools
make test             # project tests + the testbed's functional tests
make baseline         # records testbeds/billing_api/baseline/* (refuses to overwrite)
```

## Layout (Phase 1)

```text
configs/replay.yaml            frozen replay settings (k policy, flake limit, timeout)
schemas/                       canonical telemetry event JSON Schema
testbeds/billing_api/          toy service + catalog + attack + frozen rule + baseline artifacts
iide/                          oracle side: schema, normalizer, detector, replay, reliability, hashing
scripts/                       run_baseline.py, validate_testbed.py
tests/                         unit, integration, fixtures
```

See `REPRODUCIBILITY.md` for exact commands and environment details.
