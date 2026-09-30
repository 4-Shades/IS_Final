import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Runs in a fresh interpreter so modules imported by other tests can't mask a missing one.
SCRIPT = r"""
import sys
for name in ("llama_index", "chromadb"):
    sys.modules[name] = None  # any import of these now raises ImportError

from fastapi.testclient import TestClient

import common.llm
from agents.stay_agent.__main__ import app
from shared.schemas import StayResponse

class FakeClient:
    async def generate_structured(self, prompt, response_type):
        return StayResponse(stays=[{"name": "Hotel", "location": "Paris", "price_per_night": 100}])

common.llm.get_llm_client = lambda settings=None: FakeClient()
import agents.stay_agent.agent as stay_agent
stay_agent.get_llm_client = common.llm.get_llm_client

response = TestClient(app).post("/run", json={
    "origin": "Manila", "destination": "Paris",
    "start_date": "2026-11-01", "end_date": "2026-11-05", "budget": 2000,
})
assert response.status_code == 200, response.text
body = response.json()
assert body["stays"][0]["name"] == "Hotel" and body["sources"] == [], body
print("ok")
"""


# With retrieval on but the packages missing, the agent must still plan (and log why).
@pytest.mark.parametrize("rag_enabled", ["false", "true"])
def test_agents_run_without_the_rag_packages(rag_enabled):
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=ROOT,
        env={**os.environ, "RAG_ENABLED": rag_enabled, "OTEL_EXPORTER_OTLP_ENDPOINT": ""},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().endswith("ok")


# What Vercel runs: the simple store with Chroma not installed at all.
SIMPLE_STORE_SCRIPT = r"""
import sys
sys.modules["chromadb"] = None

import json, os
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from llama_index.core.base.embeddings.base import BaseEmbedding

import common.llm
import common.rag.store as store
from common.rag.ingest import embed_destination
from common.rag.simple_store import Writer
from common.rag.wikivoyage import parse_response
from shared.schemas import StayResponse

class Fake(BaseEmbedding):
    def _vec(self, text):
        return [float(len(text) % 7 + 1), 1.0, 0.5]
    def _get_query_embedding(self, q): return self._vec(q)
    async def _aget_query_embedding(self, q): return self._vec(q)
    def _get_text_embedding(self, t): return self._vec(t)

store.build_embed_model = lambda settings: Fake()
index_dir = Path(os.environ["RAG_INDEX_DIR"])
article = parse_response(json.loads(Path(os.environ["FIXTURE"]).read_text(encoding="utf-8")))
writer = Writer(index_dir, "ollama:fake", Fake(), rebuild=False)
nodes = embed_destination("Sampleville", article, embed_model=Fake(), today=date.today())
writer.replace("sampleville", nodes)
writer.finish()
store.save_aliases(index_dir, {"sampleville": "sampleville"})

class FakeClient:
    async def generate_structured(self, prompt, response_type):
        assert "<guidance>" in prompt, "retrieved guidance should reach the prompt"
        stay = {"name": "Hotel", "location": "Sampleville", "price_per_night": 90}
        return StayResponse(stays=[stay])

import agents.stay_agent.agent as stay_agent
stay_agent.get_llm_client = lambda settings=None: FakeClient()
from agents.stay_agent.__main__ import app

body = TestClient(app).post("/run", json={
    "origin": "Manila", "destination": "Sampleville",
    "start_date": "2026-11-01", "end_date": "2026-11-05", "budget": 2000,
}).json()
# Any chromadb import on this path would fail and disable retrieval, leaving no sources.
assert body["sources"] and all("wikivoyage.org" in s["url"] for s in body["sources"]), body
print("ok")
"""


def test_simple_store_retrieves_without_chroma_installed(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", SIMPLE_STORE_SCRIPT],
        cwd=ROOT,
        env={
            **os.environ,
            "RAG_ENABLED": "true",
            "RAG_STORE": "simple",
            "RAG_INDEX_DIR": str(tmp_path / "index"),
            "LLM_PROVIDER": "ollama",
            "OLLAMA_EMBEDDING_MODEL": "fake",
            "FIXTURE": str(ROOT / "tests" / "fixtures" / "wikivoyage_sampleville.json"),
            "OTEL_EXPORTER_OTLP_ENDPOINT": "",
        },
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    assert result.stdout.strip().endswith("ok")
