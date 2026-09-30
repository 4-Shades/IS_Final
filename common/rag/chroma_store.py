"""Chroma vector store: a local folder, updated a destination at a time (self-hosted)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.schema import BaseNode
from llama_index.vector_stores.chroma import ChromaVectorStore

from common.rag.store import IndexUnavailable

COLLECTION = "travel_guidance"


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


def load(
    index_dir: Path, identity: str, embed_model: Callable[[], BaseEmbedding]
) -> VectorStoreIndex:
    if not (index_dir / "chroma.sqlite3").exists():
        raise IndexUnavailable(f"no index at {index_dir}; run python -m common.rag.ingest")
    client = open_client(index_dir)
    if COLLECTION not in {c.name for c in client.list_collections()}:
        raise IndexUnavailable(f"no {COLLECTION} collection in {index_dir}; run the ingest")
    collection = get_collection(client)
    built_with = collection.metadata.get("embedding")
    if built_with != identity:
        raise IndexUnavailable(
            f"index built with {built_with} but settings use {identity}; re-run the ingest"
        )
    return VectorStoreIndex.from_vector_store(
        ChromaVectorStore(chroma_collection=collection), embed_model=embed_model()
    )


class Writer:
    """Replaces one destination's passages at a time, keeping the others."""

    def __init__(
        self, index_dir: Path, identity: str, embed_model: BaseEmbedding, *, rebuild: bool
    ) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        self._client = open_client(index_dir)
        self.fresh = COLLECTION not in {c.name for c in self._client.list_collections()}
        if not self.fresh:
            built_with = get_collection(self._client).metadata.get("embedding")
            if built_with != identity:
                if not rebuild:
                    raise IndexUnavailable(
                        f"The index was built with {built_with}, but settings now use "
                        f"{identity}. Re-run with --rebuild to replace it."
                    )
                self._client.delete_collection(COLLECTION)
                self.fresh = True
        self._collection = create_collection(self._client, identity)

    def replace(self, destination_key: str, nodes: list[BaseNode]) -> None:
        self._collection.delete(where={"destination_key": destination_key})
        ChromaVectorStore(chroma_collection=self._collection).add(nodes)

    def finish(self) -> int:
        return self._collection.count()
