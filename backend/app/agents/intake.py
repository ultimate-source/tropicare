# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/intake.py — IntakeAgent
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
from typing import Any

from .base import BaseAgent, MCPClient
from .prompts import (
    INTAKE_SYSTEM, INTAKE_EXTRACT_PROMPT, INTAKE_FOLLOWUP_PROMPT,
    format_patient_context, render,
)
from ..models.schemas import PatientContext

log = logging.getLogger("tropicare.agents")


class IntakeAgent(BaseAgent):
    name = "intake"

    async def _build_messages(
        self,
        free_text:       str,
        prior_context:   dict[str, Any] | None = None,
        clinician_reply: str | None  = None,
        current_context: dict[str, Any] | None = None,
        **_,
    ) -> tuple[str, list[dict[str, Any]]]:

        if clinician_reply and current_context:
            # Follow-up turn — refine existing context
            user_content = render(
                INTAKE_FOLLOWUP_PROMPT,
                current_context_json=json.dumps(current_context, ensure_ascii=False, indent=2),
                clinician_reply=clinician_reply,
            )
        else:
            prior_block = (
                f"CONTEXTE EXISTANT :\n{format_patient_context(prior_context)}"
                if prior_context else ""
            )
            user_content = render(
                INTAKE_EXTRACT_PROMPT,
                free_text=free_text,
                prior_context=prior_block,
            )

        return INTAKE_SYSTEM, [{"role": "user", "content": user_content}]

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        # Enrich with NLP entity extraction via MCP tool
        raw_text = kwargs.get("free_text", "")
        tool_calls = []

        if raw_text:
            try:
                entities = await self._mcp.call("symptom_extractor", free_text=raw_text, language="fr")
                kwargs["extracted_entities"] = entities
                tool_calls.append("symptom_extractor")
            except Exception as e:
                log.warning("symptom_extractor tool failed: %s", e)

        system, messages = await self._build_messages(**kwargs)
        raw, usage = await self._call_claude(system, messages)
        result = await self._parse_output(raw, **kwargs)
        return result, usage, tool_calls

    async def _parse_output(self, raw: str, **_) -> dict:
        return self._extract_json(raw)
