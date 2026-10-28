# IIDE pre-pilot status (not a 144-run result)

Harness check against committed baselines and gate files. No LLM was called. G2 kappa is rubric-consistency (D-43), not independence.

- Ready for 144-run: **False**
- Gates: {'G1': 'PASSED', 'G2': 'OPEN', 'G3': 'NOT_EVALUATED', 'G4': 'NOT_EVALUATED'}
- G2 pack: **MEETS_THRESHOLD**
- Unreviewed instructions: 24
- Unconfigured agents: 2

## Blockers

- required gates still open: ['G2'] (pass --allow-open-gates with a reason to override)
- unconfigured agents: ['pilot_agent_a', 'pilot_agent_b']
- 24 instruction(s) still DRAFT_UNREVIEWED (spec 10: review difficulty before execution)

## Testbeds

| Testbed | hashes | flake max | A0 | tests |
|---|---|---:|---:|---|
| billing_api | True | 0.000 | 6/6 | True |
| file_portal | True | 0.000 | 6/6 | True |

## Spec 20 (definition of done)

| Item | met | note |
|---|---|---|
| g1_documented | True | D-40 |
| two_testbeds | True | billing_api and file_portal |
| functional_suites_at_baseline | True | from committed baseline_coverage.json |
| attacks_baseline_validated | True | A0 equals the attack set; hashes match |
| flake_under_limit | True | per-attack, D-05 |
| baseline_artifacts_committed | True | spec 6.1 |
| instruction_triples | True | 8 matched groups × 3 variants; 24 still DRAFT_UNREVIEWED |
| workspace_isolation | True | allowlist; process-level only (D-03) |
| manifest_and_records | True | 144-row manifest; run_record schema |
| eligible_scoring | True | Phase 3 library; no 144-run scores |
| metric_undefined_handling | True | section 9 tests |
| section9_fixture | True | tests/unit/test_scoring_*.py |
| annotation_reliability | False | G2 MEETS_THRESHOLD; gate OPEN |
| comparison_baselines_run | True | G4 construct check, not a 144-run |
| pilot_report_144 | False | 144-run not executed; this file is a pre-pilot status report |
| novelty_claims_bounded | True | G1 memo claim restrictions |
