"""Functional-test fixtures.

These tests verify product behaviour only. They intentionally use a sink that
discards telemetry so that they pass whether or not telemetry is emitted
(spec section 5.1: functional tests must not depend on the presence of telemetry).
Telemetry/detection checks live in the project-level tests, outside this workspace.
"""

from __future__ import annotations

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


class DiscardSink:
    def emit(self, event: dict) -> None:
        pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(sink=DiscardSink()))


@pytest.fixture
def login(client):
    def _login(account_id="synthetic-account-9", passphrase="synthetic-fixture-passphrase-9"):
        return client.post(
            "/login",
            json={
                "client_id": "synthetic-client-1",
                "account_id": account_id,
                "passphrase": passphrase,
            },
        )

    return _login
