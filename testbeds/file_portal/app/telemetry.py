"""Structured telemetry emission for the billing_api toy service.

The service emits canonical events (spec 4.1) to a *sink*. The sink is injected by
whoever builds the app: the replay harness supplies its own sink so that the oracle,
not the code under test, controls where events are collected.

This module deliberately imports nothing from the `iide` package so that the
agent-visible workspace (app/ + tests/) is self-contained.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

SCHEMA_VERSION = "1.0"
SERVICE_NAME = "file_portal"


class TelemetrySink(Protocol):
    def emit(self, event: dict[str, Any]) -> None: ...


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class Telemetry:
    """Builds canonical events and forwards them to the sink."""

    def __init__(
        self,
        sink: TelemetrySink,
        *,
        clock: Callable[[], str] = _utc_now_iso,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._sink = sink
        self._clock = clock
        self._id_factory = id_factory

    def emit(
        self,
        *,
        event_type: str,
        severity: str,
        actor_id: str,
        target_type: str,
        target_id: str,
        source: str,
        correlation_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": self._id_factory(),
            "timestamp": self._clock(),
            "service": SERVICE_NAME,
            "event_type": event_type,
            "severity": severity,
            "actor_id": actor_id,
            "target_type": target_type,
            "target_id": target_id,
            "source": source,
            "correlation_id": correlation_id,
            "attributes": dict(attributes or {}),
        }
        self._sink.emit(event)
        return event
