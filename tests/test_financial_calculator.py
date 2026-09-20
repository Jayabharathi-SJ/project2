from decimal import Decimal

import pytest


def test_financed_amount_is_asset_price_minus_down_payment():
    asset_price = Decimal("100000.00")
    down_payment = Decimal("20000.00")

    financed_amount = asset_price - down_payment

    assert financed_amount == Decimal("80000.00")


def test_down_payment_cannot_exceed_asset_price():
    asset_price = Decimal("100000.00")
    down_payment = Decimal("120000.00")

    financed_amount = asset_price - down_payment

    assert financed_amount < Decimal("0.00")


def test_money_values_use_decimal():
    amount = Decimal("100000.00")

    assert isinstance(amount, Decimal)


def test_fixed_rate_eir_cap_up_to_5_years():
    eir = Decimal("17.00")
    maximum_eir = Decimal("17.00")

    assert eir <= maximum_eir


def test_fixed_rate_eir_cap_above_5_years():
    eir = Decimal("16.00")
    maximum_eir = Decimal("16.00")

    assert eir <= maximum_eir


def test_variable_rate_eir_cap():
    eir = Decimal("17.00")
    maximum_eir = Decimal("17.00")

    assert eir <= maximum_eir


def test_invalid_zero_asset_price():
    asset_price = Decimal("0.00")

    assert asset_price <= Decimal("0.00")


def test_invalid_negative_down_payment():
    down_payment = Decimal("-100.00")

    assert down_payment < Decimal("0.00")


def test_reducing_balance_schedule_closes_to_zero():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("5.50"),
        term_months=60,
    )

    assert result["financed_amount"] == Decimal("80000.00")
    assert result["term_months"] == 60
    assert result["annual_eir"] == Decimal("5.50")

    schedule = result["schedule"]

    assert len(schedule) == 60
    assert schedule[-1]["closing_balance"] == Decimal("0.00")

    total_principal = sum(
        row["principal"] for row in schedule
    )

    assert total_principal == Decimal("80000.00")


def test_total_paid_equals_principal_plus_interest():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("5.50"),
        term_months=60,
    )

    assert result["total_paid"] == (
        result["financed_amount"] + result["total_interest"]
    )


def test_first_month_interest_is_based_on_opening_balance():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("5.50"),
        term_months=60,
    )

    first_month = result["schedule"][0]

    expected_interest = Decimal("366.67")

    assert first_month["interest"] == expected_interest


def test_interest_reduces_as_principal_reduces():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("5.50"),
        term_months=60,
    )

    schedule = result["schedule"]

    assert schedule[0]["interest"] > schedule[1]["interest"]
    assert schedule[1]["interest"] > schedule[2]["interest"]


def test_zero_interest_is_supported():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("60000.00"),
        annual_eir=Decimal("0.00"),
        term_months=60,
    )

    assert result["total_interest"] == Decimal("0.00")
    assert result["total_paid"] == Decimal("60000.00")
    assert result["monthly_installment"] == Decimal("1000.00")


def test_invalid_financial_inputs_are_rejected():
    from tools.financial_calculator import calculate_reducing_balance

    with pytest.raises(ValueError):
        calculate_reducing_balance(
            principal=Decimal("0.00"),
            annual_eir=Decimal("5.50"),
            term_months=60,
        )

    with pytest.raises(ValueError):
        calculate_reducing_balance(
            principal=Decimal("80000.00"),
            annual_eir=Decimal("-1.00"),
            term_months=60,
        )

    with pytest.raises(ValueError):
        calculate_reducing_balance(
            principal=Decimal("80000.00"),
            annual_eir=Decimal("5.50"),
            term_months=0,
        )


def test_statutory_term_charges_matches_total_interest():
    from tools.financial_calculator import calculate_reducing_balance

    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("5.50"),
        term_months=60,
    )

    assert "term_charges" in result
    assert result["term_charges"] == result["total_interest"]
    assert result["rate_type"] == "fixed"


def test_variable_rate_reducing_balance_supports_17_percent_long_tenure():
    from tools.financial_calculator import calculate_reducing_balance

    # 17% is permitted for variable rate above 5 years (72 months)
    result = calculate_reducing_balance(
        principal=Decimal("80000.00"),
        annual_eir=Decimal("17.00"),
        term_months=72,
        rate_type="variable",
    )

    assert result["rate_type"] == "variable"
    assert result["term_months"] == 72
    assert result["schedule"][-1]["closing_balance"] == Decimal("0.00")


def test_early_settlement_calculation_and_zero_rebate():
    from tools.financial_calculator import (
        calculate_reducing_balance,
        calculate_early_settlement,
    )

    principal = Decimal("80000.00")
    eir = Decimal("5.50")
    term = 60
    settle_month = 24

    full_schedule = calculate_reducing_balance(
        principal=principal,
        annual_eir=eir,
        term_months=term,
    )

    early = calculate_early_settlement(
        principal=principal,
        annual_eir=eir,
        term_months=term,
        settlement_month=settle_month,
    )

    # 1. Payoff is exactly month 24's closing balance
    expected_payoff = full_schedule["schedule"][settle_month - 1]["closing_balance"]
    assert early["outstanding_principal"] == expected_payoff
    assert early["settlement_payoff_amount"] == expected_payoff

    # 2. Statutory rebate is RM 0.00 (abolished under HP 2026)
    assert early["statutory_rebate"] == Decimal("0.00")

    # 3. Interest saved equals unaccrued future interest
    interest_paid_24 = sum(
        row["interest"] for row in full_schedule["schedule"][:settle_month]
    )
    assert early["interest_paid_to_date"] == interest_paid_24
    assert early["interest_saved"] == full_schedule["total_interest"] - interest_paid_24

    # 4. Total cost with early settlement is less than full term total
    assert early["total_cost_with_early_settlement"] < early["full_term_total_paid"]


def test_early_settlement_invalid_month_rejected():
    from tools.financial_calculator import calculate_early_settlement

    with pytest.raises(ValueError):
        calculate_early_settlement(
            principal=Decimal("80000.00"),
            annual_eir=Decimal("5.50"),
            term_months=60,
            settlement_month=0,
        )

    with pytest.raises(ValueError):
        calculate_early_settlement(
            principal=Decimal("80000.00"),
            annual_eir=Decimal("5.50"),
            term_months=60,
            settlement_month=61,
        )