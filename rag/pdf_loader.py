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
    Extract text from the legal PDF or pre-extracted guide page by page.
    """
    import re

    # 1. Prefer pre-extracted clean text file to avoid font warnings and encoding anomalies
    txt_path = (
        Path(__file__).resolve().parent
        / "documents"
        / "extracted_guide_text.txt"
    )
    if txt_path.exists():
        try:
            content = txt_path.read_text(encoding="utf-8")
            raw_pages = re.split(r"=== PAGE \d+ ===", content)
            pages = []
            page_num = 1
            for part in raw_pages:
                cleaned = part.strip()
                if cleaned:
                    pages.append({"page_number": page_num, "text": cleaned})
                    page_num += 1
            if pages:
                return pages
        except Exception:
            pass

    # 2. Fall back to pypdf extraction
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