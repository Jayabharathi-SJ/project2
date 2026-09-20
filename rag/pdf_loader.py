from pathlib import Path
from typing import List, Dict

from pypdf import PdfReader


PDF_PATH = (
    Path(__file__).resolve().parent
    / "documents"
    / "HP Consumer Guide_EN_2026.pdf"
)


def load_pdf_pages() -> List[Dict]:
    """
    Extract text from the legal PDF page by page.
    """

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Legal PDF not found: {PDF_PATH}"
        )

    reader = PdfReader(str(PDF_PATH))

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""
        text = text.strip()

        pages.append(
            {
                "page_number": page_number,
                "text": text,
            }
        )

    return pages


def get_pdf_page_count() -> int:
    """
    Return the total number of pages in the legal PDF.
    """

    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"Legal PDF not found: {PDF_PATH}"
        )

    reader = PdfReader(str(PDF_PATH))

    return len(reader.pages)