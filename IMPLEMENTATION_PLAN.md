# IIDE Implementation Plan

Authoritative source: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Supporting documents (proposal,
proposal review, novelty check) are in [`docs/`](docs/). Engineering choices are recorded in
[`DECISIONS.md`](DECISIONS.md).

**Status legend:** `[x]` done and verified, `[ ]` not started. Nothing past Phase 2 is implemented.

## Repository state at start of Phase 1

The project folder contained only `IIDE_EXECUTION_SPEC.md` and three PDFs (moved to `docs/`). No code,
no tests, not a git repository.

## Milestones

| Phase | Scope (spec section 18) | Gate / exit | Status |
|---|---|---|---|
| 0 | Prior-art sweep, novelty matrix, go/no-go memo | **G1** | `[ ]` Not done. **Novelty is not established.** |
| 1 | Minimal vertical slice: one endpoint, telemetry, one safe attack, one frozen rule, fresh-instance replay, baseline JSON | Rule fires consistently; flake rate under pilot threshold | `[x]` see below |
| 2 | Two pilot testbeds (billing/auth, file portal), 10-20 events each, 6-12 attacks each, rule packs, baseline artifacts | **G2** (kappa >= 0.6) | `[x]` implemented; **G2 open** (needs human annotators) |
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

### Phase 2 task checklist

- [x] Second testbed `file_portal` (10 events, 6 attacks, 8 frozen rules) and a larger `billing_api` (12 events, 6 attacks, 8 rules)
- [x] Rule-condition (`where`) support in the JSON-rule prototype (D-18)
- [x] Benign workload per testbed as negative control (D-20); cross-fire specificity check (D-21)
- [x] Catalog `security_basis` rule for `S_sec` (D-10); provisional criticality (D-19)
- [x] Baseline artifacts per testbed, with 30-replay per-attack calibration (D-05) and `benign_set_hash`
- [x] Tests: functional (billing 32, portal 25), oracle tests on both testbeds, telemetry-removal mutations (erosion and latent erosion)
- [ ] **G2**: second annotator for criticality, `security_bearing` labels and ATT&CK mappings; kappa >= 0.6 on 25-30 examples. **Not done.**
- [ ] Prior-art review (G1) still open

### Phase 2 file map

| Requirement | Files |
|---|---|
| Testbed 1 | `testbeds/billing_api/` (service, 12-event catalog, 6 attacks, `benign/`, rule pack v2.0.0 with 8 rules, mapping) |
| Testbed 2 | `testbeds/file_portal/` (same layout, rules `IIDE-PORTAL-001..008`) |
| Rule conditions | `iide/detection/json_rules.py`, `tests/unit/test_rule_conditions.py` |
| Oracle checks | `tests/integration/test_testbeds_oracle.py`, `tests/integration/test_telemetry_removal.py` |
| Baselines | `testbeds/<tb>/baseline/*` via `make baseline-all` |

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
| Replay flake rate | Measured per attack and per testbed (k=5 baseline plus >= 30 calibration replays, D-05); re-measure after any change to frozen artifacts |
| Process isolation is weaker than containers (no network block) | Documented in DECISIONS D-03; toy service opens no socket; revisit for Phase 4 |
| Agents may change telemetry transport (e.g. library migration F5) | Harness contract is `create_app(sink=...)` plus `Telemetry.emit`; decide in Phase 2 how logging-library migrations are observed (open question) |
| Flake-rate definition is not given by the spec | Interpretation chosen and tested (D-05); confirm before G3 |
| Security-bearing labels and criticality are provisional | Second reviewer sign-off (G2) before any agent run (D-10, D-19) |
| ATT&CK mapping is unverified (some attacks `UNMAPPED`) | Marked in each attack definition; validate before publication |
| Novelty gap unverified | Phase 0 / gate G1 still open; no novelty claim is made anywhere |
