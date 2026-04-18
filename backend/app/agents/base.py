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

from ..gateway.circuit_breaker import llm_breaker, mcp_breaker, CircuitBreakerOpenError
from ..observability.metrics import record_agent_metrics

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
        mcp_breaker.check()
        with tracer.start_as_current_span(f"tool.{tool}") as span:
            span.set_attribute("tool.name", tool)
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    r = await client.post(
                        f"{self._base}/tools/{tool}",
                        json=kwargs,
                    )
                    r.raise_for_status()
                    result = r.json()
                    result_count = len(result) if isinstance(result, list) else 1
                    span.set_attribute("tool.result_count", result_count)
                    mcp_breaker.record_success()
                    return result
            except CircuitBreakerOpenError:
                raise
            except Exception as exc:
                mcp_breaker.record_failure()
                raise


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
        t0 = time.monotonic()

        with tracer.start_as_current_span(f"agent.{self.name}") as span:
            span.set_attribute("agent.name", self.name)
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
                span.set_attribute("agent.latency_ms", agent_span.latency_ms)
                span.set_attribute("agent.input_tokens", agent_span.input_tokens)
                span.set_attribute("agent.output_tokens", agent_span.output_tokens)
                span.set_attribute("agent.verdict", "ok")
                record_agent_metrics(self.name, elapsed, "ok")
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
                span.set_attribute("agent.latency_ms", agent_span.latency_ms)
                span.set_attribute("agent.input_tokens", 0)
                span.set_attribute("agent.output_tokens", 0)
                span.set_attribute("agent.verdict", "error")
                span.record_exception(exc)
                record_agent_metrics(self.name, elapsed, "error")
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
        llm_breaker.check()
        try:
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
                llm_breaker.record_success()
                return text, usage
        except CircuitBreakerOpenError:
            raise
        except Exception as exc:
            llm_breaker.record_failure()
            raise

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

    @staticmethod
    def _extract_json_lenient(text: str, required_fields: list[str] | None = None) -> tuple[dict, list[str]]:
        """Extract JSON leniently: return partial dict + list of warning messages.

        On valid JSON, returns (parsed_dict, []).
        On invalid JSON, attempts to extract key-value pairs heuristically
        and returns (partial_dict, [warning_messages]).
        """
        import re
        warnings: list[str] = []

        # First try strict extraction
        text_clean = text.strip()
        text_clean = re.sub(r"^```(?:json)?\s*", "", text_clean)
        text_clean = re.sub(r"\s*```$", "", text_clean).strip()

        # Try standard JSON parse
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            s = text_clean.find(start_char)
            if s == -1:
                continue
            depth, end = 0, -1
            for i, ch in enumerate(text_clean[s:], s):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end != -1:
                try:
                    parsed = json.loads(text_clean[s:end])
                    if isinstance(parsed, dict):
                        return parsed, []
                    return {"_raw": parsed}, []
                except json.JSONDecodeError:
                    pass

        # JSON parsing failed — attempt to extract individual valid fields
        partial: dict = {}
        # Try to find individual "key": value patterns
        field_pattern = re.compile(
            r'"(\w+)"\s*:\s*('
            r'"(?:[^"\\]|\\.)*"'   # string value
            r'|\[.*?\]'            # array value
            r'|\{.*?\}'            # object value
            r'|true|false|null'    # literals
            r'|-?\d+(?:\.\d+)?'   # numbers
            r')',
            re.DOTALL,
        )
        for match in field_pattern.finditer(text_clean):
            key = match.group(1)
            val_str = match.group(2)
            try:
                partial[key] = json.loads(val_str)
            except json.JSONDecodeError:
                continue

        if partial:
            warnings.append(
                f"LLM output contained malformed JSON — extracted {len(partial)} valid field(s), "
                f"discarded non-conforming content"
            )
            # Check for missing required fields
            if required_fields:
                missing = [f for f in required_fields if f not in partial]
                if missing:
                    warnings.append(f"Missing required fields: {', '.join(missing)}")
            return partial, warnings

        warnings.append("LLM output contained no parseable JSON content")
        return {}, warnings
