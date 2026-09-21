import os
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from rag.legal_document import LegalDocument

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "legal_documents")
EMBEDDING_DIMENSION = 384


def create_qdrant_client() -> QdrantClient:
    """
    Create a QdrantClient instance using environment configuration.
    Supports local embedded storage (path) or remote cluster (url + api_key).
    """
    qdrant_url = os.getenv("QDRANT_URL")
    if qdrant_url:
        api_key = os.getenv("QDRANT_API_KEY")
        return QdrantClient(url=qdrant_url, api_key=api_key, timeout=5.0)

    path = os.getenv("QDRANT_PATH", "./qdrant_data")
    return QdrantClient(path=path)


def get_collection_name() -> str:
    return COLLECTION_NAME


def check_qdrant_health() -> Tuple[bool, str]:
    """
    Fast health probe for Qdrant vector store.
    """
    try:
        client = create_qdrant_client()
        try:
            client.get_collections()
            return True, "Ready"
        finally:
            client.close()
    except Exception as exc:
        return False, f"Qdrant unavailable: {type(exc).__name__}"


def create_legal_collection(client: QdrantClient) -> None:
    existing_collections = [
        collection.name
        for collection in client.get_collections().collections
    ]

    if COLLECTION_NAME not in existing_collections:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )


def index_legal_documents(
    client: QdrantClient,
    documents: List[LegalDocument],
) -> int:
    from rag.embedding import generate_embedding

    create_legal_collection(client)

    points = []

    for index, document in enumerate(documents):
        vector = generate_embedding(document.content)

        point = PointStruct(
            id=index + 1,
            vector=vector,
            payload={
                "document_id": document.document_id,
                "title": document.title,
                "content": document.content,
                "source": document.source,
                "topic": document.topic,
                "page_number": document.page_number,
                "keywords": document.keywords,
            },
        )

        points.append(point)

    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )

    return len(points)


def search_legal_documents(
    client: QdrantClient,
    query: str,
    limit: int = 3,
) -> List[dict]:
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    if limit <= 0:
        raise ValueError("Limit must be greater than zero.")

    from rag.embedding import generate_embedding

    query_vector = generate_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    )

    documents = []

    for result in results.points:
        documents.append(
            {
                "score": result.score,
                "document_id": result.payload["document_id"],
                "title": result.payload["title"],
                "content": result.payload["content"],
                "source": result.payload["source"],
                "topic": result.payload["topic"],
                "page_number": result.payload["page_number"],
                "keywords": result.payload["keywords"],
            }
        )

    return documents