#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# stop-dev.sh — Stop TropiCare local development environment
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE="docker compose"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

echo ""
echo "  TropiCare — Stopping local dev..."
echo ""

# ── Parse flags ───────────────────────────────────────────────────────────────
CLEAN_VOLUMES=false
for arg in "$@"; do
    case "$arg" in
        --clean|-c) CLEAN_VOLUMES=true ;;
        --help|-h)
            echo "  Usage: ./scripts/stop-dev.sh [OPTIONS]"
            echo ""
            echo "  Options:"
            echo "    --clean, -c   Remove Docker volumes (deletes all local data)"
            echo "    --help,  -h   Show this help"
            echo ""
            exit 0
            ;;
    esac
done

# ── Stop containers ──────────────────────────────────────────────────────────
if [ "$CLEAN_VOLUMES" = true ]; then
    warn "Stopping containers and removing volumes..."
    $COMPOSE down -v
    info "All containers stopped and volumes removed"
else
    $COMPOSE down
    info "All containers stopped (data volumes preserved)"
fi

echo ""
echo "  Restart with: ./start-dev.sh"
echo ""
