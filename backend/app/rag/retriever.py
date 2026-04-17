from app.config.settings import settings


class RAGRetriever:
    """Récupérateur de documents via ChromaDB pour le contexte RAG."""

    def __init__(self, collection: str):
        self.collection_name = collection
        self._client = None

    def _get_client(self):
        """Initialisation paresseuse du client ChromaDB."""
        if self._client is None:
            import chromadb

            self._client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir
            )
        return self._client

    def _get_collection(self):
        client = self._get_client()
        return client.get_or_create_collection(name=self.collection_name)

    async def query(
        self,
        query: str,
        n_results: int = 5,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        """Recherche les documents les plus pertinents."""
        collection = self._get_collection()

        params = {"query_texts": [query], "n_results": n_results}
        if metadata_filter:
            params["where"] = metadata_filter

        results = collection.query(**params)

        return [
            {"content": doc, "metadata": meta}
            for doc, meta in zip(
                results["documents"][0], results["metadatas"][0]
            )
        ] if results["documents"] and results["documents"][0] else []
