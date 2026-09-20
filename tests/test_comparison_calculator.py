from decimal import Decimal

import pytest

from tools.comparison_calculator import compare_asset_options


def test_cash_is_cheapest_option():
    result = compare_asset_options(
        cash_cost=Decimal("100000.00"),
        hp_total_cost=Decimal("115000.00"),
        lease_total_cost=Decimal("120000.00"),
    )

    assert result["recommended_option"] == "cash_purchase"
    assert result["lowest_total_cost"] == Decimal("100000.00")


def test_hire_purchase_is_cheapest_option():
    result = compare_asset_options(
        cash_cost=Decimal("120000.00"),
        hp_total_cost=Decimal("110000.00"),
        lease_total_cost=Decimal("125000.00"),
    )

    assert result["recommended_option"] == "hire_purchase"
    assert result["lowest_total_cost"] == Decimal("110000.00")


def test_leasing_is_cheapest_option():
    result = compare_asset_options(
        cash_cost=Decimal("120000.00"),
        hp_total_cost=Decimal("125000.00"),
        lease_total_cost=Decimal("115000.00"),
    )

    assert result["recommended_option"] == "leasing"
    assert result["lowest_total_cost"] == Decimal("115000.00")


def test_all_option_costs_are_returned():
    result = compare_asset_options(
        cash_cost=Decimal("100000.00"),
        hp_total_cost=Decimal("110000.00"),
        lease_total_cost=Decimal("120000.00"),
    )

    assert result["cash_purchase_cost"] == Decimal("100000.00")
    assert result["hire_purchase_cost"] == Decimal("110000.00")
    assert result["leasing_cost"] == Decimal("120000.00")


def test_negative_cash_cost_is_rejected():
    with pytest.raises(ValueError):
        compare_asset_options(
            cash_cost=Decimal("-100000.00"),
            hp_total_cost=Decimal("110000.00"),
            lease_total_cost=Decimal("120000.00"),
        )


def test_negative_hire_purchase_cost_is_rejected():
    with pytest.raises(ValueError):
        compare_asset_options(
            cash_cost=Decimal("100000.00"),
            hp_total_cost=Decimal("-110000.00"),
            lease_total_cost=Decimal("120000.00"),
        )


def test_negative_lease_cost_is_rejected():
    with pytest.raises(ValueError):
        compare_asset_options(
            cash_cost=Decimal("100000.00"),
            hp_total_cost=Decimal("110000.00"),
            lease_total_cost=Decimal("-120000.00"),
        )


def test_detailed_comparison_includes_cfo_metrics():
    from tools.comparison_calculator import compare_asset_options_detailed

    result = compare_asset_options_detailed(
        cash_cost=Decimal("100000.00"),
        hp_total_cost=Decimal("112000.00"),
        lease_total_cost=Decimal("125000.00"),
        asset_price=Decimal("100000.00"),
        cash_discount=Decimal("2000.00"),
        down_payment=Decimal("20000.00"),
        hp_monthly_installment=Decimal("1800.00"),
        hp_term_months=60,
        hp_total_interest=Decimal("12000.00"),
        lease_monthly_payment=Decimal("2083.33"),
        lease_term_months=60,
    )

    assert result["recommended_option"] == "cash_purchase"
    assert result["lowest_total_cost"] == Decimal("100000.00")
    assert "upfront_outlay" in result
    assert result["upfront_outlay"]["cash_purchase"] == Decimal("98000.00")
    assert result["upfront_outlay"]["hire_purchase"] == Decimal("20000.00")
    assert "monthly_commitment" in result
    assert result["monthly_commitment"]["hire_purchase"] == Decimal("1800.00")
    assert "liquidity_retained_vs_cash" in result
    assert result["liquidity_retained_vs_cash"]["hire_purchase"] == Decimal("78000.00")
    assert "total_interest_burden" in result
    assert result["total_interest_burden"]["hire_purchase"] == Decimal("12000.00")
    assert "ownership" in result
    assert "data_quality_notes" in result


def test_detailed_comparison_handles_missing_optional_fields():
    from tools.comparison_calculator import compare_asset_options_detailed

    result = compare_asset_options_detailed(
        cash_cost=Decimal("100000.00"),
        hp_total_cost=Decimal("112000.00"),
        lease_total_cost=Decimal("125000.00"),
    )

    assert result["recommended_option"] == "cash_purchase"
    assert result["upfront_outlay"]["cash_purchase"] == "insufficient_data"
    assert result["liquidity_retained_vs_cash"]["hire_purchase"] == "insufficient_data"