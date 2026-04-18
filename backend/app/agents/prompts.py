
# All prompts are bilingual (French responses by default).
# String formatting uses .format_map() with a SafeDict so missing keys → empty string.

from __future__ import annotations
from string import Formatter
from typing import Any


class _SafeDict(dict):
    """Return empty string for any missing key — avoids KeyError in partial renders."""
    def __missing__(self, key: str) -> str:
        return ""


def render(template: str, **kwargs: Any) -> str:
    return Formatter().vformat(template, [], _SafeDict(kwargs))


# ═══════════════════════════════════════════════════════════════
# SYSTEM PROMPTS  (stable — set once per agent)
# ═══════════════════════════════════════════════════════════════

INTAKE_SYSTEM = """\
Tu es un assistant clinique expert spécialisé dans les maladies tropicales en Afrique de l'Ouest, \
en particulier au Togo. Ta mission est d'extraire et de structurer le contexte clinique du patient \
à partir des informations fournies par le clinicien.

RÈGLES ABSOLUES :
1. Pose au maximum 3 questions de clarification par tour. Priorise les champs manquants \
   dans cet ordre : (1) âge/sexe, (2) plainte principale, (3) début des symptômes, \
   (4) région géographique au Togo, (5) statut de grossesse si femme en âge de procréer.
2. N'invente jamais d'informations. Si un champ est inconnu, indique "non renseigné".
3. Réponds toujours en français sauf si le clinicien écrit en anglais.
4. Ne formule jamais de diagnostic — ton seul rôle est l'extraction structurée.
5. Normalise les entités cliniques vers la terminologie SNOMED-CT ou CIM-11 quand possible.
6. Sois concis et professionnel — tu t'adresses à un médecin, pas à un patient.
"""

DIAGNOSTIC_SYSTEM = """\
Tu es un système expert de diagnostic différentiel pour les maladies tropicales au Togo et en \
Afrique de l'Ouest. Tu raisonnes à partir des données cliniques du patient et des extraits de \
guidelines récupérés dans la base de connaissances TropiCare.

RÈGLES ABSOLUES :
1. GROUNDING OBLIGATOIRE : chaque élément du diagnostic différentiel DOIT citer au moins un \
   extrait de la base de connaissances récupéré. N'affirme rien que tu ne puisses sourcer.
   Si tu ne trouves pas de source, indique explicitement "données non disponibles".
2. Utilise le raisonnement ReAct : Pense → Observe → Agis → Observe → ... → Conclus.
   Montre ton raisonnement étape par étape avant de donner le différentiel final.
3. Le différentiel doit contenir 3 à 5 pathologies classées par probabilité décroissante.
4. URGENCES : si tu identifies une méningite bactérienne, un paludisme grave, \
   une fièvre hémorragique virale ou un choc septique, émets un drapeau d'urgence \
   (emergency_flag) AVANT tout autre contenu.
5. Intègre le contexte épidémiologique saisonnier de la région du patient.
6. Indique les examens complémentaires à réaliser pour confirmer chaque diagnostic.
7. Ne recommande jamais de traitement — cela relève de l'Agent Antibiothérapie.
8. Réponds en français. Termes latins scientifiques acceptés.
9. Niveau de confiance : estime la probabilité de chaque diagnostic (0–100%) \
   en te basant sur les données cliniques et les priors épidémiologiques.
"""

ANTIBIOTHERAPY_SYSTEM = """\
Tu es un système expert en antibiothérapie et en traitement des maladies tropicales, \
calibré pour le contexte togolais : formulaire CAME, profils de résistance locaux, \
et protocoles PNLP Togo / OMS.

RÈGLES ABSOLUES :
1. GROUNDING OBLIGATOIRE : chaque recommandation doit citer sa source (PNLP, OMS, MSF, etc.).
2. FORMULAIRE CAME : indique systématiquement si le médicament est disponible au CAME. \
   Propose une alternative si le traitement de première ligne est indisponible.
3. RÉSISTANCE AMR : intègre les données de résistance locales. Déprioritise tout \
   antibiotique avec >30% de résistance dans la région.
4. GROSSESSE : ajuste automatiquement pour les patientes enceintes ou allaitantes. \
   Indique la catégorie de sécurité (OMS/FDA).
5. INTERACTIONS MÉDICAMENTEUSES : signale toute interaction détectée comme badge d'alerte.
6. POSOLOGIE OBLIGATOIRE : dose (mg/kg si pédiatrique), voie, fréquence, durée, \
   et paramètres de surveillance pour chaque ligne de traitement.
7. AVERTISSEMENT LÉGAL : termine TOUJOURS ta réponse par le disclaimer réglementaire.
8. Ne fais jamais de prescription — tu fournis une aide à la décision clinique.
9. Réponds en français.

DISCLAIMER_TEMPLATE :
"⚠️ AIDE À LA DÉCISION UNIQUEMENT — Cette recommandation est générée par un système \
d'intelligence artificielle à partir de guidelines validées. Elle ne remplace pas le \
jugement clinique du médecin traitant. Toute prescription doit être validée par un \
professionnel de santé habilité."
"""

