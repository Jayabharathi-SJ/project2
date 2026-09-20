from decimal import Decimal

from services.asset_analysis_service import analyze_asset_financial_options


def test_full_asset_analysis_returns_all_three_options():
    result = analyze_asset_financial_options(
        asset_price=Decimal("100000.00"),
        down_payment=Decimal("20000.00"),
        hp_period_months=60,
        hp_interest_rate=Decimal("5.50"),
        lease_period_months=60,
        lease_monthly_payment=Decimal("1800.00"),
    )

    assert "cash_purchase" in result
    assert "hire_purchase" in result
    assert "leasing" in result
    assert "comparison" in result


def test_financed_amount_is_calculated_correctly():
    result = analyze_asset_financial_options(
        asset_price=Decimal("100000.00"),
        down_payment=Decimal("20000.00"),
        hp_period_months=60,
        hp_interest_rate=Decimal("5.50"),
        lease_period_months=60,
        lease_monthly_payment=Decimal("1800.00"),
    )

    assert result["financed_amount"] == Decimal("80000.00")


def test_cash_cost_is_returned():
    result = analyze_asset_financial_options(
        asset_price=Decimal("100000.00"),
        down_payment=Decimal("20000.00"),
        hp_period_months=60,
        hp_interest_rate=Decimal("5.50"),
        lease_period_months=60,
        lease_monthly_payment=Decimal("1800.00"),
    )

    assert result["cash_purchase"]["total_cash_cost"] == Decimal("100000.00")


def test_lease_cost_is_returned():
    result = analyze_asset_financial_options(
        asset_price=Decimal("100000.00"),
        down_payment=Decimal("20000.00"),
        hp_period_months=60,
        hp_interest_rate=Decimal("5.50"),
        lease_period_months=60,
        lease_monthly_payment=Decimal("1800.00"),
    )

    assert result["leasing"]["total_lease_cost"] == Decimal("108000.00")


def test_invalid_down_payment_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        analyze_asset_financial_options(
            asset_price=Decimal("100000.00"),
            down_payment=Decimal("120000.00"),
            hp_period_months=60,
            hp_interest_rate=Decimal("5.50"),
            lease_period_months=60,
            lease_monthly_payment=Decimal("1800.00"),
        )