"""Functional tests for the login endpoint (product behaviour only)."""

from __future__ import annotations

import pytest
from app.main import create_app
from app.service import AuthService
from fastapi.testclient import TestClient

WRONG = "synthetic-wrong-guess"


def test_valid_login_succeeds(login):
    response = login()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_wrong_passphrase_is_rejected(login):
    response = login(passphrase=WRONG)
    assert response.status_code == 401


def test_unknown_account_is_indistinguishable_from_wrong_passphrase(login):
    known = login(passphrase=WRONG)
    unknown = login(account_id="synthetic-account-does-not-exist", passphrase=WRONG)
    assert unknown.status_code == known.status_code == 401
    assert unknown.json() == known.json()


def test_account_locks_after_threshold_failures(login):
    statuses = [login(passphrase=WRONG).status_code for _ in range(5)]
    assert statuses == [401] * 5
    assert login(passphrase=WRONG).status_code == 423


def test_locked_account_rejects_correct_passphrase(login):
    for _ in range(5):
        login(passphrase=WRONG)
    assert login().status_code == 423


def test_success_before_threshold_resets_failure_counter(login):
    for _ in range(4):
        assert login(passphrase=WRONG).status_code == 401
    assert login().status_code == 200
    for _ in range(4):
        assert login(passphrase=WRONG).status_code == 401
    assert login().status_code == 200


def test_lockout_is_per_account(login):
    for _ in range(5):
        login(passphrase=WRONG)
    other = login(account_id="synthetic-account-10", passphrase="synthetic-fixture-passphrase-10")
    assert other.status_code == 200


def test_lockout_threshold_is_configurable():
    class Discard:
        def emit(self, event):
            pass

    client = TestClient(create_app(sink=Discard(), max_failed_attempts=2))
    body = {
        "client_id": "synthetic-client-1",
        "account_id": "synthetic-account-9",
        "passphrase": WRONG,
    }
    assert client.post("/login", json=body).status_code == 401
    assert client.post("/login", json=body).status_code == 401
    assert client.post("/login", json=body).status_code == 423


def test_invalid_threshold_is_rejected():
    class Discard:
        def emit(self, event):
            pass

    from app.telemetry import Telemetry

    with pytest.raises(ValueError):
        AuthService(Telemetry(Discard()), max_failed_attempts=0)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"client_id": "c", "account_id": "a"},
        {"client_id": "", "account_id": "a", "passphrase": "p"},
        {"client_id": "c", "account_id": "a", "passphrase": "p", "extra": 1},
    ],
)
def test_malformed_requests_get_422(client, payload):
    assert client.post("/login", json=payload).status_code == 422
