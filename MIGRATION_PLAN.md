# AWS, Kubernetes, Live APIs, and RAG Migration Plan

## Outcome

Move the travel planner from a local, four-process demo into a secure, observable AWS workload.  The application will return provider-backed flight, hotel, and activity information, while RAG supplies only cited travel guidance and policy context.  The LLM must not invent prices, availability, or booking facts.

## Current-state assessment

- The Streamlit client calls the host at `http://localhost:8000/run`.
- The host calls the three specialist agents at fixed localhost ports, sequentially.
- Agent sessions are in memory and use fixed user/session IDs; a replica can therefore lose context or mix users.
- Results have inconsistent shapes (`flights`, `stays`, and `activities`) and are sometimes unstructured LLM text.
- There is no dependency lock file, container definition, health endpoint, authentication, persistence, test suite, or deployment configuration.

These are application changes to complete before production scaling; Kubernetes alone cannot fix them.

## Target architecture

```text
Browser
  -> CloudFront + WAF
  -> Application Load Balancer / Ingress
  -> Streamlit UI (EKS)
  -> Host API (EKS)
       -> Flight adapter -> Amadeus Flight Offers API
       -> Stay adapter   -> Amadeus Hotel APIs
       -> Activity adapter -> Google Places API + optional events provider
       -> RAG service -> Amazon RDS PostgreSQL (pgvector)
       -> LLM provider

EKS pods -> AWS Secrets Manager (IRSA) | CloudWatch / X-Ray / OpenTelemetry
CI/CD -> Amazon ECR -> EKS (Helm)      | RDS, S3, and VPC private subnets
```

