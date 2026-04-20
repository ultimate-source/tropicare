# ─────────────────────────────────────────────────────────────────────────────
# tropicare_gateway/config.py
# ─────────────────────────────────────────────────────────────────────────────
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DATABASE_URL:      str = "postgresql://tropicare:tropicare@localhost:5432/tropicare"
    REDIS_URL:         str = "redis://localhost:6379/0"
    MONGODB_URI:       str = "mongodb://localhost:27017"
    MONGODB_DB:        str = "tropicare"
    MCP_URL:           str = "http://localhost:8001"
    MODEL:             str = "claude-sonnet-4-20250514"
    CORS_ORIGINS:      list[str] = ["http://localhost:3000"]
    JWT_PUBLIC_KEY_PATH: str = "keys/public.pem"
    SESSION_RETENTION_DAYS: int = 365

    class Config:
        env_file = ".env"
        extra = "ignore"