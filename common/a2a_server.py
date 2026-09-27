"""Common FastAPI application factory for agent services."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from shared.schemas import TravelRequest

logger = logging.getLogger(__name__)
Execute = Callable[[TravelRequest], Awaitable[object]]
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(
    *, service_name: str, execute: Execute, api_key: str | None = None
) -> FastAPI:
    # Only /run is guarded; health endpoints stay open for load balancer checks.
    app = FastAPI(title=f"Travel Planner: {service_name}", version="0.1.0")

    async def require_api_key(provided: str | None = Depends(_api_key_header)) -> None:
        if api_key and not (provided and secrets.compare_digest(provided, api_key)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid X-API-Key header.",
            )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": service_name, "status": "ok", "health": "/healthz"}

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready", "service": service_name}

    @app.post("/run", dependencies=[Depends(require_api_key)])
    async def run(payload: TravelRequest, request: Request) -> object:
        request_id = request.headers.get("X-Request-ID", payload.request_id)
        logger.info(
            "agent_request service=%s request_id=%s trip_id=%s",
            service_name,
            request_id,
            payload.trip_id,
        )
        return await execute(payload)

    return app
