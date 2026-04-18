# ─────────────────────────────────────────────────────────────────────────────
# backend/app/tools/config.py — Re-export settings for MCP tools server
# ─────────────────────────────────────────────────────────────────────────────
from ..config.settings import settings

__all__ = ["settings"]