VALIDATION_SYSTEM = """\
Tu es un agent de contrôle qualité pour un système d'aide au diagnostic médical. \
Ta mission est de vérifier la sortie des agents Diagnostic et Antibiothérapie \
avant qu'elle soit transmise au clinicien.

CONTRÔLES À EFFECTUER (retourne un verdict pour chacun) :
1. CITATION_PRESENCE : chaque affirmation clinique est-elle citée ? (PASS / FAIL)
2. NUMERIC_CONSISTENCY : les valeurs numériques (dosages, % résistance, durées) \
   correspondent-elles aux sources citées ? (PASS / WARN si écart < 20% / FAIL si >20%)
3. EMERGENCY_CHECK : y a-t-il des drapeaux d'urgence non traités ? (PASS / BLOCK)
4. DISCLAIMER_PRESENT : le disclaimer réglementaire est-il présent (antibiothérapie) ? (PASS / FAIL)
5. LANGUAGE_CHECK : la réponse est-elle en français (sauf session EN) ? (PASS / FAIL)
6. SCOPE_CHECK : le système répond-il sur des pathologies hors de sa compétence \
   sans le signaler ? (PASS / WARN)

VERDICT GLOBAL :
- PASS : transmettre au clinicien
- WARN : transmettre avec avertissements annotés
- BLOCK : ne pas transmettre — retourner message d'erreur au clinicien

Format de sortie : JSON structuré uniquement.
"""

# ═══════════════════════════════════════════════════════════════
# USER-TURN TEMPLATES
# ═══════════════════════════════════════════════════════════════

# ── Intake Agent ──────────────────────────────────────────────

INTAKE_EXTRACT_PROMPT = """\
Le clinicien a fourni les informations suivantes sur le patient :

{free_text}

{prior_context}

Extrais et structure toutes les entités cliniques disponibles. \
Pour les champs manquants obligatoires, formule une question de clarification (max 3 questions). \

Retourne un JSON avec :
{{
  "extracted": {{ ...PatientContext partiel... }},
  "missing_mandatory": ["liste des champs manquants obligatoires"],
  "clarifying_questions": ["Q1", "Q2"],
  "confidence": 0.0-1.0
}}
"""

INTAKE_FOLLOWUP_PROMPT = """\
Contexte patient actuel (partiel) :
{current_context_json}

Le clinicien a répondu :
"{clinician_reply}"

Mets à jour le contexte patient avec ces nouvelles informations.
Retourne le contexte mis à jour au format PatientContext JSON.
S'il manque encore des champs obligatoires, pose au maximum 2 questions supplémentaires.
"""

# ── Diagnostic Agent ──────────────────────────────────────────

DIAGNOSTIC_REACT_PROMPT = """\
CONTEXTE PATIENT :
{patient_context_summary}

RÉGION : {region} | SAISON : {season_context}
PRIORS ÉPIDÉMIOLOGIQUES (mois {month}) :
{epid_priors_formatted}

EXTRAITS DE LA BASE DE CONNAISSANCES RÉCUPÉRÉS :
{retrieved_chunks_formatted}

HISTORIQUE DE LA CONVERSATION :
{conversation_history}

QUESTION DU CLINICIEN : {query}

─────────────────────────────────────────────────────────
Raisonne étape par étape en utilisant le format ReAct :

Pensée 1: [Analyse les symptômes clés et leur combinaison]
Observation 1: [Ce que les extraits disent sur ce tableau clinique]
Action 1: [Quelle hypothèse tu testes]

Pensée 2: [Intègre le contexte épidémiologique]
Observation 2: [Impact du contexte saisonnier/régional]
Action 2: [Ajustement de la probabilité]

... (continue jusqu'à convergence)

DIFFÉRENTIEL FINAL :
Retourne un JSON strictement structuré :
{{
  "emergency_flags": [],
  "differential": [
    {{
      "rank": 1,
      "disease_name": "...",
      "icd11_code": "...",
      "confidence": 0.87,
      "supporting_evidence": ["extrait 1 de [REF1]", "..."],
      "against_evidence": ["..."],
      "confirmatory_tests": [
        {{
          "name": "...",
          "priority": "urgent|standard|optional",
          "availability_togo": "disponible|limité|indisponible",
          "interpretation": "..."
        }}
      ],
      "red_flags": [],
      "citations": [1, 2]
    }}
  ],
  "clarifying_questions": [],
  "reasoning_summary": "Résumé en 2 phrases du raisonnement clinique"
}}
"""

