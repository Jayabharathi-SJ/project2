from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round monetary values to 2 decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def compare_asset_options(
    cash_cost: Decimal,
    hp_total_cost: Decimal,
    lease_total_cost: Decimal,
) -> Dict:
    """
    Compare Cash Purchase, Hire Purchase and Leasing
    based on total cost.

    Returns all original keys for backward compatibility,
    plus additional CFO-grade analysis fields.
    """

    costs = {
        "cash_purchase": cash_cost,
        "hire_purchase": hp_total_cost,
        "leasing": lease_total_cost,
    }

    for option, cost in costs.items():
        if cost < 0:
            raise ValueError(
                f"{option} cost cannot be negative."
            )

    recommended_option = min(
        costs,
        key=costs.get,
    )

    return {
        # --- Original keys preserved for backward compatibility ---
        "cash_purchase_cost": cash_cost,
        "hire_purchase_cost": hp_total_cost,
        "leasing_cost": lease_total_cost,
        "recommended_option": recommended_option,
        "lowest_total_cost": costs[recommended_option],
    }


def compare_asset_options_detailed(
    # Total costs (required)
    cash_cost: Decimal,
    hp_total_cost: Decimal,
    lease_total_cost: Decimal,
    # Upfront outlay details (optional but enriches CFO analysis)
    asset_price: Optional[Decimal] = None,
    cash_discount: Optional[Decimal] = None,
    down_payment: Optional[Decimal] = None,
    hp_monthly_installment: Optional[Decimal] = None,
    hp_term_months: Optional[int] = None,
    hp_total_interest: Optional[Decimal] = None,
    lease_monthly_payment: Optional[Decimal] = None,
    lease_term_months: Optional[int] = None,
) -> Dict:
    """
    Extended CFO-grade comparison that surfaces:
    - Total cost comparison (primary decision criterion)
    - Upfront cash outlay per option
    - Monthly cash flow commitment
    - Liquidity retained vs cash purchase
    - Total interest burden (hire purchase)
    - Data sufficiency labels

    NOTE: The recommended_option is always determined
    deterministically from total cost — never by LLM.
    Items marked 'insufficient_data' require additional
    inputs before they can be computed.
    """

    # Validate required inputs
    for label, val in [
        ("cash_cost", cash_cost),
        ("hp_total_cost", hp_total_cost),
        ("lease_total_cost", lease_total_cost),
    ]:
        if val < Decimal("0"):
            raise ValueError(f"{label} cannot be negative.")

    costs = {
        "cash_purchase": cash_cost,
        "hire_purchase": hp_total_cost,
        "leasing": lease_total_cost,
    }

    recommended_option = min(costs, key=costs.get)
    savings_vs_recommended = {
        opt: money(cost - costs[recommended_option])
        for opt, cost in costs.items()
    }

    # -------------------------------------------------------
    # Upfront cash outlay
    # -------------------------------------------------------
    cash_upfront = (
        money(asset_price - (cash_discount or Decimal("0")))
        if asset_price is not None
        else "insufficient_data"
    )
    hp_upfront = (
        money(down_payment)
        if down_payment is not None
        else "insufficient_data"
    )
    lease_upfront = (
        money(lease_monthly_payment)   # First month's payment is the outlay
        if lease_monthly_payment is not None
        else "insufficient_data"
    )

    # -------------------------------------------------------
    # Monthly cash flow commitment
    # -------------------------------------------------------
    cash_monthly = (
        Decimal("0.00")    # No ongoing monthly obligation after purchase
        if asset_price is not None
        else "insufficient_data"
    )
    hp_monthly = (
        money(hp_monthly_installment)
        if hp_monthly_installment is not None
        else "insufficient_data"
    )
    lease_monthly = (
        money(lease_monthly_payment)
        if lease_monthly_payment is not None
        else "insufficient_data"
    )

    # -------------------------------------------------------
    # Liquidity retained vs full cash purchase
    # -------------------------------------------------------
    if asset_price is not None and down_payment is not None:
        liquidity_retained_hp = money(
            asset_price - (cash_discount or Decimal("0")) - down_payment
        )
    else:
        liquidity_retained_hp = "insufficient_data"

    if asset_price is not None and lease_monthly_payment is not None:
        liquidity_retained_lease = money(
            asset_price
            - (cash_discount or Decimal("0"))
            - lease_monthly_payment
        )
    else:
        liquidity_retained_lease = "insufficient_data"

    # -------------------------------------------------------
    # Total interest burden (HP only)
    # -------------------------------------------------------
    interest_burden_hp = (
        money(hp_total_interest)
        if hp_total_interest is not None
        else "insufficient_data"
    )

    # -------------------------------------------------------
    # Ownership status
    # -------------------------------------------------------
    ownership = {
        "cash_purchase": "Full ownership from day 1",
        "hire_purchase": "Ownership transfers after final instalment",
        "leasing": "No ownership — asset returned at end of lease",
    }

    return {
        # --- Original keys preserved ---
        "cash_purchase_cost": cash_cost,
        "hire_purchase_cost": hp_total_cost,
        "leasing_cost": lease_total_cost,
        "recommended_option": recommended_option,
        "lowest_total_cost": costs[recommended_option],

        # --- Extended CFO analysis ---
        "savings_vs_recommended": savings_vs_recommended,

        "upfront_outlay": {
            "cash_purchase": cash_upfront,
            "hire_purchase": hp_upfront,
            "leasing": lease_upfront,
        },

        "monthly_commitment": {
            "cash_purchase": cash_monthly,
            "hire_purchase": hp_monthly,
            "leasing": lease_monthly,
        },

        "liquidity_retained_vs_cash": {
            "cash_purchase": Decimal("0.00"),
            "hire_purchase": liquidity_retained_hp,
            "leasing": liquidity_retained_lease,
        },

        "total_interest_burden": {
            "cash_purchase": Decimal("0.00"),
            "hire_purchase": interest_burden_hp,
            "leasing": "not_applicable",
        },

        "ownership": ownership,

        "data_quality_notes": (
            "Items labelled 'insufficient_data' require additional "
            "inputs before they can be computed. "
            "The recommended_option is always determined "
            "deterministically from total cost."
        ),
    }