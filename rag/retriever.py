from typing import List, Dict, Any

from qdrant_client import QdrantClient

from rag.qdrant_store import search_legal_documents


def retrieve_legal_context(
    client: QdrantClient,
    query: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant legal documents from Qdrant.
    """

    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if limit <= 0:
        raise ValueError("Limit must be greater than zero.")

    results = search_legal_documents(
        client=client,
        query=query,
        limit=limit,
    )

    contexts = []

    for result in results:
        contexts.append(
            {
                "document_id": result["document_id"],
                "content": result["content"],
                "source": result["source"],
                "page_number": result["page_number"],
                "score": result["score"],
            }
        )

    return contexts