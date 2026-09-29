"""The shared Chroma index: where it lives, how it's embedded, and destination names."""

from __future__ import annotations

import json
from pathlib import Path

import chromadb
from llama_index.core.base.embeddings.base import BaseEmbedding

from shared.config import Settings

COLLECTION = "travel_guidance"
ALIASES_FILE = "aliases.json"

# Which article sections each agent retrieves from, and the topic its query asks about.
AGENT_SECTIONS: dict[str, tuple[str, ...]] = {
    "flight": ("Get in", "Get around"),
    "stay": ("Sleep", "Stay safe", "Understand"),
    "activities": ("See", "Do", "Eat", "Drink"),
}
AGENT_TOPICS = {
    "flight": "arriving by plane, airports, and getting into the city",
    "stay": "where to stay, neighbourhoods, and accommodation",
    "activities": "things to see, do, eat, and drink",
}
INGESTED_SECTIONS = frozenset(s for sections in AGENT_SECTIONS.values() for s in sections)


def destination_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def embedding_identity(settings: Settings) -> str:
    if settings.llm_provider == "openai":
        return f"openai:{settings.openai_embedding_model}"
    return f"ollama:{settings.ollama_embedding_model}"


def build_embed_model(settings: Settings) -> BaseEmbedding:
    if settings.llm_provider == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
            api_base=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )
    from llama_index.embeddings.ollama import OllamaEmbedding

    return OllamaEmbedding(
        model_name=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
        client_kwargs={"timeout": settings.llm_timeout_seconds},
        # Ollama unloads idle models after 5 minutes; reloading on CPU while three agents
        # wait can take longer than the retrieval timeout.
        keep_alive="30m",
    )


def open_client(index_dir: str | Path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(
        path=str(index_dir),
        settings=chromadb.Settings(anonymized_telemetry=False),
    )


def get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    # embedding_function=None: Chroma's default downloads an ONNX model; LlamaIndex embeds.
    return client.get_collection(COLLECTION, embedding_function=None)


def create_collection(client: chromadb.ClientAPI, identity: str) -> chromadb.Collection:
    return client.get_or_create_collection(
        COLLECTION,
        embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"embedding": identity},
    )


def load_aliases(index_dir: str | Path) -> dict[str, str]:
    path = Path(index_dir) / ALIASES_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_aliases(index_dir: str | Path, aliases: dict[str, str]) -> None:
    path = Path(index_dir) / ALIASES_FILE
    path.write_text(json.dumps(aliases, indent=2, sort_keys=True), encoding="utf-8")
