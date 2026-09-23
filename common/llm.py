"""Provider-neutral, schema-constrained LLM access."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from shared.config import Settings, get_settings

logger = logging.getLogger(__name__)
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class LLMError(RuntimeError):
    """The provider did not return a valid structured response."""


class LLMClient(ABC):
    @abstractmethod
    async def generate_structured(
        self, prompt: str, response_type: type[ResponseModel]
    ) -> ResponseModel:
        """Generate and independently validate a response against a Pydantic model."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a vector embedding for the supplied text using the configured provider."""


class OllamaClient(LLMClient):
    """Ollama's private native API with JSON-schema constrained output."""

    def __init__(
        self, *, base_url: str, model: str, timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model or "all-minilm"
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
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds), transport=self.transport
            ) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                content = response.json()["message"]["content"]
            return response_type.model_validate_json(content)
        except (httpx.HTTPError, KeyError, TypeError, ValidationError) as exc:
            raise LLMError(f"Ollama did not return a valid {response_type.__name__}") from exc

    async def embed(self, text: str) -> list[float]:
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds), transport=self.transport
            ) as client:
                response = await client.post(f"{self.base_url}/api/embed", json=payload)
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")
                if not embeddings or not embeddings[0]:
                    raise LLMError("Ollama did not return an embedding")
            return embeddings[0]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise LLMError("Ollama did not return a valid embedding") from exc


class OpenAICompatibleClient(LLMClient):
    """Temporary controlled fallback for A/B comparison during migration."""

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.model = settings.openai_model
        self.api_key = settings.openai_api_key
        self.timeout_seconds = settings.llm_timeout_seconds

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
                    "schema": response_type.model_json_schema(),
                },
            },
            "messages": [
                {"role": "system", "content": "Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            return response_type.model_validate_json(content)
        except (httpx.HTTPError, KeyError, TypeError, ValidationError) as exc:
            raise LLMError(f"OpenAI-compatible provider did not return a valid {response_type.__name__}") from exc

    async def embed(self, text: str) -> list[float]:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        raise NotImplementedError("Embedding is not implemented for the OpenAI comparison fallback.")


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.llm_provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
            embedding_model=settings.ollama_embedding_model,
        )
    if settings.llm_provider == "openai":
        return OpenAICompatibleClient(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
