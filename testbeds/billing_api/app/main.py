"""HTTP layer for the billing_api toy service.

Harness contract (frozen for the pilot): the replay worker calls
`create_app(sink=<TelemetrySink>)` and drives the returned FastAPI app in-process via
`fastapi.testclient.TestClient`. No socket is opened, so nothing is reachable from
the network. Changing this signature would break the oracle and must be a new
experiment version.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import DEFAULT_MAX_FAILED_ATTEMPTS, AuthService
from .telemetry import Telemetry, TelemetrySink


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(min_length=1, max_length=128)
    account_id: str = Field(min_length=1, max_length=128)
    passphrase: str = Field(max_length=256)


def create_app(
    *,
    sink: TelemetrySink,
    max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
    clock: Callable[[], str] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> FastAPI:
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    if id_factory is not None:
        kwargs["id_factory"] = id_factory
    telemetry = Telemetry(sink, **kwargs)
    service = AuthService(telemetry, max_failed_attempts=max_failed_attempts)
    app = FastAPI(title="billing_api (IIDE toy testbed)")

    @app.post("/login")
    def login(
        body: LoginRequest,
        x_correlation_id: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        result = service.login(
            client_id=body.client_id,
            account_id=body.account_id,
            passphrase=body.passphrase,
            correlation_id=x_correlation_id or "uncorrelated",
        )
        if result.status == "success":
            return JSONResponse({"status": "ok"}, status_code=200)
        if result.status == "locked":
            return JSONResponse({"detail": "account locked"}, status_code=423)
        return JSONResponse({"detail": "invalid credentials"}, status_code=401)

    return app
