# TropiCare Deployment Guide

This guide covers deploying TropiCare using Docker Compose, including JWT secret management, database migrations, knowledge base seeding, and monitoring setup.

---

## Prerequisites

- Docker Engine 24+ and Docker Compose v2+
- API keys: `ANTHROPIC_API_KEY` (Anthropic Claude) and `OPENAI_API_KEY` (embeddings)
- For production: MongoDB Atlas cluster with Vector Search enabled
- Minimum 4 GB RAM for the full stack

---

## 1. Environment Configuration

### Create the `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your production values:

```env
# Required API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Database (defaults work for Docker Compose local setup)
DATABASE_URL=postgresql://tropicare:tropicare@postgres:5432/tropicare
REDIS_URL=redis://redis:6379/0

# MongoDB — use Atlas URI for production
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/tropicare?retryWrites=true&w=majority
MONGODB_DB=tropicare

# MCP Tools Server
MCP_URL=http://mcp-tools:8001

# LLM model
MODEL=claude-sonnet-4-20250514

# CORS — restrict to your domain in production
CORS_ORIGINS=["https://tropicare.health"]

# JWT public key path (inside container)
JWT_PUBLIC_KEY_PATH=/run/secrets/jwt_public.pem

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

---

## 2. JWT Key Management

TropiCare uses RS256 (RSA 4096-bit) for JWT signing. The private key signs tokens in the auth router; the public key verifies them in the Gateway middleware.

### Generate keys

```bash
make keys
# Or manually:
mkdir -p keys
openssl genrsa -out keys/private.pem 4096
openssl rsa -in keys/private.pem -pubout -out keys/public.pem
```

### Docker Compose secrets

The `docker-compose.yml` mounts the public key as a Docker secret:

```yaml
secrets:
  jwt_public.pem:
    file: ./keys/public.pem
```

The Gateway service references it:

```yaml
gateway:
  secrets:
    - jwt_public.pem
  environment:
    JWT_PUBLIC_KEY_PATH: /run/secrets/jwt_public.pem
```

### Production recommendations

- Store keys in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never commit `keys/` to version control (it's in `.gitignore`)
- Rotate keys periodically — issue new tokens with the new key, keep the old public key available for a grace period matching the access token expiry (8 hours)
- Use separate key pairs for staging and production environments

---

## 3. Docker Compose Deployment

### Services overview

| Service            | Image/Build          | Port  | Purpose                          |
|--------------------|----------------------|-------|----------------------------------|
| `postgres`         | postgres:16-alpine   | 5432  | Primary database (data + BM25)   |
| `redis`            | redis:7-alpine       | 6379  | Sessions, cache, task queue      |
| `mongodb`          | mongo:7-jammy        | 27017 | Vector search (local dev)        |
| `mongo-init`       | mongo:7-jammy        | —     | Replica set initialization       |
| `migrate`          | Dockerfile.gateway   | —     | Alembic migrations (run-once)    |
| `mcp-tools`        | Dockerfile.mcp       | 8001  | MCP clinical tools server        |
| `gateway`          | Dockerfile.gateway   | 8000  | FastAPI Gateway                  |
| `ingestion-worker` | Dockerfile.worker    | —     | ARQ document ingestion worker    |
| `frontend`         | Next.js Dockerfile   | 3000  | Web interface                    |
| `jaeger`           | jaegertracing/all-in-one | 16686 | Distributed tracing UI        |
| `prometheus`       | prom/prometheus       | 9090  | Metrics collection               |
| `grafana`          | grafana/grafana       | 3001  | Dashboards                       |

### Start the stack

```bash
# Build and start all services
docker compose up -d --build

# Or use the convenience script
./start-dev.sh    # Linux/macOS
start-dev.bat     # Windows
```

### Stop the stack

```bash
docker compose down

# Or:
./stop-dev.sh
```

### Production overrides

For production, create a `docker-compose.prod.yml` override:

```yaml
version: "3.9"

services:
  gateway:
    restart: always
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 2G
    environment:
      CORS_ORIGINS: '["https://tropicare.health"]'

  mcp-tools:
    restart: always
    deploy:
      resources:
        limits:
          memory: 1G

  # Remove local MongoDB in production (use Atlas)
  mongodb:
    profiles: ["dev-only"]
  mongo-init:
    profiles: ["dev-only"]

  # Remove observability UIs from public access in production
  jaeger:
    ports: []  # Only internal access
  grafana:
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_AUTH_ANONYMOUS_ENABLED: "false"
```

Deploy with:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 4. Database Migrations

TropiCare uses Alembic for PostgreSQL schema management. Migrations run automatically via the `migrate` service on `docker compose up`.

### Migration files

| Migration                      | Description                                    |
|--------------------------------|------------------------------------------------|
| `0001_initial_schema.py`       | Core tables: users, sessions, turns, kb_*, audit_log, feedback |
| `0002_seed_formulary.py`       | Initial CAME formulary seed data               |
| `0003_seed_amr.py`             | Initial AMR resistance data                    |
| `0004_add_analytics_indexes.py`| Performance indexes for analytics queries      |
| `0005_seed_formulary_expansion.py` | Expanded formulary (80+ entries)           |
| `0006_seed_amr_ddi_safety.py`  | AMR, DDI, and drug safety seed data            |

### Run migrations manually

```bash
# Via Docker
docker compose run --rm migrate

