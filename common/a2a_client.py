"""Resilient HTTP client used for host-to-specialist calls."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def call_agent(
    url: str,
    payload: dict[str, Any],
    *,
    request_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Return a machine-readable error instead of failing the whole trip plan."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.post(
                f"{url.rstrip('/')}/run",
                json=payload,
                headers={"X-Request-ID": request_id},
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("agent response must be a JSON object")
            return body
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("agent_call_failed url=%s request_id=%s error=%s", url, request_id, exc)
        return {"error": "Service is temporarily unavailable."}
