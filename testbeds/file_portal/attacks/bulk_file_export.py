"""Safe synthetic emulation: many reads followed by one large export."""

from __future__ import annotations

from emu_common import READER, get, post


def emulate(client, *, correlation_id: str) -> None:
    for i in range(1, 9):
        get(client, READER, f"/files/synthetic-file-{i}", correlation_id)
    post(
        client,
        READER,
        "/files/export",
        correlation_id,
        {"file_ids": [f"synthetic-file-{i}" for i in range(1, 13)]},
    )
