"""Fixtures for the product-behaviour tests (they use a sink that discards events)."""

from __future__ import annotations

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


class DiscardSink:
    def emit(self, event: dict) -> None:
        pass


class Api:
    """Thin helper around the test client."""

    def __init__(self, **app_kwargs) -> None:
        self.client = TestClient(create_app(sink=DiscardSink(), **app_kwargs))

    def login(self, account_n: int = 9, client_id: str = "synthetic-client-1", passphrase=None):
        return self.client.post(
            "/login",
            json={
                "client_id": client_id,
                "account_id": f"synthetic-account-{account_n}",
                "passphrase": passphrase or f"synthetic-fixture-passphrase-{account_n}",
            },
        )

    def session(self, account_n: int, client_id: str = "synthetic-client-1") -> dict:
        """Log in and return headers for authenticated calls."""
        response = self.login(account_n, client_id)
        assert response.status_code == 200, response.text
        return {"X-Client-Id": client_id, "X-Session-Id": response.json()["session_id"]}


@pytest.fixture
def api() -> Api:
    return Api()


# Kept from Phase 1 for the login tests.
@pytest.fixture
def client(api) -> TestClient:
    return api.client


@pytest.fixture
def login(api):
    def _login(account_id="synthetic-account-9", passphrase="synthetic-fixture-passphrase-9"):
        return api.client.post(
            "/login",
            json={
                "client_id": "synthetic-client-1",
                "account_id": account_id,
                "passphrase": passphrase,
            },
        )

    return _login
