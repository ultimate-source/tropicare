# ─────────────────────────────────────────────────────────────────────────────
# backend/app/agents/antibiotherapy.py — AntibiotherapyAgent with full MCP
# tool integration: AMR deprioritization, pediatric dosage, pregnancy safety
# filtering, DDI severity-tagged warnings, and retry-once on invalid JSON.
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from .base import BaseAgent, MCPClient
from .prompts import (
    ANTIBIOTHERAPY_SYSTEM, ANTIBIOTHERAPY_PROMPT, ANTIBIOTHERAPY_PREGNANCY_ADDENDUM,
    format_patient_context, format_chunks,
    format_ddi_warnings, format_amr_results, format_formulary_results, render,
)
from ..models.schemas import PatientContext, TreatmentPlan

log = logging.getLogger("tropicare.agents")

MANDATORY_DISCLAIMER = (
    "⚠️ AIDE À LA DÉCISION UNIQUEMENT — Cette recommandation est générée par un système "
    "d'intelligence artificielle à partir de guidelines validées. Elle ne remplace pas le "
    "jugement clinique du médecin traitant. Toute prescription doit être validée par un "
    "professionnel de santé habilité."
)

# FDA pregnancy categories considered safe for pregnant patients
_SAFE_PREGNANCY_CATEGORIES = {"A", "B", "C"}

# AMR resistance threshold above which drugs are deprioritized from first-line
_AMR_RESISTANCE_THRESHOLD = 30.0


