"""
Financial Extraction Validator — Phase 3 Multimodal Hardening.

Validates extracted financial values BEFORE they can enter the
deterministic financial calculation engine.

Responsibilities:
1. Validate numeric types and ranges for all financial fields
2. Detect and flag conflicting values (e.g., down_payment > asset_price)
3. Detect and flag missing required values
4. Assign confidence levels to extracted values
5. Ensure source/page traceability for every validated field
6. Prevent LLM-hallucinated financial values from entering calculations
7. Enforce deterministic-calculation protection

RULES:
- Never invent a financial value.
- Never silently guess a missing value.
- Never allow LLM-generated numbers to override deterministic calculations.
- All extracted values must be validated before entering financial calculations.
"""

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ConfidenceLevel(str, Enum):
    """Confidence level for an extracted value."""
    HIGH = "high"                  # Pattern-matched, plausible range
    MEDIUM = "medium"              # Pattern-matched, edge-of-range or single match
    LOW = "low"                    # Ambiguous match or weak pattern
    UNVERIFIED = "unverified"      # Extracted but not validated
    REJECTED = "rejected"          # Failed validation
    MISSING = "missing"            # Not found in document


class ValidationStatus(str, Enum):
    """Status of field validation."""
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    OUT_OF_RANGE = "out_of_range"
    TYPE_ERROR = "type_error"


class ExtractionSource(str, Enum):
    """Origin of an extracted value."""
    PDF_TEXT = "pdf_text_extraction"
    PDF_TABLE = "pdf_table_extraction"
    USER_INPUT = "user_input"
    USER_CONFIRMED = "user_confirmed"
    LLM_GENERATED = "llm_generated"     # Flag only — never trust
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Plausibility ranges for Malaysian HP / asset context
# These are sanity-check bounds, NOT legal caps.
# ---------------------------------------------------------------------------

FIELD_SPECS: Dict[str, Dict[str, Any]] = {
    "asset_price": {
        "type": "decimal",
        "min": Decimal("1000"),
        "max": Decimal("10000000"),
        "required": True,
        "description": "Total purchase price of the asset",
    },
    "down_payment": {
        "type": "decimal",
        "min": Decimal("0"),
        "max": Decimal("10000000"),
        "required": True,
        "description": "Down payment / deposit amount",
    },
    "hp_period_months": {
        "type": "integer",
        "min": 1,
        "max": 360,
        "required": True,
        "description": "Hire-purchase loan tenure in months",
    },
    "hp_interest_rate": {
        "type": "decimal",
        "min": Decimal("0"),
        "max": Decimal("25"),
        "required": True,
        "description": "Annual effective interest rate (EIR) percentage",
    },
    "lease_period_months": {
        "type": "integer",
        "min": 1,
        "max": 360,
        "required": True,
        "description": "Lease tenure in months",
    },
    "lease_monthly_payment": {
        "type": "decimal",
        "min": Decimal("100"),
        "max": Decimal("500000"),
        "required": True,
        "description": "Monthly lease payment",
    },
    "asset_name": {
        "type": "string",
        "required": False,
        "description": "Name/model of the asset",
    },
}


def _coerce_decimal(value: Any) -> Tuple[Optional[Decimal], Optional[str]]:
    """Attempt to convert a value to Decimal. Returns (value, error_message)."""
    if value is None:
        return None, "Value is None"
    if isinstance(value, Decimal):
        return value, None
    try:
        d = Decimal(str(value))
        if d.is_nan() or d.is_infinite():
            return None, f"Value is not a finite number: {value}"
        return d, None
    except (InvalidOperation, TypeError, ValueError) as exc:
        return None, f"Cannot convert to decimal: {value!r} ({exc})"


def _coerce_int(value: Any) -> Tuple[Optional[int], Optional[str]]:
    """Attempt to convert a value to int. Returns (value, error_message)."""
    if value is None:
        return None, "Value is None"
    if isinstance(value, int) and not isinstance(value, bool):
        return value, None
    try:
        i = int(value)
        return i, None
    except (TypeError, ValueError) as exc:
        return None, f"Cannot convert to integer: {value!r} ({exc})"


