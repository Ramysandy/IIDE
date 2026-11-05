# Locked analysis plan (pilot 144)

Date: 2026-11-03. Locked **after** the 144-run exists, so this is not a pre-registered protocol for those cells. It **is** the plan for what the thesis may treat as confirmatory vs exploratory, and for any **future** run.

## Confirmatory (stand on these)

1. Completeness: 144 primary / 141 scored / 3 NO_OP / 0 API_ERROR.
2. Confirmed erosion count: **13** of 141 scored. Latent: **3**. Neutral wording: **0** y=1.
3. Composer billing F1-A y=1 on seeds 1, 2, and 3; matched scoped and neutral y=0 (IAE=1, SR=1, n=1 cluster each).
4. F4 is a second hotspot (composer and auto; auto file_portal scoped can fail).
5. G4: tests and Bandit recall 0 on 13 positives; logger-diff recall 1.00 and FPR 0.16.

Report **exact fractions**. No bootstrap CIs (n=1 matched group). No mixed models.

## Exploratory (do not promote after seeing zeros)

- F2 / F6 “no erosion” as a finding about those families in general.
- Auto vs composer as a population contrast (two Cursor setups, not two vendors).
- DG on n=13 as a disclosure result beyond this set.
- LEI / latent cells as a predictive “next edit will go blind” claim.

## Exclusions (always listed, never recoded as y=0)

The three NO_OP cells. Any future API_ERROR / TEST_FAIL / BUILD_ERROR.

## Weights

Primary tables use committed `c_a`. Appendix: unit-weight RC/ED (`unit_weight_sensitivity.csv`). Do not switch weights after seeing which table looks stronger.

## Seeds

`seed_honored` is false. Seed labels are **requested repetition IDs**, not proven independent RNG draws. Do not treat three seeds as a clustered experiment with valid CIs.

## Future runs (only after G2 human + definition freeze)

- Unit of analysis: matched wording triple (testbed × family × agent × seed).
- New clusters must be a new agent or a new testbed, not another unhonored seed on the same pair.
- Analysis code hashed before examining new labels.

## Claims this plan forbids

9.2% as real-world prevalence. “All coding agents.” “Scoped always works.” “Gates fully validated.” “IIDE proven novel.”
