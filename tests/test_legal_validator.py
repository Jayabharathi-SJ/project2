from decimal import Decimal

import pytest

from rag.legal_validator import (
    validate_fixed_eir_cap,
    validate_variable_eir_cap,
)


def test_fixed_eir_17_percent_allowed_for_5_years():
    validate_fixed_eir_cap(
        annual_eir=Decimal("17"),
        term_months=60,
    )


def test_fixed_eir_above_17_percent_rejected_for_5_years():
    with pytest.raises(ValueError):
        validate_fixed_eir_cap(
            annual_eir=Decimal("17.01"),
            term_months=60,
        )


def test_fixed_eir_16_percent_allowed_above_5_years():
    validate_fixed_eir_cap(
        annual_eir=Decimal("16"),
        term_months=61,
    )


def test_fixed_eir_above_16_percent_rejected_above_5_years():
    with pytest.raises(ValueError):
        validate_fixed_eir_cap(
            annual_eir=Decimal("16.01"),
            term_months=61,
        )


def test_variable_eir_17_percent_allowed():
    validate_variable_eir_cap(
        annual_eir=Decimal("17"),
        term_months=120,
    )


def test_variable_eir_above_17_percent_rejected():
    with pytest.raises(ValueError):
        validate_variable_eir_cap(
            annual_eir=Decimal("17.01"),
            term_months=120,
        )


def test_negative_eir_rejected():
    with pytest.raises(ValueError):
        validate_fixed_eir_cap(
            annual_eir=Decimal("-1"),
            term_months=60,
        )


def test_zero_term_rejected():
    with pytest.raises(ValueError):
        validate_fixed_eir_cap(
            annual_eir=Decimal("10"),
            term_months=0,
        )


def test_validate_eir_cap_dispatcher():
    from rag.legal_validator import validate_eir_cap

    # Fixed rate: 17% allowed at 60m, but rejected at 61m
    validate_eir_cap(Decimal("17.00"), 60, rate_type="fixed")
    with pytest.raises(ValueError):
        validate_eir_cap(Decimal("16.01"), 61, rate_type="fixed")

    # Variable rate: 17% allowed at 61m and 120m
    validate_eir_cap(Decimal("17.00"), 61, rate_type="variable")
    validate_eir_cap(Decimal("17.00"), 120, rate_type="variable")
    with pytest.raises(ValueError):
        validate_eir_cap(Decimal("17.01"), 120, rate_type="variable")

    # Invalid rate type rejected
    with pytest.raises(ValueError):
        validate_eir_cap(Decimal("10.00"), 60, rate_type="floating_custom")


def test_statutory_minimum_deposit_validation():
    from rag.legal_validator import validate_minimum_deposit

    price = Decimal("100000.00")

    # 10% deposit is exactly compliant
    validate_minimum_deposit(Decimal("10000.00"), price)

    # 20% deposit is compliant
    validate_minimum_deposit(Decimal("20000.00"), price)

    # 9.99% deposit is rejected under Section 31(1)
    with pytest.raises(ValueError, match="statutory minimum deposit"):
        validate_minimum_deposit(Decimal("9999.00"), price)

    # Zero deposit is rejected
    with pytest.raises(ValueError, match="statutory minimum deposit"):
        validate_minimum_deposit(Decimal("0.00"), price)


def test_check_minimum_deposit_helper():
    from rag.legal_validator import check_minimum_deposit

    price = Decimal("100000.00")

    res_compliant = check_minimum_deposit(Decimal("15000.00"), price)
    assert res_compliant["compliant"] is True
    assert res_compliant["required_minimum"] == Decimal("10000.00")
    assert res_compliant["shortfall"] == Decimal("0.00")

    res_short = check_minimum_deposit(Decimal("8000.00"), price)
    assert res_short["compliant"] is False
    assert res_short["required_minimum"] == Decimal("10000.00")
    assert res_short["shortfall"] == Decimal("2000.00")