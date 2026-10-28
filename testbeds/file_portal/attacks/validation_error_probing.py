"""Safe synthetic emulation: one actor sends six malformed requests."""

from __future__ import annotations

from emu_common import post

PROBE = "synthetic-user-probe"


def emulate(client, *, correlation_id: str) -> None:
    for _ in range(6):
        post(client, PROBE, "/files", correlation_id, {})
