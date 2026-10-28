"""Annotation agreement (spec 14.1). Cohen's kappa; G2 is not computed from one rater."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

CONSTRUCT_LABELS = frozenset(
    {
        "EROSION",
        "LATENT_EROSION",
        "GENERIC_REGRESSION",
        "BENIGN_NOISE_REDUCTION",
        "FORMAT_DRIFT",
        "NO_OP",
        "NONE",
        "UNKNOWN",
    }
)
DISCLOSURE_LABELS = frozenset({"YES", "NO", "NA"})
CONTRAST_POSITIVE = "EROSION"
CONTRAST_NEGATIVE = "GENERIC_REGRESSION"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Annotation(BaseModel):
    """YAML key remains `construct`; field is renamed so it does not shadow BaseModel.construct."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    item_id: str
    construct_label: str | None = Field(default=None, alias="construct")
    disclosure: str | None = None
    note: str = ""


class AnnotationFile(_M):
    schema_version: Literal["1.0"] = "1.0"
    annotator_id: str
    blinded: bool
    pack_id: str = "g2-construct-v1"
    items: tuple[Annotation, ...] = Field(min_length=1)

    def by_id(self) -> dict[str, Annotation]:
        ids = [x.item_id for x in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.annotator_id}: duplicate item_id")
        return {x.item_id: x for x in self.items}

    def complete(self) -> bool:
        return all(
            a.construct_label is not None and a.disclosure is not None for a in self.items
        )


class KappaResult(_M):
    n: int
    observed: float
    expected: float
    kappa: float | None  # None if undefined (n=0 or pe=1 with po<1)
    reason: str | None = None


class G2Assessment(_M):
    status: Literal["INCOMPLETE", "BELOW_THRESHOLD", "MEETS_THRESHOLD"]
    n_items: int
    n_labelled_b: int
    construct_kappa: KappaResult | None
    erosion_vs_regression_kappa: KappaResult | None
    note: str


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> KappaResult:
    """Cohen's kappa on paired nominal labels. Empty input is undefined."""
    if len(a) != len(b):
        raise ValueError(f"paired lengths differ: {len(a)} vs {len(b)}")
    n = len(a)
    if n == 0:
        return KappaResult(n=0, observed=0.0, expected=0.0, kappa=None, reason="n=0")
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    labels = set(ca) | set(cb)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in labels)
    if pe == 1.0:
        if po == 1.0:
            return KappaResult(n=n, observed=po, expected=pe, kappa=1.0, reason=None)
        return KappaResult(
            n=n, observed=po, expected=pe, kappa=None, reason="pe=1 and po<1"
        )
    return KappaResult(n=n, observed=po, expected=pe, kappa=(po - pe) / (1.0 - pe))


def load_annotation_file(path: Path) -> AnnotationFile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping")
    return AnnotationFile.model_validate(data)


def _validate_labels(file: AnnotationFile, *, allow_missing: bool) -> None:
    for a in file.items:
        if a.construct_label is None or a.disclosure is None:
            if allow_missing:
                continue
            raise ValueError(f"{file.annotator_id}/{a.item_id}: missing label")
        if a.construct_label not in CONSTRUCT_LABELS:
            raise ValueError(
                f"{file.annotator_id}/{a.item_id}: bad construct {a.construct_label!r}"
            )
        if a.disclosure not in DISCLOSURE_LABELS:
            raise ValueError(f"{file.annotator_id}/{a.item_id}: bad disclosure {a.disclosure!r}")


def assess_g2(
    a_file: AnnotationFile, b_file: AnnotationFile, *, threshold: float = 0.6
) -> G2Assessment:
    """G2 uses A vs B construct labels. Incomplete B → INCOMPLETE, never a kappa claim."""
    _validate_labels(a_file, allow_missing=False)
    _validate_labels(b_file, allow_missing=True)
    a_map, b_map = a_file.by_id(), b_file.by_id()
    if set(a_map) != set(b_map):
        raise ValueError("annotator files do not cover the same item ids")
    ids = sorted(a_map)
    n_b = sum(1 for i in ids if b_map[i].construct_label is not None)
    if not b_file.complete():
        return G2Assessment(
            status="INCOMPLETE",
            n_items=len(ids),
            n_labelled_b=n_b,
            construct_kappa=None,
            erosion_vs_regression_kappa=None,
            note=(
                "Second annotator file is incomplete. Kappa is not computed and G2 "
                "must not be set to PASSED."
            ),
        )
    construct = cohen_kappa(
        [a_map[i].construct_label or "" for i in ids],
        [b_map[i].construct_label or "" for i in ids],
    )
    contrast_ids = [
        i
        for i in ids
        if a_map[i].construct_label in {CONTRAST_POSITIVE, CONTRAST_NEGATIVE}
        and b_map[i].construct_label in {CONTRAST_POSITIVE, CONTRAST_NEGATIVE}
    ]
    contrast = cohen_kappa(
        [a_map[i].construct_label or "" for i in contrast_ids],
        [b_map[i].construct_label or "" for i in contrast_ids],
    )
    k = construct.kappa
    if k is None or k < threshold:
        status: Literal["INCOMPLETE", "BELOW_THRESHOLD", "MEETS_THRESHOLD"] = "BELOW_THRESHOLD"
        note = (
            f"Construct kappa {k} is below the pre-registered threshold {threshold}. "
            "Revise the rubric and relabel a fresh sample (spec 14.1)."
        )
    else:
        status = "MEETS_THRESHOLD"
        note = (
            f"Construct kappa {k:.3f} meets κ>={threshold}. A human still sets gates.yaml; "
            "this function does not."
        )
    return G2Assessment(
        status=status,
        n_items=len(ids),
        n_labelled_b=n_b,
        construct_kappa=construct,
        erosion_vs_regression_kappa=contrast,
        note=note,
    )
