from rag.legal_document import LegalDocument


def test_legal_document_creation():
    document = LegalDocument(
        document_id="HP2026-EIR-001",
        title="Hire-Purchase Amendment Act 2026",
        content="Effective Interest Rate uses reducing balance.",
        source="Bank Negara Malaysia",
        topic="Effective Interest Rate",
        page_number=3,
        keywords=[
            "EIR",
            "reducing balance",
        ],
    )

    assert document.document_id == "HP2026-EIR-001"
    assert document.title == "Hire-Purchase Amendment Act 2026"
    assert document.page_number == 3


def test_legal_document_keywords():
    document = LegalDocument(
        document_id="HP2026-RB-001",
        title="Reducing Balance",
        content="Interest is calculated on outstanding principal.",
        source="Bank Negara Malaysia",
        topic="Reducing Balance",
        page_number=4,
        keywords=[
            "reducing balance",
            "interest",
            "principal",
        ],
    )

    assert "reducing balance" in document.keywords
    assert "interest" in document.keywords