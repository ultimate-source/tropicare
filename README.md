# 🩺 TropiCare

**AI-powered clinical decision support for tropical disease diagnosis and antibiotherapy in Togo.**

TropiCare combines a multi-agent LLM pipeline with Retrieval-Augmented Generation (RAG) to deliver evidence-based diagnostic and treatment recommendations calibrated to Togo's epidemiology — WHO guidelines, CAME formulary, and local antimicrobial resistance (AMR) data.

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [RAG Pipeline](#rag-pipeline)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Make Commands](#make-commands)
- [API Reference](#api-reference)
- [Evaluation & Benchmarks](#evaluation--benchmarks)
- [Observability](#observability)
- [Project Structure](#project-structure)
- [Testing](#testing)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 14+)                       │
│         React · Tailwind CSS · NDJSON Streaming                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Gateway (FastAPI + Uvicorn)                      │
│     JWT RS256 · RBAC · Rate Limiting · Security Headers · CSRF      │
│     OpenTelemetry · Prometheus /metrics · Circuit Breakers           │
└──────────────┬──────────────────────────────────────┬───────────────┘
               │                                      │
               ▼                                      ▼
┌──────────────────────────┐          ┌───────────────────────────────┐
│     Orchestrator         │          │     MCP Tools Server (:8001)  │
│  Intake → Diagnostic →   │◄────────►│  hybrid_retrieve              │
│  Antibiotherapy →        │          │  formulary_lookup             │
│  Validation              │          │  amr_lookup · ddi_check       │
│  (Claude Sonnet 4)       │          │  epid_calendar · safety_class │
└──────┬───────────────────┘          │  symptom_extractor            │
       │                              └───────────────────────────────┘
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16          Redis 7           MongoDB 7                  │
│  (data + BM25 FTS)      (sessions/cache)  (Atlas Vector Search)     │
└──────────────────────────────────────────────────────────────────────┘
```

The Gateway streams NDJSON events progressively to the frontend, enabling real-time rendering of differential diagnoses and treatment plans. Agents communicate with the MCP Tools Server via HTTP tool calls, keeping clinical knowledge tools decoupled from agent logic.

---

## Tech Stack

| Layer          | Technologies                                                    |
|----------------|-----------------------------------------------------------------|
| Frontend       | Next.js 14+, React, Tailwind CSS                               |
| Backend        | FastAPI, Uvicorn, Claude Sonnet 4 (Anthropic), OpenTelemetry   |
| Databases      | PostgreSQL 16, Redis 7, MongoDB 7 (Atlas Vector Search)        |
| Ingestion      | ARQ (async task queue), OpenAI text-embedding-3-large (3072-d)  |
| Observability  | Jaeger (traces), Prometheus + Grafana (metrics), structlog      |
| Infrastructure | Docker Compose, Alembic (migrations)                            |
| Testing        | pytest, Hypothesis (property-based), Jest/React Testing Library |

---

## Features

- **Differential diagnosis** with confidence scores and ICD-11 codes
- **Antibiotherapy recommendations** adapted to Togo (CAME formulary, local AMR data)
- **Emergency detection**: meningitis, severe malaria, viral hemorrhagic fever, septic shock
- **Drug interaction checking** (DDI) and pregnancy/lactation safety
- **Structured citations** — every clinical assertion is sourced
- **Real-time streaming** — results render progressively via NDJSON
- **Seasonal epidemiological context** per region via `epid_calendar` tool
- **Administrable knowledge base** — upload PDF/DOCX with automatic ingestion
- **Admin analytics dashboard**
- **Immutable audit log** for regulatory compliance
- **Security hardening** — CSRF, rate limiting, security headers, PII hashing in audit logs

---

## Multi-Agent Pipeline

Four specialized agents execute sequentially for each clinical query:

### 1. Intake Agent
Extracts structured patient context from free text: age, sex, weight, region, symptoms, vital signs, lab results, allergies, current medications, pregnancy status. Uses the MCP `symptom_extractor` tool for entity recognition.

### 2. Diagnostic Agent (ReAct)
Performs iterative reasoning (up to 4 Think → Observe → Act cycles) with hybrid retrieval across 3 simultaneous queries. Produces a ranked differential diagnosis with: rank, disease name, ICD-11 code, confidence, supporting evidence, confirmatory tests, red flags. Emits emergency alerts when critical conditions are detected.

### 3. Antibiotherapy Agent
Parallel MCP tool calls: `formulary_lookup`, `amr_lookup`, `drug_ddi_check`, `safety_classifier`. Filters candidates by: CAME availability, AMR resistance < 30%, absence of contraindications, pregnancy safety. Produces treatment lines (1st line, 2nd line, alternatives) with dosage, route, frequency, duration, and monitoring.

### 4. Validation Agent
Deterministic quality gate (temperature = 0) checking: citation presence, numeric consistency (± 20%), emergency flags, disclaimer presence, language, scope. Verdict: `PASS` | `WARN` (forward with annotations) | `BLOCK` (reject).

---

## RAG Pipeline

### Ingestion (async ARQ worker)

1. **Parsing** — section extraction from PDF/DOCX
2. **Chunking** — semantic splitting: 512 tokens max, 64 token overlap, sentence boundary respect
3. **Metadata** — disease tags, drug tags, content type classification
4. **Embedding** — OpenAI `text-embedding-3-large` (3072 dimensions)
5. **Deduplication** — SHA-256 content hash
6. **Storage** — upsert to PostgreSQL (`kb_chunks` for BM25) + MongoDB (`kb_vectors` for vector search)

### Hybrid Retrieval

- **BM25** — full-text search on PostgreSQL (French tokenization)
- **Vector similarity** — cosine search on MongoDB Atlas Vector Search (3072-dim)
- **Fusion** — Reciprocal Rank Fusion (RRF) + cross-encoder reranking
- Metadata filtering by region, disease tags, content type

---

## Quick Start

### Prerequisites

- Docker and Docker Compose v2+
- Python 3.12+
- Node.js 20+ and npm
- API keys: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`

### Setup

**1. Clone and configure**

```bash
git clone <repo-url> && cd tropicare
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and OPENAI_API_KEY in .env
```

**2. Generate JWT key pair (RS256)**

```bash
make keys
```

**3. Start the full stack** (builds images, runs migrations, initializes MongoDB replica set)

```bash
make up
```

**4. Seed the knowledge base** (place PDFs in `data/seed_documents/`)

```bash
make seed
```

**5. Verify**

```bash
curl http://localhost:8000/api/v1/health
# → {"status":"ok","service":"tropicare-gateway"}
```

### Service URLs

| Service    | URL                          | Notes                        |
|------------|------------------------------|------------------------------|
| Frontend   | http://localhost:3000         | Clinician interface          |
| Gateway    | http://localhost:8000         | REST API                     |
| MCP Tools  | http://localhost:8001         | MCP tool server              |
| Grafana    | http://localhost:3001         | admin / tropicare            |
| Jaeger     | http://localhost:16686        | Distributed traces           |
| Prometheus | http://localhost:9090         | Metrics                      |

### Create an admin user

```bash
make create-admin email=admin@tropicare.health password=AdminPass123
```

### Create the first admin user

Dev users are seeded automatically by the migration. After `docker compose up`:

| Role | Email | Password |
|------|-------|----------|
| Admin + Clinician | admin@tropicare.health | AdminPass123 |
| Clinician | clinician@tropicare.health | ClinicPass123 |

These are created by migration `0007_seed_dev_users` and removed on `alembic downgrade -1`.

To create additional users:

```bash
# Via the registration API
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"medecin@hopital.tg","password":"SecurePass1","role":"clinician"}'
```

### Frontend development (outside Docker)

```bash
cd frontend
npm install
npm run dev
```

---

## Environment Variables

| Variable               | Description                              | Default                                                      |
|------------------------|------------------------------------------|--------------------------------------------------------------|
| `ANTHROPIC_API_KEY`    | Anthropic API key (Claude)               | — (required)                                                 |
| `OPENAI_API_KEY`       | OpenAI API key (embeddings)              | — (required)                                                 |
| `DATABASE_URL`         | PostgreSQL connection URL                | `postgresql://tropicare:tropicare@localhost:5432/tropicare`   |
| `REDIS_URL`            | Redis connection URL                     | `redis://localhost:6379/0`                                   |
| `MONGODB_URI`          | MongoDB connection URI                   | `mongodb://localhost:27017`                                  |
| `MONGODB_DB`           | MongoDB database name                    | `tropicare`                                                  |
| `MCP_URL`              | MCP Tools Server URL                     | `http://localhost:8001`                                      |
| `MODEL`                | LLM model identifier                     | `claude-sonnet-4-20250514`                                   |
| `JWT_PUBLIC_KEY_PATH`  | Path to JWT RS256 public key             | `keys/public.pem`                                            |
| `CORS_ORIGINS`         | Allowed CORS origins (JSON array)        | `["http://localhost:3000"]`                                  |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry collector endpoint  | `http://jaeger:4317`                                         |

---

## Make Commands

```bash
make help             # Show all available targets
make install          # Install Python dependencies
make keys             # Generate RS256 JWT key pair
make up               # Start full stack (Docker Compose)
make down             # Stop all containers
make logs             # Tail logs (make logs svc=gateway)
make ps               # Container status
make migrate          # Run Alembic migrations (Docker)
make migrate-local    # Run Alembic migrations locally
make seed             # Seed the knowledge base
make create-admin     # Create admin user (email=... password=...)
make lint             # Run ruff + mypy
make format           # Format code (ruff)
make test             # Unit tests (pytest)
make test-integration # Integration tests
make eval             # Run evaluation pipeline
make clean            # Remove build artifacts
make clean-data       # Remove all local data (Docker volumes)
```

---

## API Reference

All endpoints are served by the Gateway on port 8000. Authentication uses JWT RS256 Bearer tokens. See [docs/api.md](docs/api.md) for the full API reference with request/response schemas and example curl commands.

### Quick Overview

| Method   | Endpoint                                | Auth       | Rate Limit | Description                    |
|----------|-----------------------------------------|------------|------------|--------------------------------|
| `POST`   | `/api/v1/auth/register`                 | None       | 10/min     | Register a new user            |
| `POST`   | `/api/v1/auth/login`                    | None       | 10/min     | Login, get JWT tokens          |
| `POST`   | `/api/v1/auth/refresh`                  | None       | 10/min     | Refresh access token           |
| `GET`    | `/api/v1/auth/me`                       | Bearer     | —          | Get current user profile       |
| `POST`   | `/api/v1/sessions`                      | Clinician  | 30/min     | Create consultation session    |
| `GET`    | `/api/v1/sessions/{id}`                 | Clinician  | —          | Get session state              |
| `POST`   | `/api/v1/sessions/{id}/turns`           | Clinician  | 60/min     | Submit query, stream response  |
| `POST`   | `/api/v1/feedback`                      | Clinician  | —          | Submit clinician feedback      |
| `GET`    | `/api/v1/admin/documents`               | Admin      | —          | List KB documents              |
| `POST`   | `/api/v1/admin/documents`               | Admin      | —          | Upload KB document             |
| `DELETE` | `/api/v1/admin/documents/{id}`          | Admin      | —          | Supersede a document           |
| `GET`    | `/api/v1/admin/analytics`               | Admin      | —          | Get analytics summary          |
| `GET`    | `/api/v1/health`                        | None       | —          | Health check                   |
| `GET`    | `/metrics`                              | None       | —          | Prometheus metrics             |

---

## Evaluation & Benchmarks

### Workflow

1. Validate seed cases with a Togolese partner clinician
2. Generate remaining cases: `make benchmark-gen`
3. Interactive clinician review: `make benchmark-review`
4. Run evaluation: `make eval`

### Metrics

**Diagnostic:** top-1/3/5 accuracy (ICD-11), MRR, emergency recall, citation rate, latency (p50/p95)

**Antibiotherapy:** 1st-line adherence, CAME coverage, contraindication absence, disclaimer rate, citation count

---

## Observability

- **Jaeger** (http://localhost:16686) — distributed traces via OpenTelemetry (OTLP gRPC)
- **Prometheus** (http://localhost:9090) — application metrics (request count, agent latency histograms, error rates)
- **Grafana** (http://localhost:3001) — pre-provisioned dashboards (admin / tropicare)
- **Structured logging** — JSON via structlog with request_id, session_id, agent_name, latency_ms
- **Audit log** — immutable PostgreSQL table, partitioned by year

---

## Project Structure

```
tropicare/
├── backend/
│   └── app/
│       ├── agents/          # LLM agents (intake, diagnostic, antibiotherapy, validation)
│       ├── config/          # Consolidated settings
│       ├── gateway/         # FastAPI app, JWT auth, RBAC, middleware, routers
│       ├── ingestion/       # Document ingestion pipeline (parsing, chunking, embedding)
│       ├── models/          # Pydantic schemas
│       ├── observability/   # Tracing, metrics, structured logging
│       ├── orchestrator/    # Agent pipeline controller, session store, audit logger
│       ├── tools/           # MCP tool server (MongoDB Atlas Vector Search)
│       └── eval/            # Evaluation harness and benchmarks
├── frontend/
│   └── src/
│       ├── app/             # Next.js pages (App Router)
│       ├── components/      # React components (chat, intake, results)
│       ├── hooks/           # Custom hooks (useStream)
│       └── lib/             # Shared types and utilities
├── tests/
│   ├── unit/                # Unit tests (agents, tools)
│   ├── integration/         # Integration tests (API, orchestrator)
│   └── property/            # Hypothesis property-based tests
├── alembic/                 # Database migrations
├── docker/                  # Dockerfiles, Prometheus/Grafana config
├── scripts/                 # Admin and seeding scripts
├── keys/                    # JWT RS256 key pair (generated, gitignored)
├── docker-compose.yml       # Full infrastructure stack
├── pyproject.toml           # Python project config and pytest settings
└── Makefile                 # Development commands
```

---

## Testing

```bash
# Unit tests
make test

# Integration tests (requires running stack)
make test-integration

# Property-based tests only
pytest tests/property/ -v

# All tests with markers
pytest -m unit          # unit tests only
pytest -m integration   # integration tests only
pytest -m property      # property-based tests only
```

---

## License

TBD.
