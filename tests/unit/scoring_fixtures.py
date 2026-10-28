from __future__ import annotations

from iide.scoring.types import AttackOutcome

# Spec section 9: illustrative proposal example. A SYNTHETIC UNIT-TEST FIXTURE, not a result.
# (attack, c_a, r(P0), d(P1), r(P1))
SECTION9_ROWS = [
    ("credential_bruteforce", 3, 2, True, 1),
    ("role_escalation", 3, 1, False, 0),
    ("token_replay", 2, 1, True, 1),
    ("bulk_export", 3, 2, True, 2),
    ("webhook_tampering", 2, 1, True, 1),
    ("rate_limit_evasion", 1, 1, True, 1),
]


def section9_outcomes() -> list[AttackOutcome]:
    return [
        AttackOutcome(
            attack_id=name,
            criticality=c,
            d0=True,
            d1=d1,
            r0=r0,
            r1=r1,
            rules0=r0,
            rules1=r1,
        )
        for name, c, r0, d1, r1 in SECTION9_ROWS
    ]


def outcome(attack_id, c, d0, d1, r0=1, r1=1, rules0=None, rules1=None) -> AttackOutcome:
    return AttackOutcome(
        attack_id=attack_id,
        criticality=c,
        d0=d0,
        d1=d1,
        r0=r0 if d0 else 0,
        r1=r1 if d1 else 0,
        rules0=rules0,
        rules1=rules1,
    )
