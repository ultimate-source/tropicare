# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/validation.py — ValidationAgent
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
from typing import Any

from .base import BaseAgent
from .prompts import VALIDATION_SYSTEM, VALIDATION_PROMPT, format_chunks, render
from ..models.schemas import DiagnosticDifferential, TreatmentPlan


class ValidationAgent(BaseAgent):
    name       = "validation"
    _max_tokens = 1024
    _temp       = 0.0  # deterministic for quality gate

    async def _build_messages(
        self,
        agent_output: dict,
        agent_type:   str,
        source_chunks: list[dict],
        session_language: str = "fr",
        output_type: str = "diagnostic",
        **_,
    ) -> tuple[str, list[dict]]:
        prompt = render(
            VALIDATION_PROMPT,
            agent_type=agent_type,
            agent_output_json=json.dumps(agent_output, ensure_ascii=False, indent=2)[:3000],
            source_chunks_formatted=format_chunks(source_chunks[:4], max_chars_per_chunk=200),
            session_language=session_language,
            output_type=output_type,
        )
        return VALIDATION_SYSTEM, [{"role": "user", "content": prompt}]

    async def _parse_output(self, raw: str, **_) -> dict:
        return self._extract_json(raw)

    async def run_validation(
        self,
        agent_output:  dict,
        agent_type:    str,
        source_chunks: list[dict],
        session_language: str = "fr",
        output_type: str = "diagnostic",
    ) -> dict:
        """Returns validation result dict with global_verdict and annotations."""
        result, _ = await self.run(
            agent_output=agent_output,
            agent_type=agent_type,
            source_chunks=source_chunks,
            session_language=session_language,
            output_type=output_type,
        )
        if result is None:
            return {"global_verdict": "WARN", "annotations": ["Validation agent failed — output unverified"]}
        return result
