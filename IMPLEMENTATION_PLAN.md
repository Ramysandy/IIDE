# IIDE Implementation Plan

Authoritative source: [`IIDE_EXECUTION_SPEC.md`](IIDE_EXECUTION_SPEC.md). Supporting documents (proposal,
proposal review, novelty check) are in [`docs/`](docs/) as gitignored PDFs. The G1 memo is
[`docs/g1_prior_art.md`](docs/g1_prior_art.md). Engineering choices are in [`DECISIONS.md`](DECISIONS.md).

**Status legend:** `[x]` done and verified, `[ ]` not started. Nothing past Phase 5 is implemented.

## Repository state at start of Phase 1

The project folder contained only `IIDE_EXECUTION_SPEC.md` and three PDFs (moved to `docs/`). No code,
no tests, not a git repository.

## Milestones

| Phase | Scope (spec section 18) | Gate / exit | Status |
|---|---|---|---|
| 0 | Prior-art sweep, novelty matrix, go/no-go memo | **G1** | `[x]` memo in `docs/g1_prior_art.md`; **G1 PASSED** (operator sign-off 2026-10-28). Novelty is **not** claimed as established. |
| 1 | Minimal vertical slice: one endpoint, telemetry, one safe attack, one frozen rule, fresh-instance replay, baseline JSON | Rule fires consistently; flake rate under pilot threshold | `[x]` see below |
| 2 | Two pilot testbeds (billing/auth, file portal), 10-20 events each, 6-12 attacks each, rule packs, baseline artifacts | **G2** (kappa >= 0.6) | `[x]` implemented; **G2 OPEN** (28-item pack in `docs/g2/`; second annotator not done) |
| 3 | Scoring library (RC, ED, LEI, IAE, IIF, SR, DG, CAI, ISP, NRG, Pareto), section 9 fixtures | Unit tests match hand calculations | `[x]` implemented and tested; bootstrap CIs deferred to Phase 7 |
| 4 | Agent harness, manifest, 144-run pilot | **G3** (flake < 5%) | `[x]` harness + 144-row manifest + dry-run; **144-run not executed** (G2 open, agents unconfigured) |
| 5 | Baselines and decision | **G4** | `[x]` construct check on scripted patches; **G4 NOT_EVALUATED** for the 144-run (no 144-run exists) |
| 6-7 | Scale or pivot; analysis and paper | | `[ ]` |

### Phase 0 task checklist

- [x] Inspect repository, environment, and current files
- [x] `IMPLEMENTATION_PLAN.md` with milestones and risks
- [x] Prior-art sweep of named neighbors (Overeager, trace tampering, SecDrift, WeSCE, IaC regression, IFG) plus spec search phrases
- [x] Novelty matrix and go/no-go memo (`docs/g1_prior_art.md`, `docs/g1_matrix.yaml`)
- [x] **G1 PASSED** by operator sign-off 2026-10-28 on the recorded memo (D-40). Novelty is not claimed as established.

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
- [ ] **G2**: 28-item construct pack in `docs/g2/` (D-41). Fill `annotator_b.yaml` independently, then `make g2-agreement`. Target κ ≥ 0.6. `S_sec` / criticality / instruction worksheets are in `docs/reviews/` (D-42) and are still unlabelled by A2.

### Phase 2 file map

| Requirement | Files |
|---|---|
| Testbed 1 | `testbeds/billing_api/` (service, 12-event catalog, 6 attacks, `benign/`, rule pack v2.0.0 with 8 rules, mapping) |
| Testbed 2 | `testbeds/file_portal/` (same layout, rules `IIDE-PORTAL-001..008`) |
| Rule conditions | `iide/detection/json_rules.py`, `tests/unit/test_rule_conditions.py` |
| Oracle checks | `tests/integration/test_testbeds_oracle.py`, `tests/integration/test_telemetry_removal.py` |
| Baselines | `testbeds/<tb>/baseline/*` via `make baseline-all` |

### Phase 3 task checklist

- [x] RC, ED, LEI (+ unit-weight and rule-count sensitivity variants), detection debt (`iide/scoring/coverage.py`)
- [x] IAE, IIF, SR over matched cells (`iide/scoring/causal.py`); DG (`disclosure.py`)
- [x] Binary entropy, CAI, ISP posterior (`ambiguity.py`); NRG and Pareto frontier (`frontier.py`)
- [x] Section 9 worked example as automated tests; explicit LEI exclusion test; boundary, validation and seeded property tests
- [x] Replay-record adapter and report generator (`adapters.py`, `iide/analysis/reports.py`, `scripts/score_replays.py`)
- [x] Scoring verified on real ledgers: baseline self-comparison and the Phase 2 telemetry-removal mutants
- [ ] Not in scope: bootstrap intervals, mixed models, agent run-record scoring (Phases 4-7)
- [ ] Open decisions: D-26 (UNKNOWN aggregation) and D-27 (redundancy across replays) need confirmation

### Phase 4 task checklist

- [x] Instruction dataset F1, F2, F4, F6 x 3 variants x 2 testbeds (F3 and F5 deferred, D-32); all DRAFT_UNREVIEWED
- [x] Neutral maintenance target `app/formatting.py` added to both testbeds; baselines re-recorded as `phase4-0.1`
- [x] Workspace allowlist (app/, tests/, pytest.ini) and isolation checks; oracle artifacts never copied
- [x] CodingAgent protocol, local_patch development adapter, generic command adapter (not vendor-validated)
- [x] Two agent slots in `configs/agents.yaml` (currently `unconfigured` placeholders)
- [x] 144-run manifest (2 x 4 x 3 x 2 x 3) with stable run IDs; `make run-pilot DRY_RUN=1`
- [x] Orchestration: build, frozen tests, replay, miss confirmation, scoring, run ledger, resumability
- [x] Real 144-run start is refused while G1/G2 are open, agents are unconfigured, or instructions are unreviewed (G1 now PASSED; G2 still OPEN)
- [ ] **G3**: 144-run with real agents. **Not started.** Configure two adapters and close G1/G2 first.
- [ ] Docker/network isolation still process-level (D-03/D-31)

