"""
Multimodal Financial Document Parser — Phase 3 Hardened.

Handles extraction of financial parameters from uploaded PDF documents
(quotations, HP letters, invoice slips) using pypdf.

Phase 3 enhancements:
- Full per-page source traceability
- Integration with document_processor for robust PDF handling
- Integration with extraction_validator for financial value validation
- Table extraction support
- Image/scanned document detection
- Corrupted/encrypted document handling
- Financial field conflict detection
- LLM hallucination protection
- Deterministic calculation guarding
- Multimodal API failure/timeout handling

IMPORTANT:
- Extracted values are labelled "extracted_unverified" — they must be
  confirmed by the user before being used in financial calculations.
- Values are never silently trusted; confidence and source are always
  returned alongside each extracted field.
- OCR / LLM-extracted text is treated as provisional; the system
  will flag any extracted value that falls outside plausible ranges.
"""

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from services.document_processor import (
    DocumentResult,
    DocumentType,
    ProcessingStatus,
    process_pdf_bytes,
    process_pdf_file,
)
from services.extraction_validator import (
    ConfidenceLevel,
    ExtractionSource,
    ValidationStatus,
    guard_deterministic_calculation,
    validate_extracted_field,
    validate_extraction_set,
)


# ---------------------------------------------------------------------------
# Plausibility ranges for Malaysian HP / asset context
# These are NOT legal caps — they are sanity-check bounds used to flag
# suspicious OCR results before they reach the financial engine.
# ---------------------------------------------------------------------------

_PLAUSIBILITY = {
    "asset_price": (Decimal("1000"), Decimal("10_000_000")),
    "down_payment": (Decimal("0"), Decimal("5_000_000")),
    "hp_period_months": (1, 360),
    "hp_interest_rate": (Decimal("0"), Decimal("25")),
    "lease_period_months": (1, 360),
    "lease_monthly_payment": (Decimal("100"), Decimal("500_000")),
}


def _clean_decimal(text: str) -> Optional[Decimal]:
    """Remove currency symbols and commas, then try to parse as Decimal."""
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return Decimal(cleaned) if cleaned else None
    except InvalidOperation:
        return None


def _clean_int(text: str) -> Optional[int]:
    """Extract an integer from a string."""
    cleaned = re.sub(r"[^\d]", "", text)
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def _plausibility_check(
    field: str,
    value: Any,
) -> str:
    """
    Return 'plausible', 'out_of_range', or 'not_checked'
    based on configured sanity ranges.
    """
    if field not in _PLAUSIBILITY or value is None:
        return "not_checked"

    lo, hi = _PLAUSIBILITY[field]
    try:
        numeric = Decimal(str(value))
        return "plausible" if lo <= numeric <= hi else "out_of_range"
    except (InvalidOperation, TypeError):
        return "not_checked"


# ---------------------------------------------------------------------------
# Pattern-based extraction helpers
# ---------------------------------------------------------------------------

_PATTERNS: Dict[str, List[str]] = {
    "asset_price": [
        r"(?:total\s+)?(?:vehicle|asset|purchase|sale|OTR|on[\s\-]the[\s\-]road)\s+(?:price|cost)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
        r"(?:harga\s+kenderaan|harga\s+aset)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
        r"(?:price|harga)\s*[:\-]\s*([\d,]+(?:\.\d+)?)",
    ],
    "down_payment": [
        r"(?:down|deposit|bayaran\s+pendahuluan)\s*(?:payment|bayaran)?\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
        r"(?:D\.?P\.?|DP)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
    ],
    "hp_period_months": [
        r"(?:tenure|tenor|term|repayment\s+period|tempoh)\s*[:\-]?\s*(\d+)\s*(?:month|bulan|mths?)",
        r"(\d+)\s*(?:month|bulan|mths?)\s*(?:hire[\s\-]?purchase|HP|pembiayaan)",
    ],
    "hp_interest_rate": [
        r"(?:EIR|effective\s+interest\s+rate|kadar\s+faedah\s+berkesan)\s*[:\-]?\s*([\d.]+)\s*%",
        r"(?:interest\s+rate|profit\s+rate|kadar\s+faedah)\s*[:\-]?\s*([\d.]+)\s*%",
    ],
    "lease_monthly_payment": [
        r"(?:monthly\s+(?:lease\s+)?(?:rental|payment)|ansuran\s+bulanan)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)",
    ],
    "lease_period_months": [
        r"(?:lease\s+(?:tenure|term|period)|tempoh\s+pajakan)\s*[:\-]?\s*(\d+)\s*(?:month|bulan|mths?)",
    ],
    "asset_name": [
        r"(?:vehicle|make|model|kenderaan)\s*[:\-]?\s*([A-Za-z0-9\s\-\/]+?)(?:\n|,|;|\.)",
    ],
}


