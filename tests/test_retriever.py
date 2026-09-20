from rag.qdrant_store import create_qdrant_client
from rag.retriever import retrieve_legal_context


def test_retrieve_legal_context():
    client = create_qdrant_client()

    results = retrieve_legal_context(
        client=client,
        query="What is the maximum EIR for fixed rate hire-purchase financing?",
        limit=3,
    )

    client.close()

    assert len(results) > 0
    assert len(results) <= 3

    for result in results:
        assert "document_id" in result
        assert "content" in result
        assert "source" in result
        assert "page_number" in result
        assert "score" in result


def test_retrieve_legal_context_relevant_content():
    client = create_qdrant_client()

    results = retrieve_legal_context(
        client=client,
        query="reducing balance method and EIR",
        limit=3,
    )

    client.close()

    assert len(results) > 0

    combined_content = " ".join(
        result["content"].lower()
        for result in results
    )

    assert (
        "reducing balance" in combined_content
        or "eir" in combined_content
    )


def test_empty_query_is_rejected():
    client = create_qdrant_client()

    try:
        retrieve_legal_context(
            client=client,
            query="",
            limit=3,
        )
    except ValueError as exc:
        assert "Query cannot be empty" in str(exc)
    finally:
        client.close()


def test_invalid_limit_is_rejected():
    client = create_qdrant_client()

    try:
        retrieve_legal_context(
            client=client,
            query="EIR",
            limit=0,
        )
    except ValueError as exc:
        assert "Limit must be greater than zero" in str(exc)
    finally:
        client.close()