### Phase 4 file map

| Requirement | Files |
|---|---|
| Instructions | `testbeds/<tb>/instructions/F{1,2,4,6}/{ambiguous,scoped,neutral}.yaml` |
| Harness | `iide/runner/{agent_interface,workspace,local_patch_runner,command_agent,manifest,orchestration,pilot,records,instructions,config}.py` |
| Config | `configs/{experiment,agents,gates}.yaml` |
| CLI | `scripts/run_pilot.py`, `scripts/score_runs.py`; `make manifest-pilot`, `make run-pilot DRY_RUN=1` |
| Schemas | `schemas/{instruction,run_record}.schema.json` |

### Phase 5 task checklist

- [x] Functional-tests baseline (predicts `NONE` on eligible runs; misses telemetry-only loss by construction)
- [x] Logging-statement AST diff (`_emit*` / `.emit` / `logging.*` call counts)
- [x] Static signal-inventory (catalog event-type string literals vs frozen catalog)
- [x] Dynamic signal-inventory (one replay; integration test on `filter_lockout`)
- [x] SAST: Bandit run if CLI on PATH (still predicts `NONE` for this construct); CodeQL not found, not claimed
- [x] LLM diff reviewer: frozen prompt, `command: null` → `UNAVAILABLE` (never invented)
- [x] IFG-style monitor: `UNAVAILABLE` (not fair/reproducible in this budget)
- [x] Confusion vs replay-oracle `y` on four scripted patches; report at `experiments/reports/g4_calibration.{md,json}`
- [x] `filter_lockout` verified as confirmed oracle erosion with tests still passing
- [x] `make report` / `scripts/verify_reproducibility.py` pre-pilot status (D-42); not a 144-run result
- [x] Blinded review packs in `docs/reviews/` for `S_sec`, criticality, and instructions (A2 pending)
- [ ] **G4 on the 144-run:** blocked (G2 open, agents unconfigured, 144-run not executed). `gates.yaml` G4 is `NOT_EVALUATED`.

### Phase 5 file map

| Requirement | Files |
|---|---|
| Methods | `iide/analysis/comparison.py` |
| Calibration fixtures | `iide/analysis/fixtures.py`, `tests/fixtures/local_patches/{erode_lockout,filter_lockout,erode_invoice_read,simplify_formatter}.yaml` |
| LLM prompt (unconfigured) | `configs/llm_reviewer.yaml` |
| CLI | `scripts/compare_baselines.py`; `make compare-baselines` |
| Report | `experiments/reports/g4_calibration.{md,json}` |
| Pre-pilot status | `iide/analysis/status.py`, `scripts/verify_reproducibility.py`; `make report` |
| Human review packs | `docs/reviews/{s_sec,criticality,instructions}/`, `scripts/export_review_packs.py` |
| Tests | `tests/unit/test_comparison_baselines.py`, `tests/integration/test_g4_calibration.py`, `tests/unit/test_pre_pilot_status.py`, `tests/unit/test_review_packs.py` |

## Dependencies between phases

- Phase 2 reuses the Phase 1 testbed template, catalog/rule/mapping loaders, and replay runner. Editing
  `iide/replay/*` or `iide/detection/*` changes the Phase 1 frozen hashes, so Phase 2 must record new
  baselines under a new `experiment_version` (see DECISIONS D-11).
- Phase 3 builds on `ReplayRecord.redundancy_event_types` (for `r(a,P)`) and on `attack_detected`.
- Phase 4 needs a real workspace-isolation mechanism (spec 11.2). The harness copies an allowlisted
  workspace without oracle artifacts; the agent still runs as the same OS user and the network is not
  blocked (D-03/D-31). Upgrade before any untrusted-agent run.
- Phase 5 compares simpler baselines to the replay oracle on **scripted** patches. It does not
  substitute for G4 on a real 144-run (D-38, D-39).

## Risks

| Risk | Mitigation / status |
|---|---|
| Replay flake rate | Measured per attack and per testbed (k=5 baseline plus >= 30 calibration replays, D-05); re-measure after any change to frozen artifacts |
| Process isolation is weaker than containers (no network block) | Documented in D-03/D-31; workspace has no oracle artifacts; Docker daemon is not running; upgrade before untrusted-agent runs |
| Agents may change telemetry transport (e.g. library migration F5) | Harness contract is `create_app(sink=...)` plus `Telemetry.emit`; F5 is out of the Phase 4 family set (D-32) until D-03a is resolved |
| Flake-rate definition is not given by the spec | Interpretation chosen and tested (D-05); confirm before G3 |
| Security-bearing labels and criticality are provisional | Worksheets in `docs/reviews/` (D-42); A2 still pending (D-10, D-19). G2 construct labels are a separate pack. |
| ATT&CK mapping is unverified (some attacks `UNMAPPED`) | Marked in each attack definition; validate before publication |
| Novelty gap unverified | Sweep recorded (D-40); recommended GO; G1 PASSED 2026-10-28; no novelty claim is made |
| G4 construct check ≠ G4 on the experiment | Calibration report is `PROVISIONAL`; `gates.yaml` G4 stays `NOT_EVALUATED` until a real 144-run exists (D-39) |
