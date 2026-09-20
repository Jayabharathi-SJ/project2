from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round monetary values to 2 decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_lease_cost(
    monthly_payment: Decimal,
    lease_period_months: int,
) -> Dict:
    """
    Calculate the total basic lease cost.
    """

    if monthly_payment <= 0:
        raise ValueError("Monthly lease payment must be greater than zero.")

    if lease_period_months <= 0:
        raise ValueError("Lease period must be greater than zero.")

    total_lease_cost = money(
        monthly_payment * Decimal(lease_period_months)
    )

    return {
        "monthly_payment": money(monthly_payment),
        "lease_period_months": lease_period_months,
        "total_lease_cost": total_lease_cost,
    }