from typing import List

from rag.legal_document import LegalDocument
from rag.pdf_loader import load_pdf_pages


def create_legal_documents() -> List[LegalDocument]:
    pages = load_pdf_pages()

    documents = []

    for page in pages:
        text = page["text"].strip()

        if not text:
            continue

        document = LegalDocument(
            document_id=f"HP2026-PAGE-{page['page_number']}",
            title="Consumer Guide: Five Key Highlights of the Hire-Purchase (Amendment) Act 2026",
            content=text,
            source="Bank Negara Malaysia Consumer Guide 2026",
            topic="Hire-Purchase (Amendment) Act 2026",
            page_number=page["page_number"],
            keywords=[
                "hire-purchase",
                "EIR",
                "reducing balance",
                "Malaysia",
            ],
        )

        documents.append(document)

    return documents