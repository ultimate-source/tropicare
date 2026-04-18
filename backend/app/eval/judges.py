# ═══════════════════════════════════════════════════════════════
# judges.py — LLM-as-judge evaluators (for qualitative metrics)
# ═══════════════════════════════════════════════════════════════

CITATION_JUDGE_PROMPT = """\
Tu évalues une réponse médicale générée par un système d'IA.

RÉPONSE SYSTÈME :
{response_text}

SOURCES DISPONIBLES :
{sources_text}

Pour chaque affirmation clinique dans la réponse :
1. Identifie si elle est sourcée (citation présente)
2. Vérifie si le chiffre/fait est cohérent avec la source

Retourne UNIQUEMENT un JSON :
{{
  "total_claims": 12,
  "cited_claims": 11,
  "citation_rate": 0.92,
  "numeric_discrepancies": ["Dosage artésunate mentionné 2.4mg/kg vs source 2.4mg/kg ✓"],
  "unsourced_claims": ["..."],
  "verdict": "PASS" | "WARN" | "FAIL"
}}
"""

HALLUCINATION_JUDGE_PROMPT = """\
Tu es un médecin expert en maladies tropicales. Évalue la réponse suivante pour détecter :
1. Des médicaments inventés ou des noms génériques incorrects
2. Des dosages cliniquement impossibles (ex: 1000mg/kg)
3. Des associations diagnostiques aberrantes (ex: malaria causée par un virus)
4. Des affirmations épidémiologiques fausses pour le Togo

RÉPONSE À ÉVALUER :
{response_text}

Retourne un JSON :
{{
  "hallucinations_detected": [],
  "suspicious_claims": [],
  "verdict": "PASS" | "WARN" | "FAIL",
  "confidence": 0.95
}}
"""

async def llm_judge(prompt: str, api_key: str, model: str = "claude-sonnet-4-20250514") -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
        # Strip any markdown code fences
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(text)

async def judge_citation_quality(response: dict, api_key: str) -> dict:
    diff_text  = json.dumps(response.get("differential", []), ensure_ascii=False, indent=2)
    tx_text    = json.dumps(response.get("treatment", {}), ensure_ascii=False, indent=2)
    src_text   = json.dumps(response.get("citations", []), ensure_ascii=False, indent=2)
    prompt = CITATION_JUDGE_PROMPT.format(
        response_text=diff_text + "\n\n" + tx_text,
        sources_text=src_text,
    )
    return await llm_judge(prompt, api_key)

async def judge_hallucination(response: dict, api_key: str) -> dict:
    text = json.dumps(response, ensure_ascii=False, indent=2)
    prompt = HALLUCINATION_JUDGE_PROMPT.format(response_text=text[:3000])
    return await llm_judge(prompt, api_key)
