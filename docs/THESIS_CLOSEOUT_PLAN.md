# IIDE thesis close-out plan

Date: 2026-11-03. Source: October 2026 research report §14–15, live 144-cell record.

**Rule:** do not add runs until labels, definitions, and G3/G4 memos are honest.

**Defense vs submission**

- You can **defend** a restricted thesis now: two toy apps, two Cursor setups, 141 scored cells, 13 confirmed erosions.
- You cannot **submit** a stronger claim until a second **person** labels G2, and dated G3/G4 memos cover the **full 144**.

This file is the checklist. Deliverables live next to each step. `configs/gates.yaml` is **not** rewritten here; that is an operator paste after you accept the memos.

| # | Step | Gate | Status | Deliverable |
|---|---|---|---|---|
| 1 | Independent human G2 | G2 | **Blocked on a person** (pack prepared) | [`g2/HUMAN_RATER.md`](g2/HUMAN_RATER.md), [`g2/annotator_human.yaml`](g2/annotator_human.yaml) |
| 2 | Freeze S_sec / criticality | Measurement | Memo written; YAML **not** edited | [`gates/definition_freeze.md`](gates/definition_freeze.md), [`../experiments/reports/unit_weight_sensitivity.csv`](../experiments/reports/unit_weight_sensitivity.csv) |
| 3 | Full-pilot G3 reassessment | G3 | Memo written; original n=3 kept | [`gates/g3_full_pilot_reassessment.md`](gates/g3_full_pilot_reassessment.md) |
| 4 | Full-pilot G4 decision | G4 | Memo written; module still PROVISIONAL | [`gates/g4_full_pilot_reassessment.md`](gates/g4_full_pilot_reassessment.md) |
| 5 | Locked analysis plan | Stats | Written | [`paper/analysis_plan.md`](paper/analysis_plan.md) |
| 6 | Repro packet honesty | Repro | `REPRODUCIBILITY.md` updated | [`../REPRODUCIBILITY.md`](../REPRODUCIBILITY.md) |
| 7 | Paper skeleton → 144 | G1 / thesis | Written | [`paper/pilot_144.md`](paper/pilot_144.md) |
| 8 | Scale | Phase 6 | **Deferred** | Do not start |

## What this execution will not do

- Fill G2 as a fake second human (D-44 already used the coding assistant).
- Change attack YAML criticality (that would break frozen hashes).
- Set `gates.yaml` G3/G4 to “144” without your dated sign-off.
- Report bootstrap CIs (n=1 cluster).
- Add F3/F5, Docker, or a third vendor.

## Immediate next human action

Give [`g2/HUMAN_RATER.md`](g2/HUMAN_RATER.md) and [`g2/items.yaml`](g2/items.yaml) to one person who has not seen [`g2/annotator_a.yaml`](g2/annotator_a.yaml). They fill [`g2/annotator_human.yaml`](g2/annotator_human.yaml). Then run:

```bash
.venv/bin/python scripts/score_g2.py --b docs/g2/annotator_human.yaml
```
