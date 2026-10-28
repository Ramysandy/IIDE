"""Safe synthetic emulation: an admin session grants the admin role to a viewer account."""

from __future__ import annotations

from emu_common import headers, login

CLIENT = "synthetic-client-admin-1"


def emulate(client, *, correlation_id: str) -> None:
    session = login(client, "synthetic-account-1", CLIENT, correlation_id)
    client.post(
        "/roles",
        json={"target_account_id": "synthetic-account-3", "new_role": "admin"},
        headers=headers(CLIENT, session, correlation_id),
    )
