# ADK-Powered Travel Planner

**Project Proponents:** Chaim Joseph Cordova & Psalmantha Allaine Ipong

## Overview
The **ADK-Powered Travel Planner** is a multi-agent travel-planning application. A host service coordinates specialist services for flights, stays, and activities, while a Streamlit UI provides the user-facing workflow.

The application uses Ollama for local, schema-constrained generation by default. Generated flights, stays, and activities are illustrative suggestions only; they are not live availability, live prices, or bookable offers.

## Features
- **Multi-Agent Architecture:** Orchestrates specialized agents for different travel aspects.
- **Local LLM Inference:** Uses Meta Llama models served privately by Ollama.
- **Structured Responses:** Validates model output against shared Pydantic contracts.
- **Open Travel Data Adapters:** Provides Nominatim-compatible geocoding, Overpass places, and Open-Meteo weather adapters.
- **Retrieval Context:** Supports curated, licensed guidance with source citations and local embeddings.
- **Containerized Runtime:** Uses a split Docker design so API services and the UI install only the dependencies they need.
- **Interactive UI:** User-friendly web interface built with Streamlit.
- **Microservices:** Each agent runs as an independent service.

## System Components
1.  **Host Agent:** The central orchestrator that manages the workflow.
2.  **Flight Agent:** Suggests flight options.
3.  **Stay Agent:** Suggests accommodation options.
4.  **Activities Agent:** Recommends local activities.
5.  **Travel Data Providers:** Shared adapters for geocoding, places, and weather context.
6.  **RAG Layer:** Filters curated documents by destination, language, access policy, and validity dates.
7.  **Frontend:** Streamlit application for user interaction.

## Prerequisites
- Python 3.11+
- Ollama for local, non-container development
- Docker Desktop for containerized deployment
- Kubernetes with a GPU node pool for the Ollama manifest

## Installation

1. Clone the repository or navigate to the project directory.

2. Create and activate a virtual environment, then install the project dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.api.txt
   ```

   If you are working on the UI locally, install the frontend extra as well:

   ```bash
   pip install -r requirements.ui.txt
   ```

3. Copy the environment template:

   ```bash
   copy .env.example .env
   ```

4. For local development, install Ollama and pull the configured models:

   ```bash
   ollama pull llama3.2:3b
   ollama pull all-minilm
   ```

   The default local Ollama URL is `http://localhost:11434`.

## Usage

The application consists of a backend (agents) and a frontend (UI). You need to run both.

### Local services

Start Ollama first, then start each service in a separate terminal:
```bash
ollama serve
uvicorn agents.host_agent.__main__:app --port 8000
uvicorn agents.flight_agent.__main__:app --port 8001
uvicorn agents.stay_agent.__main__:app --port 8002
uvicorn agents.activities_agent.__main__:app --port 8003
```

Start the UI in another terminal:
```bash
streamlit run travel_ui.py
```

The UI is available at `http://localhost:8501`.

### Docker Compose

Copy `.env.example` to `.env`, then start the service stack with a private Ollama-backed backend:

```bash
docker compose --profile ollama up --build
```

The Compose file uses two runtime targets from the same Dockerfile:

- `api-runtime` for the FastAPI host and specialist services
- `ui-runtime` for the Streamlit frontend

Specialist services communicate with Ollama at `http://ollama:11434` over the internal backend network. Ollama has no published host port, and its model cache is persisted in the `ollama-data` volume. Pull the configured models inside the Ollama container:

```bash
docker compose --profile ollama exec ollama ollama pull llama3.2:3b
docker compose --profile ollama exec ollama ollama pull all-minilm
```

To start the optional local PostgreSQL and Redis services, set `POSTGRES_PASSWORD` in `.env` and use:

```bash
docker compose --profile ollama --profile data up --build
```

### Kubernetes Ollama deployment

The manifest in `kubernetes/ollama.yaml` defines persistent model storage, a GPU-targeted deployment, a private `ClusterIP` service, readiness and liveness probes, NetworkPolicy, and a model preload job.

Apply it to a cluster with a node labeled `workload=gpu`:

```bash
kubectl apply -f kubernetes/ollama.yaml
kubectl -n travel-planner wait --for=condition=available deployment/ollama --timeout=10m
kubectl -n travel-planner get pods,svc
```

The manifest intentionally creates no Ingress and does not expose port `11434` publicly.

## Configuration

Configuration is loaded from environment variables. Important settings include:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama` | Selects Ollama or the temporary OpenAI-compatible fallback. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama URL outside containers; Compose uses `http://ollama:11434`. |
| `OLLAMA_MODEL` | `llama3.2:3b` | Generation model. |
| `OLLAMA_EMBEDDING_MODEL` | `embeddinggemma` | Local embedding model for retrieval. |
| `OPEN_TRAVEL_DATA_ENABLED` | `false` | Enables the open-travel-data rollout flag. |
| `WEATHER_PROVIDER_ENABLED` | `false` | Controls weather-provider rollout. |
| `PLACES_PROVIDER_ENABLED` | `false` | Controls places-provider rollout. |
| `GROUND_TRANSPORT_ENABLED` | `false` | Reserved for validated transit coverage. |

Do not commit `.env` or API keys. Use `.env.example` as the starting template.

## Testing

Run the test suite with:

```bash
python -m pytest -q
```

Run linting with:

```bash
python -m ruff check .
```

## Project Structure

```text
IS_Final/
├── agents/                 # Agent implementations
│   ├── activities_agent/
│   ├── flight_agent/
│   ├── host_agent/
│   └── stay_agent/
├── common/                 # LLM, RAG, provider, and communication utilities
├── shared/                 # Shared data schemas
├── kubernetes/             # Kubernetes Ollama deployment
├── tests/                  # Contract and provider tests
├── Dockerfile              # Split multi-stage API/UI Docker image build
├── requirements.api.txt    # FastAPI runtime dependencies
├── requirements.ui.txt     # Streamlit runtime dependencies
├── compose.yaml            # Containerized service stack
├── .env.example            # Environment configuration template
├── .env                    # Local runtime overrides (not committed)
├── run.py                  # Script to start all agents
├── travel_ui.py            # Streamlit frontend application
├── README.md               # Project documentation
├── OLLAMA_OPEN_TRAVEL_PLAN.md
└── pyproject.toml         # Project lint/test configuration
```
