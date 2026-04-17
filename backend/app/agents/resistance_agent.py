from app.models.schemas import DiagnosticResult
from app.rag.retriever import RAGRetriever


class ResistanceAgent:
    """Agent de vérification des résistances antimicrobiennes locales."""

    def __init__(self):
        self.retriever = RAGRetriever(collection="resistance")

    async def check(self, diagnostic: DiagnosticResult, region: str) -> dict:
        """Vérifie les données de résistance pour la région donnée."""
        # TODO: interroger la base de données de résistance locale
        # TODO: croiser avec les données OMS sur la résistance au Togo

        return {
            "region": region,
            "resistance_patterns": [],
            "last_updated": None,
        }