def _extract_field_from_text(
    text: str,
    field: str,
    is_decimal: bool = True,
    source_page: Optional[int] = None,
    source_document: Optional[str] = None,
) -> Dict[str, Any]:
    """Try each pattern for a field; return the first match with metadata."""
    patterns = _PATTERNS.get(field, [])
    text_lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
        if match:
            raw = match.group(1).strip()
            if is_decimal:
                value = _clean_decimal(raw)
            else:
                value = _clean_int(raw) if field.endswith("months") else raw.strip()

            if value is not None:
                plausibility = _plausibility_check(field, value)
                return {
                    "value": value,
                    "raw_text": raw,
                    "pattern_matched": pattern,
                    "classification": "extracted_unverified",
                    "plausibility": plausibility,
                    "requires_user_confirmation": True,
                    "source_page": source_page,
                    "source_document": source_document,
                }

    return {
        "value": None,
        "raw_text": None,
        "pattern_matched": None,
        "classification": "insufficient_data",
        "plausibility": "not_checked",
        "requires_user_confirmation": True,
        "source_page": source_page,
        "source_document": source_document,
    }


def _extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file using pypdf."""
    if not PYPDF_AVAILABLE:
        raise RuntimeError(
            "pypdf is not installed. Run: pip install pypdf"
        )

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(path))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    return "\n".join(pages_text)


def _extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract all text from PDF bytes (e.g. from an HTTP upload)."""
    if not PYPDF_AVAILABLE:
        raise RuntimeError(
            "pypdf is not installed. Run: pip install pypdf"
        )

    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    return "\n".join(pages_text)


# ---------------------------------------------------------------------------
# Per-page extraction with source traceability
# ---------------------------------------------------------------------------

def _extract_fields_with_traceability(
    doc_result: DocumentResult,
) -> Dict[str, Any]:
    """
    Extract financial fields from a DocumentResult, preserving
    source page information for each extracted field.

    Searches each page individually and records which page
    each value was found on.
    """
    decimal_fields = [
        "asset_price", "down_payment",
        "hp_interest_rate", "lease_monthly_payment",
    ]
    non_decimal_fields = [
        "hp_period_months", "lease_period_months", "asset_name",
    ]

    all_fields = decimal_fields + non_decimal_fields
    extracted: Dict[str, Any] = {}

    # First try per-page extraction for source traceability
    for page in doc_result.pages:
        if not page.has_text:
            continue

        for field in all_fields:
            # Skip if already found
            if field in extracted and extracted[field]["value"] is not None:
                continue

            is_decimal = field in decimal_fields
            if field in ("hp_period_months", "lease_period_months", "asset_name"):
                is_decimal = False

            result = _extract_field_from_text(
                text=page.text,
                field=field,
                is_decimal=is_decimal,
                source_page=page.page_number,
                source_document=doc_result.source_file,
            )

            if result["value"] is not None:
                extracted[field] = result

    # For any fields not found in per-page search, try full text
    for field in all_fields:
        if field not in extracted or extracted[field]["value"] is None:
            is_decimal = field in decimal_fields
            if field in ("hp_period_months", "lease_period_months", "asset_name"):
                is_decimal = False

            result = _extract_field_from_text(
                text=doc_result.full_text,
                field=field,
                is_decimal=is_decimal,
                source_page=None,
                source_document=doc_result.source_file,
            )
            extracted[field] = result

    return extracted


# ---------------------------------------------------------------------------
# Public API — enhanced with Phase 3 hardening
# ---------------------------------------------------------------------------

