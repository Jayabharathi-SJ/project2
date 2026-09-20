from unittest.mock import patch

from graph.nodes import research_agent_node


def valid_state():
    return {
        "asset_name": "Commercial Van",
        "asset_price": 80000,
        "down_payment": 16000,
        "hp_period_months": 60,
        "hp_interest_rate": 5.0,
        "lease_period_months": 60,
        "lease_monthly_payment": 1500,
        "audit_trail": [
            {"agent": "validate_input", "action": "input_validation_passed"}
        ],
        "warnings": [],
    }


def test_research_agent_falls_back_when_qdrant_fails():
    state = valid_state()

    # Simulate Qdrant client connection failure
    with patch("graph.nodes.create_qdrant_client", side_effect=ConnectionError("Qdrant offline")):
        result = research_agent_node(state)

    assert result["current_step"] == "research_completed"
    assert "legal_rules" in result
    assert len(result["legal_rules"]) > 0

    # Ensure the fallback rules come from legal_rules.py
    assert any("legal_rules.py" in rule.get("source", "") for rule in result["legal_rules"])

    # Ensure warning was recorded
    warnings = result.get("warnings", [])
    assert any("fell back to verified in-memory rules" in w for w in warnings)

    # Ensure audit trail was preserved and appended
    trail = result.get("audit_trail", [])
    assert len(trail) == 2
    assert trail[0]["agent"] == "validate_input"
    assert trail[1]["agent"] == "research_agent"
    assert "fallback" in trail[1]["source"].lower()
