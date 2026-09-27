from fastapi.testclient import TestClient

from common.a2a_server import create_app
from shared.schemas import FlightResponse, TravelRequest

PAYLOAD = {
    "origin": "Manila",
    "destination": "Paris",
    "start_date": "2026-11-01",
    "end_date": "2026-11-05",
    "budget": 2000,
}


async def _execute(_: TravelRequest) -> FlightResponse:
    return FlightResponse(error="stub")


def test_health_and_readiness_endpoints() -> None:
    client = TestClient(create_app(service_name="test", execute=_execute))
    assert client.get("/healthz").json() == {"status": "ok", "service": "test"}
    assert client.get("/readyz").json() == {"status": "ready", "service": "test"}


def test_run_is_open_without_a_configured_key() -> None:
    client = TestClient(create_app(service_name="test", execute=_execute))
    assert client.post("/run", json=PAYLOAD).status_code == 200


def test_run_requires_matching_key_when_configured() -> None:
    client = TestClient(create_app(service_name="test", execute=_execute, api_key="secret"))
    assert client.post("/run", json=PAYLOAD).status_code == 401
    assert client.post("/run", json=PAYLOAD, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/run", json=PAYLOAD, headers={"X-API-Key": "secret"}).status_code == 200


def test_health_stays_open_when_key_is_configured() -> None:
    client = TestClient(create_app(service_name="test", execute=_execute, api_key="secret"))
    assert client.get("/healthz").status_code == 200
