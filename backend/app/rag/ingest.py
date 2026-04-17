"""Script d'ingestion de documents dans la base vectorielle."""

import chromadb
from app.config.settings import settings


def ingest_documents(collection_name: str, documents: list[dict]):
    """Ingère des documents dans ChromaDB.

    Args:
        collection_name: nom de la collection (diagnostics, treatments, resistance)
        documents: liste de dicts avec 'id', 'content', 'metadata'
    """
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    collection = client.get_or_create_collection(name=collection_name)

    collection.add(
        ids=[doc["id"] for doc in documents],
        documents=[doc["content"] for doc in documents],
        metadatas=[doc.get("metadata", {}) for doc in documents],
    )

    print(f"{len(documents)} documents ingérés dans '{collection_name}'")


if __name__ == "__main__":
    # Exemple : ingestion de documents OMS/PNLP
    sample_docs = [
        {
            "id": "oms-palu-001",
            "content": "Directives OMS pour le traitement du paludisme...",
            "metadata": {"source": "OMS", "type": "guideline", "region": "Togo"},
        },
    ]
    ingest_documents("treatments", sample_docs)
