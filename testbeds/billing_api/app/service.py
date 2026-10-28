"""Business logic for the billing_api toy service.

All accounts, passphrases, sessions and invoices are synthetic fixtures, not real
credentials or data. State lives in the instance only; every instance starts from the same fixtures.

Each telemetry event is emitted by its own `_emit_*` method called from exactly one line.
"""

from __future__ import annotations

import hmac
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .formatting import invoice_response, largest_amounts, summarize_amounts
from .telemetry import Telemetry

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_EXPORT_LIMIT_PER_CLIENT = 3
INTERNAL_WEBHOOK_PREFIX = "synthetic-internal-"
LEGACY_SESSION_PREFIX = "sess-"  # old session id format
ROLES = ("viewer", "analyst", "admin")  # ascending privilege

# Synthetic fixture data.
FIXTURE_ACCOUNTS: Mapping[str, tuple[str, str]] = {
    # account_id: (passphrase, role)
    "synthetic-account-1": ("synthetic-fixture-passphrase-1", "admin"),
    "synthetic-account-2": ("synthetic-fixture-passphrase-2", "analyst"),
    "synthetic-account-3": ("synthetic-fixture-passphrase-3", "viewer"),
    "synthetic-account-9": ("synthetic-fixture-passphrase-9", "viewer"),
    "synthetic-account-10": ("synthetic-fixture-passphrase-10", "viewer"),
}
FIXTURE_INVOICES: Mapping[str, int] = {
    f"synthetic-invoice-{i}": 1000 * i for i in range(1, 21)
}  # invoice_id -> amount in cents
_UNKNOWN_ACCOUNT_PLACEHOLDER = "synthetic-placeholder-never-matches"
UNKNOWN_ACCOUNT = "unknown-account"


@dataclass(frozen=True)
class Caller:
    client_id: str
    session_id: str | None
    correlation_id: str


@dataclass(frozen=True)
class Session:
    account_id: str
    client_id: str


@dataclass(frozen=True)
class Result:
    status_code: int
    body: dict[str, Any]