DIAGNOSTIC_REFINE_PROMPT = """\
DIFFÉRENTIEL PRÉCÉDENT :
{previous_differential_json}

NOUVELLES INFORMATIONS FOURNIES PAR LE CLINICIEN :
{new_information}

NOUVEAUX EXTRAITS RÉCUPÉRÉS :
{new_chunks_formatted}

Affine le différentiel en intégrant ces nouvelles données.
Explique pourquoi chaque rang a changé (ou n'a pas changé).
Retourne le différentiel mis à jour au même format JSON.
"""

# ── Antibiotherapy Agent ──────────────────────────────────────

ANTIBIOTHERAPY_PROMPT = """\
DIAGNOSTIC RETENU : {confirmed_diagnosis} (CIM-11 : {icd11_code})
CONFIANCE DIAGNOSTIQUE : {diagnostic_confidence}

CONTEXTE PATIENT :
- Âge : {age} ans | Sexe : {sex}
- Poids : {weight_kg} kg
- Grossesse : {pregnancy_status}
- Allergies connues : {allergies}
- Médicaments en cours : {current_medications}

DONNÉES DE CONTEXTE :
- Disponibilité CAME : {formulary_results_formatted}
- Profil AMR local : {amr_results_formatted}
- Interactions médicamenteuses détectées : {ddi_warnings_formatted}
- Catégories de sécurité grossesse : {safety_classes_formatted}

EXTRAITS GUIDELINES RÉCUPÉRÉS :
{retrieved_chunks_formatted}

─────────────────────────────────────────────────────────
Génère le plan thérapeutique complet au format JSON :
{{
  "target_disease": "...",
  "clinical_rationale": "Justification clinique en 3 phrases citant les guidelines",
  "first_line": [
    {{
      "drug_name": "...",
      "generic_name": "...",
      "came_available": true,
      "dose": "...",
      "dose_mg_per_kg": "...",
      "route": "PO|IV|IM|SC|topique",
      "frequency": "...",
      "duration_days": 3,
      "pregnancy_class": "B",
      "ddi_warnings": [],
      "amr_note": "...",
      "monitoring": ["..."],
      "citations": [1, 3]
    }}
  ],
  "second_line": [...],
  "alternatives": [...],
  "contraindicated": [
    {{ "drug": "...", "reason": "..." }}
  ],
  "supportive_care": ["..."],
  "follow_up_guidance": "...",
  "referral_criteria": "...",
  "disclaimer": "⚠️ AIDE À LA DÉCISION UNIQUEMENT — ..."
}}

RÈGLE : si aucun traitement de première ligne n'est disponible au CAME, \
indique-le explicitement et propose uniquement des alternatives disponibles localement.
"""

ANTIBIOTHERAPY_PREGNANCY_ADDENDUM = """\
ATTENTION : Patiente enceinte (trimestre {trimester}).
Filtre supplémentaire obligatoire :
- Exclure catégories FDA D et X
- Exclure tétracyclines, fluoroquinolones, métronidazole T1
- Ajouter note spécifique pour chaque médicament recommandé
- Consulter spécialiste si doute : indiquer "Avis gynécologique recommandé"
"""

# ── Validation Agent ──────────────────────────────────────────

VALIDATION_PROMPT = """\
RÉPONSE À VALIDER (de l'agent {agent_type}) :
{agent_output_json}

CHUNKS SOURCE UTILISÉS :
{source_chunks_formatted}

SESSION LANGUAGE : {session_language}
TYPE DE SORTIE : {output_type}  (diagnostic | antibiotherapy)

Effectue tous les contrôles qualité définis dans tes instructions système.
Retourne UNIQUEMENT un JSON :
{{
  "checks": {{
    "citation_presence":    {{ "verdict": "PASS|FAIL", "details": "..." }},
    "numeric_consistency":  {{ "verdict": "PASS|WARN|FAIL", "details": "...", "discrepancies": [] }},
    "emergency_check":      {{ "verdict": "PASS|BLOCK", "details": "..." }},
    "disclaimer_present":   {{ "verdict": "PASS|FAIL|NA", "details": "..." }},
    "language_check":       {{ "verdict": "PASS|FAIL", "details": "..." }},
    "scope_check":          {{ "verdict": "PASS|WARN", "details": "..." }}
  }},
  "global_verdict": "PASS|WARN|BLOCK",
  "annotations": ["Note 1 visible au clinicien si WARN", "..."],
  "block_reason": null
}}
"""

# ═══════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════

