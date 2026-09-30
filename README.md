# ADK-Powered Travel Planner

**Project Proponents:** Chaim Joseph Cordova & Psalmantha Allaine Ipong

## Overview
The **ADK-Powered Travel Planner** is a multi-agent travel-planning application. A host service coordinates specialist services for flights, stays, and activities, while a Streamlit UI provides the user-facing workflow.

Generated flights, stays, and activities are illustrative suggestions only; they are not live availability, live prices, or bookable offers.

**Documentation:** the full docs are a [Mintlify](https://mintlify.com) site in [`docs/`](docs/), organized as tutorials, how-to guides, reference, and explanation. New here? Start with the tutorial, [`docs/tutorials/first-trip-plan.mdx`](docs/tutorials/first-trip-plan.mdx). To browse the site locally, install the CLI (`npm i -g mint`), then run `mint dev` in `docs/` and open `http://localhost:3000`.

**Project status:** the [self-hosted setup](#self-hosted-setup) is the supported way to run the project. For a public URL, the agents run on [Vercel](#vercel) at no fixed cost. The [AWS and Railway deployment](#cloud-setup-aws-and-railway-dormant) is **dormant**: the AWS stack is spun down, the Railway Flight service is paused, and Grafana Cloud is unused. Its code and infrastructure stay in the repository so it can be [reactivated](#reactivating-the-cloud-deployment).

## Features
- **Multi-Agent Architecture:** Orchestrates specialized agents for different travel aspects.
- **Pluggable LLM Provider:** Ollama (Meta Llama, self-hosted) or OpenAI `gpt-4o-mini` (cloud), selected by `LLM_PROVIDER`.
- **Structured Responses:** Requests JSON-schema-constrained output from either provider and validates it against shared Pydantic contracts.
- **Open Travel Data Adapters:** Nominatim-compatible geocoding, Overpass places, and Open-Meteo weather adapters in `common/travel_data.py`. Not yet wired into any agent, so their flags currently have no effect.
- **Retrieval-Augmented Generation:** Flight, Stay, and Activities add relevant [Wikivoyage](https://en.wikivoyage.org) passages to their prompts, retrieved with LlamaIndex from a local Chroma index, and trip plans list them as sources. Optional: without an index, planning works as before.
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

|  | Self-hosted (supported) | Vercel | AWS and Railway (dormant) |
| --- | --- | --- | --- |
| **Where it runs** | Your machine: Python processes or Docker Compose | Vercel Services (all four agents), Streamlit Community Cloud (UI) | AWS ECS (Host, Stay, Activities), Railway (Flight), Streamlit Community Cloud (UI) |
| **LLM** | Ollama, running locally (`llama3.2:3b`) | OpenAI `gpt-4o-mini` | OpenAI `gpt-4o-mini` |
| **Guidance (RAG)** | Yes, once the index is built | No | No |
| **Needs** | Python 3.11+, Ollama or Docker Desktop, about 3 GB of disk for models and about 4 GB of free RAM | Vercel account (free Hobby plan), Node.js, OpenAI API key with credits | AWS account, AWS CLI v2, Terraform 1.6+, Docker Desktop, Railway account, OpenAI API key with credits |
| **Cost** | Free | Free while idle; about $0.001 per trip plan in OpenAI usage | About $50/month while running, a few cents when spun down; plus OpenAI usage and Railway's plan |
| **Use it for** | Development, testing, offline demos | A public HTTPS URL others can use | Kept for reference; see below |

All setups share the same code; only configuration differs. You can also mix them, for example running the UI locally against the cloud backend by setting `HOST_SERVICE_URL`.

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

Install [Ollama](https://ollama.com), then pull the model and start it:

```bash
ollama pull llama3.2:3b
ollama serve
```

In another terminal, start all four agents and the UI together:

```bash
python run.py
```

Or start each service in its own terminal:

```bash
uvicorn agents.host_agent.__main__:app --port 8000 --env-file .env
uvicorn agents.flight_agent.__main__:app --port 8001 --env-file .env
uvicorn agents.stay_agent.__main__:app --port 8002 --env-file .env
uvicorn agents.activities_agent.__main__:app --port 8003 --env-file .env
streamlit run travel_ui.py
```

Only `run.py` loads `.env` by itself, so keep `--env-file .env` on each `uvicorn` command or your settings are ignored. `streamlit run` has no such option: if you set `HOST_API_KEY`, also set it in the UI's terminal.

The UI is available at `http://localhost:8501`.

### 2 (alternative). Run with Docker Compose

Compose runs Ollama, the four agents, and the UI in containers. You don't need to install Ollama yourself.

```bash
docker compose --profile ollama up --build
docker compose --profile ollama exec ollama ollama pull llama3.2:3b
```

The UI is available at `http://localhost:8501`. The agents reach Ollama at `http://ollama:11434` on an internal network; Ollama has no published port, and its models persist in the `ollama-data` volume. Compose builds the root `Dockerfile` twice: `api-runtime` for the agents and `ui-runtime` for the UI.

To also start the optional PostgreSQL and Redis services, set `POSTGRES_PASSWORD` in `.env` and add `--profile data`.

### If trip plans come back "temporarily unavailable"

The Host calls Flight, Stay, and Activities at the same time, and all three share one Ollama. On a CPU-only machine Ollama works through them largely one at a time, so each agent can take longer than the defaults allow even though a single agent answers in seconds. Symptoms: the UI shows "Service is temporarily unavailable" for some or all agents after about 30 seconds, while each agent's own `/run` works when called alone.

Raise the timeouts in `.env` (both `run.py` and Docker Compose read it):

```env
LLM_TIMEOUT_SECONDS=150
DOWNSTREAM_TIMEOUT_SECONDS=170
```

`LLM_TIMEOUT_SECONDS` is how long an agent waits for Ollama; `DOWNSTREAM_TIMEOUT_SECONDS` is how long the Host waits for each agent, so keep it a little higher. Keep both under 180 seconds, which is how long the UI waits for a plan. Restart the services afterwards (for Compose, `docker compose --profile ollama up -d`). If plans still time out, a smaller model (`OLLAMA_MODEL`) or a GPU is the real fix.

### Add travel guidance (RAG)

Build the Wikivoyage guidance index once, so trip plans for the 20 destinations in `data/rag/destinations.txt` use real travel-guide passages and list their sources:

```bash
# Docker Compose
docker compose --profile ollama exec ollama ollama pull embeddinggemma
docker compose --profile ollama --profile ingest run --rm ingest
docker compose --profile ollama restart flight stay activities

# Without Docker (Ollama running, virtual environment active)
ollama pull embeddinggemma
python -m common.rag.ingest
```

Restart the agents after every build. Other destinations still get plans, without sources. See [`docs/how-to/build-the-guidance-index.mdx`](docs/how-to/build-the-guidance-index.mdx) for adding destinations, aliases, and switching embedding models. Wikivoyage text is CC BY-SA 4.0; the index and downloaded articles stay local and are gitignored.

### Using OpenAI instead of Ollama locally

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` in `.env`. Ollama is then not needed.

### Running Ollama on a separate server

If your machine can't run the model, host Ollama elsewhere and point `OLLAMA_BASE_URL` at it. Every option needs about 3 GB of persistent disk mounted at `/root/.ollama` and about 4 GB of memory; small or trial plans can't fit this. After the server starts, run `ollama pull llama3.2:3b` in its shell. Keep Ollama private: it has no authentication.

- **Render:** Docker runtime, Dockerfile path `./infra/ollama/Dockerfile`, Docker context `.`, port `11434`, persistent disk at `/root/.ollama`. Use the service's private Render URL as `OLLAMA_BASE_URL`.
- **Railway:** Dockerfile path `infra/ollama/Dockerfile`, start command `ollama serve`, health check `/api/tags`, port `11434`. Attach a volume at `/root/.ollama` **before** pulling models; without it, the pull fails with `no space left on device` and models are lost on every redeploy.
- **Kubernetes:** `infra/kubernetes/ollama.yaml` defines persistent storage, a GPU-targeted deployment, a private `ClusterIP` service, probes, a NetworkPolicy, and a model preload job. It creates no Ingress. Apply it to a cluster with a node labeled `workload=gpu`:

  ```bash
  kubectl apply -f infra/kubernetes/ollama.yaml
  kubectl -n travel-planner wait --for=condition=available deployment/ollama --timeout=10m
  ```

## Vercel

The four agents run on [Vercel](https://vercel.com) as Vercel Services defined in [`vercel.json`](vercel.json): only the Host is public, and it reaches Flight, Stay, and Activities over private service bindings. The Streamlit UI stays on Streamlit Community Cloud, because Vercel can't run Streamlit's always-on server. Vercel uses OpenAI, with guidance retrieval off, and each service installs only [`requirements/api-core.txt`](requirements/api-core.txt).

Setup, in short (full steps in [`docs/how-to/deploy-to-vercel.mdx`](docs/how-to/deploy-to-vercel.mdx)):

1. `npm i -g vercel`, `vercel login`, then `vercel link --yes --project travel-planner` from the repository root. This also connects the project to GitHub, so pushes to `main` deploy.
2. Set `LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o-mini`, `LLM_TIMEOUT_SECONDS=120`, `DOWNSTREAM_TIMEOUT_SECONDS=150`, and `RAG_ENABLED=false` with `vercel env add`.
3. Add the secrets `OPENAI_API_KEY` and `HOST_API_KEY` **together**: without `HOST_API_KEY` the Host accepts anyone's requests on your OpenAI credits.
4. Set the Streamlit Cloud secrets `HOST_SERVICE_URL` (the project's production `vercel.app` domain) and `HOST_API_KEY`.

## Cloud setup (AWS and Railway, dormant)

> **Dormant.** Nothing below is currently running. The AWS ECS stack is spun down; the foundation (VPC, ECR images, SSM parameters, GitHub OIDC role) is kept and costs a few cents a month. The Railway Flight service is paused, and Grafana Cloud receives no data. See [Reactivating the cloud deployment](#reactivating-the-cloud-deployment).

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

1. **Store the two keys in SSM.** ECS reads them at task start; they never enter Terraform state. The OpenAI key goes only to Stay and Activities. The Host API key is what clients must send as `X-API-Key`; generate a long random value. On Git Bash for Windows, prefix each command with `MSYS_NO_PATHCONV=1`, or the parameter name is rewritten into a Windows path.

   ```bash
   aws ssm put-parameter --region us-east-1 --name /travel/openai-api-key --type SecureString --value "sk-..."
   aws ssm put-parameter --region us-east-1 --name /travel/host-api-key --type SecureString --value "$(openssl rand -hex 32)"
   ```

2. **Apply the foundation.** In `infra/aws/foundation`, copy `terraform.tfvars.example` to `terraform.tfvars`, then run `terraform init` and `terraform apply -var-file=terraform.tfvars`. If your AWS account already has a GitHub Actions OIDC provider, set `create_github_oidc_provider = false` first.

3. **Push the agent image.** [GitHub Actions](#continuous-integration) builds the root `Dockerfile` and pushes it to the `host`, `stay`, and `activities` ECR repositories on every push to `main`, tagged with the short commit SHA. To push by hand instead, see [Deploy](infra/aws/ecs-agents/README.md#deploy).

4. **Deploy the Flight agent on Railway.** See [Railway Flight agent](#railway-flight-agent) below, and note its HTTPS URL.

5. **Apply the ECS module.** In `infra/aws/ecs-agents`, copy `terraform.tfvars.example` to `terraform.tfvars` and fill in the foundation outputs, the image tag, and the Flight URL (`flight_service_url`). Then plan and apply as in its [README](infra/aws/ecs-agents/README.md#deploy). The public API URL is the `host_public_url` output.

6. **Deploy the UI on Streamlit Community Cloud.** Create an app from this GitHub repository with main file `travel_ui.py` and Python 3.11. Streamlit Cloud installs the root `requirements.txt`, which contains only the UI dependencies. In the app's secrets, set:

   ```toml
   HOST_SERVICE_URL = "<value of the host_public_url output, e.g. http://travel-host-123.us-east-1.elb.amazonaws.com>"
   HOST_API_KEY = "<the value stored in /travel/host-api-key>"
   ```

   Any other client must send the key too, for example `curl -H "X-API-Key: <key>" -H "Content-Type: application/json" -d @trip.json <host_public_url>/run`. Requests without it get `401`.

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
- **Deploying code changes:** push to `main`. Railway redeploys Flight itself; GitHub Actions pushes a new AWS image tagged with the short commit SHA (shown in the run summary). Set that as `image_tag` and apply the ECS module to deploy it.

### Public API security

The Host is the only public entry point. It is protected by:

- **An API key.** `POST /run` requires `X-API-Key` to match `/travel/host-api-key`. Health checks stay open so the load balancer can reach them. To rotate the key, update the parameter and run `aws ecs update-service --cluster travel-agents --service travel-host --force-new-deployment --region us-east-1`, then update the Streamlit secret.
- **AWS WAF on the load balancer.** AWS's common-exploit and known-bad-input rule sets, plus a per-IP rate limit (`waf_rate_limit_per_5_minutes`, default 2,000). It is created and destroyed with the ECS module and costs roughly $8/month while it exists.
- **Access logs** for every request, kept in S3 for 30 days (`alb_logs_bucket` foundation output).
- **Security groups** that block all direct inbound traffic to the tasks.

**Not yet: HTTPS.** Traffic to the load balancer is plain HTTP, so the API key travels unencrypted. HTTPS needs a domain name, because AWS certificates can't be issued for the load balancer's own `elb.amazonaws.com` address. Once you have a domain, the path is: a Route53 hosted zone, a DNS-validated ACM certificate, an HTTPS listener on port 443 with port 80 redirecting to it, and `HOST_SERVICE_URL` updated to `https://`.

### Observability (Grafana Cloud)

Each agent can push metrics to Grafana Cloud over OpenTelemetry (OTLP). It's off unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so self-hosted runs need no Grafana account. Metrics are pushed rather than scraped because the ECS tasks scale to zero every night, leaving nothing for a scraper to reach.

What's exported, per agent (`travel-host`, `travel-stay`, `travel-activities`, `travel-flight`):

- **HTTP requests:** count, latency, and status code per route, from FastAPI instrumentation.
- **LLM calls:** `llm.request.duration` by provider, model, and outcome (`success`/`error`).
- **Tokens:** `llm.token.usage` by provider, model, and type (`prompt`/`completion`). For OpenAI this is what you're billed for.

Setup:

1. In the Grafana Cloud portal, open your stack's **OpenTelemetry** tile → **Configure**, and generate a token. Copy the two values it shows: `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS`.
2. Store the headers value in SSM (it contains the token):

   ```bash
   MSYS_NO_PATHCONV=1 aws ssm put-parameter --region us-east-1 --name /travel/otel-otlp-headers --type SecureString --value "Authorization=Basic%20..."
   ```

3. In `infra/aws/ecs-agents/terraform.tfvars`, set `otel_exporter_otlp_endpoint` to the endpoint and `otel_headers_parameter_arn` to the foundation output of the same name. Applies on the next spin up.
4. For Railway Flight, add `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_EXPORTER_OTLP_HEADERS` as service variables.

A ready-made dashboard is in [`infra/grafana/travel-planner-dashboard.json`](infra/grafana/travel-planner-dashboard.json): trip plans served, rejected requests, estimated OpenAI cost, LLM error rate, request and LLM latency (p95), LLM calls by outcome, and tokens used. Import it with **Dashboards → New → Import → Upload dashboard JSON file**, and pick your stack's Prometheus data source (named like `grafanacloud-<stack>-prom`).

In Grafana, OTLP metric names become Prometheus-style: dots turn into underscores and a unit suffix is added, and the service appears as `job="travel-planner/travel-stay"`. Starting queries (confirm exact names in **Explore**):

```promql
sum by (job) (rate(http_server_duration_milliseconds_count[5m]))
histogram_quantile(0.95, sum by (le, llm_provider) (rate(llm_request_duration_seconds_bucket[5m])))
sum by (token_type) (increase(llm_token_usage_total[1h]))
```

### Reactivating the cloud deployment

1. **AWS:** spin the ECS module up with the [spin up](infra/aws/ecs-agents/README.md#spin-down--spin-up) commands, setting `image_tag` to an image already in ECR (the last tag CI pushed before the spin down). It takes about 10 minutes, gets a new `host_public_url`, and recreates the `AWS_ROLE_ARN` variable so CI resumes pushing images. To deploy code committed while dormant, push to `main` afterwards and apply again with the new tag.
2. **Railway:** resume the Flight service in the Railway dashboard. If it's still on a trial plan, check the remaining credit first.
3. **Streamlit Cloud:** set `HOST_SERVICE_URL` to the new `host_public_url`, and `HOST_API_KEY` to the value in `/travel/host-api-key`.
4. **Grafana Cloud:** nothing to change. Metrics start arriving as soon as traffic does, as long as the stack still exists. If the trial has ended, confirm the free tier is active, and if the token was deleted, generate a new one and update `/travel/otel-otlp-headers` and the Railway variable.
5. **Check it:** a `POST /run` without `X-API-Key` should return `401`, and with it a trip plan.

While dormant, GitHub Actions skips the image push: the ECS module deletes the `AWS_ROLE_ARN` repository variable on spin down and recreates it on spin up. Spinning up and down therefore needs a GitHub token in `GITHUB_TOKEN`; see [Spin down / spin up](infra/aws/ecs-agents/README.md#spin-down--spin-up) for the one-time token setup.

## Configuration

Configuration is loaded from environment variables (`.env` when self-hosted; Terraform, the Railway dashboard, and Streamlit secrets in the cloud).

| Variable | Self-hosted | Cloud | Purpose |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | `ollama` (default) | `openai` | Which LLM backend the agents call. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` (Compose: `http://ollama:11434`) | Not used | Ollama server URL. |
| `OLLAMA_MODEL` | `llama3.2:3b` | Not used | Ollama generation model. |
| `OLLAMA_EMBEDDING_MODEL` | `embeddinggemma` | Not used | Embeds guidance passages when `LLM_PROVIDER=ollama`. |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Same | Embeds guidance passages when `LLM_PROVIDER=openai`. |
| `RAG_ENABLED` | `true` | `true` | Add Wikivoyage guidance to prompts. Harmless with no index built. |
| `RAG_TOP_K` | `2` | `2` | Passages per agent. More passages make CPU-only Ollama slower. |
| `RAG_INDEX_DIR` | `data/rag/index` | Same | Where the Chroma index lives. |
| `OPENAI_MODEL` | `gpt-4o-mini` (default) | `gpt-4o-mini` | OpenAI model. |
| `OPENAI_API_KEY` | Only if using OpenAI | From SSM on AWS; a Railway variable for Flight | OpenAI API key. Never commit it. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Same | OpenAI-compatible API endpoint. |
| `LLM_TIMEOUT_SECONDS` | `90` | `120` | Timeout for a single LLM call. |
| `FLIGHT_SERVICE_URL`, `STAY_SERVICE_URL`, `ACTIVITIES_SERVICE_URL` | `http://localhost:8001`-`8003` | Railway URL; `http://stay.travel.internal:8002`, `http://activities.travel.internal:8003` (set by Terraform) | Specialist agent URLs used by the Host. |
| `DOWNSTREAM_TIMEOUT_SECONDS` | `30` | `150` | How long the Host waits for each specialist agent. |
| `HOST_SERVICE_URL` | `http://localhost:8000` | The `host_public_url` output | Where the UI sends requests. |
| `HOST_API_KEY` | Unset (Host is open) | From SSM on AWS; a Streamlit secret for the UI | Key the Host requires as `X-API-Key` on `POST /run`, and that the UI sends. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Unset (metrics off) | Grafana Cloud OTLP endpoint | Where agents push metrics. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Unset | From SSM on AWS; a Railway variable for Flight | Grafana Cloud auth header. Contains a token; never commit it. |
| `OPEN_TRAVEL_DATA_ENABLED`, `WEATHER_PROVIDER_ENABLED`, `PLACES_PROVIDER_ENABLED`, `GROUND_TRANSPORT_ENABLED` | `false` | `false` | Rollout flags for the open travel-data providers. No agent reads them yet. |

Do not commit `.env` or API keys. Use `.env.example` as the starting template.

## Testing

```bash
python -m pytest -q
python -m ruff check .
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and pull request to `main`:

- **`test`:** the same `pytest` and `ruff` commands as above.
- **`build-and-push`** (pushes to `main` only, after tests pass): builds the agent image and pushes it to the three ECR repositories, tagged with the short commit SHA. It does not deploy; spinning up and applying the ECS module stays manual.

It signs in to AWS through GitHub's OIDC provider, so no AWS keys are stored in GitHub. The job needs the `AWS_ROLE_ARN` repository variable (the foundation's `github_actions_role_arn` output). The ECS module creates it on spin up and deletes it on spin down, so images are only pushed while the cloud stack is running; with the stack down, `build-and-push` shows as skipped. Only pushes to `main` of this repository can assume that role, and it can only push to the three ECR repositories.

## Project Structure

```text
IS_Final/
├── .github/workflows/      # CI: tests and lint, then ECR image push on main
├── docs/                   # Mintlify documentation site
├── agents/                 # Agent implementations
│   ├── activities_agent/
│   ├── flight_agent/
│   ├── host_agent/
│   └── stay_agent/
├── common/                 # LLM, RAG (common/rag/), provider, and communication utilities
├── data/rag/               # destinations.txt for the guidance index (index and cache are gitignored)
├── shared/                 # Shared config and data schemas
├── tests/                  # Contract and provider tests
├── infra/
│   ├── aws/foundation/     # Cloud: Terraform for VPC, subnets, security groups, IAM, ECR
│   ├── aws/ecs-agents/     # Cloud: Terraform for Host, Stay, Activities on ECS + ALB
│   ├── grafana/            # Cloud: importable Grafana dashboard
│   ├── ollama/Dockerfile   # Self-hosted: Ollama image for a separate server
│   └── kubernetes/         # Self-hosted: Kubernetes Ollama deployment
├── requirements/
│   ├── api-core.txt        # FastAPI agent runtime without retrieval (Vercel)
│   ├── api.txt             # api-core.txt plus the retrieval packages
│   ├── ui.txt              # Streamlit runtime
│   └── dev.txt             # api + ui + test and lint tools
├── requirements.txt        # Streamlit Cloud entry point (-r requirements/ui.txt)
├── Dockerfile              # api-runtime (default) and ui-runtime targets; used by Compose, ECS, Railway
├── compose.yaml            # Self-hosted containerized stack
├── vercel.json             # Vercel Services: four agents, only the Host public
├── run.py                  # Self-hosted: starts all agents and the UI without Docker
├── travel_ui.py            # Streamlit frontend
├── .env.example            # Environment template (copy to .env, which is not committed)
├── pyproject.toml          # pytest and ruff configuration
└── README.md
```
