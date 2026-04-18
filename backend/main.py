# ─────────────────────────────────────────────────────────────────────────────
# backend/main.py — Legacy entry point (gateway/main.py is the primary app)
# ─────────────────────────────────────────────────────────────────────────────
from app.gateway.main import app  # noqa: F401 — re-export the FastAPI app
