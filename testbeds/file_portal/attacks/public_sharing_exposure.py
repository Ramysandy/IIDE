"""Safe synthetic emulation: a private file is made public."""

from __future__ import annotations

from emu_common import OWNER, post


def emulate(client, *, correlation_id: str) -> None:
    post(
        client, OWNER, "/files/synthetic-file-13/sharing", correlation_id, {"visibility": "public"}
    )
