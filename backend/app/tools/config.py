# ─────────────────────────────────────────────────────────────────────────────
# backend/app/tools/config.py — Re-export settings for MCP tools server
# ─────────────────────────────────────────────────────────────────────────────
from backend.app.config.settings import settings

__all__ = ["settings"]
