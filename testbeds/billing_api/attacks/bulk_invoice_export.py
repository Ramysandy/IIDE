"""Safe synthetic emulation: many invoice reads followed by one large export."""

from __future__ import annotations

from emu_common import headers, login

CLIENT = "synthetic-client-analyst-1"


def emulate(client, *, correlation_id: str) -> None:
    session = login(client, "synthetic-account-2", CLIENT, correlation_id)
    h = headers(CLIENT, session, correlation_id)
    for i in range(1, 9):
        client.get(f"/invoices/synthetic-invoice-{i}", headers=h)
    client.post(
        "/invoices/export",
        json={"invoice_ids": [f"synthetic-invoice-{i}" for i in range(1, 13)]},
        headers=h,
    )
