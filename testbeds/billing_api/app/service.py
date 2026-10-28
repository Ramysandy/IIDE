"""Authentication business logic for the billing_api toy service.

All accounts and passphrases below are synthetic fixtures, not real credentials.
Lockout is permanent for the lifetime of the instance (there is no unlock flow);
every replay uses a fresh instance, so state never leaks between replays.
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .telemetry import Telemetry

DEFAULT_MAX_FAILED_ATTEMPTS = 5

# Synthetic fixture data.
FIXTURE_ACCOUNTS: Mapping[str, str] = {
    "synthetic-account-9": "synthetic-fixture-passphrase-9",
    "synthetic-account-10": "synthetic-fixture-passphrase-10",
}
_UNKNOWN_ACCOUNT_PLACEHOLDER = "synthetic-placeholder-never-matches"


@dataclass(frozen=True)
class LoginResult:
    status: Literal["success", "invalid_credentials", "locked"]
    failure_count: int


class AuthService:
    def __init__(
        self,
        telemetry: Telemetry,
        *,
        accounts: Mapping[str, str] | None = None,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
    ) -> None:
        if max_failed_attempts < 1:
            raise ValueError("max_failed_attempts must be >= 1")
        self._telemetry = telemetry
        self._accounts = dict(FIXTURE_ACCOUNTS if accounts is None else accounts)
        self._max_failed_attempts = max_failed_attempts
        # Failure counters are tracked for every account_id (known or not) so the
        # response and telemetry do not reveal which accounts exist.
        self._failures: dict[str, int] = {}

    @property
    def max_failed_attempts(self) -> int:
        return self._max_failed_attempts

    def login(
        self,
        *,
        client_id: str,
        account_id: str,
        passphrase: str,
        correlation_id: str,
    ) -> LoginResult:
        failures = self._failures.get(account_id, 0)

        if failures >= self._max_failed_attempts:
            failures += 1
            self._failures[account_id] = failures
            self._emit_login_failed(
                client_id, account_id, correlation_id, failures, reason="account_locked"
            )
            return LoginResult("locked", failures)

        expected = self._accounts.get(account_id, _UNKNOWN_ACCOUNT_PLACEHOLDER)
        passphrase_ok = hmac.compare_digest(passphrase.encode(), expected.encode())
        if passphrase_ok and account_id in self._accounts:
            self._failures[account_id] = 0
            self._telemetry.emit(
                event_type="auth.login_success",
                severity="INFO",
                actor_id=client_id,
                target_type="account",
                target_id=account_id,
                source="auth_service",
                correlation_id=correlation_id,
                attributes={},
            )
            return LoginResult("success", 0)

        failures += 1
        self._failures[account_id] = failures
        self._emit_login_failed(
            client_id, account_id, correlation_id, failures, reason="invalid_credentials"
        )
        if failures == self._max_failed_attempts:
            self._emit_lockout(client_id, account_id, correlation_id, failures)
        return LoginResult("invalid_credentials", failures)

    def _emit_login_failed(
        self,
        client_id: str,
        account_id: str,
        correlation_id: str,
        failure_count: int,
        *,
        reason: str,
    ) -> None:
        self._telemetry.emit(
            event_type="auth.login_failed",
            severity="WARN",
            actor_id=client_id,
            target_type="account",
            target_id=account_id,
            source="auth_service",
            correlation_id=correlation_id,
            attributes={
                "failure_count": failure_count,
                "threshold": self._max_failed_attempts,
                "reason": reason,
            },
        )

    def _emit_lockout(
        self, client_id: str, account_id: str, correlation_id: str, failure_count: int
    ) -> None:
        self._telemetry.emit(
            event_type="auth.lockout",
            severity="ERROR",
            actor_id=client_id,
            target_type="account",
            target_id=account_id,
            source="auth_service",
            correlation_id=correlation_id,
            attributes={
                "failure_count": failure_count,
                "threshold": self._max_failed_attempts,
            },
        )
