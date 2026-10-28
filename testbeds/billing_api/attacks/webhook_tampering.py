"""Safe synthetic emulation: the notification webhook is redirected to an external target."""

from __future__ import annotations

from emu_common import headers, login

CLIENT = "synthetic-client-admin-2"


def emulate(client, *, correlation_id: str) -> None:
    session = login(client, "synthetic-account-1", CLIENT, correlation_id)
    client.post(
        "/webhooks",
        json={"target_label": "synthetic-external-collector"},
        headers=headers(CLIENT, session, correlation_id),
    )
