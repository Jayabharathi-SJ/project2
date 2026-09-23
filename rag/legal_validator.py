from decimal import Decimal


def validate_fixed_eir_cap(
    annual_eir: Decimal,
    term_months: int,
) -> None:
    """
    Validate the maximum fixed-rate EIR based on tenure.

    Up to 5 years (60 months): maximum 17% p.a.
    Above 5 years: maximum 16% p.a.
    """

    if annual_eir < 0:
        raise ValueError("EIR cannot be negative.")

    if term_months <= 0:
        raise ValueError("Term must be greater than zero.")

    if term_months <= 60:
        maximum_eir = Decimal("17")
    else:
        maximum_eir = Decimal("16")

    if annual_eir > maximum_eir:
        raise ValueError(
            f"Fixed-rate EIR cannot exceed "
            f"{maximum_eir}% p.a. for this tenure."
        )


def validate_variable_eir_cap(
    annual_eir: Decimal,
    term_months: int,
) -> None:
    """
    Validate the maximum variable-rate EIR.

    Maximum: 17% p.a.
    """

    if annual_eir < 0:
        raise ValueError("EIR cannot be negative.")

    if term_months <= 0:
        raise ValueError("Term must be greater than zero.")

    maximum_eir = Decimal("17")

    if annual_eir > maximum_eir:
        raise ValueError(
            "Variable-rate EIR cannot exceed 17% p.a."
        )


def validate_eir_cap(
    annual_eir: Decimal,
    term_months: int,
    rate_type: str = "fixed",
) -> None:
    """
    Unified EIR validator dispatching to fixed or variable statutory caps.

    - Fixed-rate: 17% p.a. (tenures <= 60 months), 16% p.a. (tenures > 60 months)
    - Variable-rate: 17% p.a. (all tenures)
    """

    normalized_type = rate_type.strip().lower()
    if normalized_type == "fixed":
        validate_fixed_eir_cap(annual_eir=annual_eir, term_months=term_months)
    elif normalized_type == "variable":
        validate_variable_eir_cap(annual_eir=annual_eir, term_months=term_months)
    else:
        raise ValueError(
            f"Unsupported rate type: '{rate_type}'. Must be 'fixed' or 'variable'."
        )


def validate_minimum_deposit(
    down_payment: Decimal,
    asset_price: Decimal,
) -> None:
    """
    Validate compliance with the statutory minimum deposit requirement
    under Section 31(1) of the Malaysian Hire-Purchase Act 1967 (Act 212)
    and Bank Negara Malaysia Consumer Guide 2026.

    Statutory minimum deposit: at least 10% of the cash price.
    """

    if asset_price <= Decimal("0"):
        raise ValueError("Asset price must be greater than zero.")

    if down_payment < Decimal("0"):
        raise ValueError("Down payment cannot be negative.")

    if down_payment > asset_price:
        raise ValueError("Down payment cannot exceed asset price.")

    minimum_required = (asset_price * Decimal("0.10")).quantize(Decimal("0.01"))

    if down_payment < minimum_required:
        raise ValueError(
            f"Down payment (RM {down_payment:.2f}) is below the statutory minimum deposit "
            f"of 10% (RM {minimum_required:.2f}) required under Section 31(1) of the "
            "Hire-Purchase Act 1967."
        )


def check_minimum_deposit(
    down_payment: Decimal,
    asset_price: Decimal,
) -> dict:
    """
    Non-raising evaluation of statutory deposit compliance.
    """

    if asset_price <= Decimal("0"):
        raise ValueError("Asset price must be greater than zero.")

    minimum_required = (asset_price * Decimal("0.10")).quantize(Decimal("0.01"))
    actual = down_payment.quantize(Decimal("0.01"))
    shortfall = max(Decimal("0.00"), minimum_required - actual)

    return {
        "compliant": actual >= minimum_required,
        "required_minimum": minimum_required,
        "actual_deposit": actual,
        "shortfall": shortfall,
    }


