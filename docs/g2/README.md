# G2 labeling pack

1. Read [`RUBRIC.md`](RUBRIC.md).
2. Label [`items.yaml`](items.yaml) into [`annotator_b.yaml`](annotator_b.yaml) (assistant A2; already filled) or [`annotator_human.yaml`](annotator_human.yaml) (independent person). Do not open `annotator_a.yaml`.
3. Run `make g2-agreement` (assistant B) or `.venv/bin/python scripts/score_g2.py --b docs/g2/annotator_human.yaml`. Kappa is computed only when every B label is filled.
4. The script never writes `gates.yaml`. Operator set G2 PASSED (D-44) with the
   restriction that κ=1.0 is not independent human agreement.

`annotator_a.yaml` is the provisional first rater (fixture/catalog author). `annotator_b.yaml` is filled. Operator set G2 PASSED (D-44); do not cite κ=1.0 as independent human agreement.

For a **human** second rater (thesis close-out): [`HUMAN_RATER.md`](HUMAN_RATER.md) and empty [`annotator_human.yaml`](annotator_human.yaml). `make g2-agreement` with `--b docs/g2/annotator_human.yaml` stays INCOMPLETE until that file is filled.
