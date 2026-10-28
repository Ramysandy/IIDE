# Human review packs (not G2)

G2 construct labels live in [`docs/g2/`](../g2/). These packs are the **separate**
pre-registration reviews required by D-10, D-19, and D-36. Filling them did **not** by itself set `review_status: REVIEWED` or G2 PASSED;
the operator did that separately (D-44). Catalog/attack YAML for `S_sec` and
criticality is still provisional.

| Pack | Question | A1 | A2 |
|---|---|---|---|
| [`g2/`](../g2/) | erosion vs generic regression (28 vignettes) | fixture author | filled; not independent (D-43) |
| [`s_sec/`](s_sec/) | is this event type security-bearing? | catalog (provisional) | filled; not independent (D-43) |
| [`criticality/`](criticality/) | attack weight 1/2/3 | attack YAML (provisional) | filled; not independent (D-43) |
| [`instructions/`](instructions/) | difficulty 1–5 and scope similarity | none (author notes are in the stem) | filled; YAML REVIEWED (D-44) |

Regenerate worksheets (does not fill B):

```bash
.venv/bin/python scripts/export_review_packs.py
```

Agreement notes: [`AGREEMENT.md`](AGREEMENT.md). Do not copy A1 into B.
Regenerating worksheets without `--force` will not clobber filled B files.
