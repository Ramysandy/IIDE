# IIDE Implementation Plan

Authoritative source: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Supporting documents (proposal,
proposal review, novelty check) are in [`docs/`](docs/). Engineering choices are recorded in
[`DECISIONS.md`](DECISIONS.md).

**Status legend:** `[x]` done and verified, `[ ]` not started. Nothing past Phase 1 is implemented.

## Repository state at start of Phase 1

The project folder contained only `IIDE_EXECUTION_SPEC.md` and three PDFs (moved to `docs/`). No code,
no tests, not a git repository.

## Milestones

| Phase | Scope (spec section 18) | Gate / exit | Status |
|---|---|---|---|
| 0 | Prior-art sweep, novelty matrix, go/no-go memo | **G1** | `[ ]` Not done. **Novelty is not established.** |
| 1 | Minimal vertical slice: one endpoint, telemetry, one safe attack, one frozen rule, fresh-instance replay, baseline JSON | Rule fires consistently; flake rate under pilot threshold | `[x]` see below |
| 2 | Two pilot testbeds (billing/auth, file portal), 10-20 events each, 6-12 attacks each, rule packs, baseline artifacts | **G2** (kappa >= 0.6) | `[ ]` |
| 3 | Scoring library (RC, ED, LEI, IAE, IIF, SR, DG, CAI, ISP, NRG, Pareto), section 9 fixtures | Unit tests match hand calculations | `[ ]` |
| 4 | Agent harness, manifest, 144-run pilot | **G3** (flake < 5%) | `[ ]` |
| 5 | Baselines and decision | **G4** | `[ ]` |
| 6-7 | Scale or pivot; analysis and paper | | `[ ]` |

### Phase 1 task checklist

- [x] Toy service with login success/failure and lockout (`testbeds/billing_api/app/`)
- [x] Canonical telemetry event schema (`schemas/telemetry_event.schema.json`) and event catalog
- [x] One safe synthetic attack emulation (`credential_bruteforce`) and attack definition (spec 4.3)
- [x] One frozen deterministic rule (`IIDE-BILLING-001`) and attack -> rule -> event-type mapping
- [x] Replay runner: fresh Python process per replay, oracle-owned sink, timeout and error handling
- [x] Detection decision d(a,P) and replay flake measures (`iide/replay/reliability.py`)
- [x] Frozen-artifact hashes; baseline result JSON; replay ledger; flake calibration
- [x] Tests: service, schema, normalizer, catalog, detection, replay repeatability, negative controls,
      telemetry-removal fixture, error handling, baseline script
- [x] `README.md`, `REPRODUCIBILITY.md`, `DECISIONS.md`

### Phase 1 file map

| Requirement | Files |
|---|---|
| Toy service | `testbeds/billing_api/app/{service,main,telemetry}.py`, `testbeds/billing_api/tests/` |
| Telemetry schema | `schemas/telemetry_event.schema.json`, `iide/telemetry/{schema,normalize,inventory}.py`, `testbeds/billing_api/event_catalog.yaml` |
| Attack | `testbeds/billing_api/attacks/credential_bruteforce.{yaml,py}` |
| Frozen rule + mapping | `testbeds/billing_api/detection/{rules/billing_rule_pack.json,mapping.json}`, `iide/detection/{interface,json_rules}.py` |
| Replay | `iide/replay/{sandbox,runner,reliability}.py` |
| Baseline | `scripts/run_baseline.py`, `testbeds/billing_api/baseline/` |
| Records, ids, hashes, config | `iide/{models,ids,hashing,config}.py`, `configs/replay.yaml` |
| Tests | `tests/unit/`, `tests/integration/`, `tests/fixtures/` |

## Dependencies between phases

- Phase 2 reuses the Phase 1 testbed template, catalog/rule/mapping loaders, and replay runner. Editing
  `iide/replay/*` or `iide/detection/*` changes the Phase 1 frozen hashes, so Phase 2 must record new
  baselines under a new `experiment_version` (see DECISIONS D-11).
- Phase 3 builds on `ReplayRecord.redundancy_event_types` (for `r(a,P)`) and on `attack_detected`.
- Phase 4 needs a real workspace-isolation mechanism (spec 11.2). Phase 1 only provides process-level
  isolation of replays.

## Risks

| Risk | Mitigation / status |
|---|---|
| Replay flake rate | Measured in Phase 1 (k=5 baseline plus a 30-replay calibration); re-measure per testbed in Phase 2 |
| Process isolation is weaker than containers (no network block) | Documented in DECISIONS D-03; toy service opens no socket; revisit for Phase 4 |
| Agents may change telemetry transport (e.g. library migration F5) | Harness contract is `create_app(sink=...)` plus `Telemetry.emit`; decide in Phase 2 how logging-library migrations are observed (open question) |
| Flake-rate definition is not given by the spec | Interpretation chosen and tested (D-05); confirm before G3 |
| Security-bearing labels are provisional | Pre-register `S_sec` in Phase 2 before any agent run (D-10) |
| ATT&CK mapping is unverified | Marked `UNVERIFIED` in the attack definition; validate in Phase 2 |
| Novelty gap unverified | Phase 0 / gate G1 still open; no novelty claim is made anywhere |
