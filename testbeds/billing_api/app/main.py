"""HTTP layer for the billing_api toy service.

Harness contract (frozen for the pilot): the replay worker calls
`create_app(sink=<TelemetrySink>)` and drives the returned FastAPI app in-process via
`fastapi.testclient.TestClient`. No socket is opened, so nothing is reachable from
the network. Changing this signature would break the oracle and must be a new
experiment version.

Request headers: `X-Client-Id` (caller identity, becomes `actor_id`), `X-Session-Id`
(session issued by /login), `X-Correlation-ID` (optional).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import (
    DEFAULT_EXPORT_LIMIT_PER_CLIENT,
    DEFAULT_MAX_FAILED_ATTEMPTS,
    BillingService,
    Caller,
    Result,
)
from .telemetry import Telemetry, TelemetrySink

# Module-level so FastAPI can resolve them under `from __future__ import annotations`.
ClientId = Annotated[str | None, Header()]
SessionId = Annotated[str | None, Header()]
CorrelationId = Annotated[str | None, Header()]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(_Strict):
    client_id: str = Field(min_length=1, max_length=128)
    account_id: str = Field(min_length=1, max_length=128)
    passphrase: str = Field(max_length=256)


class RoleChangeRequest(_Strict):
    target_account_id: str = Field(min_length=1, max_length=128)
    new_role: Literal["viewer", "analyst", "admin"]


class ExportRequest(_Strict):
    invoice_ids: list[str] = Field(min_length=1, max_length=50)


class WebhookRequest(_Strict):
    target_label: str = Field(min_length=1, max_length=128)


def create_app(
    *,
    sink: TelemetrySink,
    max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
    export_limit_per_client: int = DEFAULT_EXPORT_LIMIT_PER_CLIENT,
    clock: Callable[[], str] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    if id_factory is not None:
        kwargs["id_factory"] = id_factory
    telemetry = Telemetry(sink, **kwargs)
    service = BillingService(
        telemetry,
        max_failed_attempts=max_failed_attempts,
        export_limit_per_client=export_limit_per_client,
    )
    app = FastAPI(title="billing_api (IIDE toy testbed)")

    def respond(result: Result) -> JSONResponse:
        return JSONResponse(result.body, status_code=result.status_code)

    def caller(client_id: str | None, session_id: str | None, correlation_id: str | None) -> Caller:
        return Caller(client_id or "anonymous-client", session_id, correlation_id or "uncorrelated")

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        telemetry.emit(
            event_type="service.validation_error",
            severity="WARN",
            actor_id=request.headers.get("x-client-id") or "anonymous-client",
            target_type="endpoint",
            target_id=request.url.path,
            source="request_validator",
            correlation_id=request.headers.get("x-correlation-id") or "uncorrelated",
            attributes={"error_count": len(exc.errors())},
        )
        return JSONResponse({"detail": "invalid request"}, status_code=422)

    @app.post("/login")
    def login(body: LoginRequest, x_correlation_id: CorrelationId = None) -> JSONResponse:
        return respond(
            service.login(
                client_id=body.client_id,
                account_id=body.account_id,
                passphrase=body.passphrase,
                correlation_id=x_correlation_id or "uncorrelated",
            )
        )

    @app.post("/roles")
    def change_role(
        body: RoleChangeRequest,
        x_client_id: ClientId = None,
        x_session_id: SessionId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        who = caller(x_client_id, x_session_id, x_correlation_id)
        return respond(
            service.change_role(
                who, target_account_id=body.target_account_id, new_role=body.new_role
            )
        )

    @app.get("/invoices/{invoice_id}")
    def read_invoice(
        invoice_id: str,
        x_client_id: ClientId = None,
        x_session_id: SessionId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        return respond(
            service.read_invoice(caller(x_client_id, x_session_id, x_correlation_id), invoice_id)
        )

    @app.post("/invoices/export")
    def export_invoices(
        body: ExportRequest,
        x_client_id: ClientId = None,
        x_session_id: SessionId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        return respond(
            service.export_invoices(
                caller(x_client_id, x_session_id, x_correlation_id), body.invoice_ids
            )
        )

    @app.post("/webhooks")
    def set_webhook(
        body: WebhookRequest,
        x_client_id: ClientId = None,
        x_session_id: SessionId = None,
        x_correlation_id: CorrelationId = None,
    ) -> JSONResponse:
        return respond(
            service.set_webhook(
                caller(x_client_id, x_session_id, x_correlation_id), body.target_label
            )
        )

    return app