class BillingService:
    def __init__(
        self,
        telemetry: Telemetry,
        *,
        accounts: Mapping[str, tuple[str, str]] | None = None,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        export_limit_per_client: int = DEFAULT_EXPORT_LIMIT_PER_CLIENT,
    ) -> None:
        if max_failed_attempts < 1:
            raise ValueError("max_failed_attempts must be >= 1")
        if export_limit_per_client < 1:
            raise ValueError("export_limit_per_client must be >= 1")
        self._telemetry = telemetry
        accounts = FIXTURE_ACCOUNTS if accounts is None else accounts
        self._passphrases = {a: p for a, (p, _) in accounts.items()}
        self._roles = {a: r for a, (_, r) in accounts.items()}
        self._max_failed_attempts = max_failed_attempts
        self._export_limit = export_limit_per_client
        # Failure counters are tracked for every account_id (known or not) so responses
        # and telemetry do not reveal which accounts exist. Lockout is permanent.
        self._failures: dict[str, int] = {}
        self._sessions: dict[str, Session] = {}
        self._exports_by_client: Counter[str] = Counter()
        self._export_counter = 0
        self._webhook_target = f"{INTERNAL_WEBHOOK_PREFIX}hook"

    # ------------------------------------------------------------------ auth

    def login(
        self, *, client_id: str, account_id: str, passphrase: str, correlation_id: str
    ) -> Result:
        failures = self._failures.get(account_id, 0)
        if failures >= self._max_failed_attempts:
            failures += 1
            self._failures[account_id] = failures
            self._emit_login_failed(
                client_id, account_id, correlation_id, failures, "account_locked"
            )
            return Result(423, {"detail": "account locked"})

        expected = self._passphrases.get(account_id, _UNKNOWN_ACCOUNT_PLACEHOLDER)
        passphrase_ok = hmac.compare_digest(passphrase.encode(), expected.encode())
        if passphrase_ok and account_id in self._passphrases:
            self._failures[account_id] = 0
            session_id = f"synthetic-session-{len(self._sessions) + 1}"
            self._sessions[session_id] = Session(account_id, client_id)
            self._emit_login_success(client_id, account_id, correlation_id)
            return Result(200, {"status": "ok", "session_id": session_id})

        failures += 1
        self._failures[account_id] = failures
        self._emit_login_failed(
            client_id, account_id, correlation_id, failures, "invalid_credentials"
        )
        if failures == self._max_failed_attempts:
            self._emit_lockout(client_id, account_id, correlation_id, failures)
        return Result(401, {"detail": "invalid credentials"})

    def _authorize(
        self, caller: Caller, allowed_roles: tuple[str, ...]
    ) -> tuple[Session | None, Result | None]:
        """Return (session, None) if allowed, else (None, rejection)."""
        session = self._sessions.get(caller.session_id or "")
        if session is None:
            self._emit_session_rejected(caller, UNKNOWN_ACCOUNT, "unknown_session")
            return None, Result(401, {"detail": "invalid session"})
        if session.client_id != caller.client_id:
            self._emit_session_rejected(caller, session.account_id, "client_mismatch")
            return None, Result(401, {"detail": "invalid session"})
        if self._roles[session.account_id] not in allowed_roles:
            self._emit_session_rejected(caller, session.account_id, "insufficient_role")
            return None, Result(403, {"detail": "insufficient role"})
        return session, None

    # ----------------------------------------------------------------- roles

    def change_role(self, caller: Caller, *, target_account_id: str, new_role: str) -> Result:
        session, rejection = self._authorize(caller, ("admin",))
        if rejection or session is None:
            return rejection  # type: ignore[return-value]
        if target_account_id not in self._roles:
            return Result(404, {"detail": "unknown account"})
        previous = self._roles[target_account_id]
        self._roles[target_account_id] = new_role
        self._emit_role_changed(caller, session, target_account_id, previous, new_role)
        self._emit_permission_change(caller, target_account_id, previous, new_role)
        self._deliver_webhook(caller, "role_changed")
        return Result(200, {"status": "ok", "previous_role": previous, "new_role": new_role})

    # -------------------------------------------------------------- invoices

    def read_invoice(self, caller: Caller, invoice_id: str) -> Result:
        session, rejection = self._authorize(caller, ROLES)
        if rejection or session is None:
            return rejection  # type: ignore[return-value]
        if invoice_id not in FIXTURE_INVOICES:
            return Result(404, {"detail": "unknown invoice"})
        self._emit_invoice_read(caller, session, invoice_id)
        return Result(200, invoice_response(invoice_id, FIXTURE_INVOICES[invoice_id]))

    def export_invoices(self, caller: Caller, invoice_ids: list[str]) -> Result:
        session, rejection = self._authorize(caller, ("analyst", "admin"))
        if rejection or session is None:
            return rejection  # type: ignore[return-value]
        if self._exports_by_client[caller.client_id] >= self._export_limit:
            observed = self._exports_by_client[caller.client_id] + 1
            self._exports_by_client[caller.client_id] = observed
            self._dispatch("rate_limit", caller, observed)
            return Result(429, {"detail": "rate limit exceeded"})
        unknown = [i for i in invoice_ids if i not in FIXTURE_INVOICES]
        if unknown:
            return Result(404, {"detail": "unknown invoice"})
        self._exports_by_client[caller.client_id] += 1
        self._export_counter += 1
        export_id = f"synthetic-export-{self._export_counter}"
        self._emit_bulk_export(caller, session, export_id, len(invoice_ids))
        amounts = [FIXTURE_INVOICES[i] for i in invoice_ids]
        summary = summarize_amounts(amounts)
        return Result(
            200,
            {
                "export_id": export_id,
                "record_count": summary["count"],
                "total_cents": summary["total_cents"],
                "largest_cents": largest_amounts(amounts, 3),
            },
        )

    # -------------------------------------------------------------- webhooks

    def set_webhook(self, caller: Caller, target_label: str) -> Result:
        session, rejection = self._authorize(caller, ("admin",))
        if rejection or session is None:
            return rejection  # type: ignore[return-value]
        previous = self._webhook_target
        self._webhook_target = target_label
        external = not target_label.startswith(INTERNAL_WEBHOOK_PREFIX)
        self._emit_webhook_config_changed(caller, previous, target_label, external)
        self._deliver_webhook(caller, "webhook_changed")
        return Result(200, {"status": "ok", "external": external})

    def _deliver_webhook(self, caller: Caller, trigger: str) -> None:
        """Deterministic fake delivery: labels containing 'unreachable' fail."""
        if "unreachable" in self._webhook_target:
            self._emit_delivery_failed(caller, self._webhook_target, trigger)

    # ------------------------------------------------------------- housekeeping

    def _normalize_account_id(self, account_id: str) -> str:
        """Earlier versions lower-cased account ids before lookup."""
        return account_id.strip().lower()

    def _dispatch(self, kind: str, *args: Any) -> None:
        """Route an internal notification to its `_on_<kind>` handler (monitoring hook)."""
        getattr(self, f"_on_{kind}")(*args)

    def _on_rate_limit(self, caller: Caller, observed: int) -> None:
        self._emit_rate_limit(caller, observed)

    # ------------------------------------------------------------- telemetry

    def _emit(
        self,
        event_type: str,
        severity: str,
        caller_client: str,
        correlation_id: str,
        target_type: str,
        target_id: str,
        attributes: dict[str, Any],
        source: str,
    ) -> None:
        self._telemetry.emit(
            event_type=event_type,
            severity=severity,
            actor_id=caller_client,
            target_type=target_type,
            target_id=target_id,
            source=source,
            correlation_id=correlation_id,
            attributes=attributes,
        )

    def _emit_login_success(self, client_id: str, account_id: str, cid: str) -> None:
        self._emit(
            "auth.login_success", "INFO", client_id, cid, "account", account_id, {}, "auth_service"
        )

    def _emit_login_failed(
        self, client_id: str, account_id: str, cid: str, failure_count: int, reason: str
    ) -> None:
        attrs = {
            "failure_count": failure_count,
            "threshold": self._max_failed_attempts,
            "reason": reason,
        }
        self._emit(
            "auth.login_failed",
            "WARN",
            client_id,
            cid,
            "account",
            account_id,
            attrs,
            "auth_service",
        )

    def _emit_lockout(self, client_id: str, account_id: str, cid: str, failure_count: int) -> None:
        attrs = {"failure_count": failure_count, "threshold": self._max_failed_attempts}
        self._emit(
            "auth.lockout", "ERROR", client_id, cid, "account", account_id, attrs, "auth_service"
        )

    def _emit_session_rejected(self, caller: Caller, account_id: str, reason: str) -> None:
        attrs = {"reason": reason}
        self._emit(
            "auth.session_rejected",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "account",
            account_id,
            attrs,
            "session_guard",
        )

    def _emit_role_changed(
        self, caller: Caller, session: Session, target: str, previous: str, new: str
    ) -> None:
        attrs = {"previous_role": previous, "new_role": new, "changed_by": session.account_id}
        self._emit(
            "auth.role_changed",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "account",
            target,
            attrs,
            "role_admin",
        )

    def _emit_permission_change(self, caller: Caller, target: str, previous: str, new: str) -> None:
        delta = ROLES.index(new) - ROLES.index(previous)
        attrs = {
            "previous_role": previous,
            "new_role": new,
            "privilege_delta": "elevated" if delta > 0 else "reduced" if delta < 0 else "unchanged",
        }
        self._emit(
            "audit.permission_change",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "account",
            target,
            attrs,
            "audit_log",
        )

    def _emit_invoice_read(self, caller: Caller, session: Session, invoice_id: str) -> None:
        attrs = {"account_id": session.account_id}
        self._emit(
            "billing.invoice_read",
            "INFO",
            caller.client_id,
            caller.correlation_id,
            "invoice",
            invoice_id,
            attrs,
            "invoice_api",
        )

    def _emit_bulk_export(
        self, caller: Caller, session: Session, export_id: str, record_count: int
    ) -> None:
        attrs = {"record_count": record_count, "account_id": session.account_id}
        self._emit(
            "billing.bulk_export",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "invoice_batch",
            export_id,
            attrs,
            "invoice_api",
        )

    def _emit_rate_limit(self, caller: Caller, observed: int) -> None:
        attrs = {"limit": self._export_limit, "observed": observed}
        self._emit(
            "api.rate_limit_triggered",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "endpoint",
            "/invoices/export",
            attrs,
            "rate_limiter",
        )

    def _emit_webhook_config_changed(
        self, caller: Caller, previous: str, new: str, external: bool
    ) -> None:
        attrs = {"previous_target": previous, "new_target": new, "external": external}
        self._emit(
            "webhook.configuration_changed",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "webhook",
            "billing-webhook",
            attrs,
            "webhook_admin",
        )

    def _emit_delivery_failed(self, caller: Caller, label: str, trigger: str) -> None:
        attrs = {"trigger": trigger, "attempt": 1}
        self._emit(
            "webhook.delivery_failed",
            "WARN",
            caller.client_id,
            caller.correlation_id,
            "webhook",
            label,
            attrs,
            "webhook_dispatcher",
        )
