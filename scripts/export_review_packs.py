#!/usr/bin/env python3
"""Write blinded second-annotator worksheets for S_sec, criticality, and instructions.

Does not copy A1 labels into B. Does not set review_status=REVIEWED.
Refuses to overwrite a completed annotator_b.yaml unless --force is passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from iide.config import TESTBEDS_DIR  # noqa: E402
from iide.replay.runner import load_testbed  # noqa: E402
from iide.runner.config import load_experiment_config  # noqa: E402
from iide.runner.instructions import load_instructions  # noqa: E402

REVIEWS = REPO_ROOT / "docs" / "reviews"


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=10000,
        ),
        encoding="utf-8",
    )


def _b_is_complete(path: Path, value_keys: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    items = data.get("items") or []
    if not items:
        return False
    return all(all(row.get(k) is not None for k in value_keys) for row in items)


def export_s_sec(*, force: bool) -> None:
    items: list[dict] = []
    a_items: list[dict] = []
    b_items: list[dict] = []
    for tb_id in ("billing_api", "file_portal"):
        tb = load_testbed(TESTBEDS_DIR / tb_id)
        for event_type, entry in sorted(tb.catalog.items()):
            item_id = f"{tb_id}/{event_type}"
            items.append(
                {
                    "id": item_id,
                    "testbed_id": tb_id,
                    "event_type": event_type,
                    "description": entry.description,
                    "owning_module": entry.owning_module,
                    "required_by_rules": list(entry.required_by_rules),
                    "required_by_attacks": list(entry.required_by_attacks),
                }
            )
            a_items.append(
                {
                    "item_id": item_id,
                    "label": "SECURITY" if entry.security_bearing else "NOT_SECURITY",
                    "note": entry.criticality_rationale,
                }
            )
            b_items.append({"item_id": item_id, "label": None, "note": ""})
    root = REVIEWS / "s_sec"
    b_path = root / "annotator_b.yaml"
    if _b_is_complete(b_path, ("label",)) and not force:
        raise SystemExit(f"{b_path} already has labels; pass --force to overwrite")
    _dump(root / "items.yaml", {"schema_version": "1.0", "pack_id": "s_sec-v1", "items": items})
    _dump(
        root / "annotator_a.yaml",
        {
            "schema_version": "1.0",
            "annotator_id": "A1",
            "blinded": False,
            "pack_id": "s_sec-v1",
            "items": a_items,
        },
    )
    _dump(
        root / "annotator_b.yaml",
        {
            "schema_version": "1.0",
            "annotator_id": "A2",
            "blinded": True,
            "pack_id": "s_sec-v1",
            "items": b_items,
        },
    )


def export_criticality(*, force: bool) -> None:
    items: list[dict] = []
    a_items: list[dict] = []
    b_items: list[dict] = []
    for tb_id in ("billing_api", "file_portal"):
        tb = load_testbed(TESTBEDS_DIR / tb_id)
        for attack_id, attack in sorted(tb.attacks.items()):
            item_id = f"{tb_id}/{attack_id}"
            items.append(
                {
                    "id": item_id,
                    "testbed_id": tb_id,
                    "attack_id": attack_id,
                    "description": attack.description,
                    "technique_id": attack.technique_id,
                    "technique_mapping_status": attack.technique_mapping_status,
                    "required_event_types": list(attack.required_event_types),
                }
            )
            a_items.append(
                {
                    "item_id": item_id,
                    "criticality": attack.criticality,
                    "note": attack.criticality_status,
                }
            )
            b_items.append({"item_id": item_id, "criticality": None, "note": ""})
    root = REVIEWS / "criticality"
    b_path = root / "annotator_b.yaml"
    if _b_is_complete(b_path, ("criticality",)) and not force:
        raise SystemExit(f"{b_path} already has labels; pass --force to overwrite")
    _dump(
        root / "items.yaml",
        {"schema_version": "1.0", "pack_id": "criticality-v1", "items": items},
    )
    _dump(
        root / "annotator_a.yaml",
        {
            "schema_version": "1.0",
            "annotator_id": "A1",
            "blinded": False,
            "pack_id": "criticality-v1",
            "items": a_items,
        },
    )
    _dump(
        root / "annotator_b.yaml",
        {
            "schema_version": "1.0",
            "annotator_id": "A2",
            "blinded": True,
            "pack_id": "criticality-v1",
            "items": b_items,
        },
    )


def export_instructions(*, force: bool) -> None:
    exp = load_experiment_config()
    items: list[dict] = []
    b_items: list[dict] = []
    for tb_id in exp.testbeds:
        recs = load_instructions(TESTBEDS_DIR / tb_id)
        for rec in recs.values():
            if rec.family not in exp.families:
                continue
            item_id = f"{tb_id}/{rec.instruction_id}"
            items.append(
                {
                    "id": item_id,
                    "testbed_id": tb_id,
                    "instruction_id": rec.instruction_id,
                    "family": rec.family,
                    "variant": rec.variant,
                    "prompt_text": rec.prompt_text,
                    "target_module": rec.target_module,
                    "matched_group_id": rec.matched_group_id,
                    "author_difficulty_notes": rec.difficulty_notes,
                }
            )
            b_items.append(
                {
                    "item_id": item_id,
                    "difficulty": None,
                    "scope_similarity": None,
                    "note": "",
                }
            )
    root = REVIEWS / "instructions"
    b_path = root / "annotator_b.yaml"
    if _b_is_complete(b_path, ("difficulty", "scope_similarity")) and not force:
        raise SystemExit(f"{b_path} already has labels; pass --force to overwrite")
    _dump(
        root / "items.yaml",
        {"schema_version": "1.0", "pack_id": "instructions-v1", "items": items},
    )
    _dump(
        root / "annotator_b.yaml",
        {
            "schema_version": "1.0",
            "annotator_id": "A2",
            "blinded": True,
            "pack_id": "instructions-v1",
            "items": b_items,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite completed annotator_b.yaml files (destroys A2 labels)",
    )
    args = parser.parse_args(argv)
    export_s_sec(force=args.force)
    export_criticality(force=args.force)
    export_instructions(force=args.force)
    print(f"wrote review packs under {REVIEWS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
