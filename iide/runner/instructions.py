"""Instruction dataset (spec 10): records, loader and cross-validation.

Instruction wording is the manipulated variable. A matched group is one
(testbed, family) triple: ambiguous / scoped / neutral. These records live on the oracle
side (`testbeds/<tb>/instructions/<family>/<variant>.yaml`) and are never copied into an
agent workspace; only `prompt_text` is given to an agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Variant = Literal["ambiguous", "scoped", "neutral"]
VARIANTS: tuple[Variant, ...] = ("ambiguous", "scoped", "neutral")
VARIANT_SUFFIX = {"ambiguous": "A", "scoped": "S", "neutral": "N"}


class InstructionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    instruction_id: str = Field(pattern=r"^F[1-6]-[ASN]$")
    family: str = Field(pattern=r"^F[1-6]$")
    variant: Variant
    prompt_text: str = Field(min_length=20)
    target_module: str  # path inside the agent workspace, e.g. app/service.py
    protected_event_types: list[str]  # non-empty only for scoped variants
    matched_group_id: str
    difficulty_notes: str
    source_type: Literal["synthetic", "adapted_public_issue"]
    authoring_version: str
    # Spec 10: pilot reviewers rate difficulty and scope similarity BEFORE execution.
    review_status: Literal["DRAFT_UNREVIEWED", "REVIEWED"]

    @model_validator(mode="after")
    def _consistent(self) -> InstructionRecord:
        if not self.instruction_id.startswith(f"{self.family}-"):
            raise ValueError("instruction_id must start with the family")
        if not self.instruction_id.endswith(VARIANT_SUFFIX[self.variant]):
            raise ValueError("instruction_id suffix does not match variant")
        if self.variant == "scoped" and not self.protected_event_types:
            raise ValueError("a scoped instruction must list protected_event_types")
        if self.variant != "scoped" and self.protected_event_types:
            raise ValueError("only scoped instructions list protected_event_types")
        return self


def load_instruction(path: Path) -> InstructionRecord:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return InstructionRecord.model_validate(data)


def load_instructions(testbed_root: Path) -> dict[str, InstructionRecord]:
    """All instructions of one testbed keyed by instruction_id."""
    out: dict[str, InstructionRecord] = {}
    for path in sorted((testbed_root / "instructions").glob("F*/*.yaml")):
        rec = load_instruction(path)
        if path.parent.name != rec.family or path.stem != rec.variant:
            raise ValueError(f"{path}: file location does not match family/variant")
        if rec.instruction_id in out:
            raise ValueError(f"{path}: duplicate instruction_id {rec.instruction_id}")
        out[rec.instruction_id] = rec
    return out


def matched_groups(
    instructions: dict[str, InstructionRecord],
) -> dict[str, dict[Variant, InstructionRecord]]:
    groups: dict[str, dict[Variant, InstructionRecord]] = {}
    for rec in instructions.values():
        groups.setdefault(rec.matched_group_id, {})[rec.variant] = rec
    return groups


def instruction_problems_for_testbed(tb: Any) -> list[str]:
    """Cross-check one testbed's instruction dataset against its catalog and workspace."""
    from iide.runner.workspace import allowlisted_files
    from iide.telemetry.inventory import security_bearing_event_types

    return validate_instruction_set(
        load_instructions(tb.root),
        catalog_event_types=set(tb.catalog),
        security_event_types=set(security_bearing_event_types(tb.catalog)),
        workspace_files={p.relative_to(tb.root).as_posix() for p in allowlisted_files(tb.root)},
        rule_ids=set(tb.detector.rule_ids),
        testbed_id=tb.testbed_id,
    )


def validate_instruction_set(
    instructions: dict[str, InstructionRecord],
    *,
    catalog_event_types: set[str],
    security_event_types: set[str],
    workspace_files: set[str],
    rule_ids: set[str],
    testbed_id: str | None = None,
) -> list[str]:
    """Return a list of problems (empty if the set is well formed)."""
    problems: list[str] = []
    for gid, group in matched_groups(instructions).items():
        if set(group) != set(VARIANTS):
            problems.append(f"{gid}: needs exactly ambiguous, scoped and neutral variants")
            continue
        amb, sc, neu = group["ambiguous"], group["scoped"], group["neutral"]
        if not sc.prompt_text.startswith(amb.prompt_text):
            problems.append(f"{gid}: scoped prompt must be the ambiguous prompt plus a clause")
        if len({amb.family, sc.family, neu.family}) != 1:
            problems.append(f"{gid}: variants belong to different families")
        if sc.target_module != amb.target_module:
            problems.append(f"{gid}: scoped and ambiguous must target the same module")
        if neu.target_module == amb.target_module:
            problems.append(f"{gid}: neutral must target a different (non-telemetry) module")
        ratio = len(neu.prompt_text.split()) / len(amb.prompt_text.split())
        if not 0.6 <= ratio <= 2.0:
            problems.append(f"{gid}: neutral prompt size ratio {ratio:.2f} outside [0.6, 2.0]")
        if testbed_id is not None:
            expected_gid = f"{testbed_id}-{amb.family}"
            if gid != expected_gid:
                problems.append(f"{gid}: expected matched_group_id {expected_gid}")
    for rec in instructions.values():
        if rec.target_module not in workspace_files:
            problems.append(f"{rec.instruction_id}: target_module {rec.target_module} not found")
        unknown = set(rec.protected_event_types) - catalog_event_types
        if unknown:
            problems.append(f"{rec.instruction_id}: protected types not in catalog: {unknown}")
        if rec.variant == "scoped" and not set(rec.protected_event_types) <= security_event_types:
            problems.append(f"{rec.instruction_id}: protected types must be security-bearing")
        leaked = [r for r in rule_ids if r in rec.prompt_text]
        if leaked:
            problems.append(f"{rec.instruction_id}: prompt leaks detection rule ids {leaked}")
        for banned in ("detection", "attack", "oracle", "replay", "baseline"):
            if banned in rec.prompt_text.lower():
                problems.append(f"{rec.instruction_id}: prompt mentions {banned!r}")
    return problems
