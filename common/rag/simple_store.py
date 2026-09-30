"""LlamaIndex's built-in vector store: plain files loaded into memory, read-only (Vercel)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.schema import BaseNode

from common.rag.store import IndexUnavailable

META_FILE = "meta.json"


def read_meta(index_dir: Path) -> dict:
    path = index_dir / META_FILE
    if not path.exists():
        raise IndexUnavailable(
            f"no index at {index_dir}; run python -m common.rag.ingest --store simple"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load(
    index_dir: Path, identity: str, embed_model: Callable[[], BaseEmbedding]
) -> VectorStoreIndex:
    built_with = read_meta(index_dir).get("embedding")
    if built_with != identity:
        raise IndexUnavailable(
            f"index built with {built_with} but settings use {identity}; re-run the ingest"
        )
    storage = StorageContext.from_defaults(persist_dir=str(index_dir))
    return load_index_from_storage(storage, embed_model=embed_model())


class Writer:
    """Collects every destination's passages, then writes the whole index at once."""

    fresh = True  # always rebuilt from the destinations given

    def __init__(
        self, index_dir: Path, identity: str, embed_model: BaseEmbedding, *, rebuild: bool
    ) -> None:
        self._dir = index_dir
        self._identity = identity
        self._embed_model = embed_model
        self._nodes: dict[str, list[BaseNode]] = {}

    def replace(self, destination_key: str, nodes: list[BaseNode]) -> None:
        self._nodes[destination_key] = nodes

    def finish(self) -> int:
        nodes = [node for group in self._nodes.values() for node in group]
        self._dir.mkdir(parents=True, exist_ok=True)
        # Nodes arrive already embedded, so this only builds and saves the index.
        index = VectorStoreIndex(nodes, embed_model=self._embed_model)
        index.storage_context.persist(persist_dir=str(self._dir))
        meta = {
            "embedding": self._identity,
            "passages": len(nodes),
            "built": date.today().isoformat(),
        }
        (self._dir / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return len(nodes)
