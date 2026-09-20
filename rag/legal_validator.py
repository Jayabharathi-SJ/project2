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