"""
Document Processing Pipeline — Phase 3 Multimodal Hardening.

Handles:
- PDF text extraction with per-page source traceability
- Table detection and structured extraction
- Image/scanned document detection
- Corrupted/encrypted/empty document handling
- Page-level metadata preservation
- Processing timeout protection

IMPORTANT:
- This module extracts raw text/data only.
- Financial value extraction and validation is handled by extraction_validator.py.
- No extracted value is used in calculations without explicit validation.
"""

import io
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

    class PdfReadError(Exception):
        """Fallback when pypdf is not installed."""
        pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PROCESSING_TIME_SECONDS = 60
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MIN_TEXT_CHARS_PER_PAGE = 20  # Pages with fewer chars are flagged as image-based


class DocumentType(str, Enum):
    """Classification of input document type."""
    PDF_TEXT = "pdf_text"
    PDF_SCANNED = "pdf_scanned"
    PDF_MIXED = "pdf_mixed"          # Some pages text, some scanned
    PDF_EMPTY = "pdf_empty"
    PDF_CORRUPTED = "pdf_corrupted"
    PDF_ENCRYPTED = "pdf_encrypted"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Overall processing status."""
    SUCCESS = "success"
    PARTIAL = "partial"            # Some pages processed, some failed
    EMPTY = "empty"                # No extractable content
    ERROR = "error"                # Fatal processing error
    TIMEOUT = "timeout"            # Processing exceeded time limit
    UNSUPPORTED = "unsupported"    # File type not supported


@dataclass
class PageResult:
    """Extraction result for a single PDF page."""
    page_number: int
    text: str
    char_count: int
    has_text: bool
    is_likely_scanned: bool
    tables_detected: int = 0
    raw_table_data: List[List[str]] = field(default_factory=list)
    processing_error: Optional[str] = None
    source: str = ""


@dataclass
class DocumentResult:
    """Complete document processing result."""
    status: ProcessingStatus
    document_type: DocumentType
    page_count: int
    pages: List[PageResult]
    full_text: str
    text_pages_count: int
    scanned_pages_count: int
    tables_found: int
    processing_time_seconds: float
    file_size_bytes: int
    warnings: List[str]
    errors: List[str]
    source_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "status": self.status.value,
            "document_type": self.document_type.value,
            "page_count": self.page_count,
            "text_pages_count": self.text_pages_count,
            "scanned_pages_count": self.scanned_pages_count,
            "tables_found": self.tables_found,
            "processing_time_seconds": round(self.processing_time_seconds, 3),
            "file_size_bytes": self.file_size_bytes,
            "full_text_preview": self.full_text[:500] if self.full_text else "",
            "pages": [
                {
                    "page_number": p.page_number,
                    "char_count": p.char_count,
                    "has_text": p.has_text,
                    "is_likely_scanned": p.is_likely_scanned,
                    "tables_detected": p.tables_detected,
                    "text_preview": p.text[:200] if p.text else "",
                    "source": p.source,
                    "processing_error": p.processing_error,
                }
                for p in self.pages
            ],
            "warnings": self.warnings,
            "errors": self.errors,
            "source_file": self.source_file,
        }


# ---------------------------------------------------------------------------
# Table detection heuristics
# ---------------------------------------------------------------------------

# Patterns that suggest tabular data in extracted text
_TABLE_PATTERNS = [
    # Multiple columns separated by whitespace (at least 3 columns)
    re.compile(r"^.{5,}\s{2,}.{5,}\s{2,}.{5,}$", re.MULTILINE),
    # Lines with multiple pipe separators
    re.compile(r"^.*\|.*\|.*$", re.MULTILINE),
    # Lines with multiple tab separators
    re.compile(r"^.*\t.*\t.*$", re.MULTILINE),
    # Repeated dash/equal separators (table borders)
    re.compile(r"^[-=]{10,}$", re.MULTILINE),
]

# Financial table indicators
_FINANCIAL_TABLE_INDICATORS = [
    re.compile(r"(?:total|subtotal|amount|balance|payment)\s*[:|\s]\s*[\d,]+(?:\.\d{2})?", re.IGNORECASE),
    re.compile(r"(?:RM|MYR|USD)\s*[\d,]+(?:\.\d{2})?", re.IGNORECASE),
    re.compile(r"(?:month|bulan)\s*\d+\s*[\d,]+(?:\.\d{2})?", re.IGNORECASE),
]


def _detect_tables_in_text(text: str) -> Tuple[int, List[List[str]]]:
    """
    Detect potential table structures in extracted text.

    Returns:
        (table_count, list_of_raw_table_rows)
    """
    if not text or len(text) < 20:
        return 0, []

    table_count = 0
    raw_tables: List[List[str]] = []

    # Check for financial table patterns
    for pattern in _FINANCIAL_TABLE_INDICATORS:
        matches = pattern.findall(text)
        if len(matches) >= 2:
            table_count += 1
            raw_tables.append(matches[:20])  # Cap at 20 rows

    # Check for structural table patterns
    for pattern in _TABLE_PATTERNS:
        matches = pattern.findall(text)
        if len(matches) >= 3:  # At least 3 rows = likely table
            table_count += 1
            raw_tables.append(matches[:20])

    return table_count, raw_tables


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_pdf_bytes(
    pdf_bytes: bytes,
    source_name: str = "uploaded_document",
    timeout_seconds: float = MAX_PROCESSING_TIME_SECONDS,
) -> DocumentResult:
    """
    Process PDF bytes and extract text with full page-level traceability.

    Parameters
    ----------
    pdf_bytes : bytes
        Raw PDF file content.
    source_name : str
        Human-readable source identifier for traceability.
    timeout_seconds : float
        Maximum processing time before timeout.

    Returns
    -------
    DocumentResult with per-page extraction results.
    """
    start_time = time.monotonic()
    warnings: List[str] = []
    errors: List[str] = []

    # --- Pre-validation ---
    if not pdf_bytes:
        return DocumentResult(
            status=ProcessingStatus.EMPTY,
            document_type=DocumentType.PDF_EMPTY,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=0,
            warnings=["Document is empty (0 bytes)."],
            errors=[],
            source_file=source_name,
        )

    file_size = len(pdf_bytes)
    if file_size > MAX_FILE_SIZE_BYTES:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.UNKNOWN,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=[],
            errors=[
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed ({MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB)."
            ],
            source_file=source_name,
        )

    if not PYPDF_AVAILABLE:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.UNKNOWN,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=[],
            errors=["pypdf is not installed. Run: pip install pypdf"],
            source_file=source_name,
        )

    # --- PDF parsing ---
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except PdfReadError as exc:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.PDF_CORRUPTED,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=[],
            errors=[f"PDF is corrupted or malformed: {exc}"],
            source_file=source_name,
        )
    except Exception as exc:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.PDF_CORRUPTED,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=[],
            errors=[f"Failed to read PDF: {type(exc).__name__}: {exc}"],
            source_file=source_name,
        )

    # Check for encryption
    if reader.is_encrypted:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.PDF_ENCRYPTED,
            page_count=len(reader.pages),
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=[],
            errors=["PDF is encrypted. Decryption is required before processing."],
            source_file=source_name,
        )

    total_pages = len(reader.pages)
    if total_pages == 0:
        return DocumentResult(
            status=ProcessingStatus.EMPTY,
            document_type=DocumentType.PDF_EMPTY,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=time.monotonic() - start_time,
            file_size_bytes=file_size,
            warnings=["PDF contains zero pages."],
            errors=[],
            source_file=source_name,
        )

    # --- Per-page extraction ---
    pages: List[PageResult] = []
    all_text_parts: List[str] = []
    text_page_count = 0
    scanned_page_count = 0
    total_tables = 0

    for page_idx, page in enumerate(reader.pages):
        page_number = page_idx + 1

        # Timeout check
        elapsed = time.monotonic() - start_time
        if elapsed > timeout_seconds:
            warnings.append(
                f"Processing timed out after {elapsed:.1f}s at page {page_number}/{total_pages}."
            )
            return DocumentResult(
                status=ProcessingStatus.TIMEOUT,
                document_type=DocumentType.PDF_MIXED,
                page_count=total_pages,
                pages=pages,
                full_text="\n".join(all_text_parts),
                text_pages_count=text_page_count,
                scanned_pages_count=scanned_page_count,
                tables_found=total_tables,
                processing_time_seconds=elapsed,
                file_size_bytes=file_size,
                warnings=warnings,
                errors=errors,
                source_file=source_name,
            )

        try:
            text = page.extract_text() or ""
            text = text.strip()
        except Exception as exc:
            error_msg = f"Page {page_number}: extraction failed — {type(exc).__name__}: {exc}"
            errors.append(error_msg)
            pages.append(PageResult(
                page_number=page_number,
                text="",
                char_count=0,
                has_text=False,
                is_likely_scanned=True,
                processing_error=error_msg,
                source=f"{source_name}#page{page_number}",
            ))
            scanned_page_count += 1
            continue

        char_count = len(text)
        has_text = char_count >= MIN_TEXT_CHARS_PER_PAGE
        is_likely_scanned = not has_text

        # Table detection
        tables_detected, raw_table_data = _detect_tables_in_text(text) if has_text else (0, [])
        total_tables += tables_detected

        if has_text:
            text_page_count += 1
            all_text_parts.append(text)
        else:
            scanned_page_count += 1
            if char_count > 0:
                warnings.append(
                    f"Page {page_number}: only {char_count} characters extracted — "
                    "may be scanned/image-based."
                )

        pages.append(PageResult(
            page_number=page_number,
            text=text,
            char_count=char_count,
            has_text=has_text,
            is_likely_scanned=is_likely_scanned,
            tables_detected=tables_detected,
            raw_table_data=raw_table_data,
            source=f"{source_name}#page{page_number}",
        ))

    # --- Classify document type ---
    full_text = "\n".join(all_text_parts)

    if text_page_count == 0:
        doc_type = DocumentType.PDF_SCANNED
        if not full_text.strip():
            doc_type = DocumentType.PDF_EMPTY
    elif scanned_page_count == 0:
        doc_type = DocumentType.PDF_TEXT
    else:
        doc_type = DocumentType.PDF_MIXED

    # --- Determine status ---
    if text_page_count == 0 and total_pages > 0:
        status = ProcessingStatus.EMPTY
        warnings.append(
            "No readable text was extracted. The document may be "
            "entirely scanned/image-based. OCR is required."
        )
    elif text_page_count < total_pages:
        status = ProcessingStatus.PARTIAL
    else:
        status = ProcessingStatus.SUCCESS

    processing_time = time.monotonic() - start_time

    return DocumentResult(
        status=status,
        document_type=doc_type,
        page_count=total_pages,
        pages=pages,
        full_text=full_text,
        text_pages_count=text_page_count,
        scanned_pages_count=scanned_page_count,
        tables_found=total_tables,
        processing_time_seconds=processing_time,
        file_size_bytes=file_size,
        warnings=warnings,
        errors=errors,
        source_file=source_name,
    )


def process_pdf_file(
    file_path: str,
    timeout_seconds: float = MAX_PROCESSING_TIME_SECONDS,
) -> DocumentResult:
    """
    Process a PDF file from the filesystem.

    Parameters
    ----------
    file_path : str
        Path to the PDF file.
    timeout_seconds : float
        Maximum processing time.

    Returns
    -------
    DocumentResult
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.UNKNOWN,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=0.0,
            file_size_bytes=0,
            warnings=[],
            errors=[f"File not found: {file_path}"],
            source_file=str(path),
        )

    try:
        pdf_bytes = path.read_bytes()
    except (IOError, OSError) as exc:
        return DocumentResult(
            status=ProcessingStatus.ERROR,
            document_type=DocumentType.UNKNOWN,
            page_count=0,
            pages=[],
            full_text="",
            text_pages_count=0,
            scanned_pages_count=0,
            tables_found=0,
            processing_time_seconds=0.0,
            file_size_bytes=0,
            warnings=[],
            errors=[f"Cannot read file: {exc}"],
            source_file=str(path),
        )

    return process_pdf_bytes(
        pdf_bytes=pdf_bytes,
        source_name=str(path),
        timeout_seconds=timeout_seconds,
    )
