"""Functional tests for authentication (product behaviour only)."""

from __future__ import annotations

import pytest
from app.service import BillingService
from app.telemetry import Telemetry
from conftest import Api, DiscardSink

WRONG = "synthetic-wrong-guess"


def test_valid_login_succeeds_and_issues_a_session(login):
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["session_id"].startswith("synthetic-session-")


def test_sessions_are_distinct_per_login(api):
    first = api.login(9).json()["session_id"]
    second = api.login(9).json()["session_id"]
    assert first != second


def test_wrong_passphrase_is_rejected(login):
    assert login(passphrase=WRONG).status_code == 401


def test_unknown_account_is_indistinguishable_from_wrong_passphrase(login):
    known = login(passphrase=WRONG)
    unknown = login(account_id="synthetic-account-does-not-exist", passphrase=WRONG)
    assert unknown.status_code == known.status_code == 401
    assert unknown.json() == known.json()


def test_account_locks_after_threshold_failures(login):
    assert [login(passphrase=WRONG).status_code for _ in range(5)] == [401] * 5
    assert login(passphrase=WRONG).status_code == 423


def test_locked_account_rejects_correct_passphrase(login):
    for _ in range(5):
        login(passphrase=WRONG)
    assert login().status_code == 423


def test_success_before_threshold_resets_failure_counter(login):
    for _ in range(2):
        for _ in range(4):
            assert login(passphrase=WRONG).status_code == 401
        assert login().status_code == 200


def test_lockout_is_per_account(login):
    for _ in range(5):
        login(passphrase=WRONG)
    other = login(account_id="synthetic-account-10", passphrase="synthetic-fixture-passphrase-10")
    assert other.status_code == 200


def test_lockout_threshold_is_configurable():
    api = Api(max_failed_attempts=2)
    assert [api.login(9, passphrase=WRONG).status_code for _ in range(3)] == [401, 401, 423]


def test_invalid_service_parameters_are_rejected():
    for kwargs in ({"max_failed_attempts": 0}, {"export_limit_per_client": 0}):
        with pytest.raises(ValueError):
            BillingService(Telemetry(DiscardSink()), **kwargs)


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
