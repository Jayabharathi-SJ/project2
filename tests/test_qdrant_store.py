from rag.legal_document import LegalDocument
from rag.qdrant_store import (
    create_qdrant_client,
    create_legal_collection,
    get_collection_name,
    index_legal_documents,
)


def test_qdrant_client_creation():
    client = create_qdrant_client()

    assert client is not None


def test_legal_collection_name():
    name = get_collection_name()

    assert name == "legal_documents"


def test_legal_collection_creation():
    client = create_qdrant_client()

    create_legal_collection(client)

    collections = [
        collection.name
        for collection in client.get_collections().collections
    ]

    assert "legal_documents" in collections


def test_legal_document_indexing():
    client = create_qdrant_client()

    document = LegalDocument(
        document_id="HP2026-EIR-001",
        title="Hire-Purchase Amendment Act 2026",
        content="Effective Interest Rate uses reducing balance.",
        source="Bank Negara Malaysia",
        topic="Effective Interest Rate",
        page_number=3,
        keywords=["EIR", "reducing balance"],
    )

    count = index_legal_documents(
        client=client,
        documents=[document],
    )

    assert count == 1