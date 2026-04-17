from app.models.schemas import ConsultationRequest, DiagnosticResult
from app.rag.retriever import RAGRetriever


class DiagnosticAgent:
    """Agent de raisonnement diagnostique fondé sur les preuves."""

    def __init__(self):
        self.retriever = RAGRetriever(collection="diagnostics")

    async def analyze(self, request: ConsultationRequest) -> DiagnosticResult:
        """Analyse les symptômes et produit un raisonnement diagnostique."""
        # Récupération du contexte pertinent via RAG
        context = await self.retriever.query(
            query=", ".join(request.symptoms),
            metadata_filter={"region": request.region},
        )

        # TODO: appel LLM avec contexte RAG + épidémiologie Togo
        # TODO: raisonnement différentiel (paludisme, typhoïde, etc.)

        return DiagnosticResult(
            diagnostics=[],
            confidence=0.0,
            reasoning="Non implémenté",
        )
