"""Retrieval of curated Wikivoyage guidance for the agents' prompts."""

from __future__ import annotations

from common.rag.types import EMPTY, Guidance
from shared.config import Settings, get_settings

__all__ = ["EMPTY", "Guidance", "retrieve_guidance"]


async def retrieve_guidance(
    agent: str, destination: str, *, settings: Settings | None = None, **kwargs
) -> Guidance:
    settings = settings or get_settings()
    if not settings.rag_enabled:
        return EMPTY
    # Imported only when retrieval is on, so deployments without the RAG packages
    # (LlamaIndex, Chroma) still run the agents.
    from common.rag import retrieve

    return await retrieve.retrieve_guidance(agent, destination, settings=settings, **kwargs)
