"""Build the guidance index from Wikivoyage: python -m common.rag.ingest"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

import httpx
from llama_index.core import Document
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode
from llama_index.vector_stores.chroma import ChromaVectorStore

from common.rag import store
from common.rag.wikivoyage import LICENSE, Article, ArticleNotFound, fetch_article
from shared.config import get_settings

DEFAULT_DESTINATIONS = Path("data/rag/destinations.txt")
CACHE_MAX_AGE = timedelta(days=30)
EXPIRY = timedelta(days=365)
_EMBED_KEYS = {"destination", "section"}


def ymd(day: date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def read_destinations(path: Path) -> list[tuple[str, list[str]]]:
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        title, _, aliases = line.partition("|")
        entries.append((title.strip(), [a.strip() for a in aliases.split(",") if a.strip()]))
    return entries


def load_article(title: str, cache_dir: Path, *, refresh: bool, client: httpx.Client) -> Article:
    cache = cache_dir / f"{store.destination_key(title).replace(' ', '_')}.json"
    fresh = cache.exists() and time.time() - cache.stat().st_mtime < CACHE_MAX_AGE.total_seconds()
    if fresh and not refresh:
        return Article(**json.loads(cache.read_text(encoding="utf-8")))
    article = fetch_article(title, client=client)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(asdict(article)), encoding="utf-8")
    time.sleep(1)  # be polite to the Wikimedia API
    return article


def build_nodes(destination: str, article: Article, today: date) -> list:
    key = store.destination_key(destination)
    documents = []
    for section, text in article.sections.items():
        if section not in store.INGESTED_SECTIONS:
            continue
        metadata = {
            "destination": destination,
            "destination_key": key,
            "section": section,
            "title": f"Wikivoyage: {article.title}, {section}",
            "source_url": f"{article.url}#{section.replace(' ', '_')}",
            "revision_id": article.revision_id,
            "license": LICENSE,
            "language": "en",
            "access_policy": "curated",
            "effective_ymd": ymd(today),
            "expiry_ymd": ymd(today + EXPIRY),
        }
        documents.append(
            Document(
                text=text,
                metadata=metadata,
                excluded_embed_metadata_keys=[k for k in metadata if k not in _EMBED_KEYS],
                excluded_llm_metadata_keys=list(metadata),
            )
        )
    nodes = SentenceSplitter(chunk_size=300, chunk_overlap=30).get_nodes_from_documents(documents)
    counts: dict[str, int] = {}
    for node in nodes:
        section = node.metadata["section"]
        counts[section] = counts.get(section, 0) + 1
        node.id_ = f"{key}|{section}|{counts[section]}"
    return nodes


def ingest_destination(
    destination: str,
    article: Article,
    *,
    collection,
    embed_model: BaseEmbedding,
    today: date,
) -> int:
    nodes = build_nodes(destination, article, today)
    if not nodes:
        return 0
    texts = [node.get_content(metadata_mode=MetadataMode.EMBED) for node in nodes]
    for node, embedding in zip(nodes, embed_model.get_text_embedding_batch(texts)):
        node.embedding = embedding
    collection.delete(where={"destination_key": store.destination_key(destination)})
    ChromaVectorStore(chroma_collection=collection).add(nodes)
    return len(nodes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the guidance index from Wikivoyage.")
    parser.add_argument("--destinations", help='Comma-separated, e.g. "Kyoto,Lisbon".')
    parser.add_argument("--file", type=Path, default=DEFAULT_DESTINATIONS)
    parser.add_argument("--refresh", action="store_true", help="Re-download cached articles.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the index first, e.g. after switching embeddings.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    index_dir = Path(settings.rag_index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    identity = store.embedding_identity(settings)
    client = store.open_client(index_dir)

    existing = {c.name for c in client.list_collections()}
    if store.COLLECTION in existing:
        built_with = store.get_collection(client).metadata.get("embedding")
        if built_with != identity:
            if not args.rebuild:
                print(
                    f"The index was built with {built_with}, but settings now use {identity}. "
                    "Re-run with --rebuild to replace it.",
                    file=sys.stderr,
                )
                return 1
            client.delete_collection(store.COLLECTION)
            store.save_aliases(index_dir, {})
    collection = store.create_collection(client, identity)

    if args.destinations:
        entries = [(d.strip(), []) for d in args.destinations.split(",") if d.strip()]
    else:
        entries = read_destinations(args.file)

    embed_model = store.build_embed_model(settings)
    aliases = store.load_aliases(index_dir)
    cache_dir = index_dir.parent / "cache"
    today = date.today()
    failed = []
    print(f"Embedding with {identity} into {index_dir}")
    with httpx.Client(timeout=30) as http:
        for destination, extra in entries:
            try:
                article = load_article(destination, cache_dir, refresh=args.refresh, client=http)
                count = ingest_destination(
                    destination,
                    article,
                    collection=collection,
                    embed_model=embed_model,
                    today=today,
                )
            except (ArticleNotFound, httpx.HTTPError) as exc:
                print(f"  {destination}: skipped ({exc})", file=sys.stderr)
                failed.append(destination)
                continue
            key = store.destination_key(destination)
            for alias in [destination, article.title, *extra]:
                aliases[store.destination_key(alias)] = key
            print(f"  {destination}: {count} passages from {article.url}")
    store.save_aliases(index_dir, aliases)
    print(f"Done: {collection.count()} passages in total.")
    return 1 if failed and len(failed) == len(entries) else 0


if __name__ == "__main__":
    sys.exit(main())
