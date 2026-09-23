import json

import httpx
import pytest

from common.llm import LLMError, OllamaClient
from shared.schemas import FlightResponse


@pytest.mark.asyncio
async def test_ollama_client_sends_schema_and_validates_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == httpx.URL("http://ollama:11434/api/chat")
        assert payload["format"] == FlightResponse.model_json_schema()
        assert payload["options"]["temperature"] == 0
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"flights": [{"airline": "Example Air", "departure_time": "09:00", "return_time": "18:00", "price": 100, "stops": 0}]}
                    )
                }
            },
        )

    client = OllamaClient(
        base_url="http://ollama:11434", model="llama3.2:3b", timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )
    result = await client.generate_structured("Test prompt", FlightResponse)
    assert result.flights[0].airline == "Example Air"


@pytest.mark.asyncio
async def test_ollama_client_rejects_invalid_model_json() -> None:
    client = OllamaClient(
        base_url="http://ollama:11434", model="llama3.2:3b", timeout_seconds=5,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"message": {"content": "{}"}})),
    )
    with pytest.raises(LLMError):
        await client.generate_structured("Test prompt", FlightResponse)
