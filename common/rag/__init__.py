"""Retrieval of curated Wikivoyage guidance for the agents' prompts."""

from __future__ import annotations

import logging

from common.rag.types import EMPTY, Guidance
from shared.config import Settings, get_settings

__all__ = ["EMPTY", "Guidance", "retrieve_guidance"]

logger = logging.getLogger(__name__)
_missing_packages_logged = False


async def retrieve_guidance(
    agent: str, destination: str, *, settings: Settings | None = None, **kwargs
) -> Guidance:
    settings = settings or get_settings()
    if not settings.rag_enabled:
        return EMPTY
    # Imported only when retrieval is on, so deployments without the RAG packages
    # (LlamaIndex, Chroma) still run the agents.
    try:
        from common.rag import retrieve
    except ImportError as exc:
        global _missing_packages_logged
        if not _missing_packages_logged:
            logger.warning(
                "rag_disabled reason=packages not installed (%s); set RAG_ENABLED=false", exc
            )
            _missing_packages_logged = True
        return EMPTY

    return await retrieve.retrieve_guidance(agent, destination, settings=settings, **kwargs)
