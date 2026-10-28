"""Safe synthetic emulation: a victim's session id is presented from another client."""

from __future__ import annotations

from emu_common import headers, login

VICTIM_CLIENT = "synthetic-client-victim-1"
ATTACKER_CLIENT = "synthetic-client-attacker-2"
REPLAYS = 4


def emulate(client, *, correlation_id: str) -> None:
    victim_session = login(client, "synthetic-account-3", VICTIM_CLIENT, correlation_id)
    for _ in range(REPLAYS):
        client.get(
            "/invoices/synthetic-invoice-1",
            headers=headers(ATTACKER_CLIENT, victim_session, correlation_id),
        )
