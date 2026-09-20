import asyncio
from decimal import Decimal

from graph.workflow import build_cfo_graph


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


def test_cfo_graph_valid_input():
    graph = build_cfo_graph()

    result = asyncio.run(
        graph.ainvoke(valid_state())
    )

    assert result["validation_passed"] is True
    assert result["validation_errors"] == []

    assert result["current_step"] == "cfo_recommendation_completed"

    assert "financial_analysis" in result
    assert "legal_validation" in result

    assert result["recommendation"] is not None


def test_cfo_graph_invalid_input():
    graph = build_cfo_graph()

    state = valid_state()
    state["down_payment"] = Decimal("120000")

    result = asyncio.run(
        graph.ainvoke(state)
    )

    assert result["validation_passed"] is False
    assert len(result["validation_errors"]) > 0

    assert result["current_step"] == "input_validation_failed"