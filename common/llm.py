"""Provider-neutral, schema-constrained LLM access."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar

import httpx
from opentelemetry import metrics
from pydantic import BaseModel, ValidationError

from shared.config import Settings, get_settings

logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)

# No-ops unless common.telemetry installs a meter provider.
_meter = metrics.get_meter("travel.llm")
_request_duration = _meter.create_histogram(
    "llm.request.duration", unit="s", description="Duration of structured LLM calls."
)
_token_usage = _meter.create_counter(
    "llm.token.usage", unit="{token}", description="Tokens consumed by LLM calls."
)


def _record_duration(provider: str, model: str, started: float, outcome: str) -> None:
    _request_duration.record(
        time.perf_counter() - started,
        {"llm.provider": provider, "llm.model": model, "outcome": outcome},
    )


def _record_tokens(provider: str, model: str, prompt: Any, completion: Any) -> None:
    for token_type, count in (("prompt", prompt), ("completion", completion)):
        if isinstance(count, int) and count > 0:
            _token_usage.add(
                count, {"llm.provider": provider, "llm.model": model, "token.type": token_type}
            )


class LLMError(RuntimeError):
    """The provider did not return a valid structured response."""


class LLMClient(ABC):
    @abstractmethod
    async def generate_structured(
        self, prompt: str, response_type: type[ResponseModel]
    ) -> ResponseModel:
        """Generate and independently validate a response against a Pydantic model."""


class OllamaClient(LLMClient):
    """Ollama's private native API with JSON-schema constrained output."""

    def __init__(
        self, *, base_url: str, model: str, timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def generate_structured(
        self, prompt: str, response_type: type[ResponseModel]
    ) -> ResponseModel:
        payload = {
            "model": self.model,
            "stream": False,
            "format": response_type.model_json_schema(),
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON that satisfies the supplied schema. "
                        "Do not invent live prices, availability, bookings, or sources."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        started, outcome = time.perf_counter(), "error"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds), transport=self.transport
            ) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                body = response.json()
                _record_tokens(
                    "ollama", self.model, body.get("prompt_eval_count"), body.get("eval_count")
                )
                content = body["message"]["content"]
            result = response_type.model_validate_json(content)
            outcome = "success"
            return result
        except (httpx.HTTPError, KeyError, TypeError, ValidationError) as exc:
            raise LLMError(f"Ollama did not return a valid {response_type.__name__}") from exc
        finally:
            _record_duration("ollama", self.model, started, outcome)


# Keywords OpenAI strict mode may reject; Pydantic re-validates these after parsing.
_STRICT_UNSUPPORTED_KEYWORDS = frozenset({
    "default", "minLength", "maxLength", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems",
})


def to_openai_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Every object closed and every property required, as OpenAI strict mode demands."""

    def walk(node: Any) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        result: dict[str, Any] = {}
        for key, value in node.items():
            if key in _STRICT_UNSUPPORTED_KEYWORDS:
                continue
            if key in {"properties", "$defs"}:
                result[key] = {name: walk(child) for name, child in value.items()}
            else:
                result[key] = walk(value)
        if result.get("type") == "object" and "properties" in result:
            result["additionalProperties"] = False
            result["required"] = list(result["properties"])
        return result

    return walk(schema)


def _provider_error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return response.text[:300]


class OpenAICompatibleClient(LLMClient):
    """OpenAI Chat Completions with strict JSON-schema output."""

    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key
        self.timeout_seconds = settings.llm_timeout_seconds
        self.transport = transport

    async def generate_structured(
        self, prompt: str, response_type: type[ResponseModel]
    ) -> ResponseModel:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_type.__name__.lower(),
                    "strict": True,
                    "schema": to_openai_strict_schema(response_type.model_json_schema()),
                },
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON that satisfies the supplied schema. "
                        "Do not invent live prices, availability, bookings, or sources."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        started, outcome = time.perf_counter(), "error"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds), transport=self.transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                usage = body.get("usage") or {}
                _record_tokens(
                    "openai",
                    self.model,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                )
                content = body["choices"][0]["message"]["content"]
            result = response_type.model_validate_json(content)
            outcome = "success"
            return result
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"OpenAI-compatible provider returned HTTP {exc.response.status_code} "
                f"for {response_type.__name__}: {_provider_error_message(exc.response)}"
            ) from exc
        except (httpx.HTTPError, KeyError, TypeError, ValidationError) as exc:
            raise LLMError(
                f"OpenAI-compatible provider did not return a valid {response_type.__name__}: "
                f"{type(exc).__name__}: {str(exc)[:300]}"
            ) from exc
        finally:
            _record_duration("openai", self.model, started, outcome)


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.llm_provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