# Or locally (requires DATABASE_URL in environment)
make migrate-local
```

### Create a new migration

```bash
alembic revision --autogenerate -m "description of change"
```

### Rollback

```bash
alembic downgrade -1
```

### MongoDB setup

MongoDB requires a replica set for Atlas Vector Search compatibility. The `mongo-init` service handles this automatically for local development:

```bash
# Verify replica set status
docker compose exec mongodb mongosh --eval "rs.status()"
```

For production, use MongoDB Atlas with a Vector Search index on the `kb_vectors` collection:

```json
{
  "name": "vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      { "type": "vector", "path": "embedding", "numDimensions": 3072, "similarity": "cosine" },
      { "type": "filter", "path": "disease_tags" },
      { "type": "filter", "path": "content_type" },
      { "type": "filter", "path": "language" },
      { "type": "filter", "path": "superseded" }
    ]
  }
}
```

---

## 5. Knowledge Base Seeding

### Seed clinical documents

Place PDF/DOCX files in `data/seed_documents/`, then:

```bash
make seed
```

This uploads documents to the Gateway admin endpoint, which enqueues them for ingestion by the ARQ worker. The worker parses, chunks, embeds, and stores them in PostgreSQL (BM25) and MongoDB (vector search).

### Database seed data

The Alembic migrations automatically seed:
- **CAME formulary** — 80+ entries covering antimalarials, antibiotics, antifungals, antiparasitics, and supportive care
- **AMR data** — 50+ drug-pathogen-region resistance profiles for Togo and West Africa
- **DDI interactions** — 30+ clinically significant tropical disease medication interactions
- **Drug safety** — 40+ entries with pregnancy categories and lactation safety data

### Create an admin user

An admin user is required to upload documents and access analytics:

```bash
make create-admin email=admin@tropicare.health password=SecureAdminPass1
```

Password requirements: ≥10 characters, 1 uppercase, 1 lowercase, 1 digit.

---

## 6. Monitoring Setup

### Jaeger (Distributed Tracing)

- URL: http://localhost:16686
- Receives traces via OTLP gRPC on port 4317
- Trace hierarchy: `gateway.request` → `orchestrator.handle_turn` → `agent.*` → `tool.*`
- Each agent span includes: agent name, latency_ms, input/output tokens, verdict

### Prometheus (Metrics)

- URL: http://localhost:9090
- Scrapes the Gateway `/metrics` endpoint every 15 seconds
- Configuration: `docker/prometheus.yml`

Key metrics:
- `tropicare_request_count` — by endpoint and status code
- `tropicare_agent_latency_seconds` — histograms by agent (p50, p95, p99)
- `tropicare_agent_errors_total` — error count by agent

### Grafana (Dashboards)

- URL: http://localhost:3001
- Default credentials: `admin` / `tropicare` (change in production)
- Pre-provisioned dashboard: `docker/grafana/provisioning/dashboards/tropicare.json`

Dashboard panels:
- Request rate over time
- Agent latency distribution
- Error rate by agent
- Active session count

### Structured Logging

The Gateway uses `structlog` with JSON output. Each log entry includes:
- `timestamp`, `level`, `request_id`, `session_id`, `agent_name`, `latency_ms`

View logs:

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f gateway
docker compose logs -f mcp-tools
```

### Audit Log

The immutable audit log is stored in the PostgreSQL `audit_log` table (partitioned by year). PII fields are SHA-256 hashed before persistence. Query audit events:

```sql
SELECT event_type, session_id, created_at
FROM audit_log
WHERE event_type = 'turn_completed'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 7. Health Checks

Verify all services are running:

```bash
# Gateway
curl http://localhost:8000/api/v1/health
# → {"status":"ok","service":"tropicare-gateway"}

# MCP Tools
curl http://localhost:8001/health

# Container status
docker compose ps
```

---

## 8. Troubleshooting

### MongoDB replica set not initialized

```bash
docker compose exec mongodb mongosh --eval 'rs.initiate({_id:"rs0",members:[{_id:0,host:"mongodb:27017"}]})'
```

### Migrations fail

```bash
# Check PostgreSQL is healthy
docker compose exec postgres pg_isready -U tropicare

# Run migrations manually with verbose output
docker compose run --rm migrate alembic upgrade head --sql
```

### Gateway can't connect to MCP Tools

```bash
# Check MCP Tools health
docker compose logs mcp-tools

# Verify network connectivity
docker compose exec gateway curl http://mcp-tools:8001/health
```

### Redis connection errors

```bash
docker compose exec redis redis-cli ping
# → PONG
```

### Reset all data

```bash
make clean-data
# This removes all Docker volumes (PostgreSQL, Redis, MongoDB data)
```
