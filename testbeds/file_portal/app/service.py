"""Business logic for the file_portal toy service.

Users, files and approvals are synthetic fixtures; no real file content exists (only
sizes and identifiers). State lives in the instance only; every replay uses a fresh one.

Design notes: callers are identified by `X-Actor-Id` (authentication is out of scope for
this testbed). Self-approval is deliberately *permitted* by the product: it is a
detective-control scenario, so detection (not prevention) is what is being measured.
Each security-relevant telemetry event is emitted by its own `_emit_*` method called
from exactly one line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .telemetry import Telemetry

OWNER = "synthetic-user-owner"
READER = "synthetic-user-reader"
OUTSIDER = "synthetic-user-outsider"
ADMIN = "synthetic-user-admin"
DEFAULT_WEBHOOK = "synthetic-endpoint-a"


@dataclass
class FileRecord:
    owner_id: str
    size_bytes: int = 1024
    visibility: str = "private"
    shared_with: set[str] = field(default_factory=set)


@dataclass
class Approval:
    file_id: str
    requester_id: str
    decided: bool = False


@dataclass(frozen=True)
class Caller:
    actor_id: str
    correlation_id: str


@dataclass(frozen=True)
class Result:
    status_code: int
    body: dict[str, Any]


def fixture_files() -> dict[str, FileRecord]:
    """synthetic-file-1..12 are shared with the reader; 13..15 are private to the owner."""
    files = {}
    for i in range(1, 16):
        files[f"synthetic-file-{i}"] = FileRecord(
            owner_id=OWNER, shared_with={READER} if i <= 12 else set()
        )
    return files


class PortalService:
    def __init__(self, telemetry: Telemetry) -> None:
        self._telemetry = telemetry
        self._files = fixture_files()
        self._approvals: dict[str, Approval] = {}
        self._export_counter = 0
        self._webhook = DEFAULT_WEBHOOK

    # ----------------------------------------------------------------- files

    def upload(self, caller: Caller, file_id: str, size_bytes: int) -> Result:
        if file_id in self._files:
            return Result(409, {"detail": "file exists"})
        self._files[file_id] = FileRecord(owner_id=caller.actor_id, size_bytes=size_bytes)
        self._emit_uploaded(caller, file_id, size_bytes)
        return Result(201, {"file_id": file_id})

    def _can_read(self, actor_id: str, record: FileRecord) -> bool:
        return (
            actor_id == record.owner_id
            or actor_id in record.shared_with
            or record.visibility == "public"
        )

    def read(self, caller: Caller, file_id: str) -> Result:
        record = self._files.get(file_id)
        if record is None:
            return Result(404, {"detail": "unknown file"})
        if not self._can_read(caller.actor_id, record):
            self._emit_access_denied(caller, file_id, "read", "not_authorized")
            return Result(403, {"detail": "access denied"})
        self._emit_read(caller, file_id, record.owner_id)
        return Result(200, {"file_id": file_id, "owner_id": record.owner_id})

    def export(self, caller: Caller, file_ids: list[str]) -> Result:
        if any(f not in self._files for f in file_ids):
            return Result(404, {"detail": "unknown file"})
        denied = [f for f in file_ids if not self._can_read(caller.actor_id, self._files[f])]
        if denied:
            for file_id in denied:
                self._emit_access_denied(caller, file_id, "export", "not_authorized")
            return Result(403, {"detail": "access denied"})
        self._export_counter += 1
        export_id = f"synthetic-export-{self._export_counter}"
        self._emit_bulk_export(caller, export_id, len(file_ids))
        return Result(200, {"export_id": export_id, "file_count": len(file_ids)})

    def set_sharing(self, caller: Caller, file_id: str, visibility: str) -> Result:
        record = self._files.get(file_id)
        if record is None:
            return Result(404, {"detail": "unknown file"})
        if caller.actor_id != record.owner_id:
            self._emit_access_denied(caller, file_id, "share", "not_owner")
            return Result(403, {"detail": "access denied"})
        previous, record.visibility = record.visibility, visibility
        self._emit_sharing_changed(caller, file_id, previous, visibility)
        self._notify(caller, f"sharing_{visibility}")
        return Result(200, {"status": "ok", "previous_visibility": previous})

    # ------------------------------------------------------------- approvals

    def request_approval(self, caller: Caller, file_id: str) -> Result:
        if file_id not in self._files:
            return Result(404, {"detail": "unknown file"})
        approval_id = f"synthetic-approval-{len(self._approvals) + 1}"
        self._approvals[approval_id] = Approval(file_id, caller.actor_id)
        self._emit_approval_requested(caller, approval_id, file_id)
        return Result(201, {"approval_id": approval_id})

    def decide(self, caller: Caller, approval_id: str, decision: str) -> Result:
        approval = self._approvals.get(approval_id)
        if approval is None:
            return Result(404, {"detail": "unknown approval"})
        if approval.decided:
            return Result(409, {"detail": "already decided"})
        record = self._files[approval.file_id]
        if caller.actor_id not in (record.owner_id, ADMIN):
            self._emit_access_denied(caller, approval_id, "approve", "not_approver")
            return Result(403, {"detail": "access denied"})
        approval.decided = True
        self_approved = caller.actor_id == approval.requester_id
        if decision == "approve":
            record.shared_with.add(approval.requester_id)
        self._emit_approval_completed(caller, approval_id, approval, decision, self_approved)
        self._notify(caller, "approval_completed")
        return Result(200, {"status": "ok", "decision": decision, "self_approved": self_approved})

    # --------------------------------------------------------------- webhook

    def set_webhook(self, caller: Caller, label: str) -> Result:
        if caller.actor_id != ADMIN:
            self._emit_access_denied(caller, "file-portal-webhook", "webhook", "not_admin")
            return Result(403, {"detail": "access denied"})
        self._webhook = label
        return Result(200, {"status": "ok"})

    def _notify(self, caller: Caller, trigger: str) -> None:
        """Deterministic fake delivery: labels containing 'unreachable' fail."""
        if "unreachable" in self._webhook:
            self._emit_notification_failed(caller, trigger)
        else:
            self._emit_notification_sent(caller, trigger)

    # ------------------------------------------------------------- telemetry

    def _emit(
        self,
        event_type: str,
        severity: str,
        caller: Caller,
        target_type: str,
        target_id: str,
        attributes: dict[str, Any],
        source: str,
    ) -> None:
        self._telemetry.emit(
            event_type=event_type,
            severity=severity,
            actor_id=caller.actor_id,
            target_type=target_type,
            target_id=target_id,
            source=source,
            correlation_id=caller.correlation_id,
            attributes=attributes,
        )

    def _emit_uploaded(self, caller: Caller, file_id: str, size_bytes: int) -> None:
        self._emit(
            "file.uploaded",
            "INFO",
            caller,
            "file",
            file_id,
            {"size_bytes": size_bytes},
            "file_store",
        )

    def _emit_read(self, caller: Caller, file_id: str, owner_id: str) -> None:
        self._emit(
            "file.read", "INFO", caller, "file", file_id, {"owner_id": owner_id}, "file_store"
        )

    def _emit_access_denied(
        self, caller: Caller, target_id: str, operation: str, reason: str
    ) -> None:
        attrs = {"operation": operation, "reason": reason}
        self._emit("file.access_denied", "WARN", caller, "file", target_id, attrs, "access_guard")

    def _emit_bulk_export(self, caller: Caller, export_id: str, file_count: int) -> None:
        attrs = {"file_count": file_count}
        self._emit("file.bulk_export", "WARN", caller, "file_batch", export_id, attrs, "file_store")

    def _emit_sharing_changed(self, caller: Caller, file_id: str, previous: str, new: str) -> None:
        attrs = {"previous_visibility": previous, "new_visibility": new}
        self._emit("audit.sharing_changed", "WARN", caller, "file", file_id, attrs, "audit_log")

    def _emit_approval_requested(self, caller: Caller, approval_id: str, file_id: str) -> None:
        attrs = {"file_id": file_id}
        self._emit(
            "approval.requested", "INFO", caller, "approval", approval_id, attrs, "approval_flow"
        )

    def _emit_approval_completed(
        self,
        caller: Caller,
        approval_id: str,
        approval: Approval,
        decision: str,
        self_approved: bool,
    ) -> None:
        attrs = {
            "decision": decision,
            "self_approved": self_approved,
            "requester_id": approval.requester_id,
            "file_id": approval.file_id,
        }
        self._emit(
            "approval.completed", "WARN", caller, "approval", approval_id, attrs, "approval_flow"
        )

    def _emit_notification_sent(self, caller: Caller, trigger: str) -> None:
        self._emit(
            "webhook.notification_sent",
            "INFO",
            caller,
            "webhook",
            self._webhook,
            {"trigger": trigger},
            "notifier",
        )

    def _emit_notification_failed(self, caller: Caller, trigger: str) -> None:
        attrs = {"trigger": trigger, "attempt": 1}
        self._emit(
            "webhook.notification_failed",
            "WARN",
            caller,
            "webhook",
            self._webhook,
            attrs,
            "notifier",
        )
