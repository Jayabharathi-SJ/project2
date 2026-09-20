from decimal import Decimal

from graph.nodes import financial_analysis_node


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


def test_financial_analysis_returns_result():
    result = financial_analysis_node(valid_state())

    assert "financial_analysis" in result
    assert result["current_step"] == "financial_analysis_completed"


def test_financed_amount_is_correct():
    result = financial_analysis_node(valid_state())

    analysis = result["financial_analysis"]

    assert analysis["financed_amount"] == Decimal("80000")


def test_cash_purchase_result():
    result = financial_analysis_node(valid_state())

    cash = result["financial_analysis"]["cash_purchase"]

    assert cash["total_cash_cost"] == Decimal("100000.00")


def test_hire_purchase_result():
    result = financial_analysis_node(valid_state())

    hp = result["financial_analysis"]["hire_purchase"]

    assert hp["financed_amount"] == Decimal("80000")
    assert hp["term_months"] == 60
    assert hp["annual_eir"] == Decimal("5.5")
    assert hp["total_paid"] > Decimal("80000")


def test_lease_result():
    result = financial_analysis_node(valid_state())

    lease = result["financial_analysis"]["leasing"]

    assert lease["monthly_payment"] == Decimal("1800.00")
    assert lease["lease_period_months"] == 60
    assert lease["total_lease_cost"] == Decimal("108000.00")


def test_comparison_result_exists():
    result = financial_analysis_node(valid_state())

    comparison = result["financial_analysis"]["comparison"]

    assert "cash_purchase_cost" in comparison
    assert "hire_purchase_cost" in comparison
    assert "leasing_cost" in comparison
    assert "recommended_option" in comparison


def test_cash_discount_is_applied():
    state = valid_state()
    state["cash_discount"] = Decimal("5000")

    result = financial_analysis_node(state)

    cash = result["financial_analysis"]["cash_purchase"]

    assert cash["total_cash_cost"] == Decimal("95000.00")


def test_financial_analysis_contains_all_options():
    result = financial_analysis_node(valid_state())

    analysis = result["financial_analysis"]

    assert "cash_purchase" in analysis
    assert "hire_purchase" in analysis
    assert "leasing" in analysis
    assert "comparison" in analysis