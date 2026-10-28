"""Safe synthetic emulation of repeated failed authentication (T1110 label).

Deterministic: fixed identifiers, fixed number of attempts, fixed wrong guesses.
Operates only on the in-process toy service through the supplied test client.
The guesses are placeholder strings, not real credentials.
"""

from __future__ import annotations

ATTACKER_CLIENT_ID = "synthetic-client-attacker-1"
TARGET_ACCOUNT_ID = "synthetic-account-9"
ATTEMPTS = 6  # threshold (5) + one attempt against the now-locked account


def emulate(client, *, correlation_id: str) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        client.post(
            "/login",
            json={
                "client_id": ATTACKER_CLIENT_ID,
                "account_id": TARGET_ACCOUNT_ID,
                "passphrase": f"synthetic-wrong-guess-{attempt}",
            },
            headers={"X-Correlation-ID": correlation_id},
        )
