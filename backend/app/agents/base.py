# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/base.py — BaseAgent, AgentSpan, MCPClient only
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

import httpx
from opentelemetry import trace
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log    = logging.getLogger("tropicare.agents")
tracer = trace.get_tracer("tropicare.agents")

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"


class AgentSpan(BaseModel):
    agent:      str
    started_at: float
    ended_at:   float
    latency_ms: int
    input_tokens:  int
    output_tokens: int
    tool_calls:    list[str]
    verdict:       str  # "ok" | "error" | "blocked"
    error:         str | None = None


class MCPClient:
    """Thin async client that calls the MCP tool server via HTTP."""

    def __init__(self, base_url: str, timeout: int = 30):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def call(self, tool: str, **kwargs: Any) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                f"{self._base}/tools/{tool}",
                json=kwargs,
            )
            r.raise_for_status()
            return r.json()


class BaseAgent(ABC):
    """
    Abstract agent.  Subclasses implement `_build_messages` and `_parse_output`.
    The base class handles:
      - Claude API call with streaming support
      - Retry with exponential back-off
      - OpenTelemetry span emission
      - Token accounting
    """

    name: str = "base"

    def __init__(
        self,
        api_key:    str,
        mcp:        MCPClient,
        model:      str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        self._api_key    = api_key
        self._mcp        = mcp
        self._model      = model
        self._max_tokens = max_tokens
        self._temp       = temperature

    # ── Public entry point ────────────────────────────────────────────────────

    async def run(self, **kwargs: Any) -> tuple[Any, AgentSpan]:
        span_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()

        with tracer.start_as_current_span(f"agent.{self.name}") as span:
            span.set_attribute("agent", self.name)
            try:
                result, usage, tool_calls = await self._execute(**kwargs)
                elapsed = time.monotonic() - t0
                agent_span = AgentSpan(
                    agent=self.name,
                    started_at=t0,
                    ended_at=t0 + elapsed,
                    latency_ms=int(elapsed * 1000),
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    tool_calls=tool_calls,
                    verdict="ok",
                )
                span.set_attribute("latency_ms", agent_span.latency_ms)
                return result, agent_span

            except Exception as exc:
                elapsed = time.monotonic() - t0
                log.error("Agent %s failed: %s", self.name, exc, exc_info=True)
                agent_span = AgentSpan(
                    agent=self.name,
                    started_at=t0,
                    ended_at=t0 + elapsed,
                    latency_ms=int(elapsed * 1000),
                    input_tokens=0,
                    output_tokens=0,
                    tool_calls=[],
                    verdict="error",
                    error=str(exc),
                )
                return None, agent_span

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        """Override to add pre/post tool-call steps."""
        system, messages = await self._build_messages(**kwargs)
        raw, usage = await self._call_claude(system, messages)
        result = await self._parse_output(raw, **kwargs)
        return result, usage, []

    @abstractmethod
    async def _build_messages(self, **kwargs) -> tuple[str, list[dict]]:
        """Return (system_prompt, messages_list) for this agent's turn."""

    @abstractmethod
    async def _parse_output(self, raw: str, **kwargs) -> Any:
        """Parse Claude's text output into a typed result."""

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
    )
    async def _call_claude(
        self,
        system:   str,
        messages: list[dict],
    ) -> tuple[str, dict]:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                ANTHROPIC_API,
                headers={
                    "x-api-key":          self._api_key,
                    "anthropic-version":  "2023-06-01",
                    "content-type":       "application/json",
                },
                json={
                    "model":       self._model,
                    "max_tokens":  self._max_tokens,
                    "temperature": self._temp,
                    "system":      system,
                    "messages":    messages,
                },
            )
            r.raise_for_status()
            body = r.json()
            text = body["content"][0]["text"]
            usage = body.get("usage", {})
            return text, usage

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Extract first JSON object or array from Claude's output."""
        import re
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        # Find outermost { } or [ ]
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            s = text.find(start_char)
            if s == -1:
                continue
            depth, end = 0, -1
            for i, ch in enumerate(text[s:], s):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end != -1:
                return json.loads(text[s:end])
        raise ValueError(f"No JSON found in:\n{text[:300]}")
