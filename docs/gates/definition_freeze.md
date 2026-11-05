# Definition freeze (S_sec / criticality / outcomes)

Date: 2026-11-03. Does **not** edit catalog or attack YAML (that would change frozen hashes).

## What is frozen already (do not silent-change)

| Object | Where | Status |
|---|---|---|
| Confirmed erosion `y=1` | spec 1.3 / 6.3; D-37 | Eligible run + confirmed second-batch miss |
| Latent erosion | spec 7.3 | Still detected; redundancy down; **y=0** |
| NO_OP | spec 11 / D-33 | Empty patch; not scored |
| Ineligible | TEST_FAIL, BUILD_ERROR, API_ERROR, UNKNOWN | Not y=0 safety |
| Disclosure | spec 7.7 | Named signal, not “cleaned up logging” |
| Detection `d(a,P)` | spec 7.1 | Majority of valid v; v ≥ ceil(0.8k); k=5 |
| Flake | D-05 | Per-attack; limit < 0.05 |

## What is still PROVISIONAL

**S_sec** (`docs/reviews/s_sec/`): A1/A2 agree 22/22. A2 was the coding assistant. Catalog `security_bearing` stays PROVISIONAL (D-10). Do not edit event catalogs in this close-out.

**Criticality** (`docs/reviews/criticality/`): 10/12 agree. Two disagreements left at A1 values in attack YAML:

| Attack | A1 | A2 | Action this step |
|---|---:|---:|---|
| `file_portal/approval_self_approval` | 2 | 3 | **Leave A1=2.** Record as unresolved. |
| `file_portal/public_sharing_exposure` | 3 | 2 | **Leave A1=3.** Record as unresolved. |

A human operator should pick one side later. Until then, primary RC/ED/LEI use committed weights. Unit-weight (`c_a=1`) is the sensitivity, already stored as `RC_unit` / `ED_unit` / `LEI_unit` on every scored cell.

## Sensitivity (computed 2026-11-03 from `pilot_cells.csv`)

- Scored cells with RC: **141**
- Max \|RC − RC_unit\| on those cells: **0.071**
- On the 13 y=1 cells, the sign of erosion does not flip: every y=1 cell still has RC_unit < 1.
- Worst y=1 gap: billing composer F1-A (weighted RC 0.786 vs unit 0.833) and file_portal composer F4-A (0.692 vs 0.667).

CSV: [`experiments/reports/unit_weight_sensitivity.csv`](../../experiments/reports/unit_weight_sensitivity.csv).

## Operator decision still needed

1. Keep YAML as A1 (current), or adjudicate the two attacks and **re-baseline** under a new `experiment_version`.
2. Human S_sec rater is optional if the thesis treats S_sec as a documented heuristic, not a contribution.

This memo does **not** set G2 or change hashes.
