"""Safe synthetic emulation: an admin approves their own access request."""

from __future__ import annotations

from emu_common import ADMIN, post


def emulate(client, *, correlation_id: str) -> None:
    created = post(client, ADMIN, "/approvals", correlation_id, {"file_id": "synthetic-file-13"})
    approval_id = created.json()["approval_id"]
    post(
        client, ADMIN, f"/approvals/{approval_id}/decision", correlation_id, {"decision": "approve"}
    )
