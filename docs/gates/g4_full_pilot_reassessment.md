# G4 full-pilot reassessment

Date: 2026-11-03.

**Original sign-off (keep on file, D-48, 2026-10-28):** three live billing_api F1 composer-2.5 diffs. `functional_tests` and `sast_bandit` missed the oracle-positive. Analysis module still labels the construct check **PROVISIONAL**.

This memo recounts the 144-cell live G4 file. It does **not** edit `configs/gates.yaml`. Checkers were not given oracle `y`.

## Criteria (spec 18 G4)

The replay oracle should identify relevant events missed by simpler baselines, **or** the claimed advantage must be narrowed.

## Evaluation set (verified 2026-11-03)

Source: `experiments/reports/g4_all_all_allseeds.json` vs `pilot_cells.csv`.

| Set | n |
|---|---:|
| Eligible G4 cases (NO_OP / ineligible dropped) | **141** |
| Oracle y=1 (confirmed erosion) | **13** |
| Oracle y=0 | **128** (125 NONE + 3 LATENT_EROSION) |

13 + 128 = 141. Matches the CSV scored count.

## Confusion (same file)

| Method | TP | FP | FN | TN | una | Recall | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| functional_tests | 0 | 0 | 13 | 128 | 0 | 0.00 | 0.00 |
| sast_bandit | 0 | 0 | 13 | 128 | 0 | 0.00 | 0.00 |
| logger_call_diff | 13 | 21 | 0 | 107 | 0 | 1.00 | 0.16 |
| static_event_literals | 9 | 3 | 4 | 125 | 0 | 0.69 | 0.02 |
| llm_reviewer | 0 | 0 | 0 | 0 | 141 | n/a | n/a |
| ifg_monitor | 0 | 0 | 0 | 0 | 141 | n/a | n/a |

FPR for logger-diff: 21/128 = 0.164.

## What each checker is for

- **Functional tests:** feature behavior. By construction they already passed on eligible cells, so they cannot see telemetry-only loss.
- **Bandit:** generic SAST. No missing-telemetry query.
- **Logger-call AST diff:** counts `_emit*` / `.emit` / `logging.*`. Catches deleted calls; cannot see a filtered no-op inside emit; over-flags y=0 edits (21 FPs).
- **Static literals:** catalog strings in source. Leftover helpers keep a literal and produce FNs (4 on this set, all composer billing F1-A / F4-A).

## Recommended operator decision

**Restricted PASS:** on this 141-cell comparison, replay found 13 confirmed erosions that tests and Bandit missed. Logger-diff is **not** a drop-in oracle (FPR 0.16). Keep the comparison module **PROVISIONAL** until you paste this decision into `gates.yaml` if you want G4 to mean the 144-run.

Do not claim G4 on LLM reviewer or IFG (unavailable).

## Still not claimed

Production SAST quality. Logger-diff as a monitor in CI. G4 on any agent other than these two Cursor setups.
