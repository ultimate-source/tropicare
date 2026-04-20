#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start-dev.sh — Start TropiCare local development environment
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE="docker compose"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   TropiCare — Starting local dev     ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || error "Docker is not installed"
docker info >/dev/null 2>&1      || error "Docker daemon is not running"

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn ".env created from .env.example — please fill in your API keys"
        warn "  ANTHROPIC_API_KEY and OPENAI_API_KEY are required"
        echo ""
        read -rp "  Press Enter once you've updated .env (or Ctrl+C to abort)..."
    else
        error ".env file not found and no .env.example to copy from"
    fi
fi

# ── JWT keys ──────────────────────────────────────────────────────────────────
if [ ! -f keys/private.pem ]; then
    info "Generating RS256 JWT key pair..."
    mkdir -p keys
    openssl genrsa -out keys/private.pem 4096 2>/dev/null
    openssl rsa -in keys/private.pem -pubout -out keys/public.pem 2>/dev/null
    info "JWT keys generated in keys/"
else
    info "JWT keys already exist — skipping"
fi

# ── Start Docker stack ────────────────────────────────────────────────────────
info "Starting Docker services..."
$COMPOSE up -d --build

# ── Wait for health checks ───────────────────────────────────────────────────
info "Waiting for services to be healthy..."

wait_for() {
    local name="$1" url="$2" retries=30
    while [ $retries -gt 0 ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            info "$name is ready"
            return 0
        fi
        retries=$((retries - 1))
        sleep 2
    done
    warn "$name did not become healthy in time"
    return 1
}

wait_for "PostgreSQL"  "http://localhost:8000/api/v1/health" || true
wait_for "Gateway"     "http://localhost:8000/api/v1/health"
wait_for "Qdrant"      "http://localhost:6333/healthz"
wait_for "MCP Tools"   "http://localhost:8001/health"

# ── MongoDB Atlas vector search index (if using Atlas) ────────────────────────
if grep -q "^MONGODB_URI=mongodb+srv" .env 2>/dev/null; then
    info "MongoDB Atlas detected — ensuring vector search index exists..."
    python scripts/setup_atlas_index.py || warn "Atlas index setup failed (see output above)"
fi

# ── Ingest knowledge base documents (if any) ─────────────────────────────────
DOC_COUNT=$(find docs/medic -maxdepth 1 -type f \( -name '*.pdf' -o -name '*.docx' \) 2>/dev/null | wc -l)
if [ "$DOC_COUNT" -gt 0 ]; then
    info "Found $DOC_COUNT document(s) in docs/medic/ — ingesting into knowledge base..."
    python scripts/ingest_docs.py --gateway http://localhost:8000 || warn "Document ingestion had errors (see output above)"
else
    warn "No PDF/DOCX files in docs/medic/ — knowledge base will be empty"
    warn "  Place clinical guidelines there and re-run, or run: python scripts/ingest_docs.py"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║   TropiCare is running!                          ║"
echo "  ╠══════════════════════════════════════════════════╣"
echo "  ║   Frontend   → http://localhost:3000             ║"
echo "  ║   Gateway    → http://localhost:8000             ║"
echo "  ║   Grafana    → http://localhost:3001             ║"
echo "  ║   Jaeger     → http://localhost:16686            ║"
echo "  ║   Qdrant     → http://localhost:6333             ║"
echo "  ╠══════════════════════════════════════════════════╣"
echo "  ║   Stop with: ./stop-dev.sh                        ║"
echo "  ║   Logs with: docker compose logs -f gateway      ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""
