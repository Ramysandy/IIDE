"""Safe synthetic emulation: sustained calls to a throttled endpoint (3 allowed, 3 limited)."""

from __future__ import annotations

from emu_common import headers, login

CLIENT = "synthetic-client-scraper-1"
CALLS = 6


def emulate(client, *, correlation_id: str) -> None:
    session = login(client, "synthetic-account-2", CLIENT, correlation_id)
    h = headers(CLIENT, session, correlation_id)
    for _ in range(CALLS):
        client.post("/invoices/export", json={"invoice_ids": ["synthetic-invoice-1"]}, headers=h)
