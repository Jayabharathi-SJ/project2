from typing import List

from pydantic import BaseModel, Field


class LegalDocument(BaseModel):
    """
    Structured representation of a legal document chunk
    used by the Virtual CFO legal RAG system.
    """

    document_id: str = Field(
        ...,
        min_length=1,
    )

    title: str = Field(
        ...,
        min_length=1,
    )

    content: str = Field(
        ...,
        min_length=1,
    )

    source: str = Field(
        ...,
        min_length=1,
    )

    topic: str = Field(
        ...,
        min_length=1,
    )

    page_number: int = Field(
        ...,
        gt=0,
    )

    keywords: List[str] = Field(
        default_factory=list,
    )