"""Common FastAPI application factory for agent services."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request

from shared.schemas import TravelRequest

logger = logging.getLogger(__name__)
Execute = Callable[[TravelRequest], Awaitable[object]]


def create_app(*, service_name: str, execute: Execute) -> FastAPI:
    app = FastAPI(title=f"Travel Planner: {service_name}", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready", "service": service_name}

    @app.post("/run")
    async def run(payload: TravelRequest, request: Request) -> object:
        request_id = request.headers.get("X-Request-ID", payload.request_id)
        logger.info("agent_request service=%s request_id=%s trip_id=%s", service_name, request_id, payload.trip_id)
        return await execute(payload)

    return app
