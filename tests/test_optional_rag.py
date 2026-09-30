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