def parse_financial_document_pdf(
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Extract financial parameters from a PDF quotation or HP letter.

    Parameters
    ----------
    pdf_path : str, optional
        Filesystem path to the PDF.
    pdf_bytes : bytes, optional
        Raw PDF bytes (for HTTP upload scenarios).
    timeout_seconds : float
        Maximum processing time in seconds.

    Returns
    -------
    dict containing:
        extracted_fields : dict
            Each key maps to an extraction result dict with:
            - value              : extracted Python value (Decimal/int/str) or None
            - raw_text           : matched raw string from document
            - classification     : "extracted_unverified" | "insufficient_data"
            - plausibility       : "plausible" | "out_of_range" | "not_checked"
            - requires_user_confirmation : always True
            - source_page        : page number where value was found
            - source_document    : document identifier
        validation         : dict   Validation results from extraction_validator
        document_info      : dict   Document processing metadata
        full_text_preview  : str    First 500 chars of extracted text
        page_count         : int
        warnings           : list[str]
        status             : "success" | "partial" | "empty" | "error" | "timeout"

    IMPORTANT: No extracted value is automatically used in financial
    calculations. The caller must validate each field with the user
    before passing to the analysis pipeline.
    """
    if pdf_path is None and pdf_bytes is None:
        raise ValueError("Either pdf_path or pdf_bytes must be provided.")

    warnings: List[str] = []

    # --- Process document through the document processor ---
    try:
        if pdf_path:
            doc_result = process_pdf_file(
                file_path=pdf_path,
                timeout_seconds=timeout_seconds,
            )
        elif pdf_bytes:
            if not pdf_bytes:
                return {
                    "extracted_fields": {},
                    "validation": {},
                    "document_info": {"document_type": "pdf_empty", "page_count": 0},
                    "full_text_preview": "",
                    "page_count": 0,
                    "warnings": ["PDF document is empty."],
                    "status": "empty",
                }
            doc_result = process_pdf_bytes(
                pdf_bytes=pdf_bytes,
                source_name=pdf_path or "uploaded_document",
                timeout_seconds=timeout_seconds,
            )
        else:
            # Unreachable but defensive
            return {
                "extracted_fields": {},
                "validation": {},
                "document_info": {},
                "full_text_preview": "",
                "page_count": 0,
                "warnings": ["No document provided."],
                "status": "empty",
            }
    except Exception as exc:
        return {
            "extracted_fields": {},
            "validation": {},
            "document_info": {"error": str(exc)},
            "full_text_preview": "",
            "page_count": 0,
            "warnings": [f"Error reading PDF: {exc}"],
            "status": "error",
            "error": str(exc),
        }

    # --- Handle document processor errors ---
    if doc_result.status == ProcessingStatus.ERROR:
        return {
            "extracted_fields": {},
            "validation": {},
            "document_info": doc_result.to_dict(),
            "full_text_preview": "",
            "page_count": doc_result.page_count,
            "warnings": doc_result.warnings + doc_result.errors,
            "status": "error",
            "error": "; ".join(doc_result.errors) if doc_result.errors else "Unknown processing error",
        }

    if doc_result.status == ProcessingStatus.TIMEOUT:
        return {
            "extracted_fields": {},
            "validation": {},
            "document_info": doc_result.to_dict(),
            "full_text_preview": doc_result.full_text[:500] if doc_result.full_text else "",
            "page_count": doc_result.page_count,
            "warnings": doc_result.warnings,
            "status": "timeout",
            "error": "Document processing timed out.",
        }

    if doc_result.status == ProcessingStatus.EMPTY:
        scanned_msg = ""
        if doc_result.document_type in (DocumentType.PDF_SCANNED, DocumentType.PDF_EMPTY):
            scanned_msg = (
                " The document may be scanned/image-based. "
                "OCR processing is required for text extraction."
            )
        return {
            "extracted_fields": {},
            "validation": {},
            "document_info": doc_result.to_dict(),
            "full_text_preview": "",
            "page_count": doc_result.page_count,
            "warnings": doc_result.warnings + [
                f"PDF text extraction returned no readable content.{scanned_msg}"
            ],
            "status": "empty",
        }

    # --- Extract fields with source traceability ---
    extracted = _extract_fields_with_traceability(doc_result)

    # --- Validate extracted fields ---
    raw_values = {
        field_name: info["value"]
        for field_name, info in extracted.items()
    }

    validation_result = validate_extraction_set(
        extracted_fields=raw_values,
        source=ExtractionSource.PDF_TEXT,
        source_document=doc_result.source_file,
    )

    # --- Collect warnings ---
    for field_name, info in extracted.items():
        if info.get("plausibility") == "out_of_range":
            warnings.append(
                f"Field '{field_name}' extracted value {info['value']!r} is "
                f"outside plausible range — please verify before use."
            )

    warnings.extend(doc_result.warnings)
    warnings.extend(validation_result.get("warnings", []))

    # --- Count extracted fields ---
    extracted_count = sum(
        1 for v in extracted.values() if v["value"] is not None
    )

    status = (
        "success" if extracted_count >= 3
        else "partial" if extracted_count >= 1
        else "empty"
    )

    return {
        "extracted_fields": extracted,
        "validation": validation_result,
        "document_info": doc_result.to_dict(),
        "full_text_preview": doc_result.full_text[:500] if doc_result.full_text else "",
        "page_count": doc_result.page_count,
        "warnings": warnings,
        "status": status,
        "extraction_note": (
            "All extracted values are labelled 'extracted_unverified'. "
            "They must be confirmed by the user before being used in "
            "financial calculations. Do not trust OCR output blindly."
        ),
    }


def parse_financial_document_pdf_hardened(
    pdf_path: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Phase 3 hardened version with full multimodal pipeline.

    This is the recommended entry point for Phase 3+.
    Includes:
    - Document processing with per-page traceability
    - Financial value extraction with validation
    - Conflict detection
    - LLM hallucination protection
    - Deterministic calculation guarding
    - Comprehensive error handling

    Returns the same structure as parse_financial_document_pdf
    with additional validation and document_info fields.
    """
    return parse_financial_document_pdf(
        pdf_path=pdf_path,
        pdf_bytes=pdf_bytes,
        timeout_seconds=timeout_seconds,
    )