class AntibiotherapyAgent(BaseAgent):
    name = "antibiotherapy"

    async def _execute(self, **kwargs) -> tuple[Any, dict, list[str]]:
        ctx        = kwargs.get("patient_context", {})
        diagnosis  = kwargs.get("confirmed_diagnosis", "")
        icd11      = kwargs.get("icd11_code", "")
        confidence = kwargs.get("diagnostic_confidence", 0.0)

        tool_calls: list[str]  = []
        total_usage            = {"input_tokens": 0, "output_tokens": 0}
        tool_warnings: list[str] = []

        # ── Step 1: retrieve treatment guidelines ────────────────────────────
        chunks: list[dict] = []
        for q in [
            f"traitement {diagnosis} Togo PNLP",
            f"antibiothérapie {diagnosis} Afrique Ouest",
            f"{diagnosis} protocole OMS posologie",
        ]:
            try:
                retrieved = await self._mcp.call("hybrid_retrieve", query=q, k=6)
                chunks.extend(retrieved)
                tool_calls.append("hybrid_retrieve")
            except Exception as e:
                log.warning("Antibiotherapy retrieval failed: %s", e)
                tool_warnings.append(f"Recherche documentaire partielle (hybrid_retrieve: {q[:30]}…)")

        # Deduplicate
        seen: dict[str, dict] = {}
        for c in chunks:
            cid = c.get("chunk_id", "")
            if cid not in seen or c.get("score", 0) > seen[cid].get("score", 0):
                seen[cid] = c
        top_chunks = sorted(seen.values(), key=lambda c: c.get("score", 0), reverse=True)[:8]

        # Empty KB: warn when no guideline evidence was retrieved (Req 33.2)
        if not top_chunks:
            tool_warnings.append(
                "Aucune évidence de guidelines trouvée dans la base de connaissances — "
                "consultez directement les protocoles PNLP locaux"
            )

        # ── Step 2: parallel tool calls ──────────────────────────────────────
        # Extract candidate drugs from retrieved chunks heuristically
        candidate_drugs = self._extract_candidate_drugs(top_chunks, diagnosis)
        current_meds    = [m.get("name", "") for m in ctx.get("current_medications", [])]
        all_drugs       = list(set(candidate_drugs + current_meds))

        # Run formulary, AMR, DDI, safety in parallel
        formulary_results, amr_results, ddi_warnings, safety_classes = await asyncio.gather(
            self._check_formulary(candidate_drugs),
            self._check_amr(candidate_drugs, diagnosis),
            self._check_ddi(all_drugs) if len(all_drugs) >= 2 else asyncio.sleep(0, result=[]),
            self._check_safety(candidate_drugs, ctx.get("pregnancy_status")),
            return_exceptions=True,
        )

        for name, result in [
            ("formulary_lookup", formulary_results),
            ("amr_lookup", amr_results),
            ("drug_ddi_check", ddi_warnings),
            ("safety_classifier", safety_classes),
        ]:
            if isinstance(result, Exception):
                log.warning("%s failed: %s", name, result)
                tool_warnings.append(f"Données {name} indisponibles")
            else:
                tool_calls.append(name)

        formulary_results = formulary_results if not isinstance(formulary_results, Exception) else []
        amr_results       = amr_results       if not isinstance(amr_results, Exception)       else []
        ddi_warnings      = ddi_warnings       if not isinstance(ddi_warnings, Exception)      else []
        safety_classes    = safety_classes     if not isinstance(safety_classes, Exception)    else []

        # ── Step 3: build prompt + call Claude ───────────────────────────────
        preg_status  = ctx.get("pregnancy_status", "not_pregnant")
        trimester    = {"pregnant_t1": 1, "pregnant_t2": 2, "pregnant_t3": 3}.get(preg_status)

        base_prompt = render(
            ANTIBIOTHERAPY_PROMPT,
            confirmed_diagnosis=diagnosis,
            icd11_code=icd11,
            diagnostic_confidence=f"{confidence:.0%}",
            age=ctx.get("age_years", "?"),
            sex=ctx.get("sex", "?"),
            weight_kg=ctx.get("weight_kg", "?"),
            pregnancy_status=preg_status,
            allergies=", ".join(ctx.get("allergies", [])) or "Aucune connue",
            current_medications=", ".join(m.get("name", "") for m in ctx.get("current_medications", [])) or "Aucun",
            formulary_results_formatted=format_formulary_results(formulary_results),
            amr_results_formatted=format_amr_results(amr_results),
            ddi_warnings_formatted=format_ddi_warnings(ddi_warnings),
            safety_classes_formatted=self._format_safety(safety_classes),
            retrieved_chunks_formatted=format_chunks(top_chunks),
        )

        if trimester:
            base_prompt += "\n\n" + render(
                ANTIBIOTHERAPY_PREGNANCY_ADDENDUM, trimester=trimester
            )

        messages = [{"role": "user", "content": base_prompt}]
        raw, usage = await self._call_claude(ANTIBIOTHERAPY_SYSTEM, messages)
        total_usage["input_tokens"]  += usage.get("input_tokens", 0)
        total_usage["output_tokens"] += usage.get("output_tokens", 0)

        # ── Step 4: citations ────────────────────────────────────────────────
        citations = []
        try:
            citations = await self._mcp.call("citation_formatter", chunks=top_chunks)
            tool_calls.append("citation_formatter")
        except Exception as e:
            log.warning("citation_formatter failed: %s", e)
            tool_warnings.append("Formatage des citations indisponible (citation_formatter)")

        # ── Step 5: parse output with retry-once on invalid JSON ─────────────
        parse_kwargs = dict(
            citations=citations,
            ddi_warnings=ddi_warnings,
            amr_results=amr_results,
            safety_classes=safety_classes,
            patient_context=ctx,
        )
        try:
            result = await self._parse_output(raw, **parse_kwargs)
        except (ValueError, ValidationError):
            # Retry LLM call once with explicit JSON instruction
            log.warning("First parse failed, retrying LLM call with explicit JSON instruction")
            retry_messages = messages.copy()
            retry_messages.append({"role": "assistant", "content": raw})
            retry_messages.append({
                "role": "user",
                "content": (
                    "Ta réponse précédente ne contenait pas de JSON valide. "
                    "Retourne UNIQUEMENT un objet JSON valide avec la structure exacte suivante, "
                    "sans texte avant ou après :\n"
                    '{"target_disease": "...", "clinical_rationale": "...", '
                    '"first_line": [{"drug_name": "...", "generic_name": "...", '
                    '"came_available": true, "dose": "...", "route": "PO", '
                    '"frequency": "...", "duration_days": 7}], '
                    '"second_line": [], "alternatives": [], '
                    '"contraindicated": [], "supportive_care": [], '
                    '"follow_up_guidance": "...", "referral_criteria": "...", '
                    '"disclaimer": "..."}'
                ),
            })
            try:
                retry_raw, retry_usage = await self._call_claude(
                    ANTIBIOTHERAPY_SYSTEM, retry_messages
                )
                total_usage["input_tokens"] += retry_usage.get("input_tokens", 0)
                total_usage["output_tokens"] += retry_usage.get("output_tokens", 0)
                result = await self._parse_output(retry_raw, **parse_kwargs)
            except (ValueError, ValidationError):
                # Last resort: lenient extraction of whatever valid fields exist
                log.warning("Retry parse also failed, attempting lenient JSON extraction")
                partial, json_warnings = self._extract_json_lenient(
                    retry_raw if 'retry_raw' in dir() else raw,
                    required_fields=["target_disease", "first_line"],
                )
                tool_warnings.extend(json_warnings)
                # Build a minimal valid result from partial data
                partial.setdefault("target_disease", diagnosis or "Inconnu")
                partial.setdefault("clinical_rationale", "")
                partial.setdefault("first_line", [])
                partial.setdefault("second_line", [])
                partial.setdefault("alternatives", [])
                partial.setdefault("contraindicated", [])
                partial.setdefault("supportive_care", [])
                partial.setdefault("follow_up_guidance", "")
                partial.setdefault("referral_criteria", "")
                partial["disclaimer"] = MANDATORY_DISCLAIMER
                partial["citations"] = citations or []
                result = partial

        # ── Attach tool failure warnings as annotations ──────────────────────
        if tool_warnings:
            existing = result.get("_tool_warnings", []) if isinstance(result, dict) else []
            if isinstance(result, dict):
                result["_tool_warnings"] = existing + tool_warnings

        return result, total_usage, tool_calls

    async def _build_messages(self, **kwargs) -> tuple[str, list[dict]]:
        return ANTIBIOTHERAPY_SYSTEM, []

    async def _parse_output(
        self,
        raw: str,
        citations=None,
        ddi_warnings=None,
        amr_results=None,
        safety_classes=None,
        patient_context=None,
        **_,
    ) -> dict:
        data = self._extract_json(raw)

        # Guarantee disclaimer is always present
        data["disclaimer"] = MANDATORY_DISCLAIMER
        data["citations"] = citations or []

        amr_results = amr_results or []
        ddi_warnings = ddi_warnings or []
        safety_classes = safety_classes or []
        patient_context = patient_context or {}

        # ── Build lookup maps for post-processing ────────────────────────────

        # AMR: map drug name (lowered) → resistance_pct
        high_resistance_drugs: dict[str, float] = {}
        amr_no_data_note: str | None = None
        for profile in amr_results:
            drug_name = (profile.get("drug") or "").lower()
            # Detect the structured unavailability marker
            if drug_name == "*" and profile.get("confidence") == "no_data":
                amr_no_data_note = profile.get("recommendation", self._NO_AMR_DATA_NOTE)
                continue
            pct = profile.get("resistance_pct")
            if pct is not None and pct > _AMR_RESISTANCE_THRESHOLD:
                high_resistance_drugs[drug_name] = pct

        # Safety: map drug name (lowered) → pregnancy_category
        safety_map: dict[str, str] = {}
        for entry in safety_classes:
            drug_name = (entry.get("drug") or "").lower()
            cat = entry.get("pregnancy_category", "")
            if cat:
                safety_map[drug_name] = cat.upper()

        # DDI: map drug name (lowered) → list of severity-tagged warning strings
        ddi_map: dict[str, list[str]] = {}
        severity_icons = {
            "contraindicated": "🚫",
            "major": "⛔",
            "moderate": "⚠️",
            "minor": "ℹ️",
        }
        for w in ddi_warnings:
            sev = w.get("severity", "minor")
            icon = severity_icons.get(sev, "ℹ️")
            warning_str = (
                f"{icon} [{sev.upper()}] {w.get('drug_a', '?')} × {w.get('drug_b', '?')}: "
                f"{w.get('clinical_effect', '')} — {w.get('management', '')}"
            )
            for drug_key in [
                (w.get("drug_a") or "").lower(),
                (w.get("drug_b") or "").lower(),
            ]:
                if drug_key:
                    ddi_map.setdefault(drug_key, []).append(warning_str)

        # ── Determine patient flags ──────────────────────────────────────────
        is_pregnant = patient_context.get("pregnancy_status", "not_pregnant") not in (
            "not_pregnant",
            "not_applicable",
            "unknown",
        )
        age_years = patient_context.get("age_years")
        weight_kg = patient_context.get("weight_kg")
        is_pediatric = age_years is not None and age_years < 18 and weight_kg

        # ── Process each tier ────────────────────────────────────────────────
        demoted_from_first: list[dict] = []

        for tier_key in ("first_line", "second_line", "alternatives"):
            drugs = data.get(tier_key, [])
            if not isinstance(drugs, list):
                continue

            for drug in drugs:
                generic = (drug.get("generic_name") or drug.get("drug_name") or "").lower()

                # Attach DDI severity-tagged warnings (Req 10.3)
                existing_ddi = drug.get("ddi_warnings", [])
                extra_ddi = ddi_map.get(generic, [])
                if extra_ddi:
                    drug["ddi_warnings"] = list(set(existing_ddi + extra_ddi))

                # Attach AMR note for high-resistance drugs (Req 9.3)
                if generic in high_resistance_drugs:
                    pct = high_resistance_drugs[generic]
                    drug["amr_note"] = (
                        f"Résistance locale {pct:.0f}% (>{_AMR_RESISTANCE_THRESHOLD:.0f}%) — "
                        f"déprioritisé selon données AMR régionales"
                    )
                elif amr_no_data_note and not drug.get("amr_note"):
                    # No AMR data available at all — recommend PNLP protocol (Req 11.4)
                    drug["amr_note"] = amr_no_data_note

                # Pediatric dosage calculation (Req 10.1)
                if is_pediatric:
                    drug["dose_mg_per_kg"] = self._calculate_pediatric_dose(
                        drug.get("dose", ""), weight_kg
                    )

                # Attach pregnancy class from safety data (Req 10.2)
                if is_pregnant and generic in safety_map:
                    drug["pregnancy_class"] = safety_map[generic]

        # ── AMR deprioritization: move high-resistance drugs out of first_line ─
        first_line = data.get("first_line", [])
        if isinstance(first_line, list):
            kept = []
            for drug in first_line:
                generic = (drug.get("generic_name") or drug.get("drug_name") or "").lower()
                if generic in high_resistance_drugs:
                    demoted_from_first.append(drug)
                else:
                    kept.append(drug)
            data["first_line"] = kept
            # Append demoted drugs to alternatives
            if demoted_from_first:
                alts = data.get("alternatives", [])
                if not isinstance(alts, list):
                    alts = []
                alts.extend(demoted_from_first)
                data["alternatives"] = alts

        # ── Pregnancy safety filtering: remove FDA D/X drugs (Req 10.2) ──────
        if is_pregnant:
            for tier_key in ("first_line", "second_line", "alternatives"):
                drugs = data.get(tier_key, [])
                if not isinstance(drugs, list):
                    continue
                data[tier_key] = [
                    d for d in drugs
                    if self._is_pregnancy_safe(d, safety_map)
                ]

        # ── Validate through Pydantic model ──────────────────────────────────
        validated = TreatmentPlan.model_validate(data)
        return validated.model_dump()

    @staticmethod
    def _calculate_pediatric_dose(dose_str: str, weight_kg: float) -> str | None:
        """Extract numeric mg value from dose string and compute mg/kg for pediatric patients."""
        if not dose_str or not weight_kg or weight_kg <= 0:
            return None
        # Try to extract a numeric mg value from the dose string
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*mg", dose_str, re.IGNORECASE)
        if not match:
            return None
        total_mg = float(match.group(1).replace(",", "."))
        mg_per_kg = total_mg / weight_kg
        return f"{mg_per_kg:.1f} mg/kg"

    @staticmethod
    def _is_pregnancy_safe(drug: dict, safety_map: dict[str, str]) -> bool:
        """Return True if the drug is safe for pregnant patients (FDA A/B/C or unknown)."""
        generic = (drug.get("generic_name") or drug.get("drug_name") or "").lower()
        # Check from safety_map first (MCP safety_classifier results)
        cat = safety_map.get(generic, "")
        if not cat:
            # Fall back to pregnancy_class already on the drug dict
            cat = (drug.get("pregnancy_class") or "").upper()
        if not cat:
            # No safety data available — keep the drug (clinician decides)
            return True
        return cat in _SAFE_PREGNANCY_CATEGORIES

    async def _check_formulary(self, drugs: list[str]) -> list[dict]:
        results = []
        for drug in drugs[:6]:
            try:
                res = await self._mcp.call("formulary_lookup", drug_name=drug)
                results.append(res)
            except Exception:
                pass
        return results

    # Expanded pathogen map covering tropical diseases common in Togo.
    # Some diagnoses map to multiple likely pathogens.
    _PATHOGEN_MAP: dict[str, list[str]] = {
        "typhoïde":    ["Salmonella typhi"],
        "typhoid":     ["Salmonella typhi"],
        "choléra":     ["Vibrio cholerae"],
        "cholera":     ["Vibrio cholerae"],
        "méningite":   ["Neisseria meningitidis", "Streptococcus pneumoniae"],
        "meningit":    ["Neisseria meningitidis", "Streptococcus pneumoniae"],
        "pneumonie":   ["Streptococcus pneumoniae", "Haemophilus influenzae", "Klebsiella pneumoniae"],
        "pneumonia":   ["Streptococcus pneumoniae", "Haemophilus influenzae", "Klebsiella pneumoniae"],
        "shigell":     ["Shigella"],
        "dysenterie":  ["Shigella", "Entamoeba histolytica"],
        "urinaire":    ["Escherichia coli", "Klebsiella pneumoniae"],
        "urinary":     ["Escherichia coli", "Klebsiella pneumoniae"],
        "cystite":     ["Escherichia coli"],
        "pyélonéphrite": ["Escherichia coli", "Klebsiella pneumoniae"],
        "diarrhée":    ["Escherichia coli", "Salmonella", "Shigella"],
        "diarrhea":    ["Escherichia coli", "Salmonella", "Shigella"],
        "septicémie":  ["Staphylococcus aureus", "Escherichia coli"],
        "sepsis":      ["Staphylococcus aureus", "Escherichia coli"],
        "tuberculose": ["Mycobacterium tuberculosis"],
        "tuberculosis": ["Mycobacterium tuberculosis"],
        "otite":       ["Streptococcus pneumoniae", "Haemophilus influenzae"],
        "cellulite":   ["Staphylococcus aureus", "Streptococcus pyogenes"],
        "impétigo":    ["Staphylococcus aureus", "Streptococcus pyogenes"],
        "gonorrhée":   ["Neisseria gonorrhoeae"],
        "syphilis":    ["Treponema pallidum"],
        "leptospir":   ["Leptospira"],
    }

    # Structured note appended when no AMR data is available for any pair
    _NO_AMR_DATA_NOTE = (
        "Aucune donnée AMR disponible pour les paires médicament-pathogène interrogées. "
        "Recommandation : suivre le protocole empirique PNLP en vigueur pour cette pathologie."
    )

    def _infer_pathogens(self, diagnosis: str) -> list[str]:
        """Infer likely pathogens from diagnosis, supporting multiple pathogens."""
        diag_lower = diagnosis.lower()
        for keyword, pathogens in self._PATHOGEN_MAP.items():
            if keyword in diag_lower:
                return pathogens
        return ["Bacteria"]

    async def _check_amr(self, drugs: list[str], diagnosis: str) -> list[dict]:
        """Query AMR data for each drug-pathogen pair.

        For each pair, first tries region="Togo". If no data is returned
        (empty result, confidence="no_data", or resistance_pct is None),
        retries with region="West Africa" and marks the result with
        ``fallback_region: true``.

        Each result includes: drug, pathogen, region, resistance_pct,
        confidence, data_source, year, recommendation, fallback_region.

        When NO AMR data is available for ANY pair, a structured note
        recommending the empirical PNLP protocol is appended.
        """
        pathogens = self._infer_pathogens(diagnosis)
        results: list[dict] = []

        for drug in drugs[:6]:
            for pathogen in pathogens:
                result = await self._amr_lookup_with_fallback(drug, pathogen)
                if result is not None:
                    results.append(result)

        # If no usable AMR data at all, append a structured unavailability note
        has_usable_data = any(
            r.get("confidence") != "no_data" and r.get("resistance_pct") is not None
            for r in results
        )
        if not has_usable_data:
            results.append({
                "drug": "*",
                "pathogen": "*",
                "region": "N/A",
                "resistance_pct": None,
                "confidence": "no_data",
                "data_source": "N/A",
                "year": None,
                "recommendation": self._NO_AMR_DATA_NOTE,
                "fallback_region": False,
            })

        return results

    async def _amr_lookup_with_fallback(self, drug: str, pathogen: str) -> dict | None:
        """Try Togo first, fall back to West Africa if no data."""
        # Try Togo-specific data first
        try:
            res = await self._mcp.call(
                "amr_lookup", drug=drug, pathogen=pathogen, region="Togo",
            )
            if self._is_valid_amr_result(res):
                res["fallback_region"] = False
                return self._normalize_amr_result(res, drug, pathogen, "Togo")
        except Exception:
            pass

        # Fall back to West Africa
        try:
            res = await self._mcp.call(
                "amr_lookup", drug=drug, pathogen=pathogen, region="West Africa",
            )
            if self._is_valid_amr_result(res):
                res["fallback_region"] = True
                return self._normalize_amr_result(res, drug, pathogen, "West Africa")
        except Exception:
            pass

        return None

    @staticmethod
    def _is_valid_amr_result(res: dict | None) -> bool:
        """Return True if the AMR result contains usable data."""
        if not res or not isinstance(res, dict):
            return False
        # Accept if there's a resistance_pct or confidence != "no_data"
        if res.get("confidence") == "no_data" and res.get("resistance_pct") is None:
            return False
        if res.get("resistance_pct") is None and not res.get("confidence"):
            return False
        return True

    @staticmethod
    def _normalize_amr_result(
        res: dict, drug: str, pathogen: str, region: str,
    ) -> dict:
        """Ensure all required fields are present in the AMR result."""
        return {
            "drug": res.get("drug", drug),
            "pathogen": res.get("pathogen", pathogen),
            "region": res.get("region", region),
            "resistance_pct": res.get("resistance_pct"),
            "confidence": res.get("confidence", "low"),
            "data_source": res.get("data_source", "unknown"),
            "year": res.get("year"),
            "recommendation": res.get("recommendation", ""),
            "fallback_region": res.get("fallback_region", False),
        }

    async def _check_ddi(self, drugs: list[str]) -> list[dict]:
        return await self._mcp.call("drug_ddi_check", drug_list=drugs)

    async def _check_safety(self, drugs: list[str], pregnancy_status: str | None) -> list[dict]:
        if not pregnancy_status or pregnancy_status in ("not_pregnant", "not_applicable"):
            return []
        trimester = {"pregnant_t1": 1, "pregnant_t2": 2, "pregnant_t3": 3}.get(pregnancy_status)
        results = []
        for drug in drugs[:6]:
            try:
                res = await self._mcp.call("safety_classifier", drug=drug, trimester=trimester)
                results.append(res)
            except Exception:
                pass
        return results

    @staticmethod
    def _extract_candidate_drugs(chunks: list[dict], diagnosis: str) -> list[str]:
        """Heuristic drug name extraction from chunk text."""
        known_drugs = [
            "artésunate", "artéméther", "luméfantrine", "artéméther-luméfantrine",
            "quinine", "chloroquine", "primaquine", "doxycycline",
            "ceftriaxone", "amoxicilline", "azithromycine", "ciprofloxacine",
            "rifampicine", "isoniazide", "pyrazinamide", "éthambutol",
            "cotrimoxazole", "métronidazole", "fluconazole", "amphotéricine",
            "ivermectine", "albendazole", "praziquantel", "mébendazole",
        ]
        text = " ".join(c.get("chunk_text", "") for c in chunks).lower()
        return [d for d in known_drugs if d in text]

    @staticmethod
    def _format_safety(safety: list[dict]) -> str:
        if not safety:
            return "Non applicable"
        return "\n".join(
            f"  • {s.get('drug', '?')} : Catégorie {s.get('pregnancy_category', 'N/D')} "
            f"| Allaitement: {'Oui' if s.get('lactation_safe') else 'Non' if s.get('lactation_safe') is False else 'N/D'}"
            for s in safety
        )
