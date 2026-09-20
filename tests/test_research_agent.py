from graph.nodes import research_agent_node


def valid_state():
    return {
        "asset_name": "Toyota Corolla",
        "asset_price": 100000,
        "down_payment": 20000,
        "hp_period_months": 60,
        "hp_interest_rate": 5.5,
        "lease_period_months": 60,
        "lease_monthly_payment": 1800,
    }


def test_research_agent_returns_findings():
    result = research_agent_node(valid_state())

    assert "research_findings" in result
    assert isinstance(result["research_findings"], list)
    assert len(result["research_findings"]) > 0


def test_research_agent_current_step():
    result = research_agent_node(valid_state())

    assert result["current_step"] == "research_completed"


def test_research_agent_contains_asset_information():
    result = research_agent_node(valid_state())

    findings = result["research_findings"]

    asset_finding = next(
        item
        for item in findings
        if item["topic"] == "Asset"
    )

    assert "Toyota Corolla" in asset_finding["finding"]


def test_research_agent_contains_legal_rag_context():
    result = research_agent_node(valid_state())

    findings = result["research_findings"]

    legal_finding = next(
        item
        for item in findings
        if item["topic"] == "Legal RAG"
    )

    assert "contexts" in legal_finding
    assert isinstance(legal_finding["contexts"], list)
    assert len(legal_finding["contexts"]) > 0


def test_research_agent_returns_legal_rules():
    result = research_agent_node(valid_state())

    assert "legal_rules" in result
    assert isinstance(result["legal_rules"], list)
    assert len(result["legal_rules"]) > 0