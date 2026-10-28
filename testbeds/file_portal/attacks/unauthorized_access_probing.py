"""Safe synthetic emulation: an outsider probes six files it cannot read."""

from __future__ import annotations

from emu_common import OUTSIDER, get


def emulate(client, *, correlation_id: str) -> None:
    for i in range(1, 7):
        get(client, OUTSIDER, f"/files/synthetic-file-{i}", correlation_id)
