# ─────────────────────────────────────────────────────────────────────────────
# Makefile — TropiCare development commands
# Usage: make <target>
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install dev up down logs migrate seed keys lint test eval clean

PYTHON   := python3.12
PIP      := pip
COMPOSE  := docker compose
ALEMBIC  := alembic

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  TropiCare — available targets:"
	@echo ""
	@echo "  install    Install all Python dependencies"
	@echo "  keys       Generate RS256 JWT key pair"
	@echo "  up         Start full stack (Docker Compose)"
	@echo "  down       Stop all containers"
	@echo "  logs       Tail service logs (pass svc=gateway)"
	@echo "  migrate    Run Alembic migrations"
	@echo "  seed       Seed KB with priority-1 documents"
	@echo "  lint       Run ruff + mypy"
	@echo "  test       Run unit tests (pytest)"
	@echo "  eval       Run benchmark eval pipeline"
	@echo "  clean      Remove build artifacts and __pycache__"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install:
	$(PIP) install -r requirements/dev.txt

# ── JWT key pair ──────────────────────────────────────────────────────────────
keys:
	@mkdir -p keys
	@if [ ! -f keys/private.pem ]; then \
		openssl genrsa -out keys/private.pem 4096; \
		openssl rsa -in keys/private.pem -pubout -out keys/public.pem; \
		echo "✓ RS256 key pair generated in keys/"; \
	else \
		echo "keys/ already exists — skipping"; \
	fi

# ── Docker stack ──────────────────────────────────────────────────────────────
up: keys
	$(COMPOSE) up -d --build
	@echo ""
	@echo "  Stack started:"
	@echo "    Gateway    → http://localhost:8000"
	@echo "    Frontend   → http://localhost:3000"
	@echo "    Grafana    → http://localhost:3001  (admin / tropicare)"
	@echo "    Jaeger     → http://localhost:16686"
	@echo "    Qdrant     → http://localhost:6333"
	@echo ""

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f $(svc)

ps:
	$(COMPOSE) ps

# ── Migrations ────────────────────────────────────────────────────────────────
migrate:
	$(COMPOSE) run --rm migrate

migrate-local:
	DATABASE_URL=$(shell grep DATABASE_URL .env | cut -d= -f2) \
		$(ALEMBIC) upgrade head

revision r:
	$(ALEMBIC) revision --autogenerate -m "$(msg)"

downgrade:
	$(ALEMBIC) downgrade -1

# ── Create first admin user ───────────────────────────────────────────────────
create-admin:
	@test -n "$(email)"    || (echo "Usage: make create-admin email=... password=..." && exit 1)
	@test -n "$(password)" || (echo "Usage: make create-admin email=... password=..." && exit 1)
	DATABASE_URL=$(shell grep DATABASE_URL .env | cut -d= -f2) \
		$(PYTHON) scripts/create_admin.py --email $(email) --password $(password)

# ── Seed KB ───────────────────────────────────────────────────────────────────
seed:
	@echo "Seeding knowledge base with priority-1 documents..."
	$(PYTHON) scripts/seed_kb.py \
		--gateway http://localhost:8000 \
		--docs-dir data/seed_documents \
		--token $(shell cat .dev_token 2>/dev/null || echo "SET_DEV_TOKEN")

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	ruff check .
	mypy tropicare_agents tropicare_orchestrator tropicare_gateway tropicare_tools tropicare_ingestion \
		--ignore-missing-imports --strict

format:
	ruff format .

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/unit/ -v --tb=short -q

test-integration:
	pytest tests/integration/ -v --tb=short \
		-m "not eval" \
		--gateway-url http://localhost:8000

# ── Eval ──────────────────────────────────────────────────────────────────────
eval:
	$(PYTHON) -m tropicare_eval.harness \
		--benchmark tropicare_eval/data/benchmark_v1.json \
		--gateway-url http://localhost:8000 \
		--model $(MODEL) \
		--output-dir eval_reports

eval-ci:
	pytest tropicare_eval/ -m eval --tb=short -q \
		-x \
		--gateway-url http://localhost:8000

# ── Generate remaining benchmark cases ───────────────────────────────────────
benchmark-gen:
	$(PYTHON) -m tropicare_eval.generate_benchmark \
		--seed tropicare_eval/data/benchmark_v1_seed.json \
		--output tropicare_eval/data/benchmark_v1.json \
		--concurrency 3

benchmark-review:
	$(PYTHON) -m tropicare_eval.generate_benchmark --review

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete
	find . -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null; true
	find . -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null; true

clean-data:
	@read -p "Delete ALL local data (DB, Redis, Qdrant)? [y/N] " yn; \
	if [ "$$yn" = "y" ]; then \
		$(COMPOSE) down -v; \
		echo "✓ Volumes removed"; \
	fi













def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway",  default="http://localhost:8000")
    parser.add_argument("--docs-dir", default="data/seed_documents")
    parser.add_argument("--token",    default=os.getenv("DEV_TOKEN", ""))
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}

    for filename, src_type, title, version in SEED_DOCS:
        fpath = Path(args.docs_dir) / filename
        if not fpath.exists():
            print(f"  SKIP {filename} — file not found")
            continue

        with open(fpath, "rb") as f:
            r = httpx.post(
                f"{args.gateway}/api/v1/admin/documents",
                headers=headers,
                data={"title": title, "source_type": src_type, "version": version},
                files={"file": (filename, f)},
                timeout=30,
            )
        if r.status_code == 202:
            print(f"  ✓ Queued: {filename} → {r.json()['document_id']}")
        else:
            print(f"  ✗ Failed: {filename} — {r.status_code} {r.text[:100]}")

if __name__ == "__main__":
    main()