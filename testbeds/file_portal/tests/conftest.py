"""Functional-test fixtures (product behaviour only; telemetry is discarded)."""

from __future__ import annotations

import pytest
from app.main import create_app
from fastapi.testclient import TestClient

OWNER = "synthetic-user-owner"
READER = "synthetic-user-reader"
OUTSIDER = "synthetic-user-outsider"
ADMIN = "synthetic-user-admin"


class DiscardSink:
    def emit(self, event: dict) -> None:
        pass


class Api:
    def __init__(self) -> None:
        self.client = TestClient(create_app(sink=DiscardSink()))

    def h(self, actor: str) -> dict:
        return {"X-Actor-Id": actor}

    def read(self, actor: str, n: int):
        return self.client.get(f"/files/synthetic-file-{n}", headers=self.h(actor))

    def post(self, actor: str, path: str, **body):
        return self.client.post(path, json=body, headers=self.h(actor))


@pytest.fixture
def api() -> Api:
    return Api()
