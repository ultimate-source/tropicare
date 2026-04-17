# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/diagnostic.py — DiagnosticAgent with full ReAct loop
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import datetime
import json
import logging
import re as _re
from typing import Any

from .base import BaseAgent, MCPClient
from .prompts import (
    DIAGNOSTIC_SYSTEM, DIAGNOSTIC_REACT_PROMPT, DIAGNOSTIC_REFINE_PROMPT,
    format_patient_context, format_chunks, format_epid_priors, render,
)
from ..models.schemas import DiagnosticDifferential, PatientContext

log = logging.getLogger("tropicare.agents")

_MONTH_NAMES_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


class DiagnosticAgent(BaseAgent):
    name = "diagnostic"

    # Maximum ReAct iterations before forcing a conclusion
    MAX_REACT_TURNS = 4

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        ctx: dict     = kwargs.get("patient_context", {})
        query: str    = kwargs.get("query", "")
        history: list = kwargs.get("conversation_history", [])
        prior_diff    = kwargs.get("previous_differential")
        new_info      = kwargs.get("new_information")

        tool_calls: list[str] = []
        total_usage: dict     = {"input_tokens": 0, "output_tokens": 0}

        # ── Step 1: retrieve epidemiological priors ──────────────────────────
        region = ctx.get("region", "Maritime")
        month  = datetime.date.today().month
        epid: dict = {}
        try:
            epid = await self._mcp.call("epid_calendar", region=region, month=month)
            tool_calls.append("epid_calendar")
        except Exception as e:
            log.warning("epid_calendar failed: %s", e)

        # ── Step 2: hybrid retrieval (3 query expansions) ───────────────────
        symptoms    = [s.get("normalized", "") for s in ctx.get("symptoms", [])]
        region_str  = ctx.get("region", "")
        q_main      = query
        q_symptoms  = " ".join(symptoms[:4])
        q_epid      = f"maladies tropicales {region_str} Togo saison {'pluies' if month in range(5, 11) else 'sèche'}"

        chunks: list[dict] = []
        for q in [q_main, q_symptoms, q_epid]:
            if not q.strip():
                continue
            try:
                retrieved = await self._mcp.call(
                    "hybrid_retrieve", query=q, k=8, language=None
                )
                chunks.extend(retrieved)
                tool_calls.append("hybrid_retrieve")
            except Exception as e:
                log.warning("hybrid_retrieve failed for q=%r: %s", q[:40], e)

        # Deduplicate chunks by chunk_id, keep highest score
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c.get("chunk_id", "")
            if cid not in seen or c.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = c
        top_chunks = sorted(seen.values(), key=lambda c: c.get("score", 0), reverse=True)[:8]

        # ── Step 3: ReAct loop ───────────────────────────────────────────────
        season_ctx   = f"{_MONTH_NAMES_FR[month]} — {'saison des pluies' if month in range(5, 11) else 'saison sèche'}"
        epid_priors  = epid.get("disease_priors", {})
        epid_alerts  = epid.get("outbreak_alerts", [])

        # Build base prompt
        if prior_diff and new_info:
            user_prompt = render(
                DIAGNOSTIC_REFINE_PROMPT,
                previous_differential_json=json.dumps(prior_diff, ensure_ascii=False, indent=2),
                new_information=new_info,
                new_chunks_formatted=format_chunks(top_chunks),
            )
        else:
            user_prompt = render(
                DIAGNOSTIC_REACT_PROMPT,
                patient_context_summary=format_patient_context(ctx),
                region=region,
                season_context=season_ctx,
                month=month,
                epid_priors_formatted=format_epid_priors(epid_priors),
                retrieved_chunks_formatted=format_chunks(top_chunks),
                conversation_history=self._format_history(history),
                query=query,
            )

        messages = [{"role": "user", "content": user_prompt}]

        # Iterative ReAct: if Claude asks for more info, retrieve and continue
        final_raw = ""
        for turn in range(self.MAX_REACT_TURNS):
            raw, usage = await self._call_claude(DIAGNOSTIC_SYSTEM, messages)
            total_usage["input_tokens"]  += usage.get("input_tokens", 0)
            total_usage["output_tokens"] += usage.get("output_tokens", 0)
            final_raw = raw

            # Check if Claude needs more retrieval (signals "RETRIEVE:" in thought)
            if "RETRIEVE:" in raw and turn < self.MAX_REACT_TURNS - 1:
                retrieval_queries = _re.findall(r"RETRIEVE:\s*(.+)", raw)
                new_chunks: list[dict] = []
                for rq in retrieval_queries[:2]:
                    try:
                        extra = await self._mcp.call("hybrid_retrieve", query=rq.strip(), k=5)
                        new_chunks.extend(extra)
                        tool_calls.append("hybrid_retrieve")
                    except Exception as e:
                        log.warning("ReAct retrieval failed: %s", e)

                if new_chunks:
                    # Add Claude's thinking + new evidence as next turn
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": f"Nouveaux extraits récupérés :\n{format_chunks(new_chunks)}\n\nContinue ton raisonnement et produis le différentiel final.",
                    })
                    continue  # next ReAct iteration

            # No more RETRIEVE signals → we have the final answer
            break

        # ── Step 4: format citations ─────────────────────────────────────────
        citations = []
        try:
            citations = await self._mcp.call("citation_formatter", chunks=top_chunks)
            tool_calls.append("citation_formatter")
        except Exception as e:
            log.warning("citation_formatter failed: %s", e)

        result = await self._parse_output(final_raw, citations=citations, epid_alerts=epid_alerts)
        return result, total_usage, tool_calls

    async def _build_messages(self, **kwargs) -> tuple[str, list[dict]]:
        # Not used directly — _execute builds messages inline
        return DIAGNOSTIC_SYSTEM, []

    async def _parse_output(self, raw: str, citations=None, epid_alerts=None, **_) -> dict:
        data = self._extract_json(raw)

        # Inject outbreak alerts as emergency flags if present
        if epid_alerts:
            for alert in epid_alerts:
                data.setdefault("emergency_flags", []).append({
                    "disease": alert,
                    "level": "urgent",
                    "action": "Alerte épidémique en cours — notifier district sanitaire",
                })

        data["citations"] = citations or []
        return data

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return "Première consultation"
        lines = []
        for turn in history[-4:]:  # last 4 turns only
            role = "Clinicien" if turn.get("role") == "user" else "Système"
            lines.append(f"{role}: {str(turn.get('content', ''))[:200]}")
        return "\n".join(lines)
