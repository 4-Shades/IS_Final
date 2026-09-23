import json

import httpx
import pytest

from common.llm import OllamaClient
from common.rag import RAGIndex


@pytest.mark.asyncio
async def test_ollama_client_embeds_text_with_embedding_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == httpx.URL("http://ollama:11434/api/embed")
        assert payload["model"] == "all-minilm"
        assert payload["input"] == "Paris context"
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3]]})

    client = OllamaClient(
        base_url="http://ollama:11434",
        model="llama3.2:3b",
        embedding_model="all-minilm",
        timeout_seconds=5,
        transport=httpx.MockTransport(handler),
    )

    assert await client.embed("Paris context") == [0.1, 0.2, 0.3]


def test_rag_search_filters_documents_and_requires_citations() -> None:
    index = RAGIndex()
    index.add_document(
        "Paris museums are open late on Fridays.",
        metadata={
            "destination": "Paris",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "source_url": "https://example.com/paris-museums",
            "title": "Paris museum hours",
        },
        embedding=[1.0, 0.0],
    )
    index.add_document(
        "Rome museums are closed on Mondays.",
        metadata={
            "destination": "Rome",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "source_url": "https://example.com/rome-museums",
            "title": "Rome museum hours",
        },
        embedding=[0.0, 1.0],
    )

    results = index.search("Paris museum hours", destination="Paris", top_k=1)

    assert len(results) == 1
    assert results[0].document.metadata["destination"] == "Paris"
    assert results[0].citation.source_url == "https://example.com/paris-museums"
    assert results[0].citation.title == "Paris museum hours"


def test_rag_prompt_includes_citation_context() -> None:
    index = RAGIndex()
    index.add_document(
        "Paris museums are open late on Fridays.",
        metadata={
            "destination": "Paris",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "source_url": "https://example.com/paris-museums",
            "title": "Paris museum hours",
        },
        embedding=[1.0, 0.0],
    )

    prompt, citations = index.augment_prompt("Plan a Paris museum day", destination="Paris")

    assert "Paris museums are open late on Fridays." in prompt
    assert "https://example.com/paris-museums" in prompt
    assert citations[0].source_url == "https://example.com/paris-museums"
