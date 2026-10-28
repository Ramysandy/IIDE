"""Helpers shared by file_portal attack emulations (synthetic identifiers only)."""

from __future__ import annotations

OWNER = "synthetic-user-owner"
READER = "synthetic-user-reader"
OUTSIDER = "synthetic-user-outsider"
ADMIN = "synthetic-user-admin"


def headers(actor_id: str, correlation_id: str) -> dict[str, str]:
    return {"X-Actor-Id": actor_id, "X-Correlation-ID": correlation_id}


def get(client, actor_id: str, path: str, correlation_id: str):
    return client.get(path, headers=headers(actor_id, correlation_id))


def post(client, actor_id: str, path: str, correlation_id: str, body: dict):
    return client.post(path, json=body, headers=headers(actor_id, correlation_id))
