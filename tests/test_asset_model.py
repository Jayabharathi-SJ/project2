from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.asset import AssetAnalysisRequest


def valid_request():
    return {
        "asset_name": "Toyota Corolla",
        "asset_price": Decimal("100000"),
        "down_payment": Decimal("20000"),
        "hp_period_months": 60,
        "hp_interest_rate": Decimal("5.5"),
        "lease_period_months": 60,
        "lease_monthly_payment": Decimal("1800"),
    }


def test_valid_asset_request():
    request = AssetAnalysisRequest(**valid_request())

    assert request.asset_name == "Toyota Corolla"
    assert request.asset_price == Decimal("100000")
    assert request.down_payment == Decimal("20000")


def test_down_payment_cannot_exceed_asset_price():
    data = valid_request()
    data["down_payment"] = Decimal("120000")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_negative_asset_price_rejected():
    data = valid_request()
    data["asset_price"] = Decimal("-100")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_zero_asset_price_rejected():
    data = valid_request()
    data["asset_price"] = Decimal("0")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_negative_down_payment_rejected():
    data = valid_request()
    data["down_payment"] = Decimal("-1")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_zero_hp_period_rejected():
    data = valid_request()
    data["hp_period_months"] = 0

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_negative_hp_interest_rate_rejected():
    data = valid_request()
    data["hp_interest_rate"] = Decimal("-1")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_empty_asset_name_rejected():
    data = valid_request()
    data["asset_name"] = "   "

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_lease_monthly_payment_must_be_positive():
    data = valid_request()
    data["lease_monthly_payment"] = Decimal("0")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_cash_discount_defaults_to_zero():
    request = AssetAnalysisRequest(**valid_request())
    assert request.cash_discount == Decimal("0.00")


def test_valid_cash_discount():
    data = valid_request()
    data["cash_discount"] = Decimal("5000.00")
    request = AssetAnalysisRequest(**data)
    assert request.cash_discount == Decimal("5000.00")


def test_negative_cash_discount_rejected():
    data = valid_request()
    data["cash_discount"] = Decimal("-500.00")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)


def test_cash_discount_exceeding_asset_price_rejected():
    data = valid_request()
    data["cash_discount"] = Decimal("150000.00")

    with pytest.raises(ValidationError):
        AssetAnalysisRequest(**data)