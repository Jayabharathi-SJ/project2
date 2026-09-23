from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict

from rag.legal_validator import validate_eir_cap, validate_fixed_eir_cap


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round monetary values to 2 decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_reducing_balance(
    principal: Decimal,
    annual_eir: Decimal,
    term_months: int,
    rate_type: str = "fixed",
) -> Dict:
    """
    Calculate a reducing-balance repayment schedule under Malaysian
    Hire-Purchase (Amendment) Act 2026 regulations.

    principal:
        Amount financed after down payment.

    annual_eir:
        Annual EIR percentage (e.g. Decimal("5.5") means 5.5% p.a.).

    term_months:
        Total repayment period in months.

    rate_type:
        "fixed" (default) or "variable".


    Returns:
        Financed amount
        Monthly instalment
        Total interest
        Total paid
        Term
        Annual EIR
        Month-by-month amortisation schedule
    """

    # Basic input validation
    if principal <= 0:
        raise ValueError(
            "Principal must be greater than zero."
        )

    if annual_eir < 0:
        raise ValueError(
            "Annual EIR cannot be negative."
        )

    if term_months <= 0:
        raise ValueError(
            "Term must be greater than zero."
        )

    # Legal EIR validation (dispatches by rate_type)
    validate_eir_cap(
        annual_eir=annual_eir,
        term_months=term_months,
        rate_type=rate_type,
    )

    # Convert annual percentage EIR to monthly rate
    monthly_rate = (
        annual_eir / Decimal("100")
    ) / Decimal("12")

    # Zero-interest case
    if monthly_rate == 0:
        monthly_installment = money(
            principal / Decimal(term_months)
        )
    else:
        factor = (
            Decimal("1") + monthly_rate
        ) ** term_months

        monthly_installment = money(
            principal
            * monthly_rate
            * factor
            / (factor - Decimal("1"))
        )

    opening_balance = money(principal)

    schedule: List[Dict] = []

    total_interest = Decimal("0.00")
    total_paid = Decimal("0.00")

    for month in range(1, term_months + 1):

        # Interest is calculated on outstanding balance
        interest = money(
            opening_balance * monthly_rate
        )

        # Final instalment is adjusted to close
        # the remaining balance exactly.
        if month == term_months:

            principal_payment = opening_balance

            installment = money(
                interest + principal_payment
            )

        else:

            installment = monthly_installment

            principal_payment = money(
                installment - interest
            )

        closing_balance = money(
            opening_balance - principal_payment
        )

        # Prevent a negative balance caused by rounding
        if closing_balance < 0:
            closing_balance = Decimal("0.00")

        schedule.append(
            {
                "month": month,
                "opening_balance": opening_balance,
                "interest": interest,
                "principal": principal_payment,
                "instalment": installment,
                "closing_balance": closing_balance,
            }
        )

        total_interest += interest
        total_paid += installment

        opening_balance = closing_balance

    result = {
        "financed_amount": money(principal),
        "monthly_installment": monthly_installment,
        "total_interest": money(total_interest),
        "term_charges": money(total_interest),
        "total_paid": money(total_paid),
        "term_months": term_months,
        "annual_eir": annual_eir,
        "rate_type": rate_type,
        "schedule": schedule,
    }

    # Independent Amortization Schedule Reconciliation Check
    is_valid, validation_errors, metrics = validate_amortization_schedule(result)
    result["amortization_reconciliation"] = {
        "reconciled": is_valid,
        "errors": validation_errors,
        "metrics": metrics,
    }
    if not is_valid:
        raise ValueError(
            "Amortization schedule reconciliation failed: " + "; ".join(validation_errors)
        )

    return result