Use EKS for the user-facing UI, host API, and specialist services. Put the ALB in public subnets and every pod and database in private subnets. Keep the database non-public. Amazon EKS removes the need to operate the Kubernetes control plane directly, and ECR is the managed image registry that fits the deployment flow. [Amazon EKS documentation](https://docs.aws.amazon.com/eks/) [AWS container decision guide](https://docs.aws.amazon.com/pdfs/decision-guides/latest/containers-on-aws-how-to-choose/containers-on-aws-how-to-choose.pdf?did=wp_card&trk=wp)

## Architecture decisions

| Area | Recommendation | Reason |
| --- | --- | --- |
| Runtime | EKS managed node groups; one deployment per service | Keeps the current agent separation and enables independent scaling. |
| Database | RDS PostgreSQL, Multi-AZ in production; enable `pgvector` | Stores users, trips, feedback, API cache, RAG documents, and embeddings. RDS PostgreSQL supports `pgvector`. [AWS reference](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html) |
| Session and cache | ElastiCache for Redis | Replaces process memory for request/session state, rate limits, and short-lived provider-result caching. |
| Documents | Versioned S3 bucket | Original guides and curated knowledge source for ingestion. |
| Secrets | Secrets Manager + EKS Pod Identity or IRSA; never Kubernetes manifests or images | Allows narrowly scoped pod access and secret rotation. AWS supports mounting Secrets Manager values into EKS pods through the Secrets Store CSI driver. [AWS guide](https://docs.aws.amazon.com/eks/latest/userguide/integration-secrets-manager.html) |
| Infrastructure | Terraform, with separate dev/staging/prod state and AWS accounts | Auditable, repeatable environments. |
| Delivery | GitHub Actions -> ECR -> Helm deploy; image digest promotion between environments | Reproducible rollbacks and no mutable production tags. |
| Observability | OpenTelemetry traces/metrics/logs, CloudWatch, alarms, and request correlation IDs | Enables debugging agent, LLM, API-provider, and RAG latency separately. |

## Phase 0 — prepare the application (Week 1)

1. Create a locked dependency file (`pyproject.toml` + lockfile or pinned `requirements.txt`) and add `pytest`, Ruff, type checking, and dependency/security scanning.
2. Replace raw dictionaries with versioned Pydantic request/response models. Include `origin`, traveller count, currency, preferences, request ID, and structured `FlightOffer`, `StayOffer`, `Activity`, `Source`, and `TripPlan` outputs.
3. Replace all `localhost` values with configuration such as `FLIGHT_SERVICE_URL`; use Kubernetes DNS names in cluster.
4. Generate an opaque `trip_id` and per-user session ID per request. Do not use the existing fixed ADK `USER_ID` / `SESSION_ID`; persist minimal session metadata in Redis/PostgreSQL.
5. Add `/healthz` (process) and `/readyz` (dependencies) endpoints, input validation, structured logs, timeouts, bounded retries with jitter, and error responses that preserve partial results.
6. Run the three downstream calls concurrently with a deadline, then clearly label unavailable sections rather than returning invented alternatives.
7. Correct the UI/API contract: the host returns `stay`, while the UI currently reads `accommodation`.

**Exit gate:** the app runs locally without `run.py`; each service starts independently, returns a validated JSON contract, and has unit/integration tests using mocked providers.

## Phase 1 — containerize and test locally (Week 2)

1. Build one production Dockerfile per runnable service (or a parameterized common image) using a slim, pinned Python base image and a non-root user.
2. Add a `docker-compose.yml` for local UI, host, three agent services, Postgres/pgvector, and Redis. It is a developer environment only; do not place live credentials in it.
3. Add `.dockerignore`, immutable image labels, image scanning, and graceful SIGTERM handling.
4. Make configuration twelve-factor: configuration from environment, secrets injected only at runtime, no `.env` committed.
5. Add contract tests between host and specialist services and a browser-to-host smoke test.

**Exit gate:** `docker compose up` produces a complete trip plan, service restart does not corrupt other users' sessions, and test/scan jobs pass in CI.

## Phase 2 — provision AWS and Kubernetes (Weeks 3–4)

1. Provision separate development, staging, and production environments. At minimum, use separate AWS accounts for production and non-production.
2. Terraform a three-AZ VPC: public ALB subnets, private EKS node/pod subnets, isolated RDS subnets, NAT egress, VPC endpoints where justified, and restrictive security groups.
3. Create ECR repositories, EKS, managed node groups, the AWS Load Balancer Controller, metrics-server, ExternalDNS if a managed domain is approved, and cert-manager/ACM TLS.
4. Create RDS PostgreSQL, Redis, a versioned/encrypted S3 document bucket, KMS keys, Secrets Manager secrets, CloudWatch log groups, dashboards, and alarms.
5. Apply Kubernetes namespaces (`travel-dev`, `travel-staging`, `travel-prod`), resource requests/limits, PodDisruptionBudgets, NetworkPolicies, HorizontalPodAutoscalers, and Pod Identity/IRSA least-privilege roles.
6. Deploy with Helm: `ui`, `host`, `flight-service`, `stay-service`, `activity-service`, plus migrations as a controlled job. Ingress exposes only UI and host routes; specialist services remain ClusterIP-only.

**Exit gate:** staging is reachable over HTTPS, pod-to-pod service discovery works, RDS/Redis are private, and a pod can read only its required secret.

## Phase 3 — real-world travel data (Weeks 4–5)

Implement provider adapters behind interfaces, so individual providers can change without rewriting agent prompts.

| Domain | Primary integration | Agent responsibility | Guardrails |
| --- | --- | --- | --- |
| Flights | Amadeus Flight Offers Search, then Flight Offers Price before presenting a final selectable offer | Normalise itinerary, fare, currency, rules, and provider deep link | Cache briefly; show provider timestamp and currency; never claim booking has occurred. |
| Accommodation | Amadeus Hotel List + Hotel Search/Offers | Resolve city/geocode, retrieve availability and price | Treat availability as volatile; use provider-supported images/attribution only. |
| Activities | Google Places API (New) Text/Nearby Search; add a licensed local-events provider only if required | Find POIs, hours, ratings, location, and maps link | Request the smallest permitted field mask and display required attribution. [Google Text Search documentation](https://developers.google.com/maps/documentation/places/web-service/text-search) |
| Context | Weather, visa/advisory, and transport APIs selected by market and legal review | Enrich itinerary, never replace the authoritative provider response | Keep date/source/provenance; state data limitations. |

Amadeus Self-Service APIs cover flights, hotels, destination experiences and other travel domains; its hotel APIs include search and booking capabilities. [Amadeus API guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/) [Amadeus hotel guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/hotels/)

Store an internal normalized offer with `provider`, `provider_offer_id`, `retrieved_at`, `expires_at`, currency, deep link, raw-payload checksum, and source URL. Store only the minimum raw provider response allowed by the provider’s terms. Provider calls need per-provider quotas, circuit breakers, backoff, and a stale-result indicator. Begin with **search and redirect**, not bookings; booking introduces payment, fraud, refunds, PCI, and supplier-contract scope.

**Exit gate:** integration tests run against provider sandboxes or recorded fixtures, live results are visibly attributed/time-stamped, error and quota behavior are safe, and no synthetic LLM price is rendered as a live price.

## Phase 4 — RAG, deliberately scoped (Weeks 5–6)

RAG is appropriate for stable or editorial context, not live inventory. Initial corpus:

- vetted destination guides and internal travel policies;
- airline baggage/change guidance where licensed and date-versioned;
- curated accessibility, safety, and destination FAQs;
- provider terms/operational notes for internal agent use only.

Do **not** put live flight/hotel availability, prices, booking terms, visa/legal advice, or unrestricted web pages into the RAG corpus. Those must come from authoritative current APIs or a controlled human-reviewed process.

1. Establish document ownership, permitted sources, licensing, review cadence, expiration, deletion process, and a redaction rule that excludes personal data.
2. Build an ingestion job: S3 upload -> malware/type validation -> text extraction -> semantic chunking -> embeddings -> pgvector rows. Attach metadata: `source_url`, publisher, locale, destination, topic, effective date, expiry, document version, and access classification.
3. At request time, retrieve top candidates with metadata filters (destination, locale, active date, user access), apply a score threshold, and pass only relevant excerpts to the host/LLM.
4. Require an answer citation for every RAG-derived factual claim. If retrieval is weak, say so; do not answer from RAG memory.
5. Add prompt-injection defenses: treat document text as untrusted data, never allow it to override system instructions, and strip/reject embedded tool directives.
6. Evaluate with a labelled question set: retrieval recall@k, citation correctness, groundedness, answer helpfulness, latency, and refusal behavior. Establish a release threshold before enabling it for users.

RDS/pgvector is the recommended first implementation because the planner already needs relational trip data and a modest controlled corpus. Re-evaluate Amazon Bedrock Knowledge Bases or a managed vector provider only when corpus size, multi-modal needs, or operations justify it. OpenAI vector stores are an alternative managed retrieval path and expose query search with metadata filters. [OpenAI vector-store reference](https://platform.openai.com/docs/api-reference/vector-stores?lang=python)

**Exit gate:** every RAG answer shows document citations, expired documents cannot be retrieved, prompt-injection tests pass, and benchmark results meet the agreed release threshold.

## Phase 5 — security, operations, and production launch (Weeks 6–7)

1. Add authentication (Cognito or existing enterprise OIDC) before storing user trips. Authorize access by user and trip; log administrative actions.
2. Encrypt data in transit and at rest (ACM TLS, KMS), minimize PII, define retention/deletion, and run a privacy/legal review for operating regions and providers.
3. Set WAF rules, API rate limits, CORS policy, dependency/image scans, signed or provenance-attested images, and regular secret rotation.
4. Create dashboards and alerts for availability, p95/p99 latency, error rate, provider quota/latency, cache hit rate, LLM token/cost, RAG no-answer rate, and retrieval/citation quality.
5. Create backups, RDS point-in-time recovery, restore drills, an incident runbook, and a documented rollback. Use canary or blue/green deployment in production.
6. Load test the host fan-out, chaos-test one unavailable provider, test an expired secret, and rehearse a database restore before launch.

## Deployment sequence and rollback

1. Deploy the refactored mock-provider application to development EKS.
2. Promote the same immutable image digest to staging and run smoke, contract, load, security, and RAG evaluation suites.
3. Enable live providers in staging with strict usage caps; validate attribution, pricing timestamp, and failure handling.
4. Launch production with a small user cohort and feature flags: `live_flights`, `live_stays`, `live_activities`, and `rag_context` are independently reversible.
5. Roll back by disabling the affected flag, then reverting the Helm release to the last image digest. Never roll back a database schema destructively; use expand/migrate/contract schema changes.

## Decisions needed before implementation

1. Which AWS region(s), expected monthly requests, availability target, and budget limit apply?
2. Is the first release search-and-redirect only, or is booking/payment genuinely in scope?
3. Which countries and user data categories will be supported, and is user authentication required in the first release?
4. What curated documents are licensed and approved for the RAG corpus, and who owns review/expiry?
5. Should the project remain a multi-service agent demo, or is a single host API with provider modules acceptable for the first production release? For this traffic level, the latter is simpler, though the plan supports either.

