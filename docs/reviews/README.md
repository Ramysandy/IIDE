# Human review packs (not G2)

G2 construct labels live in [`docs/g2/`](../g2/). These packs are the **separate**
pre-registration reviews required by D-10, D-19, and D-36. Filling them does **not**
set `review_status: REVIEWED` on instruction YAML and does **not** set G2 PASSED.

| Pack | Question | A1 | A2 |
|---|---|---|---|
| [`g2/`](../g2/) | erosion vs generic regression (28 vignettes) | fixture author | filled; not independent (D-43) |
| [`s_sec/`](s_sec/) | is this event type security-bearing? | catalog (provisional) | filled; not independent (D-43) |
| [`criticality/`](criticality/) | attack weight 1/2/3 | attack YAML (provisional) | filled; not independent (D-43) |
| [`instructions/`](instructions/) | difficulty 1–5 and scope similarity | none (author notes are in the stem) | filled; YAML still DRAFT_UNREVIEWED |

Regenerate worksheets (does not fill B):

```bash
.venv/bin/python scripts/export_review_packs.py
```

Do not copy A1 into B. Do not mark instructions REVIEWED until a human has labelled
the instruction pack and copied the decision into each instruction YAML.