def evaluate_legal_compliance(
    annual_eir: Decimal,
    term_months: int,
    rate_type: str,
    down_payment: Decimal,
    asset_price: Decimal,
    retrieved_contexts: list = None,
    qdrant_available: bool = True,
) -> dict:
    """
    Evaluates Malaysian Hire-Purchase legal compliance with strict 3-layer separation
    as required by Requirement 4:
    Layer A: Retrieved Legal Evidence (from Qdrant RAG or registered legal enactments)
    Layer B: Application of the Rule (explicit statutory provision tested)
    Layer C: Validation Result (conclusive outcome with source distinction)

    Distinguishes primary legislation (Act 212 / Term Charges Regulations) from
    regulatory consumer guidance (BNM Consumer Guide 2026).
    """
    errors = []
    rules_applied = []
    retrieved_evidence = []

    # 1. Evaluate EIR Cap
    try:
        validate_eir_cap(annual_eir=annual_eir, term_months=term_months, rate_type=rate_type)
        eir_status = "PASSED"
        eir_error = None
    except ValueError as exc:
        eir_status = "FAILED"
        eir_error = str(exc)
        errors.append(eir_error)

    if rate_type == "fixed":
        cap_val = Decimal("17.0") if term_months <= 60 else Decimal("16.0")
        rules_applied.append({
            "rule_id": "HP2026-FIXED-CAP-001",
            "statutory_basis": "Hire-Purchase (Term Charges) Regulations & BNM Consumer Guide 2026",
            "source_category": "primary_regulation_and_guidance",
            "tested_condition": f"Fixed EIR {annual_eir}% p.a. <= {cap_val}% p.a. for {term_months} months",
            "status": eir_status,
            "error": eir_error,
        })
    else:
        rules_applied.append({
            "rule_id": "HP2026-VARIABLE-CAP-001",
            "statutory_basis": "Hire-Purchase (Term Charges) Regulations & BNM Consumer Guide 2026",
            "source_category": "primary_regulation_and_guidance",
            "tested_condition": f"Variable EIR {annual_eir}% p.a. <= 17.0% p.a.",
            "status": eir_status,
            "error": eir_error,
        })

    # 2. Evaluate Statutory Minimum Deposit
    deposit_check = check_minimum_deposit(down_payment=down_payment, asset_price=asset_price)
    if not deposit_check["compliant"]:
        dep_error = (
            f"Down payment (RM {down_payment:.2f}) is below statutory minimum deposit "
            f"of 10% (RM {deposit_check['required_minimum']:.2f}) required under Section 31(1) "
            "of the Malaysian Hire-Purchase Act 1967."
        )
        errors.append(dep_error)
        dep_status = "FAILED"
    else:
        dep_status = "PASSED"
        dep_error = None

    rules_applied.append({
        "rule_id": "HP2026-DEP-001",
        "statutory_basis": "Section 31(1), Hire-Purchase Act 1967 (Act 212)",
        "source_category": "primary_legislation",
        "tested_condition": f"Deposit RM {down_payment:.2f} >= 10% of cash price RM {asset_price:.2f}",
        "status": dep_status,
        "error": dep_error,
    })

    # 3. Process Retrieved Legal Evidence
    if retrieved_contexts:
        for ctx in retrieved_contexts:
            retrieved_evidence.append({
                "document_id": ctx.get("document_id") or ctx.get("rule_id", "STATUTORY-REF"),
                "title": ctx.get("title") or ctx.get("topic", "Hire-Purchase Provision"),
                "excerpt": ctx.get("content") or ctx.get("text", ""),
                "source": ctx.get("source", "Authoritative Source"),
                "page_number": ctx.get("page_number", 1),
                "source_type": (
                    "primary_legislation"
                    if "Act 1967" in str(ctx.get("source", "")) or "Act 212" in str(ctx.get("source", ""))
                    else "regulatory_guidance"
                ),
            })

    # 4. Formulate Validation Result
    if not qdrant_available and not retrieved_evidence:
        validation_status = "INSUFFICIENT_INDEXED_SOURCES"
        passed = False
        conclusive = False
        statutory_note = (
            "Legal validation cannot be conclusively established from the currently indexed sources "
            "because the authoritative legal vector store was unreachable. Fallback statutory bounds applied."
        )
    elif errors:
        validation_status = "FAILED"
        passed = False
        conclusive = True
        statutory_note = (
            "Proposed financing terms violate statutory provisions under the Malaysian Hire-Purchase Act 1967 "
            "and Hire-Purchase (Amendment) Act 2026 regulations."
        )
    else:
        validation_status = "PASSED"
        passed = True
        conclusive = True
        statutory_note = (
            "Financing terms comply with statutory EIR caps under Hire-Purchase (Term Charges) Regulations 2026 "
            "and 10% minimum deposit under Section 31(1) of the Hire-Purchase Act 1967 (Act 212)."
        )

    return {
        "status": validation_status,
        "passed": passed,
        "conclusive": conclusive,
        "errors": errors,
        "statutory_compliance_note": statutory_note,
        "retrieved_evidence": retrieved_evidence,
        "rules_applied": rules_applied,
        "deposit_compliance": deposit_check,
        "eir_compliance": {
            "annual_eir": annual_eir,
            "term_months": term_months,
            "rate_type": rate_type,
            "compliant": eir_status == "PASSED",
        },
    }
