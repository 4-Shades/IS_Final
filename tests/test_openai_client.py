import json
from dataclasses import replace

import httpx
import pytest

from common.llm import LLMError, OpenAICompatibleClient, to_openai_strict_schema
from shared.config import get_settings
from shared.schemas import FlightResponse


def _settings(api_key: str | None = "sk-test"):
    return replace(
        get_settings(),
        openai_base_url="https://api.openai.test/v1",
        openai_model="gpt-4o-mini",
        openai_api_key=api_key,
    )


def _assert_strict(node: object) -> None:
    if isinstance(node, list):
        for item in node:
            _assert_strict(item)
        return
    if not isinstance(node, dict):
        return
    assert "default" not in node
    if node.get("type") == "object" and "properties" in node:
        assert node["additionalProperties"] is False
        assert sorted(node["required"]) == sorted(node["properties"])
    for key, value in node.items():
        if key in {"properties", "$defs"}:
            for child in value.values():
                _assert_strict(child)
        else:
            _assert_strict(value)


def test_strict_schema_closes_every_object_and_requires_every_field() -> None:
    _assert_strict(to_openai_strict_schema(FlightResponse.model_json_schema()))


def test_strict_schema_keeps_properties_named_like_keywords() -> None:
    schema = {"type": "object", "properties": {"default": {"type": "string", "default": "x"}}}
    assert to_openai_strict_schema(schema) == {
        "type": "object",
        "properties": {"default": {"type": "string"}},
        "additionalProperties": False,
        "required": ["default"],
    }


@pytest.mark.asyncio
async def test_openai_client_sends_strict_schema_and_validates_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == httpx.URL("https://api.openai.test/v1/chat/completions")
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert payload["model"] == "gpt-4o-mini"
        assert payload["response_format"]["json_schema"]["strict"] is True
        _assert_strict(payload["response_format"]["json_schema"]["schema"])
        content = {
            "flights": [{
                "airline": "Example Air", "departure_time": "09:00", "return_time": "18:00",
                "price": 100, "currency": "USD", "stops": 0, "booking_url": None,
            }],
            "error": None,
        }
        body = {"choices": [{"message": {"content": json.dumps(content)}}]}
        return httpx.Response(200, json=body)

    client = OpenAICompatibleClient(_settings(), transport=httpx.MockTransport(handler))
    result = await client.generate_structured("Test prompt", FlightResponse)
    assert result.flights[0].airline == "Example Air"


@pytest.mark.asyncio
async def test_openai_client_requires_api_key() -> None:
    client = OpenAICompatibleClient(_settings(api_key=None))
    with pytest.raises(LLMError):
        await client.generate_structured("p", FlightResponse)


@pytest.mark.asyncio
async def test_openai_client_reports_provider_error_details() -> None:
    error = {"error": {"message": "Invalid schema for response_format"}}
    client = OpenAICompatibleClient(
        _settings(), transport=httpx.MockTransport(lambda _: httpx.Response(400, json=error))
    )
    with pytest.raises(LLMError, match="HTTP 400 .*Invalid schema for response_format"):
        await client.generate_structured("p", FlightResponse)
