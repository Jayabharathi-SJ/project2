import asyncio
from decimal import Decimal

from graph.nodes import (
    cfo_recommendation_node,
    financial_analysis_node,
    legal_validation_node,
    research_agent_node,
    validate_input_node,
)
from graph.workflow import build_cfo_graph
from services.asset_analysis_service import _process_result


def valid_state():
    return {
        "asset_name": "Toyota Corolla",
        "asset_price": Decimal("100000"),
        "down_payment": Decimal("20000"),
        "hp_period_months": 60,
        "hp_interest_rate": Decimal("5.5"),
        "hp_rate_type": "fixed",
        "lease_period_months": 60,
        "lease_monthly_payment": Decimal("1800"),
        "cash_discount": Decimal("0.00"),
    }


def test_full_workflow_audit_trail_contains_all_agents():
    graph = build_cfo_graph()
    result = asyncio.run(graph.ainvoke(valid_state()))

    assert result["validation_passed"] is True
    assert "audit_trail" in result

    trail = result["audit_trail"]
    assert len(trail) >= 5

    agents = [entry["agent"] for entry in trail]
    assert "validate_input" in agents
    assert "research_agent" in agents
    assert "legal_validation" in agents
    assert "financial_engine" in agents
    assert "cfo_committee" in agents


def test_audit_trail_on_input_validation_failure():
    state = valid_state()
    state["down_payment"] = Decimal("150000")  # exceeds asset price

    result = validate_input_node(state)
    assert result["validation_passed"] is False
    assert len(result["audit_trail"]) == 1
    assert result["audit_trail"][0]["agent"] == "validate_input"
    assert result["audit_trail"][0]["action"] == "input_validation_failed"


def test_audit_trail_accumulates_on_legal_validation_failure():
    state = valid_state()
    state["down_payment"] = Decimal("5000")  # 5% < 10% statutory minimum

    step1 = validate_input_node(state)
    state.update(step1)

    step2 = research_agent_node(state)
    state.update(step2)

    step3 = legal_validation_node(state)
    assert step3["legal_validation"]["passed"] is False

    trail = step3["audit_trail"]
    agents = [e["agent"] for e in trail]
    assert "validate_input" in agents
    assert "research_agent" in agents
    assert "legal_validation" in agents
    assert trail[-1]["action"] == "legal_validation_failed"


def test_data_classifications_cover_all_categories():
    graph = build_cfo_graph()
    result = asyncio.run(graph.ainvoke(valid_state()))

    classifications = result.get("data_classifications", [])
    categories = {c["classification"] for c in classifications}

    assert "user_input" in categories
    assert "retrieved_legal" in categories
    assert "verified_rule" in categories
    assert "derived_value" in categories
    assert "cfo_synthesis" in categories


def test_process_result_includes_audit_trail_and_warnings():
    raw_result = {
        "validation_passed": True,
        "current_step": "cfo_recommendation_completed",
        "financial_analysis": {"financed_amount": Decimal("80000")},
        "audit_trail": [{"agent": "validate_input", "action": "passed"}],
        "warnings": ["Sample non-blocking warning"],
        "data_classifications": [{"field": "asset_name", "classification": "user_input"}],
        "recommendation": "Cash Purchase",
    }

    processed = _process_result(raw_result, thread_id="test-123")

    assert processed["thread_id"] == "test-123"
    assert "audit_trail" in processed
    assert len(processed["audit_trail"]) == 1
    assert "warnings" in processed
    assert "Sample non-blocking warning" in processed["warnings"]
    assert "data_classifications" in processed
    assert len(processed["data_classifications"]) == 1