def validate_extracted_field(
    field_name: str,
    value: Any,
    source: ExtractionSource = ExtractionSource.UNKNOWN,
    source_page: Optional[int] = None,
    source_document: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate a single extracted financial field.

    Returns a validation result dict containing:
    - field_name: str
    - value: validated value (Decimal/int/str) or None
    - original_value: the input value before coercion
    - status: ValidationStatus
    - confidence: ConfidenceLevel
    - source: ExtractionSource
    - source_page: optional page number
    - source_document: optional document identifier
    - errors: list of error messages
    - requires_user_confirmation: bool (always True for extracted values)
    """
    spec = FIELD_SPECS.get(field_name)
    errors: List[str] = []
    result_value = None
    status = ValidationStatus.VALID
    confidence = ConfidenceLevel.UNVERIFIED

    # --- LLM-generated value protection ---
    if source == ExtractionSource.LLM_GENERATED:
        return {
            "field_name": field_name,
            "value": None,
            "original_value": value,
            "status": ValidationStatus.INVALID,
            "confidence": ConfidenceLevel.REJECTED,
            "source": source.value,
            "source_page": source_page,
            "source_document": source_document,
            "errors": [
                "LLM-generated financial values are not permitted. "
                "Financial values must come from document extraction "
                "or user input."
            ],
            "requires_user_confirmation": True,
        }

    if spec is None:
        # Unknown field — pass through with low confidence
        return {
            "field_name": field_name,
            "value": value,
            "original_value": value,
            "status": ValidationStatus.VALID,
            "confidence": ConfidenceLevel.LOW,
            "source": source.value,
            "source_page": source_page,
            "source_document": source_document,
            "errors": [],
            "requires_user_confirmation": True,
        }

    # --- Missing value ---
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "field_name": field_name,
            "value": None,
            "original_value": value,
            "status": ValidationStatus.MISSING,
            "confidence": ConfidenceLevel.MISSING,
            "source": source.value,
            "source_page": source_page,
            "source_document": source_document,
            "errors": [f"Required field '{field_name}' is missing."] if spec.get("required") else [],
            "requires_user_confirmation": True,
        }

    # --- Type validation and coercion ---
    field_type = spec.get("type", "string")

    if field_type == "decimal":
        result_value, err = _coerce_decimal(value)
        if err:
            errors.append(err)
            status = ValidationStatus.TYPE_ERROR
    elif field_type == "integer":
        result_value, err = _coerce_int(value)
        if err:
            errors.append(err)
            status = ValidationStatus.TYPE_ERROR
    elif field_type == "string":
        result_value = str(value).strip() if value else None
        if not result_value:
            status = ValidationStatus.MISSING
    else:
        result_value = value

    # --- Range validation (only if type validation passed) ---
    if status == ValidationStatus.VALID and result_value is not None:
        min_val = spec.get("min")
        max_val = spec.get("max")

        if min_val is not None and max_val is not None:
            try:
                comparable = Decimal(str(result_value))
                min_comparable = Decimal(str(min_val))
                max_comparable = Decimal(str(max_val))

                if comparable < min_comparable or comparable > max_comparable:
                    status = ValidationStatus.OUT_OF_RANGE
                    errors.append(
                        f"Value {result_value} is outside plausible range "
                        f"[{min_val}, {max_val}] for {field_name}."
                    )
                    confidence = ConfidenceLevel.LOW
            except (InvalidOperation, TypeError):
                pass

    # --- Set confidence ---
    if status == ValidationStatus.VALID and confidence == ConfidenceLevel.UNVERIFIED:
        if source == ExtractionSource.USER_CONFIRMED:
            confidence = ConfidenceLevel.HIGH
        elif source == ExtractionSource.PDF_TEXT:
            confidence = ConfidenceLevel.MEDIUM
        elif source == ExtractionSource.PDF_TABLE:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

    if status in (ValidationStatus.TYPE_ERROR, ValidationStatus.INVALID):
        confidence = ConfidenceLevel.REJECTED
        result_value = None

    return {
        "field_name": field_name,
        "value": result_value,
        "original_value": value,
        "status": status.value,
        "confidence": confidence.value,
        "source": source.value,
        "source_page": source_page,
        "source_document": source_document,
        "errors": errors,
        "requires_user_confirmation": source != ExtractionSource.USER_CONFIRMED,
    }


def validate_extraction_set(
    extracted_fields: Dict[str, Any],
    source: ExtractionSource = ExtractionSource.PDF_TEXT,
    source_document: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate a full set of extracted financial fields.

    Performs:
    1. Individual field validation
    2. Cross-field conflict detection (e.g., down_payment > asset_price)
    3. Missing required field detection
    4. Overall confidence assessment

    Parameters
    ----------
    extracted_fields : dict
        field_name -> value (or extraction result dict with 'value' key)
    source : ExtractionSource
        Origin of the extracted values.
    source_document : str, optional
        Document identifier for traceability.

    Returns
    -------
    dict with:
        - validated_fields: dict of field_name -> validation result
        - missing_required: list of missing required field names
        - conflicts: list of conflict descriptions
        - overall_status: "valid" | "partial" | "invalid"
        - overall_confidence: "high" | "medium" | "low" | "rejected"
        - warnings: list of warning strings
        - requires_user_confirmation: bool (always True for extracted)
    """
    validated_fields: Dict[str, Any] = {}
    missing_required: List[str] = []
    conflicts: List[str] = []
    warnings: List[str] = []

    for field_name, raw_value in extracted_fields.items():
        # Support both raw values and extraction result dicts
        if isinstance(raw_value, dict) and "value" in raw_value:
            value = raw_value["value"]
            page = raw_value.get("source_page")
        else:
            value = raw_value
            page = None

        result = validate_extracted_field(
            field_name=field_name,
            value=value,
            source=source,
            source_page=page,
            source_document=source_document,
        )
        validated_fields[field_name] = result

    # --- Check for missing required fields ---
    for field_name, spec in FIELD_SPECS.items():
        if spec.get("required") and field_name not in extracted_fields:
            missing_required.append(field_name)
            validated_fields[field_name] = {
                "field_name": field_name,
                "value": None,
                "original_value": None,
                "status": ValidationStatus.MISSING.value,
                "confidence": ConfidenceLevel.MISSING.value,
                "source": source.value,
                "source_page": None,
                "source_document": source_document,
                "errors": [f"Required field '{field_name}' was not found in the document."],
                "requires_user_confirmation": True,
            }

    # --- Cross-field conflict detection ---
    ap = validated_fields.get("asset_price", {})
    dp = validated_fields.get("down_payment", {})

    if (ap.get("value") is not None and dp.get("value") is not None):
        try:
            ap_val = Decimal(str(ap["value"]))
            dp_val = Decimal(str(dp["value"]))
            if dp_val > ap_val:
                conflicts.append(
                    f"Down payment (RM {dp_val}) exceeds asset price (RM {ap_val}). "
                    "This is not permitted."
                )
                validated_fields["down_payment"]["status"] = ValidationStatus.CONFLICTING.value
                validated_fields["down_payment"]["errors"].append(
                    "Down payment exceeds asset price."
                )
        except (InvalidOperation, TypeError):
            pass

    # --- Overall assessment ---
    statuses = [v.get("status") for v in validated_fields.values()]
    confidences = [v.get("confidence") for v in validated_fields.values()]

    valid_count = statuses.count(ValidationStatus.VALID.value)
    total_count = len(statuses)

    if valid_count == total_count and not conflicts and not missing_required:
        overall_status = "valid"
    elif valid_count > 0:
        overall_status = "partial"
    else:
        overall_status = "invalid"

    # Conservative overall confidence
    if ConfidenceLevel.REJECTED.value in confidences:
        overall_confidence = ConfidenceLevel.REJECTED.value
    elif ConfidenceLevel.LOW.value in confidences:
        overall_confidence = ConfidenceLevel.LOW.value
    elif ConfidenceLevel.MEDIUM.value in confidences:
        overall_confidence = ConfidenceLevel.MEDIUM.value
    elif ConfidenceLevel.HIGH.value in confidences:
        overall_confidence = ConfidenceLevel.HIGH.value
    else:
        overall_confidence = ConfidenceLevel.UNVERIFIED.value

    if missing_required:
        warnings.append(
            f"Missing required fields: {', '.join(missing_required)}. "
            "These must be provided before financial analysis can proceed."
        )

    if conflicts:
        warnings.extend(conflicts)

    return {
        "validated_fields": validated_fields,
        "missing_required": missing_required,
        "conflicts": conflicts,
        "overall_status": overall_status,
        "overall_confidence": overall_confidence,
        "warnings": warnings,
        "requires_user_confirmation": True,
        "deterministic_calculation_note": (
            "Validated extracted values are still marked as "
            "'requires_user_confirmation'. They must be explicitly "
            "confirmed before entering the deterministic financial "
            "calculation engine. The LLM cannot override or substitute "
            "deterministic calculations."
        ),
    }


def guard_deterministic_calculation(
    field_name: str,
    calculated_value: Any,
    llm_proposed_value: Any,
) -> Dict[str, Any]:
    """
    Protection against LLM hallucinated financial values.

    If the LLM proposes a financial value that differs from the
    deterministic calculation, the deterministic value always wins.

    Parameters
    ----------
    field_name : str
        Name of the financial field.
    calculated_value : Any
        Value from deterministic calculation engine.
    llm_proposed_value : Any
        Value proposed by LLM (if any).

    Returns
    -------
    dict with:
        - field_name: str
        - final_value: the deterministic value (always)
        - llm_override_blocked: bool
        - warning: str if LLM tried to override
    """
    result = {
        "field_name": field_name,
        "final_value": calculated_value,
        "llm_override_blocked": False,
        "warning": None,
    }

    if llm_proposed_value is not None and calculated_value is not None:
        try:
            calc_dec = Decimal(str(calculated_value))
            llm_dec = Decimal(str(llm_proposed_value))

            if calc_dec != llm_dec:
                result["llm_override_blocked"] = True
                result["warning"] = (
                    f"LLM proposed {field_name}={llm_proposed_value} but "
                    f"deterministic calculation produced {calculated_value}. "
                    f"Deterministic value is authoritative."
                )
        except (InvalidOperation, TypeError, ValueError):
            # If comparison fails, deterministic value still wins
            if str(calculated_value) != str(llm_proposed_value):
                result["llm_override_blocked"] = True
                result["warning"] = (
                    f"LLM proposed a different {field_name} value. "
                    f"Deterministic value is authoritative."
                )

    return result
