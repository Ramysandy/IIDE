# G2 human rater (independent)

This pack exists because the current G2 PASS used the project coding assistant as A2 (D-44). That kappa is **not** independent human agreement. A thesis that claims label reliability needs a **person** who has not seen A1 labels.

## What to send the rater

1. [`RUBRIC.md`](RUBRIC.md) — read first.
2. [`items.yaml`](items.yaml) — 28 blinded stems. Do **not** send `annotator_a.yaml` or `annotator_b.yaml`.
3. [`annotator_human.yaml`](annotator_human.yaml) — empty template.

## What the rater does

For every item `C01`–`C28`, fill:

- `construct`: one of `EROSION`, `LATENT_EROSION`, `GENERIC_REGRESSION`, `BENIGN_NOISE_REDUCTION`, `FORMAT_DRIFT`, `NO_OP`, `NONE`, `UNKNOWN`
- `disclosure`: `YES` / `NO` only if construct is `EROSION`; otherwise `NA`
- `note`: optional one line

Do not look up A1. Do not discuss items until both files are saved.

## What you do after they return the file

```bash
.venv/bin/python scripts/score_g2.py \
  --a docs/g2/annotator_a.yaml \
  --b docs/g2/annotator_human.yaml
```

Target: construct κ ≥ 0.6. Keep disagreements. Do not edit labels just to raise kappa. This script never writes `gates.yaml`.

If κ meets the bar, write a dated operator note (new D-id) that G2 now has a **human** B, and keep the old assistant-B file as history.

## What this step is not

Not S_sec. Not criticality. Not CAI. Not a 144-run relabel.
