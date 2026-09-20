from decimal import Decimal

import pytest

from tools.cash_calculator import calculate_cash_purchase


def test_cash_purchase_without_discount():
    result = calculate_cash_purchase(
        asset_price=Decimal("100000.00")
    )

    assert result["asset_price"] == Decimal("100000.00")
    assert result["discount"] == Decimal("0.00")
    assert result["total_cash_cost"] == Decimal("100000.00")


def test_cash_purchase_with_discount():
    result = calculate_cash_purchase(
        asset_price=Decimal("100000.00"),
        discount=Decimal("5000.00")
    )

    assert result["total_cash_cost"] == Decimal("95000.00")


def test_discount_is_subtracted_from_asset_price():
    result = calculate_cash_purchase(
        asset_price=Decimal("80000.00"),
        discount=Decimal("10000.00")
    )

    assert result["total_cash_cost"] == Decimal("70000.00")


def test_zero_asset_price_is_rejected():
    with pytest.raises(ValueError):
        calculate_cash_purchase(
            asset_price=Decimal("0.00")
        )


def test_negative_asset_price_is_rejected():
    with pytest.raises(ValueError):
        calculate_cash_purchase(
            asset_price=Decimal("-1000.00")
        )


def test_negative_discount_is_rejected():
    with pytest.raises(ValueError):
        calculate_cash_purchase(
            asset_price=Decimal("100000.00"),
            discount=Decimal("-500.00")
        )


def test_discount_cannot_exceed_asset_price():
    with pytest.raises(ValueError):
        calculate_cash_purchase(
            asset_price=Decimal("100000.00"),
            discount=Decimal("120000.00")
        )