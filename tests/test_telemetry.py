import json
from dataclasses import replace

import httpx
import pytest
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

import common.telemetry as telemetry
from common.a2a_server import create_app
from common.llm import LLMError, OllamaClient, OpenAICompatibleClient
from shared.config import get_settings
from shared.schemas import FlightResponse, TravelRequest

# The global meter provider can only be set once per process; the llm module's
# instruments were created against the proxy and start recording once it is set.
_reader = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(metric_readers=[_reader]))

FLIGHT = {
    "flights": [{
        "airline": "Example Air", "departure_time": "09:00", "return_time": "18:00",
        "price": 100, "currency": "USD", "stops": 0, "booking_url": None,
    }],
    "error": None,
}


def _points(name: str) -> list:
    data = _reader.get_metrics_data()
    if data is None:
        return []
    return [
        point
        for resource in data.resource_metrics
        for scope in resource.scope_metrics
        for metric in scope.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]


def _token_total(provider: str, token_type: str) -> int:
    return sum(
        p.value for p in _points("llm.token.usage")
        if p.attributes["llm.provider"] == provider and p.attributes["token.type"] == token_type
    )


def test_create_app_skips_export_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    async def _execute(_: TravelRequest) -> FlightResponse:
        return FlightResponse(error="stub")

    create_app(service_name="test", execute=_execute)
    assert telemetry._provider_installed is False


@pytest.mark.asyncio
async def test_openai_call_records_tokens_and_duration() -> None:
    body = {
        "choices": [{"message": {"content": json.dumps(FLIGHT)}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 45},
    }
    settings = replace(get_settings(), openai_api_key="sk-test", openai_model="gpt-4o-mini")
    client = OpenAICompatibleClient(
        settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    )
    prompt_before = _token_total("openai", "prompt")

    await client.generate_structured("p", FlightResponse)

    assert _token_total("openai", "prompt") - prompt_before == 120
    durations = [
        p for p in _points("llm.request.duration")
        if p.attributes["llm.provider"] == "openai" and p.attributes["outcome"] == "success"
    ]
    assert durations and durations[0].count >= 1


@pytest.mark.asyncio
async def test_failed_ollama_call_records_error_outcome() -> None:
    client = OllamaClient(
        base_url="http://ollama:11434", model="llama3.2:3b", timeout_seconds=5,
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )
    with pytest.raises(LLMError):
        await client.generate_structured("p", FlightResponse)

    errors = [
        p for p in _points("llm.request.duration")
        if p.attributes["llm.provider"] == "ollama" and p.attributes["outcome"] == "error"
    ]
    assert errors and errors[0].count >= 1
