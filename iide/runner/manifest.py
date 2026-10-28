"""Pilot manifest: one row per run, generated before execution (spec 11.4, 12)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from iide.config import REPO_ROOT, TESTBEDS_DIR, load_replay_config
from iide.hashing import hash_patterns
from iide.ids import stable_id
from iide.replay.runner import compute_frozen_hashes, load_testbed
from iide.runner.config import AgentsConfig, ExperimentConfig
from iide.runner.instructions import (
    InstructionRecord,
    instruction_problems_for_testbed,
    load_instructions,
)

FUNCTIONAL_TEST_COMMAND = "python -m pytest tests -q -p no:cacheprovider"


def run_id_for(
    testbed_id: str,
    instruction_id: str,
    agent_id: str,
    seed: int,
    experiment_version: str,
    variant: str,
) -> str:
    """Spec 12: sha256(testbed_id|instruction_id|variant|agent_id|seed|experiment_version)[:16]."""
    return stable_id(testbed_id, instruction_id, variant, agent_id, str(seed), experiment_version)


class ManifestRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str
    testbed_id: str
    testbed_commit: str | None
    repo_dirty: bool | None
    instruction_id: str
    family: str
    variant: str
    matched_group_id: str
    prompt_sha256: str
    agent_id: str
    agent_version: str
    seed: int
    replay_k: int = Field(ge=1)
    detector_hash: str
    attack_set_hash: str
    benign_set_hash: str
    instruction_set_hash: str
    functional_test_command: str
    timeout_seconds: int = Field(ge=1)
    experiment_version: str
    created_at: str


def git_state(repo: Path = REPO_ROOT) -> tuple[str | None, bool | None]:
    """(HEAD commit, dirty?) or (None, None) when git is unavailable."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return head, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def generate_manifest(
    experiment: ExperimentConfig,
    agents: AgentsConfig,
    *,
    created_at: str | None = None,
    testbeds_dir: Path = TESTBEDS_DIR,
) -> list[ManifestRow]:
    replay = load_replay_config()
    if replay.experiment_version != experiment.experiment_version:
        raise ValueError(
            f"experiment_version mismatch: experiment.yaml={experiment.experiment_version!r} "
            f"replay.yaml={replay.experiment_version!r}"
        )
    created = created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    commit, dirty = git_state()
    rows: list[ManifestRow] = []
    for testbed_id in experiment.testbeds:
        tb = load_testbed(testbeds_dir / testbed_id)
        hashes = compute_frozen_hashes(tb)
        detector_hash = hashlib.sha256(
            f"{hashes['rule_pack_hash']}\n{hashes['detector_engine_hash']}".encode()
        ).hexdigest()
        problems = instruction_problems_for_testbed(tb)
        if problems:
            raise ValueError(f"{testbed_id} instruction set: " + "; ".join(problems))
        instructions = load_instructions(tb.root)
        instruction_set_hash = hash_patterns(tb.root, ["instructions/**/*.yaml"])
        ks = {a.replay_count for a in tb.attacks.values()}
        if len(ks) != 1:
            raise ValueError(f"{testbed_id}: attacks use different replay counts {sorted(ks)}")
        for family, variant, agent, seed in product(
            experiment.families, experiment.variants, agents.agents, experiment.seeds
        ):
            rec = _find(instructions, family, variant, testbed_id)
            rows.append(
                ManifestRow(
                    run_id=run_id_for(
                        testbed_id,
                        rec.instruction_id,
                        agent.agent_id,
                        seed,
                        experiment.experiment_version,
                        variant,
                    ),
                    testbed_id=testbed_id,
                    testbed_commit=commit,
                    repo_dirty=dirty,
                    instruction_id=rec.instruction_id,
                    family=family,
                    variant=variant,
                    matched_group_id=rec.matched_group_id,
                    prompt_sha256=hashlib.sha256(rec.prompt_text.encode()).hexdigest(),
                    agent_id=agent.agent_id,
                    agent_version=agent.agent_version,
                    seed=seed,
                    replay_k=next(iter(ks)),
                    detector_hash=detector_hash,
                    attack_set_hash=hashes["attack_set_hash"],
                    benign_set_hash=hashes["benign_set_hash"],
                    instruction_set_hash=instruction_set_hash,
                    functional_test_command=FUNCTIONAL_TEST_COMMAND,
                    timeout_seconds=experiment.agent_timeout_seconds,
                    experiment_version=experiment.experiment_version,
                    created_at=created,
                )
            )
    return sorted(rows, key=lambda r: (r.testbed_id, r.family, r.variant, r.agent_id, r.seed))


def _find(
    instructions: dict[str, InstructionRecord], family: str, variant: str, testbed_id: str
) -> InstructionRecord:
    matches = [i for i in instructions.values() if i.family == family and i.variant == variant]
    if len(matches) != 1:
        raise ValueError(
            f"{testbed_id}: expected one {family}/{variant} instruction, found {len(matches)}"
        )
    return matches[0]


def validate_manifest(
    rows: list[ManifestRow], experiment: ExperimentConfig, agents: AgentsConfig
) -> list[str]:
    """Each testbed/family/variant/agent/seed combination exists exactly once (spec 11.4)."""
    problems: list[str] = []
    expected = (
        len(experiment.testbeds)
        * len(experiment.families)
        * len(experiment.variants)
        * len(agents.agents)
        * len(experiment.seeds)
    )
    if len(rows) != expected:
        problems.append(f"expected {expected} rows, found {len(rows)}")
    keys = Counter((r.testbed_id, r.family, r.variant, r.agent_id, r.seed) for r in rows)
    problems += [f"duplicate cell {k}" for k, n in keys.items() if n > 1]
    for k in product(
        experiment.testbeds,
        experiment.families,
        experiment.variants,
        [a.agent_id for a in agents.agents],
        experiment.seeds,
    ):
        if keys[k] == 0:
            problems.append(f"missing cell {k}")
    ids = Counter(r.run_id for r in rows)
    problems += [f"duplicate run_id {i}" for i, n in ids.items() if n > 1]
    for r in rows:
        expected_id = run_id_for(
            r.testbed_id, r.instruction_id, r.agent_id, r.seed, r.experiment_version, r.variant
        )
        if r.run_id != expected_id:
            problems.append(f"{r.run_id}: run_id does not match its fields")
        if r.experiment_version != experiment.experiment_version:
            problems.append(f"{r.run_id}: experiment_version differs from experiment.yaml")
    return problems


def write_manifest(rows: list[ManifestRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r.model_dump(), sort_keys=True) + "\n" for r in rows), encoding="utf-8"
    )


def read_manifest(path: Path) -> list[ManifestRow]:
    return [
        ManifestRow.model_validate_json(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
