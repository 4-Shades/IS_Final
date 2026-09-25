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

### Streamlit Community Cloud

Streamlit Community Cloud can host `travel_ui.py`, but it cannot host Ollama or the FastAPI agent processes. Deploy the repository from GitHub with these settings:

- **Main file path:** `travel_ui.py`
- **Python version:** 3.11
- **Requirements:** `requirements.txt` in the repository root

In the app's Streamlit Cloud settings, add this secret:

```toml
HOST_SERVICE_URL = "https://your-public-host-api.example.com"
```

The host API and all specialist agents must be deployed separately on a Docker-capable service, with Ollama reachable by the host API. Do not use `localhost` for `HOST_SERVICE_URL` in the cloud app.

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

### Render Ollama service

Deploy Ollama as a separate private Render service before deploying the FastAPI agents:

- **Runtime:** Docker
- **Dockerfile path:** `./Dockerfile.ollama`
- **Docker context:** `.`
- **Port:** `11434`
- **Persistent disk mount:** `/root/.ollama`

After the service starts, open its Render shell and download the models used by the agents:

```bash
ollama pull llama3.2:3b
ollama pull embeddinggemma
```

Set the FastAPI services' `OLLAMA_BASE_URL` to the Ollama service's private Render URL. Keep the Ollama service private; only the public host API should be exposed.

### Railway Ollama service

Railway can host the Ollama service using `Dockerfile.ollama`. The repository includes `railway.toml` so Railway uses the correct Dockerfile, port, start command, and health endpoint.

Create a Railway service from this repository with these settings:

- **Dockerfile:** `Dockerfile.ollama`
- **Port:** `11434`
- **Start command:** `ollama serve`
- **Health check:** `/api/tags`

Attach a Railway volume to the service at `/root/.ollama`. Without this volume, downloaded models are lost whenever the service is redeployed.

After the service is running, use its shell to download the configured models:

```bash
ollama pull llama3.2:3b
ollama pull embeddinggemma
```

Use the Railway HTTPS domain as `OLLAMA_BASE_URL` in the FastAPI host. Do not expose an unauthenticated Ollama endpoint in production.

### Railway Flight agent service

The Flight agent remains on Railway. Stay and Activities are deployed to AWS ECS Fargate using the Terraform module described below. If you temporarily deploy all specialist agents on Railway, each service uses the repository's API image and communicates with Ollama over Railway networking.

For each service, use these settings:

- **Runtime:** Docker
- **Dockerfile path:** `./Dockerfile.agent`
- **Docker context:** `.`
- **Start command:** `python -m common.serve`
- **Health check path:** `/healthz`

Use `Dockerfile.agent` instead of `Dockerfile.ollama` for these services. This dedicated image includes Python and the API dependencies, so it is not affected by the repository's Ollama-specific `railway.toml` configuration.

Configure the services as follows:

| Service | `APP_MODULE` | `PORT` |
| --- | --- | --- |
| `travel-flight` | `agents.flight_agent.__main__` | `8001` |

Add these variables to each specialist service:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://<ollama-private-domain>:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_EMBEDDING_MODEL=embeddinggemma
LLM_TIMEOUT_SECONDS=120
DOWNSTREAM_TIMEOUT_SECONDS=150
OPEN_TRAVEL_DATA_ENABLED=false
WEATHER_PROVIDER_ENABLED=false
PLACES_PROVIDER_ENABLED=false
GROUND_TRANSPORT_ENABLED=false
```

Replace `<ollama-private-domain>` with the Ollama service's Railway private hostname. Keep the Flight service private. The ECS services use the same Ollama variables through Terraform. After all services are healthy, set the FastAPI host's `FLIGHT_SERVICE_URL` to the Railway Flight URL and use the ECS Cloud Map outputs for `STAY_SERVICE_URL` and `ACTIVITIES_SERVICE_URL`.

### AWS ECS Stay and Activities services

The Terraform module in `infra/aws/ecs-agents` deploys the Stay and Activities services to ECS Fargate using `Dockerfile.agent`. It creates separate task definitions, ECR repositories, CloudWatch log groups, and private Cloud Map DNS names:

- `http://stay.travel.internal:8002`
- `http://activities.travel.internal:8003`

The host must run inside the same VPC, such as an AWS Lambda function configured for that VPC or an ECS service. Configure the host with the Terraform outputs:

```env
STAY_SERVICE_URL=http://stay.travel.internal:8002
ACTIVITIES_SERVICE_URL=http://activities.travel.internal:8003
```

See [`infra/aws/ecs-agents/README.md`](infra/aws/ecs-agents/README.md) for prerequisites, ECR image publishing, network rules, and deployment commands. Keep `OLLAMA_BASE_URL` pointed at the existing Railway Ollama service.

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
├── infra/aws/ecs-agents/   # Terraform for Stay and Activities on ECS
├── kubernetes/             # Kubernetes Ollama deployment
├── tests/                  # Contract and provider tests
├── Dockerfile              # Split multi-stage local API/UI image build
├── Dockerfile.ollama       # Railway Ollama service image
├── Dockerfile.agent        # Railway/ECS FastAPI agent image
├── railway.toml             # Railway Ollama deployment configuration
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
