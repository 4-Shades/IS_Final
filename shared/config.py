"""Environment-driven configuration; no service address is hard-coded."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    host_service_url: str
    flight_service_url: str
    stay_service_url: str
    activities_service_url: str
    downstream_timeout_seconds: float
    llm_provider: str
    open_travel_data_enabled: bool
    weather_provider_enabled: bool
    places_provider_enabled: bool
    ground_transport_enabled: bool
    ollama_base_url: str
    ollama_model: str
    ollama_embedding_model: str
    openai_base_url: str
    openai_model: str
    openai_api_key: str | None
    llm_timeout_seconds: float


def _service_url(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value not in {"", "0", "false", "no", "off"}


@lru_cache
def get_settings() -> Settings:
    return Settings(
        host_service_url=_service_url("HOST_SERVICE_URL", "http://localhost:8000"),
        flight_service_url=_service_url("FLIGHT_SERVICE_URL", "http://localhost:8001"),
        stay_service_url=_service_url("STAY_SERVICE_URL", "http://localhost:8002"),
        activities_service_url=_service_url("ACTIVITIES_SERVICE_URL", "http://localhost:8003"),
        downstream_timeout_seconds=float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "30")),
        llm_provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
        open_travel_data_enabled=_bool_env("OPEN_TRAVEL_DATA_ENABLED", False),
        weather_provider_enabled=_bool_env("WEATHER_PROVIDER_ENABLED", False),
        places_provider_enabled=_bool_env("PLACES_PROVIDER_ENABLED", False),
        ground_transport_enabled=_bool_env("GROUND_TRANSPORT_ENABLED", False),
        ollama_base_url=_service_url("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
        openai_base_url=_service_url("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
    )
