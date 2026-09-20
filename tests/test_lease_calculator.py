from decimal import Decimal

import pytest

from tools.lease_calculator import calculate_lease_cost


def test_lease_cost_is_monthly_payment_times_period():
    result = calculate_lease_cost(
        monthly_payment=Decimal("1800.00"),
        lease_period_months=60,
    )

    assert result["total_lease_cost"] == Decimal("108000.00")


def test_lease_monthly_payment_is_returned():
    result = calculate_lease_cost(
        monthly_payment=Decimal("1800.00"),
        lease_period_months=60,
    )

    assert result["monthly_payment"] == Decimal("1800.00")


def test_lease_period_is_returned():
    result = calculate_lease_cost(
        monthly_payment=Decimal("1800.00"),
        lease_period_months=60,
    )

    assert result["lease_period_months"] == 60


def test_zero_monthly_payment_is_rejected():
    with pytest.raises(ValueError):
        calculate_lease_cost(
            monthly_payment=Decimal("0.00"),
            lease_period_months=60,
        )


def test_negative_monthly_payment_is_rejected():
    with pytest.raises(ValueError):
        calculate_lease_cost(
            monthly_payment=Decimal("-1800.00"),
            lease_period_months=60,
        )


def test_zero_lease_period_is_rejected():
    with pytest.raises(ValueError):
        calculate_lease_cost(
            monthly_payment=Decimal("1800.00"),
            lease_period_months=0,
        )


def test_negative_lease_period_is_rejected():
    with pytest.raises(ValueError):
        calculate_lease_cost(
            monthly_payment=Decimal("1800.00"),
            lease_period_months=-12,
        )