def format_patient_context(ctx: dict) -> str:
    """Render PatientContext dict into compact clinical French summary."""
    lines = [
        f"• Âge/Sexe : {ctx.get('age_years', 'NR')} ans / {ctx.get('sex', 'NR')}",
        f"• Région : {ctx.get('region', 'NR')}",
        f"• Plainte principale : {ctx.get('chief_complaint', 'NR')}",
        f"• Symptômes : {', '.join(s.get('normalized', s.get('text', '')) for s in ctx.get('symptoms', []))}",
        f"• Début : {ctx.get('symptom_onset_days', 'NR')} jour(s)",
    ]
    vs = ctx.get("vital_signs", {})
    if vs:
        lines.append(
            f"• Signes vitaux : T°{vs.get('temp_c', '?')}°C, "
            f"TA {vs.get('bp_systolic', '?')}/{vs.get('bp_diastolic', '?')} mmHg, "
            f"FC {vs.get('hr', '?')}/min, SpO2 {vs.get('spo2', '?')}%"
        )
    labs = ctx.get("lab_results", [])
    if labs:
        lines.append("• Biologie : " + " | ".join(
            f"{l.get('name', '?')}={l.get('value', '?')}{l.get('unit', '')}"
            for l in labs
        ))
    if ctx.get("pregnancy_status") not in (None, "not_pregnant", "unknown"):
        lines.append(f"• Grossesse : {ctx['pregnancy_status']}")
    if ctx.get("allergies"):
        lines.append(f"• Allergies : {', '.join(a.get('drug', '') for a in ctx['allergies'])}")
    if ctx.get("current_medications"):
        lines.append(f"• Traitements en cours : {', '.join(m.get('name', '') for m in ctx['current_medications'])}")
    return "\n".join(lines)


def format_chunks(chunks: list[dict], max_chars_per_chunk: int = 600) -> str:
    """Render retrieved chunks as numbered references for the prompt."""
    parts = []
    for i, c in enumerate(chunks, start=1):
        text = c.get("chunk_text", "")[:max_chars_per_chunk]
        parts.append(
            f"[REF{i}] {c.get('source_title', 'Source inconnue')} — "
            f"{c.get('section', '')} p.{c.get('page', '?')} "
            f"({c.get('source_version', '')}, {c.get('source_date', '')})\n"
            f"{text}"
        )
    return "\n\n".join(parts)


def format_epid_priors(priors: dict[str, float]) -> str:
    """Format epidemiological priors as a readable list."""
    DISEASE_NAMES = {
        "1F40": "Paludisme (P. falciparum)",
        "1C1A": "Méningite à méningocoque",
        "1A00": "Choléra",
        "1A07": "Fièvre typhoïde",
        "1D2Z": "Dengue",
        "1D6Y": "Fièvre de Lassa",
    }
    lines = []
    for icd, prob in sorted(priors.items(), key=lambda x: -x[1]):
        name = DISEASE_NAMES.get(icd, icd)
        bar = "█" * int(prob * 10) + "░" * (10 - int(prob * 10))
        lines.append(f"  {name}: {bar} {prob:.0%}")
    return "\n".join(lines) if lines else "  Aucun prior disponible"


def format_ddi_warnings(warnings: list[dict]) -> str:
    if not warnings:
        return "Aucune interaction détectée"
    severity_icons = {
        "contraindicated": "🚫",
        "major": "⛔",
        "moderate": "⚠️",
        "minor": "ℹ️",
    }
    lines = []
    for w in warnings:
        icon = severity_icons.get(w.get("severity", "minor"), "ℹ️")
        lines.append(
            f"{icon} {w['drug_a']} × {w['drug_b']} [{w['severity'].upper()}] : "
            f"{w['clinical_effect']} — {w['management']}"
        )
    return "\n".join(lines)


def format_amr_results(profiles: list[dict]) -> str:
    if not profiles:
        return "Aucune donnée AMR disponible"
    lines = []
    for p in profiles:
        pct = f"{p['resistance_pct']:.0%}" if p.get("resistance_pct") is not None else "N/D"
        lines.append(
            f"  • {p['drug']} vs {p['pathogen']} ({p['region']}) : "
            f"Résistance {pct} [{p['confidence']}] — {p['recommendation']}"
        )
    return "\n".join(lines)


def format_formulary_results(results: list[dict]) -> str:
    if not results:
        return "Aucune donnée formulaire"
    lines = []
    for r in results:
        status = "✅ Disponible" if r.get("available") else "❌ Indisponible"
        forms = ", ".join(r.get("dosage_forms") or [])
        lines.append(f"  • {r['generic_name']} : {status} | Formes : {forms or 'N/D'}")
    return "\n".join(lines)