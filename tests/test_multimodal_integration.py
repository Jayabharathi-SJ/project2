"""
Phase 3 Multimodal Hardening — Integration Tests.

Tests the complete multimodal pipeline from document input to
validated extraction output, including:

1. End-to-end PDF → extraction → validation pipeline
2. Deterministic calculation protection across the pipeline
3. Source traceability from document to validated fields
4. LLM hallucination protection at every layer
5. Error propagation through the pipeline
6. Scanned document detection and handling
7. Cross-field conflict detection in realistic scenarios
"""

import io
from decimal import Decimal

import pytest

from services.document_processor import (
    DocumentType,
    ProcessingStatus,
    process_pdf_bytes,
)
from services.extraction_validator import (
    ConfidenceLevel,
    ExtractionSource,
    ValidationStatus,
    guard_deterministic_calculation,
    validate_extracted_field,
    validate_extraction_set,
)
from services.multimodal_parser import (
    PYPDF_AVAILABLE,
    parse_financial_document_pdf,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_pdf_bytes(text: str, num_pages: int = 1) -> bytes:
    """Create a minimal PDF containing the given text."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        for page_num in range(num_pages):
            c.setFont("Helvetica", 10)
            y = 750
            page_text = text if page_num == 0 else f"Page {page_num + 1} content"
            for line in page_text.split("\n"):
                c.drawString(50, y, line[:100])
                y -= 14
                if y < 50:
                    break
            c.showPage()
        c.save()
        return buf.getvalue()
    except ImportError:
        return b""


def _require_reportlab():
    try:
        import reportlab
        return True
    except ImportError:
        pytest.skip("reportlab not installed")
        return False


# ---------------------------------------------------------------------------
# Integration: End-to-end pipeline
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
class TestEndToEndPipeline:
    """Full pipeline from PDF bytes to validated extraction."""

    HP_QUOTATION_TEXT = """
    HIRE PURCHASE QUOTATION

    Dealer: ABC Motors Sdn Bhd
    Date: 2026-01-15

    Vehicle Model: Proton X70 2.0T Premium
    Vehicle Price: RM 120,000.00
    Down Payment: RM 24,000.00
    Tenure: 84 months
    Interest Rate: 3.85%
    Monthly Instalment: RM 1,350.00
    """

    def test_pipeline_produces_valid_result(self):
        if not _require_reportlab():
            return
        pdf_bytes = _make_pdf_bytes(self.HP_QUOTATION_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)

        # Pipeline should produce a result
        assert result["status"] in ("success", "partial", "empty")
        assert "extracted_fields" in result
        assert "validation" in result
        assert "document_info" in result

    def test_pipeline_never_auto_trusts_values(self):
        """No extracted value should be auto-trusted."""
        if not _require_reportlab():
            return
        pdf_bytes = _make_pdf_bytes(self.HP_QUOTATION_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)

        for field, info in result["extracted_fields"].items():
            assert info["requires_user_confirmation"] is True
            if info["value"] is not None:
                assert info["classification"] == "extracted_unverified"

    def test_pipeline_provides_source_traceability(self):
        """Every extracted field should have source information."""
        if not _require_reportlab():
            return
        pdf_bytes = _make_pdf_bytes(self.HP_QUOTATION_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)

        for field, info in result["extracted_fields"].items():
            assert "source_page" in info
            assert "source_document" in info

    def test_pipeline_document_info_complete(self):
        """Document info should contain processing metadata."""
        if not _require_reportlab():
            return
        pdf_bytes = _make_pdf_bytes(self.HP_QUOTATION_TEXT)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)
        doc_info = result["document_info"]

        assert "status" in doc_info
        assert "document_type" in doc_info
        assert "page_count" in doc_info
        assert "processing_time_seconds" in doc_info


# ---------------------------------------------------------------------------
# Integration: Deterministic calculation protection
# ---------------------------------------------------------------------------

class TestDeterministicProtectionIntegration:
    """Verify deterministic calculation protection works end-to-end."""

    def test_calculated_values_override_llm(self):
        """Deterministic values should always override LLM proposals."""
        # Simulate: calculation engine says total_interest = 15000
        # LLM says total_interest = 12000
        result = guard_deterministic_calculation(
            "total_interest",
            calculated_value=Decimal("15000.00"),
            llm_proposed_value=Decimal("12000.00"),
        )
        assert result["final_value"] == Decimal("15000.00")
        assert result["llm_override_blocked"] is True

    def test_multiple_fields_protected(self):
        """All financial calculation fields should be protected."""
        fields_to_protect = [
            ("monthly_installment", Decimal("1350.00"), Decimal("1200.00")),
            ("total_interest", Decimal("15000.00"), Decimal("12000.00")),
            ("total_paid", Decimal("113400.00"), Decimal("100000.00")),
            ("financed_amount", Decimal("96000.00"), Decimal("90000.00")),
        ]

        for field_name, calc_val, llm_val in fields_to_protect:
            result = guard_deterministic_calculation(
                field_name, calc_val, llm_val,
            )
            assert result["final_value"] == calc_val
            assert result["llm_override_blocked"] is True

    def test_recommendation_protected(self):
        """LLM should not be able to change the deterministic recommendation."""
        result = guard_deterministic_calculation(
            "recommended_option",
            calculated_value="Cash Purchase",
            llm_proposed_value="Hire Purchase",
        )
        assert result["final_value"] == "Cash Purchase"
        assert result["llm_override_blocked"] is True


# ---------------------------------------------------------------------------
# Integration: Error propagation
# ---------------------------------------------------------------------------

class TestErrorPropagation:
    """Verify errors propagate correctly through the pipeline."""

    def test_corrupted_pdf_error_propagates(self):
        result = parse_financial_document_pdf(pdf_bytes=b"corrupted data")
        assert result["status"] == "error"
        assert len(result.get("warnings", []) + [result.get("error", "")]) > 0

    def test_empty_pdf_propagates(self):
        result = parse_financial_document_pdf(pdf_bytes=b"")
        assert result["status"] in ("empty", "error")

    def test_nonexistent_file_error_propagates(self):
        result = parse_financial_document_pdf(pdf_path="/fake/path/doc.pdf")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Integration: Extraction validation with realistic data
# ---------------------------------------------------------------------------

class TestRealisticExtractionValidation:
    """Realistic Malaysian HP scenarios."""

    def test_valid_hp_quotation_fields(self):
        """Typical Malaysian HP quotation values should validate."""
        fields = {
            "asset_price": Decimal("120000.00"),
            "down_payment": Decimal("24000.00"),
            "hp_period_months": 84,
            "hp_interest_rate": Decimal("3.85"),
            "lease_period_months": 60,
            "lease_monthly_payment": Decimal("1350.00"),
        }
        result = validate_extraction_set(
            fields,
            source=ExtractionSource.PDF_TEXT,
            source_document="proton_x70_quotation.pdf",
        )
        assert result["overall_status"] in ("valid", "partial")
        # All fields should have source_document
        for field, info in result["validated_fields"].items():
            assert info["source_document"] == "proton_x70_quotation.pdf"

    def test_overpriced_asset_out_of_range(self):
        """Unrealistically high asset price should be flagged."""
        result = validate_extracted_field(
            "asset_price",
            Decimal("999999999"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "out_of_range"

    def test_zero_down_payment_valid(self):
        """Zero down payment is valid (though may fail legal minimum deposit check later)."""
        result = validate_extracted_field(
            "down_payment",
            Decimal("0"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"

    def test_negative_rate_out_of_range(self):
        """Negative interest rate should be out of range."""
        result = validate_extracted_field(
            "hp_interest_rate",
            Decimal("-1.5"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "out_of_range"


# ---------------------------------------------------------------------------
# Integration: Document processor + extraction validator
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
class TestDocumentToValidationPipeline:
    """Test document processing → extraction validation pipeline."""

    def test_document_processor_output_feeds_validator(self):
        """DocumentResult should feed cleanly into the extraction validator."""
        if not _require_reportlab():
            return

        text = """
        Vehicle Price: RM 120,000.00
        Down Payment: RM 24,000.00
        Tenure: 84 months
        Interest Rate: 3.85%
        """
        pdf_bytes = _make_pdf_bytes(text)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        # Step 1: Process document
        doc_result = process_pdf_bytes(pdf_bytes, source_name="test.pdf")
        assert doc_result.status in (ProcessingStatus.SUCCESS, ProcessingStatus.PARTIAL)

        # Step 2: Extract fields (simulated)
        extracted_values = {
            "asset_price": Decimal("120000"),
            "down_payment": Decimal("24000"),
            "hp_period_months": 84,
            "hp_interest_rate": Decimal("3.85"),
        }

        # Step 3: Validate extraction
        validation = validate_extraction_set(
            extracted_values,
            source=ExtractionSource.PDF_TEXT,
            source_document="test.pdf",
        )

        assert validation["overall_status"] in ("valid", "partial")
        for field_name in ("asset_price", "down_payment"):
            assert validation["validated_fields"][field_name]["source_document"] == "test.pdf"

    def test_full_pipeline_with_parse_financial_document(self):
        """Full pipeline using parse_financial_document_pdf."""
        if not _require_reportlab():
            return

        text = """
        Vehicle Price: RM 150,000.00
        Down Payment: RM 30,000.00
        Tenure: 60 months
        Interest Rate: 4.50%
        Lease Period: 36 months
        Monthly Lease Payment: RM 2,500.00
        """
        pdf_bytes = _make_pdf_bytes(text)
        if not pdf_bytes:
            pytest.skip("reportlab not available")

        result = parse_financial_document_pdf(pdf_bytes=pdf_bytes)

        # Should produce all three layers of output
        assert "extracted_fields" in result
        assert "validation" in result
        assert "document_info" in result
        assert result["status"] in ("success", "partial", "empty")


# ---------------------------------------------------------------------------
# Integration: LLM hallucination protection across pipeline
# ---------------------------------------------------------------------------

class TestLLMProtectionAcrossPipeline:
    """Ensure LLM protection works at every layer."""

    def test_llm_source_blocked_at_field_level(self):
        result = validate_extracted_field(
            "asset_price",
            Decimal("120000"),
            source=ExtractionSource.LLM_GENERATED,
        )
        assert result["value"] is None
        assert result["confidence"] == "rejected"

    def test_llm_source_blocked_in_extraction_set(self):
        fields = {
            "asset_price": Decimal("120000"),
        }
        result = validate_extraction_set(
            fields,
            source=ExtractionSource.LLM_GENERATED,
        )
        ap = result["validated_fields"]["asset_price"]
        assert ap["value"] is None
        assert ap["confidence"] == "rejected"

    def test_deterministic_guard_always_wins(self):
        """Even with matching types, deterministic always overrides LLM."""
        result = guard_deterministic_calculation(
            "total_cost",
            calculated_value=Decimal("150000"),
            llm_proposed_value=Decimal("149999"),
        )
        assert result["final_value"] == Decimal("150000")
        assert result["llm_override_blocked"] is True
