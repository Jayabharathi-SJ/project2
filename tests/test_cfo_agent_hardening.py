import asyncio
from decimal import Decimal
from unittest.mock import patch

from agents.cfo_recommendation_agent import generate_cfo_recommendation


def sample_financial_analysis():
    return {
        "financed_amount": Decimal("80000.00"),
        "cash_purchase": {"total_cash_cost": Decimal("100000.00")},
        "hire_purchase": {"total_paid": Decimal("91759.30"), "total_cost": Decimal("111759.30")},
        "leasing": {"total_lease_cost": Decimal("108000.00")},
        "comparison": {
            "cash_purchase_cost": Decimal("100000.00"),
            "hire_purchase_cost": Decimal("111759.30"),
            "leasing_cost": Decimal("108000.00"),
            "recommended_option": "cash_purchase",
            "lowest_total_cost": Decimal("100000.00"),
        },
    }


def sample_legal_validation():
    return {
        "passed": True,
        "errors": [],
        "validated_eir": Decimal("5.5"),
        "deposit_compliant": True,
    }


def test_generate_cfo_recommendation_includes_executive_summary():
    with patch("agents.cfo_recommendation_agent.ask_nvidia", return_value="Cash purchase has the lowest total cost."):
        result = asyncio.run(
            generate_cfo_recommendation(
                financial_analysis=sample_financial_analysis(),
                legal_validation=sample_legal_validation(),
            )
        )

    assert result["status"] == "success"
    assert result["recommendation"] == "Cash Purchase"
    assert "executive_summary" in result
    assert "Cash Purchase" in result["executive_summary"]
    assert "Malaysian Hire-Purchase" in result["executive_summary"]


def test_contradiction_guard_replaces_hallucinated_recommendation():
    # Deterministic winner is Cash Purchase, but LLM hallucinates recommending Lease
    hallucinated_text = "I recommend leasing because it allows the business to upgrade equipment easily."

    with patch("agents.cfo_recommendation_agent.ask_nvidia", return_value=hallucinated_text):
        result = asyncio.run(
            generate_cfo_recommendation(
                financial_analysis=sample_financial_analysis(),
                legal_validation=sample_legal_validation(),
            )
        )

    assert result["recommendation"] == "Cash Purchase"
    # Contradiction guard must have overridden the hallucinated text
    assert "leasing" not in result["reason"].lower()
    assert "Cash Purchase has the lowest total cost" in result["reason"]


def test_cfo_recommendation_blocked_on_failed_legal_validation():
    failed_legal = {
        "passed": False,
        "errors": ["EIR of 18.0% exceeds statutory cap."],
    }

    result = asyncio.run(
        generate_cfo_recommendation(
            financial_analysis=sample_financial_analysis(),
            legal_validation=failed_legal,
        )
    )

    assert result["status"] == "blocked"
    assert result["recommendation"] == "Insufficient Data"
    assert "legal validation" in result["reason"].lower()
