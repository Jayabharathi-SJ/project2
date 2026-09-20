from decimal import Decimal

from graph.nodes import validate_input_node


def valid_state():
    return {
        "asset_name": "Toyota Corolla",
        "asset_price": Decimal("100000"),
        "down_payment": Decimal("20000"),
        "hp_period_months": 60,
        "hp_interest_rate": Decimal("5.5"),
        "lease_period_months": 60,
        "lease_monthly_payment": Decimal("1800"),
    }


def test_valid_input_passes():
    result = validate_input_node(valid_state())

    assert result["validation_passed"] is True
    assert result["validation_errors"] == []
    assert result["current_step"] == "input_validation_completed"


def test_missing_required_field_fails():
    state = valid_state()
    del state["asset_price"]

    result = validate_input_node(state)

    assert result["validation_passed"] is False
    assert "Missing required field: asset_price" in result[
        "validation_errors"
    ]


def test_down_payment_above_asset_price_fails():
    state = valid_state()
    state["down_payment"] = Decimal("120000")

    result = validate_input_node(state)

    assert result["validation_passed"] is False
    assert "Down payment cannot exceed asset price." in result[
        "validation_errors"
    ]


def test_negative_asset_price_fails():
    state = valid_state()
    state["asset_price"] = Decimal("-100")

    result = validate_input_node(state)

    assert result["validation_passed"] is False


def test_negative_eir_fails():
    state = valid_state()
    state["hp_interest_rate"] = Decimal("-1")

    result = validate_input_node(state)

    assert result["validation_passed"] is False
    assert "Hire-purchase EIR cannot be negative." in result[
        "validation_errors"
    ]


def test_eir_above_legal_cap_fails():
    state = valid_state()
    state["hp_interest_rate"] = Decimal("18")

    result = validate_input_node(state)

    assert result["validation_passed"] is False
    assert len(result["validation_errors"]) > 0


def test_zero_hp_period_fails():
    state = valid_state()
    state["hp_period_months"] = 0

    result = validate_input_node(state)

    assert result["validation_passed"] is False


def test_multiple_validation_errors_are_collected():
    state = valid_state()
    state["asset_price"] = Decimal("-100")
    state["down_payment"] = Decimal("200")
    state["hp_period_months"] = 0
    state["hp_interest_rate"] = Decimal("-1")

    result = validate_input_node(state)

    assert result["validation_passed"] is False
    assert len(result["validation_errors"]) >= 3