from decimal import Decimal

from graph.nodes import legal_validation_node


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


def test_legal_validation_passes_for_valid_eir():
    result = legal_validation_node(valid_state())

    assert result["legal_validation"]["passed"] is True
    assert result["legal_validation"]["errors"] == []
    assert result["current_step"] == "legal_validation_completed"


def test_legal_validation_returns_eir_details():
    result = legal_validation_node(valid_state())

    validation = result["legal_validation"]

    assert validation["validated_eir"] == Decimal("5.5")
    assert validation["term_months"] == 60
    assert validation["method"] == "Reducing Balance / EIR"


def test_legal_validation_fails_when_eir_exceeds_cap():
    state = valid_state()
    state["hp_interest_rate"] = Decimal("18")

    result = legal_validation_node(state)

    assert result["legal_validation"]["passed"] is False
    assert len(result["legal_validation"]["errors"]) > 0
    assert result["current_step"] == "legal_validation_failed"


def test_legal_validation_fails_for_long_term_above_cap():
    state = valid_state()
    state["hp_period_months"] = 61
    state["hp_interest_rate"] = Decimal("17")

    result = legal_validation_node(state)

    assert result["legal_validation"]["passed"] is False
    assert len(result["legal_validation"]["errors"]) > 0


def test_legal_validation_passes_variable_rate_long_term_at_17_percent():
    state = valid_state()
    state["hp_rate_type"] = "variable"
    state["hp_period_months"] = 72
    state["hp_interest_rate"] = Decimal("17")

    result = legal_validation_node(state)

    assert result["legal_validation"]["passed"] is True
    assert result["legal_validation"]["rate_type"] == "variable"
    assert result["legal_validation"]["deposit_compliant"] is True


def test_legal_validation_fails_when_deposit_below_10_percent():
    state = valid_state()
    state["down_payment"] = Decimal("5000")  # 5% on 100k

    result = legal_validation_node(state)

    assert result["legal_validation"]["passed"] is False
    assert any("statutory minimum deposit" in err.lower() for err in result["legal_validation"]["errors"])