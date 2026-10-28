"""Instruction dataset (spec 10) and its validators."""

from __future__ import annotations

import json

import jsonschema
import pytest
from conftest import TESTBED_IDS, TESTBEDS_DIR
from pydantic import ValidationError

from iide.config import REPO_ROOT
from iide.replay.runner import load_testbed
from iide.runner.instructions import (
    InstructionRecord,
    instruction_problems_for_testbed,
    load_instruction,
    load_instructions,
    matched_groups,
    validate_instruction_set,
)


@pytest.mark.parametrize("tb_id", TESTBED_IDS)
def test_each_pilot_testbed_has_complete_matched_groups(tb_id):
    tb = load_testbed(TESTBEDS_DIR / tb_id)
    assert instruction_problems_for_testbed(tb) == []
    recs = load_instructions(tb.root)
    assert {r.family for r in recs.values()} == {"F1", "F2", "F4", "F6"}
    groups = matched_groups(recs)
    assert len(groups) == 4
    for group in groups.values():
        assert set(group) == {"ambiguous", "scoped", "neutral"}
        assert group["scoped"].prompt_text.startswith(group["ambiguous"].prompt_text)
        assert group["neutral"].target_module == "app/formatting.py"
        assert group["ambiguous"].target_module == "app/service.py"
        assert {r.review_status for r in group.values()} == {"REVIEWED"}


def test_instruction_records_match_the_published_schema():
    schema = json.loads((REPO_ROOT / "schemas" / "instruction.schema.json").read_text())
    rec = load_instruction(TESTBEDS_DIR / "billing_api" / "instructions" / "F1" / "ambiguous.yaml")
    jsonschema.Draft202012Validator(schema).validate(rec.model_dump(mode="json"))


def test_scoped_must_list_protected_types_and_others_must_not():
    base = dict(
        instruction_id="F1-S",
        family="F1",
        variant="scoped",
        prompt_text="x" * 25,
        target_module="app/service.py",
        protected_event_types=["auth.lockout"],
        matched_group_id="billing_api-F1",
        difficulty_notes="n",
        source_type="synthetic",
        authoring_version="1",
        review_status="DRAFT_UNREVIEWED",
    )
    InstructionRecord.model_validate(base)
    with pytest.raises(ValidationError):
        InstructionRecord.model_validate({**base, "protected_event_types": []})
    with pytest.raises(ValidationError):
        InstructionRecord.model_validate({**base, "instruction_id": "F1-A", "variant": "ambiguous"})


def test_validate_instruction_set_flags_a_leaked_rule_id():
    recs = load_instructions(TESTBEDS_DIR / "billing_api")
    dirty = recs["F1-A"].model_copy(
        update={"prompt_text": recs["F1-A"].prompt_text + " IIDE-BILLING-001"}
    )
    leaked = validate_instruction_set(
        {**recs, "F1-A": dirty},
        catalog_event_types=set(load_testbed(TESTBEDS_DIR / "billing_api").catalog),
        security_event_types=set(),
        workspace_files={"app/service.py", "app/formatting.py"},
        rule_ids={"IIDE-BILLING-001"},
        testbed_id="billing_api",
    )
    assert any("leaks detection rule ids" in p for p in leaked)
