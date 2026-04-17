from pydantic import BaseModel


class ConsultationRequest(BaseModel):
    """Requête de consultation médicale."""
    symptoms: list[str]
    patient_age: int | None = None
    patient_weight: float | None = None
    region: str = "Lomé"
    medical_history: list[str] = []
    current_medications: list[str] = []


class DiagnosticResult(BaseModel):
    """Résultat du raisonnement diagnostique."""
    diagnostics: list[dict]
    confidence: float
    reasoning: str


class TreatmentRecommendation(BaseModel):
    """Recommandation thérapeutique."""
    medication: str
    dosage: str
    duration: str
    availability: str
    alternatives: list[str]
    source: str  # OMS, PNLP, etc.


class ConsultationResponse(BaseModel):
    """Réponse complète de consultation."""
    diagnostic: DiagnosticResult
    treatments: list[TreatmentRecommendation]
    warnings: list[str]
    references: list[str]
