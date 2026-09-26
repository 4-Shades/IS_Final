# ADK-Powered Travel Planner

**Project Proponents:** Chaim Joseph Cordova & Psalmantha Allaine Ipong

## Overview
The **ADK-Powered Travel Planner** is a multi-agent travel-planning application. A host service coordinates specialist services for flights, stays, and activities, while a Streamlit UI provides the user-facing workflow.

Generated flights, stays, and activities are illustrative suggestions only; they are not live availability, live prices, or bookable offers.

## Features
- **Multi-Agent Architecture:** Orchestrates specialized agents for different travel aspects.
- **Pluggable LLM Provider:** Ollama (Meta Llama, self-hosted) or OpenAI `gpt-4o-mini` (cloud), selected by `LLM_PROVIDER`.
- **Structured Responses:** Requests JSON-schema-constrained output from either provider and validates it against shared Pydantic contracts.
- **Open Travel Data Adapters:** Provides Nominatim-compatible geocoding, Overpass places, and Open-Meteo weather adapters.
- **Retrieval Context:** Supports curated, licensed guidance with source citations.
- **Containerized Runtime:** One Dockerfile with separate API and UI images, so each installs only the dependencies it needs.
- **Interactive UI:** User-friendly web interface built with Streamlit.
- **Microservices:** Each agent runs as an independent service.

## System Components
1.  **Host Agent:** The central orchestrator. It calls the other agents and does not use an LLM itself.
2.  **Flight Agent:** Suggests flight options.
3.  **Stay Agent:** Suggests accommodation options.
4.  **Activities Agent:** Recommends local activities.
5.  **Travel Data Providers:** Shared adapters for geocoding, places, and weather context.
6.  **RAG Layer:** Filters curated documents by destination, language, access policy, and validity dates.
7.  **Frontend:** Streamlit application for user interaction.

## Choose a setup

|  | Self-hosted | Cloud |
| --- | --- | --- |
| **Where it runs** | Your machine: Python processes or Docker Compose | AWS ECS (Host, Stay, Activities), Railway (Flight), Streamlit Community Cloud (UI) |
| **LLM** | Ollama, running locally (`llama3.2:3b`) | OpenAI `gpt-4o-mini` |
| **`LLM_PROVIDER`** | `ollama` (the default) | `openai` |
| **Needs** | Python 3.11+, Ollama or Docker Desktop, about 3 GB of disk for models and about 4 GB of free RAM | AWS account, AWS CLI v2, Terraform 1.6+, Docker Desktop, Railway account, OpenAI API key with credits |
| **Cost** | Free | About $41/month for AWS while running (a few cents when spun down), plus about $0.001 per trip plan in OpenAI usage and Railway's plan |
| **Use it for** | Development, testing, offline demos | A public URL others can use |

The two setups share the same code and Docker image; only configuration differs. You can also mix them, for example running the UI locally against the cloud backend by setting `HOST_SERVICE_URL`.

## Self-hosted setup

### 1. Install

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements/dev.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

`requirements/dev.txt` includes the API and UI runtimes (`requirements/api.txt`, `requirements/ui.txt`) plus the test and lint tools. The defaults in `.env` already target a local Ollama at `http://localhost:11434`.

### 2. Run with Python

