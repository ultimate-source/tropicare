from app.models.schemas import (
    ConsultationRequest,
    DiagnosticResult,
    TreatmentRecommendation,
)
from app.rag.retriever import RAGRetriever


class TreatmentAgent:
    """Agent de recommandation thérapeutique adapté au contexte togolais."""

    def __init__(self):
        self.retriever = RAGRetriever(collection="treatments")

    async def recommend(
        self,
        diagnostic: DiagnosticResult,
        resistance_data: dict,
        request: ConsultationRequest,
    ) -> list[TreatmentRecommendation]:
        """Recommande un traitement selon les directives OMS/PNLP."""
        # TODO: récupérer les protocoles OMS/PNLP via RAG
        # TODO: vérifier la disponibilité locale des médicaments
        # TODO: ajuster selon les données de résistance
        # TODO: adapter la posologie (âge, poids)

        return []
