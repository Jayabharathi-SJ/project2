"""
Tests for services/extraction_validator.py — Phase 3 Multimodal Hardening.

Covers:
- Individual field validation (decimal, integer, string)
- Range/plausibility checks
- Type error handling
- Missing field detection
- LLM hallucination blocking
- Cross-field conflict detection (down_payment > asset_price)
- Extraction set validation
- Deterministic calculation protection
- Source traceability preservation
- Confidence level assignment
"""

from decimal import Decimal

import pytest

from services.extraction_validator import (
    ConfidenceLevel,
    ExtractionSource,
    ValidationStatus,
    guard_deterministic_calculation,
    validate_extracted_field,
    validate_extraction_set,
)


# ---------------------------------------------------------------------------
# Tests: Individual field validation
# ---------------------------------------------------------------------------

class TestValidateExtractedFieldDecimal:
    """Test validation of decimal financial fields."""

    def test_valid_asset_price(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"
        assert result["value"] == Decimal("120000")
        assert result["requires_user_confirmation"] is True

    def test_asset_price_out_of_range_low(self):
        result = validate_extracted_field(
            "asset_price", Decimal("1"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "out_of_range"
        assert len(result["errors"]) > 0

    def test_asset_price_out_of_range_high(self):
        result = validate_extracted_field(
            "asset_price", Decimal("99999999"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "out_of_range"

    def test_invalid_decimal_string(self):
        result = validate_extracted_field(
            "asset_price", "not_a_number",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "type_error"
        assert result["value"] is None
        assert result["confidence"] == "rejected"

    def test_none_value_is_missing(self):
        result = validate_extracted_field(
            "asset_price", None,
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "missing"
        assert result["confidence"] == "missing"

    def test_empty_string_is_missing(self):
        result = validate_extracted_field(
            "asset_price", "",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "missing"


class TestValidateExtractedFieldInteger:
    """Test validation of integer financial fields."""

    def test_valid_hp_period_months(self):
        result = validate_extracted_field(
            "hp_period_months", 84,
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"
        assert result["value"] == 84

    def test_hp_period_out_of_range(self):
        result = validate_extracted_field(
            "hp_period_months", 500,
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "out_of_range"

    def test_hp_period_string_coercion(self):
        result = validate_extracted_field(
            "hp_period_months", "60",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"
        assert result["value"] == 60

    def test_hp_period_invalid_string(self):
        result = validate_extracted_field(
            "hp_period_months", "abc",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "type_error"


class TestValidateExtractedFieldString:
    """Test validation of string fields."""

    def test_valid_asset_name(self):
        result = validate_extracted_field(
            "asset_name", "Proton X70",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"
        assert result["value"] == "Proton X70"

    def test_empty_asset_name(self):
        result = validate_extracted_field(
            "asset_name", "",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "missing"


# ---------------------------------------------------------------------------
# Tests: LLM hallucination blocking
# ---------------------------------------------------------------------------

class TestLLMHallucinationBlocking:
    """Test that LLM-generated financial values are rejected."""

    def test_llm_generated_value_rejected(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.LLM_GENERATED,
        )
        assert result["status"] == "invalid"
        assert result["confidence"] == "rejected"
        assert result["value"] is None
        assert any("LLM" in e for e in result["errors"])

    def test_llm_generated_interest_rate_rejected(self):
        result = validate_extracted_field(
            "hp_interest_rate", Decimal("5.5"),
            source=ExtractionSource.LLM_GENERATED,
        )
        assert result["status"] == "invalid"
        assert result["value"] is None

    def test_user_input_accepted(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.USER_INPUT,
        )
        assert result["status"] == "valid"
        assert result["value"] == Decimal("120000")

    def test_user_confirmed_high_confidence(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.USER_CONFIRMED,
        )
        assert result["status"] == "valid"
        assert result["confidence"] == "high"
        assert result["requires_user_confirmation"] is False


# ---------------------------------------------------------------------------
# Tests: Source traceability
# ---------------------------------------------------------------------------

class TestSourceTraceability:
    """Test that source information is preserved."""

    def test_page_number_preserved(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.PDF_TEXT,
            source_page=3,
            source_document="quotation.pdf",
        )
        assert result["source_page"] == 3
        assert result["source_document"] == "quotation.pdf"

    def test_source_type_preserved(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.PDF_TABLE,
        )
        assert result["source"] == "pdf_table_extraction"


# ---------------------------------------------------------------------------
# Tests: Extraction set validation
# ---------------------------------------------------------------------------

class TestValidateExtractionSet:
    """Test validation of a complete set of extracted fields."""

    def test_complete_valid_set(self):
        fields = {
            "asset_price": Decimal("120000"),
            "down_payment": Decimal("24000"),
            "hp_period_months": 84,
            "hp_interest_rate": Decimal("3.85"),
            "lease_period_months": 60,
            "lease_monthly_payment": Decimal("1350"),
        }
        result = validate_extraction_set(
            fields, source=ExtractionSource.PDF_TEXT,
        )
        assert result["overall_status"] in ("valid", "partial")
        assert result["requires_user_confirmation"] is True
        assert "deterministic_calculation_note" in result

    def test_missing_required_fields_detected(self):
        fields = {
            "asset_price": Decimal("120000"),
            # Missing: down_payment, hp_period_months, etc.
        }
        result = validate_extraction_set(
            fields, source=ExtractionSource.PDF_TEXT,
        )
        assert len(result["missing_required"]) > 0
        assert "down_payment" in result["missing_required"]
        assert len(result["warnings"]) > 0

    def test_conflicting_values_detected(self):
        """Down payment exceeding asset price should be flagged as conflict."""
        fields = {
            "asset_price": Decimal("100000"),
            "down_payment": Decimal("200000"),  # > asset price
            "hp_period_months": 60,
            "hp_interest_rate": Decimal("5.0"),
            "lease_period_months": 60,
            "lease_monthly_payment": Decimal("1500"),
        }
        result = validate_extraction_set(
            fields, source=ExtractionSource.PDF_TEXT,
        )
        assert len(result["conflicts"]) > 0
        assert any("exceeds" in c.lower() for c in result["conflicts"])

    def test_all_invalid_produces_invalid_status(self):
        fields = {
            "asset_price": "garbage",
            "down_payment": "not_number",
        }
        result = validate_extraction_set(
            fields, source=ExtractionSource.PDF_TEXT,
        )
        # Has type errors, so status should reflect issues
        assert result["overall_confidence"] in ("rejected", "low", "missing")

    def test_extraction_dict_format_supported(self):
        """Should support extraction result dicts with 'value' key."""
        fields = {
            "asset_price": {"value": Decimal("120000"), "source_page": 1},
            "down_payment": {"value": Decimal("24000"), "source_page": 2},
        }
        result = validate_extraction_set(
            fields, source=ExtractionSource.PDF_TEXT,
        )
        assert result["validated_fields"]["asset_price"]["value"] == Decimal("120000")

    def test_empty_extraction_set(self):
        result = validate_extraction_set(
            {}, source=ExtractionSource.PDF_TEXT,
        )
        assert len(result["missing_required"]) > 0
        assert result["overall_status"] in ("invalid", "partial")


# ---------------------------------------------------------------------------
# Tests: Deterministic calculation protection
# ---------------------------------------------------------------------------

class TestDeterministicCalculationProtection:
    """Test that LLM cannot override deterministic calculations."""

    def test_matching_values_no_block(self):
        result = guard_deterministic_calculation(
            "total_interest",
            calculated_value=Decimal("15000.00"),
            llm_proposed_value=Decimal("15000.00"),
        )
        assert result["llm_override_blocked"] is False
        assert result["final_value"] == Decimal("15000.00")
        assert result["warning"] is None

    def test_different_values_blocks_llm(self):
        result = guard_deterministic_calculation(
            "total_interest",
            calculated_value=Decimal("15000.00"),
            llm_proposed_value=Decimal("12000.00"),  # LLM hallucinated
        )
        assert result["llm_override_blocked"] is True
        assert result["final_value"] == Decimal("15000.00")
        assert result["warning"] is not None
        assert "deterministic" in result["warning"].lower()

    def test_llm_none_value_no_block(self):
        result = guard_deterministic_calculation(
            "monthly_installment",
            calculated_value=Decimal("1500.00"),
            llm_proposed_value=None,
        )
        assert result["llm_override_blocked"] is False
        assert result["final_value"] == Decimal("1500.00")

    def test_calculated_none_preserved(self):
        result = guard_deterministic_calculation(
            "field",
            calculated_value=None,
            llm_proposed_value=Decimal("999"),
        )
        assert result["final_value"] is None

    def test_string_comparison_fallback(self):
        """Non-decimal values should still be protected."""
        result = guard_deterministic_calculation(
            "recommendation",
            calculated_value="Cash Purchase",
            llm_proposed_value="Hire Purchase",
        )
        assert result["llm_override_blocked"] is True
        assert result["final_value"] == "Cash Purchase"


# ---------------------------------------------------------------------------
# Tests: Confidence levels
# ---------------------------------------------------------------------------

class TestConfidenceLevels:
    def test_pdf_text_gets_medium_confidence(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["confidence"] == "medium"

    def test_user_confirmed_gets_high_confidence(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.USER_CONFIRMED,
        )
        assert result["confidence"] == "high"

    def test_unknown_source_gets_low_confidence(self):
        result = validate_extracted_field(
            "asset_price", Decimal("120000"),
            source=ExtractionSource.UNKNOWN,
        )
        assert result["confidence"] == "low"

    def test_out_of_range_gets_low_confidence(self):
        result = validate_extracted_field(
            "asset_price", Decimal("1"),
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["confidence"] == "low"

    def test_type_error_gets_rejected_confidence(self):
        result = validate_extracted_field(
            "asset_price", "invalid",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["confidence"] == "rejected"


# ---------------------------------------------------------------------------
# Tests: Unknown field handling
# ---------------------------------------------------------------------------

class TestUnknownFields:
    def test_unknown_field_passes_through(self):
        result = validate_extracted_field(
            "custom_field", "some_value",
            source=ExtractionSource.PDF_TEXT,
        )
        assert result["status"] == "valid"
        assert result["value"] == "some_value"
        assert result["confidence"] == "low"