Install [Ollama](https://ollama.com), then pull the models and start it:

```bash
ollama pull llama3.2:3b
ollama pull embeddinggemma
ollama serve
```

In another terminal, start all four agents and the UI together:

```bash
python run.py
```

Or start each service in its own terminal:

```bash
uvicorn agents.host_agent.__main__:app --port 8000
uvicorn agents.flight_agent.__main__:app --port 8001
uvicorn agents.stay_agent.__main__:app --port 8002
uvicorn agents.activities_agent.__main__:app --port 8003
streamlit run travel_ui.py
```

The UI is available at `http://localhost:8501`.

### 2 (alternative). Run with Docker Compose

Compose runs Ollama, the four agents, and the UI in containers. You don't need to install Ollama yourself.

```bash
docker compose --profile ollama up --build
docker compose --profile ollama exec ollama ollama pull llama3.2:3b
docker compose --profile ollama exec ollama ollama pull embeddinggemma
```

The UI is available at `http://localhost:8501`. The agents reach Ollama at `http://ollama:11434` on an internal network; Ollama has no published port, and its models persist in the `ollama-data` volume. Compose builds the root `Dockerfile` twice: `api-runtime` for the agents and `ui-runtime` for the UI.

To also start the optional PostgreSQL and Redis services, set `POSTGRES_PASSWORD` in `.env` and add `--profile data`.

### Using OpenAI instead of Ollama locally

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`. Ollama is then not needed.

### Running Ollama on a separate server

If your machine can't run the model, host Ollama elsewhere and point `OLLAMA_BASE_URL` at it. Every option needs about 3 GB of persistent disk mounted at `/root/.ollama` and about 4 GB of memory; small or trial plans can't fit this. After the server starts, run `ollama pull llama3.2:3b` and `ollama pull embeddinggemma` in its shell. Keep Ollama private: it has no authentication.

- **Render:** Docker runtime, Dockerfile path `./infra/ollama/Dockerfile`, Docker context `.`, port `11434`, persistent disk at `/root/.ollama`. Use the service's private Render URL as `OLLAMA_BASE_URL`.
- **Railway:** Dockerfile path `infra/ollama/Dockerfile`, start command `ollama serve`, health check `/api/tags`, port `11434`. Attach a volume at `/root/.ollama` **before** pulling models; without it, the pull fails with `no space left on device` and models are lost on every redeploy.
- **Kubernetes:** `infra/kubernetes/ollama.yaml` defines persistent storage, a GPU-targeted deployment, a private `ClusterIP` service, probes, a NetworkPolicy, and a model preload job. It creates no Ingress. Apply it to a cluster with a node labeled `workload=gpu`:

  ```bash
  kubectl apply -f infra/kubernetes/ollama.yaml
  kubectl -n travel-planner wait --for=condition=available deployment/ollama --timeout=10m
  ```

## Cloud setup

### Architecture

| Service | Platform | LLM |
| --- | --- | --- |
| Host (public API) | AWS ECS Fargate, behind an Application Load Balancer | None |
| Stay | AWS ECS Fargate, private Cloud Map DNS | OpenAI `gpt-4o-mini` |
| Activities | AWS ECS Fargate, private Cloud Map DNS | OpenAI `gpt-4o-mini` |
| Flight | Railway (`travel-flight` project) | OpenAI `gpt-4o-mini` |
| UI | Streamlit Community Cloud | None |

Request flow: UI → ALB (port 80) → Host (8000) → Stay (8002) and Activities (8003) over Cloud Map, and Flight over its Railway HTTPS URL.

AWS uses two Terraform modules:

- [`infra/aws/foundation`](infra/aws/foundation/README.md): VPC, two public subnets, internet gateway, free S3 gateway endpoint, security groups, IAM roles, and ECR repositories. There is no NAT gateway; tasks get public IPs, and the security groups block all inbound internet traffic except to the load balancer.
- [`infra/aws/ecs-agents`](infra/aws/ecs-agents/README.md): ECS cluster and services, Application Load Balancer, Cloud Map namespace (`travel.internal`), log groups, and the start/stop schedule.

### Deploy, in order

1. **Store the OpenAI key in SSM.** ECS reads it at task start and gives it only to Stay and Activities; it never enters Terraform state. On Git Bash for Windows, prefix the command with `MSYS_NO_PATHCONV=1`, or the parameter name is rewritten into a Windows path.

   ```bash
   aws ssm put-parameter --region us-east-1 --name /travel/openai-api-key --type SecureString --value "sk-..."
   ```

2. **Apply the foundation.** In `infra/aws/foundation`, copy `terraform.tfvars.example` to `terraform.tfvars`, then run `terraform init` and `terraform apply -var-file=terraform.tfvars`.

3. **Build and push the agent image.** Build the root `Dockerfile` once (its default target is the API image) and push it to the `host`, `stay`, and `activities` ECR repositories; `APP_MODULE` selects the agent at runtime. See [Deploy](infra/aws/ecs-agents/README.md#deploy) for the commands.

4. **Deploy the Flight agent on Railway.** See [Railway Flight agent](#railway-flight-agent) below, and note its HTTPS URL.

5. **Apply the ECS module.** In `infra/aws/ecs-agents`, copy `terraform.tfvars.example` to `terraform.tfvars` and fill in the foundation outputs, the image tag, and the Flight URL (`flight_service_url`). Then plan and apply as in its [README](infra/aws/ecs-agents/README.md#deploy). The public API URL is the `host_public_url` output.

6. **Deploy the UI on Streamlit Community Cloud.** Create an app from this GitHub repository with main file `travel_ui.py` and Python 3.11. Streamlit Cloud installs the root `requirements.txt`, which contains only the UI dependencies. In the app's secrets, set:

   ```toml
   HOST_SERVICE_URL = "<value of the host_public_url output, e.g. http://travel-host-123.us-east-1.elb.amazonaws.com>"
   ```

If your AWS CLI signs in with `aws login`, run `eval "$(aws configure export-credentials --format env)"` in the same shell before each Terraform command; Terraform can't read those credentials directly.

### Railway Flight agent

The Flight agent runs on Railway from this GitHub repository and **redeploys automatically on every push to `main`**. Changes that are only committed locally never reach it; check the deployed commit with `railway status --json`.

Configure the service in the Railway dashboard. The repository has no Railway config files; a root `railway.toml` is gitignored because Railway would apply it to every service built from this repo.

- **Dockerfile path:** `Dockerfile`, set in Settings → Build. This dashboard setting overrides the `RAILWAY_DOCKERFILE_PATH` variable. The default target is the API image.
- **Start command:** `python -m common.serve`
- **Health check path:** `/healthz`

Service variables:

```env
APP_MODULE=agents.flight_agent.__main__
PORT=8001
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
LLM_TIMEOUT_SECONDS=120
OPEN_TRAVEL_DATA_ENABLED=false
WEATHER_PROVIDER_ENABLED=false
PLACES_PROVIDER_ENABLED=false
GROUND_TRANSPORT_ENABLED=false
```

### Operating the cloud setup

- **Spin down when idle.** The load balancer costs about $24/month whether or not anyone uses it, and it can't be paused. Between uses, destroy and later re-create the ECS module with the [spin down / spin up](infra/aws/ecs-agents/README.md#spin-down--spin-up) commands. Everything in `foundation`, the ECR images, and the SSM key are kept, so spinning up needs no rebuild.
- **The public URL changes on every spin up.** Update `HOST_SERVICE_URL` in the Streamlit Cloud secrets afterwards.
- **Built-in savings while running:** services only run from 08:00 to 22:00 Asia/Manila time and scale to zero overnight, which also releases their public IPs (adjust with `schedule_start_cron`, `schedule_stop_cron`, `schedule_timezone`). Tasks run on Fargate Spot, about 70% cheaper than regular Fargate.
- **Railway keeps running when AWS is spun down.** Pause the Flight service in the Railway dashboard to stop its usage too.
- **Deploying code changes:** push to `main` for Flight. For the AWS agents, build and push a new image tag, update `image_tag`, and apply the ECS module.

## Configuration

Configuration is loaded from environment variables (`.env` when self-hosted; Terraform, the Railway dashboard, and Streamlit secrets in the cloud).

| Variable | Self-hosted | Cloud | Purpose |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | `ollama` (default) | `openai` | Which LLM backend the agents call. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` (Compose: `http://ollama:11434`) | Not used | Ollama server URL. |
| `OLLAMA_MODEL` | `llama3.2:3b` | Not used | Ollama generation model. |
| `OLLAMA_EMBEDDING_MODEL` | `embeddinggemma` | Not used | Ollama embedding model. |
| `OPENAI_MODEL` | `gpt-4o-mini` (default) | `gpt-4o-mini` | OpenAI model. |
| `OPENAI_API_KEY` | Only if using OpenAI | From SSM on AWS; a Railway variable for Flight | OpenAI API key. Never commit it. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Same | OpenAI-compatible API endpoint. |
| `LLM_TIMEOUT_SECONDS` | `90` | `120` | Timeout for a single LLM call. |
| `FLIGHT_SERVICE_URL`, `STAY_SERVICE_URL`, `ACTIVITIES_SERVICE_URL` | `http://localhost:8001`-`8003` | Railway URL; `http://stay.travel.internal:8002`, `http://activities.travel.internal:8003` (set by Terraform) | Specialist agent URLs used by the Host. |
| `DOWNSTREAM_TIMEOUT_SECONDS` | `30` | `150` | How long the Host waits for each specialist agent. |
| `HOST_SERVICE_URL` | `http://localhost:8000` | The `host_public_url` output | Where the UI sends requests. |
| `OPEN_TRAVEL_DATA_ENABLED`, `WEATHER_PROVIDER_ENABLED`, `PLACES_PROVIDER_ENABLED`, `GROUND_TRANSPORT_ENABLED` | `false` | `false` | Rollout flags for the open travel-data providers. |

Do not commit `.env` or API keys. Use `.env.example` as the starting template.

## Testing

```bash
python -m pytest -q
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
├── shared/                 # Shared config and data schemas
├── tests/                  # Contract and provider tests
├── infra/
│   ├── aws/foundation/     # Cloud: Terraform for VPC, subnets, security groups, IAM, ECR
│   ├── aws/ecs-agents/     # Cloud: Terraform for Host, Stay, Activities on ECS + ALB
│   ├── ollama/Dockerfile   # Self-hosted: Ollama image for a separate server
│   └── kubernetes/         # Self-hosted: Kubernetes Ollama deployment
├── requirements/
│   ├── api.txt             # FastAPI agent runtime
│   ├── ui.txt              # Streamlit runtime
│   └── dev.txt             # api + ui + test and lint tools
├── requirements.txt        # Streamlit Cloud entry point (-r requirements/ui.txt)
├── Dockerfile              # api-runtime (default) and ui-runtime targets; used by Compose, ECS, Railway
├── compose.yaml            # Self-hosted containerized stack
├── run.py                  # Self-hosted: starts all agents and the UI without Docker
├── travel_ui.py            # Streamlit frontend
├── .env.example            # Environment template (copy to .env, which is not committed)
├── pyproject.toml          # pytest and ruff configuration
└── README.md
```
