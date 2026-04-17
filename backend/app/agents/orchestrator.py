from app.models.schemas import (
    ConsultationRequest,
    ConsultationResponse,
    DiagnosticResult,
    TreatmentRecommendation,
)
from app.agents.diagnostic_agent import DiagnosticAgent
from app.agents.treatment_agent import TreatmentAgent
from app.agents.resistance_agent import ResistanceAgent


class AgentOrchestrator:
    """Orchestre les agents spécialisés pour produire une réponse complète."""

    def __init__(self):
        self.diagnostic_agent = DiagnosticAgent()
        self.treatment_agent = TreatmentAgent()
        self.resistance_agent = ResistanceAgent()

    async def process(self, request: ConsultationRequest) -> ConsultationResponse:
        """Coordonne le pipeline multi-agents."""
        # 1. Raisonnement diagnostique
        diagnostic = await self.diagnostic_agent.analyze(request)

        # 2. Vérification des résistances locales
        resistance_data = await self.resistance_agent.check(
            diagnostic, request.region
        )

        # 3. Recommandations thérapeutiques
        treatments = await self.treatment_agent.recommend(
            diagnostic, resistance_data, request
        )

        return ConsultationResponse(
            diagnostic=diagnostic,
            treatments=treatments,
            warnings=self._generate_warnings(diagnostic, resistance_data),
            references=self._collect_references(diagnostic, treatments),
        )

    def _generate_warnings(self, diagnostic, resistance_data) -> list[str]:
        """Génère les alertes cliniques."""
        # TODO: implémenter la logique d'alertes
        return []

    def _collect_references(self, diagnostic, treatments) -> list[str]:
        """Collecte les références (OMS, PNLP, etc.)."""
        # TODO: implémenter la collecte de références
        return []

    def get_status(self) -> dict:
        return {
            "diagnostic_agent": "ready",
            "treatment_agent": "ready",
            "resistance_agent": "ready",
        }
