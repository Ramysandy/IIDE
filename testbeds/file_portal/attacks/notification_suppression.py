"""Safe synthetic emulation: notifications are silenced by pointing the webhook nowhere."""

from __future__ import annotations

from emu_common import ADMIN, OWNER, post


def emulate(client, *, correlation_id: str) -> None:
    post(client, ADMIN, "/webhook", correlation_id, {"label": "synthetic-endpoint-unreachable"})
    for i in (13, 14, 15):
        post(
            client,
            OWNER,
            f"/files/synthetic-file-{i}/sharing",
            correlation_id,
            {"visibility": "private"},
        )
