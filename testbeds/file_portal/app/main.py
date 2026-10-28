"""HTTP layer for the file_portal toy service.

Entry point: `create_app(sink=<TelemetrySink>)` returns the FastAPI app. The test-suite and
deployment tooling call it with this exact signature and drive the app in-process via
`fastapi.testclient.TestClient` (no socket is opened), so keep the signature unchanged.

Request headers: `X-Actor-Id` (caller identity, becomes `actor_id`) and the optional
`X-Correlation-ID`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import Caller, PortalService, Result
from .telemetry import Telemetry, TelemetrySink

# Module-level so FastAPI can resolve them under `from __future__ import annotations`.
ActorId = Annotated[str | None, Header()]
CorrelationId = Annotated[str | None, Header()]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UploadRequest(_Strict):
    file_id: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=0, le=10_000_000)


class ExportRequest(_Strict):
    file_ids: list[str] = Field(min_length=1, max_length=50)


class SharingRequest(_Strict):
    visibility: Literal["private", "public"]


class ApprovalRequest(_Strict):
    file_id: str = Field(min_length=1, max_length=128)


class DecisionRequest(_Strict):
    decision: Literal["approve", "reject"]


class WebhookRequest(_Strict):
    label: str = Field(min_length=1, max_length=128)


def create_app(
    *,
    sink: TelemetrySink,
    clock: Callable[[], str] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    if id_factory is not None:
        kwargs["id_factory"] = id_factory
    telemetry = Telemetry(sink, **kwargs)
    service = PortalService(telemetry)
    app = FastAPI(title="file_portal (toy service)")

    def respond(result: Result) -> JSONResponse:
        return JSONResponse(result.body, status_code=result.status_code)

    def caller(actor_id: str | None, correlation_id: str | None) -> Caller:
        return Caller(actor_id or "anonymous-actor", correlation_id or "uncorrelated")

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        telemetry.emit(
            event_type="service.validation_error",
            severity="WARN",
            actor_id=request.headers.get("x-actor-id") or "anonymous-actor",
            target_type="endpoint",
            target_id=request.url.path,
            source="request_validator",
            correlation_id=request.headers.get("x-correlation-id") or "uncorrelated",
            attributes={"error_count": len(exc.errors())},
        )
        return JSONResponse({"detail": "invalid request"}, status_code=422)

    @app.post("/files")
    def upload(
        body: UploadRequest, x_actor_id: ActorId = None, x_correlation_id: CorrelationId = None
    ) -> JSONResponse:
        return respond(
            service.upload(caller(x_actor_id, x_correlation_id), body.file_id, body.size_bytes)
        )

    @app.post("/files/export")
    def export(
        body: ExportRequest, x_actor_id: ActorId = None, x_correlation_id: CorrelationId = None
    ) -> JSONResponse:
        return respond(service.export(caller(x_actor_id, x_correlation_id), body.file_ids))

    @app.get("/files/{file_id}")
    def read(
        file_id: str, x_actor_id: ActorId = None, x_correlation_id: CorrelationId = None
    ) -> JSONResponse:
        return respond(service.read(caller(x_actor_id, x_correlation_id), file_id))

    @app.post("/files/{file_id}/sharing")
    def set_sharing(
        file_id: str,
        body: SharingRequest,
        x_actor_id: ActorId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        return respond(
            service.set_sharing(caller(x_actor_id, x_correlation_id), file_id, body.visibility)
        )

    @app.post("/approvals")
    def request_approval(
        body: ApprovalRequest, x_actor_id: ActorId = None, x_correlation_id: CorrelationId = None
    ) -> JSONResponse:
        return respond(service.request_approval(caller(x_actor_id, x_correlation_id), body.file_id))

    @app.post("/approvals/{approval_id}/decision")
    def decide(
        approval_id: str,
        body: DecisionRequest,
        x_actor_id: ActorId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        return respond(
            service.decide(caller(x_actor_id, x_correlation_id), approval_id, body.decision)
        )

    @app.post("/webhook")
    def set_webhook(
        body: WebhookRequest, x_actor_id: ActorId = None, x_correlation_id: CorrelationId = None
    ) -> JSONResponse:
        return respond(service.set_webhook(caller(x_actor_id, x_correlation_id), body.label))

    return app
