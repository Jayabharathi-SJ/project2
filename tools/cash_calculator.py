from decimal import Decimal, ROUND_HALF_UP
from typing import Dict


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round monetary values to 2 decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_cash_purchase(
    asset_price: Decimal,
    discount: Decimal = Decimal("0.00"),
) -> Dict:
    """
    Calculate the total cash purchase cost of an asset.
    """

    if asset_price <= 0:
        raise ValueError("Asset price must be greater than zero.")

    if discount < 0:
        raise ValueError("Discount cannot be negative.")

    if discount > asset_price:
        raise ValueError("Discount cannot exceed asset price.")

    total_cash_cost = money(asset_price - discount)

    return {
        "asset_price": money(asset_price),
        "discount": money(discount),
        "total_cash_cost": total_cash_cost,
    }