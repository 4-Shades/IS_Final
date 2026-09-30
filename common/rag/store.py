"""Shared retrieval settings: sections, destination names, embeddings, and aliases."""

from __future__ import annotations

import json
from pathlib import Path

from llama_index.core.base.embeddings.base import BaseEmbedding

from shared.config import Settings

ALIASES_FILE = "aliases.json"
STORES = ("chroma", "simple")

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


class IndexUnavailable(RuntimeError):
    """The index is missing, unreadable, or was built with a different embedding model."""


def destination_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def embedding_identity(settings: Settings) -> str:
    if settings.llm_provider == "openai":
        model = settings.openai_embedding_model
        return f"openai:{model}:{settings.openai_embedding_dimensions}"
    return f"ollama:{settings.ollama_embedding_model}"


def build_embed_model(settings: Settings) -> BaseEmbedding:
    if settings.llm_provider == "openai":
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
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


def backend(name: str):
    # Imported on demand so a deployment without chromadb can still use the simple store.
    if name == "simple":
        from common.rag import simple_store

        return simple_store
    if name == "chroma":
        try:
            from common.rag import chroma_store
        except ImportError as exc:
            raise IndexUnavailable(f"RAG_STORE=chroma but Chroma isn't installed ({exc})") from exc
        return chroma_store
    raise IndexUnavailable(f"unknown RAG_STORE {name!r}; use one of {', '.join(STORES)}")


def load_aliases(index_dir: str | Path) -> dict[str, str]:
    path = Path(index_dir) / ALIASES_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_aliases(index_dir: str | Path, aliases: dict[str, str]) -> None:
    path = Path(index_dir) / ALIASES_FILE
    path.write_text(json.dumps(aliases, indent=2, sort_keys=True), encoding="utf-8")