def validate_amortization_schedule(
    schedule_result: Dict,
    tolerance: Decimal = Decimal("0.02"),
):
    """
    Independently validate a reducing-balance amortization schedule.
    Verifies the four financial conservation invariants under Requirement 6:
    1. sum(principal repayments) ≈ financed principal
    2. sum(instalments) ≈ total paid
    3. sum(interest) ≈ total interest
    4. final closing balance ≈ zero (0.00)
    """
    errors = []
    schedule = schedule_result.get("schedule", [])
    if not schedule:
        return False, ["Amortization schedule is empty."], {}

    financed_amount = schedule_result.get("financed_amount", Decimal("0.00"))
    total_paid = schedule_result.get("total_paid", Decimal("0.00"))
    total_interest = schedule_result.get("total_interest", Decimal("0.00"))

    sum_principal = sum((row["principal"] for row in schedule), Decimal("0.00"))
    sum_instalments = sum((row["instalment"] for row in schedule), Decimal("0.00"))
    sum_interest = sum((row["interest"] for row in schedule), Decimal("0.00"))
    final_balance = schedule[-1]["closing_balance"]

    diff_principal = abs(sum_principal - financed_amount)
    diff_instalments = abs(sum_instalments - total_paid)
    diff_interest = abs(sum_interest - total_interest)
    diff_final_balance = abs(final_balance - Decimal("0.00"))

    if diff_principal > tolerance:
        errors.append(
            f"Amortization principal reconciliation mismatch: sum of principal repayments ({sum_principal}) "
            f"differs from financed principal ({financed_amount}) by {diff_principal} (tolerance: {tolerance})."
        )

    if diff_instalments > tolerance:
        errors.append(
            f"Amortization instalments reconciliation mismatch: sum of instalments ({sum_instalments}) "
            f"differs from total paid ({total_paid}) by {diff_instalments} (tolerance: {tolerance})."
        )

    if diff_interest > tolerance:
        errors.append(
            f"Amortization interest reconciliation mismatch: sum of interest charges ({sum_interest}) "
            f"differs from total interest ({total_interest}) by {diff_interest} (tolerance: {tolerance})."
        )

    if diff_final_balance > tolerance:
        errors.append(
            f"Amortization closing balance mismatch: final month closing balance ({final_balance}) "
            f"does not reconcile to zero (tolerance: {tolerance})."
        )

    metrics = {
        "sum_principal": money(sum_principal),
        "sum_instalments": money(sum_instalments),
        "sum_interest": money(sum_interest),
        "final_closing_balance": money(final_balance),
        "tolerance": tolerance,
        "reconciled": len(errors) == 0,
    }

    return (len(errors) == 0, errors, metrics)


def calculate_early_settlement(
    principal: Decimal,
    annual_eir: Decimal,
    term_months: int,
    settlement_month: int,
    rate_type: str = "fixed",
) -> Dict:
    """
    Calculate the early settlement payoff under the Malaysian
    Hire-Purchase (Amendment) Act 2026.

    Under Section 14 amendments and BNM guidelines:
    - Rule of 78 statutory rebate is abolished.
    - Early settlement payoff amount equals the outstanding principal balance
      remaining after settlement_month's instalment has been paid.
    - No further interest charges accrue for remaining tenure.
    - Statutory rebate amount is RM 0.00 (not applicable).
    """

    if settlement_month < 1 or settlement_month > term_months:
        raise ValueError(
            f"Settlement month must be between 1 and {term_months}."
        )

    schedule_result = calculate_reducing_balance(
        principal=principal,
        annual_eir=annual_eir,
        term_months=term_months,
        rate_type=rate_type,
    )

    schedule = schedule_result["schedule"]
    settled_row = schedule[settlement_month - 1]
    payoff_amount = settled_row["closing_balance"]

    total_instalments_paid = sum(
        row["instalment"] for row in schedule[:settlement_month]
    )
    total_interest_paid = sum(
        row["interest"] for row in schedule[:settlement_month]
    )
    interest_saved = money(
        schedule_result["total_interest"] - total_interest_paid
    )
    total_cost_with_early_settlement = money(
        total_instalments_paid + payoff_amount
    )

    return {
        "settlement_month": settlement_month,
        "outstanding_principal": payoff_amount,
        "settlement_payoff_amount": payoff_amount,
        "total_instalments_paid": money(total_instalments_paid),
        "interest_paid_to_date": money(total_interest_paid),
        "interest_saved": interest_saved,
        "statutory_rebate": Decimal("0.00"),
        "total_cost_with_early_settlement": total_cost_with_early_settlement,
        "full_term_total_paid": schedule_result["total_paid"],
        "legal_rule": "HP2026-ES-001",
        "legal_note": (
            "Under the Hire-Purchase (Amendment) Act 2026 and BNM guidelines, "
            "statutory rebates (Rule of 78) are abolished. The early settlement "
            "payoff is exactly the outstanding principal balance with zero future interest."
        ),
    }