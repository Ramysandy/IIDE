"""Fixed benign workload (negative control; later the NRG volume workload, spec 7.10).

Ordinary activity that stays below every frozen threshold. It must not fire any rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The emulation directory is on sys.path for attacks; benign/ borrows the same helpers.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attacks"))
from emu_common import headers, login  # noqa: E402


def emulate(client, *, correlation_id: str) -> None:
    # Analyst: a few reads and one small export.
    analyst = "synthetic-client-benign-analyst"
    h = headers(
        analyst, login(client, "synthetic-account-2", analyst, correlation_id), correlation_id
    )
    for i in (1, 2, 3):
        client.get(f"/invoices/synthetic-invoice-{i}", headers=h)
    client.post(
        "/invoices/export",
        json={"invoice_ids": ["synthetic-invoice-1", "synthetic-invoice-2"]},
        headers=h,
    )

    # Viewer: two typos, then a successful login, two reads, one forbidden export.
    viewer = "synthetic-client-benign-viewer"
    for _ in range(2):
        client.post(
            "/login",
            json={
                "client_id": viewer,
                "account_id": "synthetic-account-3",
                "passphrase": "synthetic-typo",
            },
            headers={"X-Correlation-ID": correlation_id},
        )
    vh = headers(
        viewer, login(client, "synthetic-account-3", viewer, correlation_id), correlation_id
    )
    for i in (4, 5):
        client.get(f"/invoices/synthetic-invoice-{i}", headers=vh)
    client.post("/invoices/export", json={"invoice_ids": ["synthetic-invoice-4"]}, headers=vh)

    # Admin: non-admin role changes, an internal webhook that cannot be reached.
    admin = "synthetic-client-benign-admin"
    ah = headers(admin, login(client, "synthetic-account-1", admin, correlation_id), correlation_id)
    client.post(
        "/roles",
        json={"target_account_id": "synthetic-account-3", "new_role": "analyst"},
        headers=ah,
    )
    client.post("/webhooks", json={"target_label": "synthetic-internal-unreachable"}, headers=ah)
    client.post(
        "/roles",
        json={"target_account_id": "synthetic-account-9", "new_role": "analyst"},
        headers=ah,
    )

    # Two malformed requests (validation errors).
    for _ in range(2):
        client.post("/login", json={}, headers={"X-Correlation-ID": correlation_id})
