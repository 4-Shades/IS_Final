from fastapi.testclient import TestClient

from common.a2a_server import create_app
from shared.schemas import FlightResponse, TravelRequest


async def _execute(_: TravelRequest) -> FlightResponse:
    return FlightResponse()


def test_health_and_readiness_endpoints() -> None:
    client = TestClient(create_app(service_name="test", execute=_execute))
    assert client.get("/healthz").json() == {"status": "ok", "service": "test"}
    assert client.get("/readyz").json() == {"status": "ready", "service": "test"}
