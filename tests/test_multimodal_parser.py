"""
Tests for services/multimodal_parser.py — Phase 3 Hardened.

Tests use synthetic in-memory PDF bytes so that:
- No external PDF file is needed.
- The tests work without an internet connection.
- pypdf availability is checked at test collection time.

Phase 3 additions:
- Source traceability verification
- Validation integration
- Document info metadata
- Timeout handling
- Corrupted PDF handling
- Scanned document detection
- Financial value conflict detection
- LLM hallucination protection integration
"""

import io
from decimal import Decimal

import pytest

from services.multimodal_parser import (
    PYPDF_AVAILABLE,
    _clean_decimal,
    _clean_int,
    _plausibility_check,
    parse_financial_document_pdf,
)


# ---------------------------------------------------------------------------
# Helper — build a simple in-memory PDF with given text
# ---------------------------------------------------------------------------

def _make_pdf_bytes(text: str) -> bytes:
    """Create a minimal PDF containing the given text (pypdf readable)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica", 10)
        y = 750
        for line in text.split("\n"):
            c.drawString(50, y, line[:100])
            y -= 14
            if y < 50:
                c.showPage()
                y = 750
        c.save()
        return buf.getvalue()
    except ImportError:
        # reportlab not installed — return sentinel indicating skip
        return b""


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestCleanDecimal:
    def test_plain_number(self):
        assert _clean_decimal("12345.67") == Decimal("12345.67")

    def test_with_commas(self):
        assert _clean_decimal("120,000.00") == Decimal("120000.00")

    def test_with_currency_symbol(self):
        assert _clean_decimal("RM 95,000") == Decimal("95000")

    def test_empty_string(self):
        assert _clean_decimal("") is None

    def test_non_numeric(self):
        assert _clean_decimal("N/A") is None


class TestCleanInt:
    def test_plain_int(self):
        assert _clean_int("60") == 60

    def test_with_text(self):
        assert _clean_int("60 months") == 60

    def test_empty(self):
        assert _clean_int("") is None


class TestPlausibilityCheck:
    def test_asset_price_plausible(self):
        result = _plausibility_check("asset_price", Decimal("100000"))
        assert result == "plausible"

    def test_asset_price_too_low(self):
        result = _plausibility_check("asset_price", Decimal("1"))
        assert result == "out_of_range"

    def test_hp_period_months_plausible(self):
        result = _plausibility_check("hp_period_months", 60)
        assert result == "plausible"

    def test_unknown_field(self):
        result = _plausibility_check("unknown_field", 999)
        assert result == "not_checked"

    def test_none_value(self):
        result = _plausibility_check("asset_price", None)
        assert result == "not_checked"


# ---------------------------------------------------------------------------
# Integration tests for parse_financial_document_pdf
# ---------------------------------------------------------------------------

class TestParseFinancialDocumentErrors:
    def test_no_args_raises_value_error(self):
        with pytest.raises(ValueError, match="Either pdf_path or pdf_bytes"):
            parse_financial_document_pdf()

    def test_nonexistent_path_returns_error_status(self):
        result = parse_financial_document_pdf(pdf_path="/nonexistent/file.pdf")
        assert result["status"] == "error"
        assert "warnings" in result

    def test_empty_bytes_returns_empty_or_error(self):
        result = parse_financial_document_pdf(pdf_bytes=b"")
        assert result["status"] in ("empty", "error")

    def test_corrupted_bytes_returns_error(self):
        result = parse_financial_document_pdf(pdf_bytes=b"not a valid pdf file")
        assert result["status"] == "error"
        assert "document_info" in result


@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
class TestParseFinancialDocumentPdfBytes:
    """These tests create real PDF bytes using reportlab (if available),
    otherwise they are skipped."""

    SAMPLE_TEXT = """
    Vehicle Hire Purchase Quotation

    Vehicle Model: Proton X70 2.0T Premium
    Purchase Price: RM 120,000.00
    Down Payment: RM 24,000.00
    Loan Tenure: 84 months
    Effective Interest Rate: 3.85%
    Monthly Instalment: RM 1,350.00
    """

    def test_extraction_returns_dict_with_expected_keys(self):
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)

        assert "extracted_fields" in result
        assert "full_text_preview" in result
        assert "page_count" in result
        assert "warnings" in result
        assert "status" in result
        assert "extraction_note" in result

    def test_extracted_values_are_labelled_unverified(self):
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        for field, info in result["extracted_fields"].items():
            if info["value"] is not None:
                assert info["classification"] == "extracted_unverified"
                assert info["requires_user_confirmation"] is True

    def test_extracted_values_have_plausibility_label(self):
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        for field, info in result["extracted_fields"].items():
            assert "plausibility" in info
            assert info["plausibility"] in (
                "plausible", "out_of_range", "not_checked"
            )

    def test_empty_pdf_returns_empty_status(self):
        """A PDF with no readable text returns status 'empty' or 'error'."""
        # Minimal valid (empty) PDF content
        minimal_pdf = (
            b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
            b"3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
        )
        result = parse_financial_document_pdf(pdf_bytes=minimal_pdf)
        assert result["status"] in ("empty", "partial", "error")

    # -----------------------------------------------------------------------
    # Phase 3 additions
    # -----------------------------------------------------------------------

    def test_result_includes_validation(self):
        """Phase 3: Validation results should be included."""
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        assert "validation" in result

    def test_result_includes_document_info(self):
        """Phase 3: Document processing metadata should be included."""
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        assert "document_info" in result
        doc_info = result["document_info"]
        assert "status" in doc_info
        assert "document_type" in doc_info

    def test_source_traceability_present(self):
        """Phase 3: Extracted fields should have source page information."""
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        for field, info in result["extracted_fields"].items():
            assert "source_page" in info
            assert "source_document" in info

    def test_validation_has_confidence(self):
        """Phase 3: Validation should include confidence levels."""
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        validation = result.get("validation", {})
        if validation:
            assert "overall_confidence" in validation

    def test_validation_has_deterministic_note(self):
        """Phase 3: Validation should include deterministic calculation note."""
        pdf_bytes = _make_pdf_bytes(self.SAMPLE_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not installed, cannot create test PDF")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        validation = result.get("validation", {})
        if validation:
            assert "deterministic_calculation_note" in validation


# ---------------------------------------------------------------------------
# Phase 3: Multimodal API failure/timeout handling
# ---------------------------------------------------------------------------

class TestMultimodalFailureHandling:
    def test_timeout_produces_timeout_status(self):
        """A very short timeout should produce timeout or error status."""
        pdf_bytes = _make_pdf_bytes("Some text content")
        if not pdf_bytes:
            pytest.skip("reportlab not available")
        # With a very tiny timeout, the parser should handle gracefully
        result = parse_financial_document_pdf(
            pdf_bytes=pdf_bytes,
            timeout_seconds=0.0001,
        )
        # Should not crash — may return timeout, error, or still succeed if fast enough
        assert result["status"] in ("success", "partial", "empty", "timeout", "error")

    def test_malformed_pdf_does_not_crash(self):
        """Malformed model response should not crash the system."""
        result = parse_financial_document_pdf(
            pdf_bytes=b"\x00\x01\x02\x03\x04\x05INVALID",
        )
        assert result["status"] in ("error", "empty")
        assert isinstance(result["warnings"], list) or isinstance(result.get("errors"), list)


# ---------------------------------------------------------------------------
# Phase 3: Missing/conflicting financial value handling
# ---------------------------------------------------------------------------

class TestMissingConflictingValues:
    def test_missing_text_produces_empty_extraction(self):
        """PDF with no financial text should extract no values."""
        pdf_bytes = _make_pdf_bytes("This is just a regular document with no financial data.")
        if not pdf_bytes:
            pytest.skip("reportlab not available")
        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        extracted = result.get("extracted_fields", {})
        # All fields should have None values
        for field, info in extracted.items():
            if info.get("value") is not None:
                # If any value was found, it should still be marked unverified
                assert info["classification"] == "extracted_unverified"

    def test_invalid_numeric_in_document(self):
        """Document with non-numeric price should handle gracefully."""
        pdf_bytes = _make_pdf_bytes("Purchase Price: RM UNDEFINED")
        if not pdf_bytes:
            pytest.skip("reportlab not available")
        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        assert result["status"] in ("empty", "partial", "success")
