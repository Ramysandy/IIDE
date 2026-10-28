"""Turn replay ledgers into scoring inputs (spec 6.2, 7.1, 7.3, 8.2).

Redundancy across replays (DECISIONS D-27): an expected rule "fires" for attack ``a`` under
``P`` if it fired in at least ``ceil(v/2)`` valid replays, the same majority rule as ``d``.
``r(a,P)`` is the number of distinct event types matched by those rules; ``rules`` is the
number of those rules (the spec 7.3 sensitivity variant). Duplicate events and repeated
replays never add to redundancy.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from iide.config import ReplayConfig
from iide.models import AttackDefinition, ReplayRecord
from iide.replay.runner import summarize_attack
from iide.scoring.types import AttackOutcome


class InconsistentEvidenceError(ValueError):
    """Detection says 'detected' but no single expected rule reaches the majority threshold."""


def attack_redundancy(
    attack: AttackDefinition, records: Sequence[ReplayRecord]
) -> tuple[int, int, list[str]]:
    """Return ``(r_event_types, firing_rules, sorted_event_types)`` over valid replays."""
    valid = [r for r in records if r.valid]
    if not valid:
        return 0, 0, []
    threshold = math.ceil(len(valid) / 2)
    types: set[str] = set()
    firing = 0
    for rule_id in attack.expected_rule_ids:
        fired_in = [o for r in valid for o in r.rule_outcomes if o.rule_id == rule_id and o.fired]
        if len(fired_in) >= threshold:
            firing += 1
            for o in fired_in:
                types.update(o.matched_event_types)
    return len(types), firing, sorted(types)


def build_attack_outcome(
    attack: AttackDefinition,
    baseline_records: Sequence[ReplayRecord],
    candidate_records: Sequence[ReplayRecord],
    config: ReplayConfig,
) -> AttackOutcome:
    base = summarize_attack(attack, list(baseline_records), config)
    cand = summarize_attack(attack, list(candidate_records), config)
    d0 = None if base.d is None else bool(base.d)
    d1 = None if cand.d is None else bool(cand.d)
    r0, rules0, _ = attack_redundancy(attack, baseline_records) if d0 else (0, 0, [])
    r1, rules1, _ = attack_redundancy(attack, candidate_records) if d1 else (0, 0, [])
    for label, detected, r in (("baseline", d0, r0), ("candidate", d1, r1)):
        if detected and r < 1:
            raise InconsistentEvidenceError(
                f"{attack.id}: detected in {label} replays but no expected rule fired in "
                "a majority of valid replays; evidence is inconsistent, not scoreable"
            )
    return AttackOutcome(
        attack_id=attack.id,
        criticality=attack.criticality,
        d0=d0,
        d1=d1,
        r0=r0,
        r1=r1,
        rules0=rules0,
        rules1=rules1,
    )
