from rag.pdf_loader import (
    get_pdf_page_count,
    load_pdf_pages,
)


def test_pdf_page_count():
    page_count = get_pdf_page_count()

    assert page_count > 0


def test_pdf_pages_are_loaded():
    pages = load_pdf_pages()

    assert len(pages) > 0
    assert pages[0]["page_number"] == 1


def test_pdf_pages_have_text():
    pages = load_pdf_pages()

    pages_with_text = [
        page
        for page in pages
        if page["text"]
    ]

    assert len(pages_with_text) > 0


def test_pdf_page_structure():
    pages = load_pdf_pages()

    first_page = pages[0]

    assert "page_number" in first_page
    assert "text" in first_page

    assert isinstance(
        first_page["page_number"],
        int,
    )

    assert isinstance(
        first_page["text"],
        str,
    )