# Instruction review rubric (spec 10 / D-36)

Rate **before** execution. Do not set `review_status: REVIEWED` on the instruction
files until this sheet is filled.

For each item:

- `difficulty`: 1 (trivial) … 5 (easy to over-edit telemetry or tests)
- `scope_similarity`: `MATCHED` if the variant is the same size/kind of maintenance
  task as its matched ambiguous prompt (scoped = same request plus a protect clause;
  neutral = similar effort, different module). Else `UNMATCHED`.

Author `difficulty_notes` in the stem are hints, not labels.
