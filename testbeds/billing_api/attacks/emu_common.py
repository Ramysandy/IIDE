"""Helpers shared by billing_api attack emulations (synthetic identifiers only)."""

from __future__ import annotations


def passphrase_for(account_id: str) -> str:
    return f"synthetic-fixture-passphrase-{account_id.rsplit('-', 1)[1]}"


def login(client, account_id: str, client_id: str, correlation_id: str) -> str:
    """Log in with the account's fixture passphrase and return the session id."""
    response = client.post(
        "/login",
        json={
            "client_id": client_id,
            "account_id": account_id,
            "passphrase": passphrase_for(account_id),
        },
        headers={"X-Correlation-ID": correlation_id},
    )
    if response.status_code != 200:
        raise RuntimeError(f"fixture login failed with HTTP {response.status_code}")
    return response.json()["session_id"]


def headers(client_id: str, session_id: str, correlation_id: str) -> dict[str, str]:
    return {
        "X-Client-Id": client_id,
        "X-Session-Id": session_id,
        "X-Correlation-ID": correlation_id,
    }
