# G2 labeling pack

1. Read [`RUBRIC.md`](RUBRIC.md).
2. Label [`items.yaml`](items.yaml) into [`annotator_b.yaml`](annotator_b.yaml). Do not open `annotator_a.yaml`.
3. Run `make g2-agreement`. Kappa is computed only when every B label is filled.
4. A human sets `configs/gates.yaml` G2 to PASSED only if construct κ ≥ 0.6 and the erosion-vs-regression contrast is clear. The script never writes that file.

`annotator_a.yaml` is the provisional first rater (fixture/catalog author). It is not a second independent annotator.
