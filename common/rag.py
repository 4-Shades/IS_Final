"""Curated, citation-backed retrieval layer built on local embeddings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from typing import Any


@dataclass(frozen=True)
class Citation:
    title: str
    source_url: str
    license: str | None = None


@dataclass
class RAGDocument:
    text: str
    metadata: dict[str, Any]
    embedding: list[float]

    @property
    def citation(self) -> Citation:
        return Citation(
            title=self.metadata.get("title") or "Untitled document",
            source_url=self.metadata.get("source_url") or "",
            license=self.metadata.get("license"),
        )


@dataclass
class SearchResult:
    document: RAGDocument
    score: float
    citation: Citation


_DEFAULT_GUIDANCE = [
    {
        "text": "Paris museums often extend hours on Fridays and may require timed reservations.",
        "metadata": {
            "destination": "Paris",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-12-31",
            "source_url": "https://example.com/curated/paris-museum-hours",
            "title": "Paris museum hours",
        },
        "embedding": [1.0, 0.0],
    },
    {
        "text": "Public transit in Paris is usually the most convenient option for central sightseeing days.",
        "metadata": {
            "destination": "Paris",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-12-31",
            "source_url": "https://example.com/curated/paris-transit",
            "title": "Paris transit guidance",
        },
        "embedding": [0.9, 0.1],
    },
    {
        "text": "Rome historic attractions can involve long queues during midday; early entry helps reduce wait times.",
        "metadata": {
            "destination": "Rome",
            "language": "en",
            "license": "CC BY 4.0",
            "access_policy": "internal",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-12-31",
            "source_url": "https://example.com/curated/rome-attractions",
            "title": "Rome attraction guidance",
        },
        "embedding": [0.0, 1.0],
    },
]


class RAGIndex:
    """Minimal in-memory retrieval index for curated guidance documents."""

    def __init__(self) -> None:
        self._documents: list[RAGDocument] = []

    def add_document(self, text: str, *, metadata: dict[str, Any], embedding: list[float]) -> None:
        self._documents.append(RAGDocument(text=text, metadata=metadata, embedding=embedding))

    def add_seed_documents(self) -> None:
        if self._documents:
            return
        for item in _DEFAULT_GUIDANCE:
            self.add_document(item["text"], metadata=item["metadata"], embedding=item["embedding"])

    def _filter(self, *, destination: str | None = None, language: str | None = None) -> list[RAGDocument]:
        documents: list[RAGDocument] = []
        for doc in self._documents:
            metadata = doc.metadata
            if destination and metadata.get("destination") != destination:
                continue
            if language and metadata.get("language") != language:
                continue
            if metadata.get("access_policy") not in {None, "internal", "curated"}:
                continue
            effective = metadata.get("effective_date")
            expiry = metadata.get("expiry_date")
            today = date.today().isoformat()
            if effective and today < effective:
                continue
            if expiry and today > expiry:
                continue
            if not metadata.get("source_url"):
                continue
            documents.append(doc)
        return documents

    def augment_prompt(
        self,
        query: str,
        *,
        destination: str | None = None,
        language: str | None = "en",
        top_k: int = 3,
    ) -> tuple[str, list[Citation]]:
        results = self.search(query, destination=destination, language=language, top_k=top_k)
        if not results:
            return query, []

        snippets: list[str] = []
        citations: list[Citation] = []
        for result in results:
            snippet = result.document.text.strip()
            if not snippet:
                continue
            snippets.append(
                f"- {snippet} [Source: {result.citation.title} | {result.citation.source_url} | {result.citation.license or 'unknown license'}]"
            )
            citations.append(result.citation)

        context = "\n".join(snippets)
        return (
            f"Use the following curated guidance only. Do not invent sources or live inventory.\n{context}\n\nUser request: {query}",
            citations,
        )

    def search(
        self,
        query: str,
        *,
        destination: str | None = None,
        language: str | None = "en",
        top_k: int = 3,
    ) -> list[SearchResult]:
        if not self._documents:
            return []

        query_vector = self._embed_query(query)
        matches: list[SearchResult] = []
        for doc in self._filter(destination=destination, language=language):
            score = self._cosine_similarity(query_vector, doc.embedding)
            matches.append(SearchResult(document=doc, score=score, citation=doc.citation))
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[:top_k]

    @staticmethod
    def _embed_query(query: str) -> list[float]:
        words = query.lower().split()
        if not words:
            return [0.0]
        total = len(words)
        vector = [0.0] * max(2, total)
        for index, word in enumerate(words):
            vector[index % len(vector)] += 1.0
        norm = sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        max_len = max(len(left), len(right))
        left_padded = left + [0.0] * (max_len - len(left))
        right_padded = right + [0.0] * (max_len - len(right))
        numerator = sum(a * b for a, b in zip(left_padded, right_padded))
        left_norm = sqrt(sum(a * a for a in left_padded))
        right_norm = sqrt(sum(b * b for b in right_padded))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)


def get_rag_index() -> RAGIndex:
    if not hasattr(get_rag_index, "_instance"):
        index = RAGIndex()
        index.add_seed_documents()
        get_rag_index._instance = index
    return get_rag_index._instance
