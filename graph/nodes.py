from decimal import Decimal
from typing import Any, Dict

from agents.cfo_recommendation_agent import generate_cfo_recommendation
from graph.state import CFOState
from rag.legal_rules import get_legal_rules
from rag.qdrant_store import create_qdrant_client
from rag.retriever import retrieve_legal_context
from rag.legal_validator import (
    validate_eir_cap,
    validate_fixed_eir_cap,
    validate_minimum_deposit,
)

from tools.cash_calculator import calculate_cash_purchase
from tools.comparison_calculator import (
    compare_asset_options,
    compare_asset_options_detailed,
)
from tools.financial_calculator import calculate_reducing_balance
from tools.lease_calculator import calculate_lease_cost


def validate_input_node(state: CFOState) -> Dict[str, Any]:
    errors = []

    required_fields = [
        "asset_name",
        "asset_price",
        "down_payment",
        "hp_period_months",
        "hp_interest_rate",
        "lease_period_months",
        "lease_monthly_payment",
    ]

    for field in required_fields:
        if field not in state:
            errors.append(f"Missing required field: {field}")

    if errors:
        trail = list(state.get("audit_trail", []))
        trail.append({
            "agent": "validate_input",
            "action": "input_validation_failed",
            "errors": errors,
            "note": "Required fields missing from input.",
        })
        return {
            "validation_passed": False,
            "validation_errors": errors,
            "current_step": "input_validation_failed",
            "audit_trail": trail,
            "warnings": list(state.get("warnings", [])),
        }

    asset_name = state["asset_name"]
    asset_price = state["asset_price"]
    down_payment = state["down_payment"]
    hp_period_months = state["hp_period_months"]
    hp_interest_rate = state["hp_interest_rate"]
    hp_rate_type = state.get("hp_rate_type", "fixed")
    lease_period_months = state["lease_period_months"]
    lease_monthly_payment = state["lease_monthly_payment"]

    if not isinstance(asset_name, str) or not asset_name.strip():
        errors.append("Asset name cannot be empty.")

    if asset_price <= Decimal("0"):
        errors.append("Asset price must be greater than zero.")

    if down_payment < Decimal("0"):
        errors.append("Down payment cannot be negative.")

    if down_payment > asset_price:
        errors.append("Down payment cannot exceed asset price.")

    if hp_period_months <= 0:
        errors.append(
            "Hire-purchase period must be greater than zero."
        )

    if hp_interest_rate < Decimal("0"):
        errors.append(
            "Hire-purchase EIR cannot be negative."
        )

    if hp_rate_type not in ("fixed", "variable"):
        errors.append(
            f"Unsupported rate type: '{hp_rate_type}'. Must be 'fixed' or 'variable'."
        )

    if lease_period_months <= 0:
        errors.append(
            "Lease period must be greater than zero."
        )

    if lease_monthly_payment <= Decimal("0"):
        errors.append(
            "Lease monthly payment must be greater than zero."
        )

    if not errors:
        try:
            validate_eir_cap(
                annual_eir=hp_interest_rate,
                term_months=hp_period_months,
                rate_type=hp_rate_type,
            )
        except ValueError as exc:
            errors.append(str(exc))


    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))

    if errors:
        trail.append({
            "agent": "validate_input",
            "action": "input_validation_failed",
            "errors": errors,
            "note": "Input validation failed: " + "; ".join(errors),
        })
        return {
            "validation_passed": False,
            "validation_errors": errors,
            "current_step": "input_validation_failed",
            "audit_trail": trail,
            "warnings": warnings,
        }

    trail.append({
        "agent": "validate_input",
        "action": "input_validation_passed",
        "note": "All required fields present and within permitted ranges.",
    })

    return {
        "validation_passed": True,
        "validation_errors": [],
        "current_step": "input_validation_completed",
        "data_classifications": [
            {"field": "asset_name", "classification": "user_input"},
            {"field": "asset_price", "classification": "user_input"},
            {"field": "down_payment", "classification": "user_input"},
            {"field": "hp_period_months", "classification": "user_input"},
            {"field": "hp_interest_rate", "classification": "user_input"},
            {"field": "lease_period_months", "classification": "user_input"},
            {"field": "lease_monthly_payment", "classification": "user_input"},
            {"field": "cash_discount", "classification": "user_input"},
        ],
        "audit_trail": trail,
        "warnings": warnings,
    }


def research_agent_node(state: CFOState) -> Dict[str, Any]:
    """
    Research Agent retrieves relevant legal context
    from the Qdrant-based legal RAG system, with resilient
    in-memory fallback to verified Malaysian statutory rules.
    """

    asset_name = state["asset_name"]

    query = (
        f"Malaysian Hire-Purchase Amendment Act 2026 "
        f"EIR reducing balance requirements for financing "
        f"an asset such as {asset_name}"
    )

    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    legal_context = []
    rag_source = "Bank Negara Malaysia Consumer Guide 2026 (Qdrant)"

    try:
        client = create_qdrant_client()
        try:
            legal_context = retrieve_legal_context(
                client=client,
                query=query,
                limit=3,
            )
        finally:
            client.close()
    except Exception as exc:
        # Resilient fallback: use in-memory verified statutory rules
        verified_rules = get_legal_rules()
        legal_context = [
            {
                "text": rule.get("rule", ""),
                "source": f"rag/legal_rules.py [{rule.get('rule_id')}]",
                "score": 1.0,
                "rule_id": rule.get("rule_id"),
                "topic": rule.get("topic"),
            }
            for rule in verified_rules[:3]
        ]
        rag_source = "In-memory verified statutory rules (Qdrant fallback)"
        warnings.append(
            f"Legal RAG retrieval via Qdrant fell back to verified in-memory rules: {type(exc).__name__}"
        )

    research_findings = [
        {
            "topic": "Asset",
            "finding": (
                f"Financial analysis requested for asset: "
                f"{asset_name}."
            ),
            "source": "user_input",
            "classification": "user_input",
        },
        {
            "topic": "Legal RAG",
            "finding": (
                f"Retrieved {len(legal_context)} relevant legal "
                "contexts from the Bank Negara Malaysia "
                "Consumer Guide 2026."
            ),
            "source": rag_source,
            "classification": "retrieved_legal",
            "contexts": legal_context,
        },
    ]

    trail.append({
        "agent": "research_agent",
        "action": "rag_retrieval_completed",
        "contexts_retrieved": len(legal_context),
        "source": rag_source,
        "note": f"Retrieved {len(legal_context)} legal provisions from {rag_source}.",
    })

    classifications.append({
        "field": "legal_rules",
        "classification": "retrieved_legal",
    })

    return {
        "research_findings": research_findings,
        "legal_rules": legal_context,
        "current_step": "research_completed",
        "audit_trail": trail,
        "warnings": warnings,
        "data_classifications": classifications,
    }


def legal_validation_node(state: CFOState) -> Dict[str, Any]:
    """
    Validate the hire-purchase EIR and statutory minimum deposit against
    authoritative Malaysian Hire-Purchase 2026 legal requirements.
    """

    errors = []

    hp_interest_rate = state["hp_interest_rate"]
    hp_period_months = state["hp_period_months"]
    hp_rate_type = state.get("hp_rate_type", "fixed")
    down_payment = state["down_payment"]
    asset_price = state["asset_price"]

    try:
        validate_eir_cap(
            annual_eir=hp_interest_rate,
            term_months=hp_period_months,
            rate_type=hp_rate_type,
        )
    except ValueError as exc:
        errors.append(str(exc))

    try:
        validate_minimum_deposit(
            down_payment=down_payment,
            asset_price=asset_price,
        )
    except ValueError as exc:
        errors.append(str(exc))

    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    if errors:
        trail.append({
            "agent": "legal_validation",
            "action": "legal_validation_failed",
            "errors": errors,
            "source": "Malaysian Hire-Purchase Act 1967 & 2026 Regulations",
            "note": "Statutory validation failed: " + "; ".join(errors),
        })
        return {
            "legal_validation": {
                "passed": False,
                "errors": errors,
            },
            "validation_passed": False,
            "validation_errors": errors,
            "current_step": "legal_validation_failed",
            "audit_trail": trail,
            "warnings": warnings,
            "data_classifications": classifications,
        }

    trail.append({
        "agent": "legal_validation",
        "action": "legal_validation_passed",
        "hp_eir": f"{hp_interest_rate}%",
        "hp_term_months": hp_period_months,
        "rate_type": hp_rate_type,
        "deposit_compliant": True,
        "source": "BNM HP 2026 EIR cap rules & HP Act 1967 s. 31 minimum deposit",
        "note": f"EIR of {hp_interest_rate}% complies with statutory cap; 10% minimum deposit satisfied.",
    })
    classifications.append({
        "field": "legal_validation",
        "classification": "verified_rule",
    })

    return {
        "legal_validation": {
            "passed": True,
            "errors": [],
            "validated_eir": hp_interest_rate,
            "term_months": hp_period_months,
            "rate_type": hp_rate_type,
            "deposit_compliant": True,
            "method": "Reducing Balance / EIR",
            "source": "Bank Negara Malaysia Consumer Guide 2026 & Revised Term Charges Regulations",
            "classification": "verified_rule",
        },
        "current_step": "legal_validation_completed",
        "audit_trail": trail,
        "warnings": warnings,
        "data_classifications": classifications,
    }


def financial_analysis_node(state: CFOState) -> Dict[str, Any]:
    asset_price = state["asset_price"]
    down_payment = state["down_payment"]
    hp_period_months = state["hp_period_months"]
    hp_interest_rate = state["hp_interest_rate"]
    hp_rate_type = state.get("hp_rate_type", "fixed")
    lease_period_months = state["lease_period_months"]
    lease_monthly_payment = state["lease_monthly_payment"]

    cash_discount = state.get(
        "cash_discount",
        Decimal("0.00"),
    )

    financed_amount = asset_price - down_payment

    cash_result = calculate_cash_purchase(
        asset_price=asset_price,
        discount=cash_discount,
    )

    hp_result = calculate_reducing_balance(
        principal=financed_amount,
        annual_eir=hp_interest_rate,
        term_months=hp_period_months,
        rate_type=hp_rate_type,
    )

    lease_result = calculate_lease_cost(
        monthly_payment=lease_monthly_payment,
        lease_period_months=lease_period_months,
    )

    hp_total_cost = (
        down_payment
        + hp_result["total_paid"]
    )

    # Extended CFO-grade comparison with upfront, cashflow, liquidity metrics
    comparison = compare_asset_options_detailed(
        cash_cost=cash_result["total_cash_cost"],
        hp_total_cost=hp_total_cost,
        lease_total_cost=lease_result["total_lease_cost"],
        asset_price=asset_price,
        cash_discount=cash_discount,
        down_payment=down_payment,
        hp_monthly_installment=hp_result["monthly_installment"],
        hp_term_months=hp_period_months,
        hp_total_interest=hp_result["total_interest"],
        lease_monthly_payment=lease_monthly_payment,
        lease_term_months=lease_period_months,
    )

    financial_analysis = {
        "financed_amount": financed_amount,
        "cash_purchase": cash_result,
        "hire_purchase": hp_result,
        "leasing": lease_result,
        "comparison": comparison,
    }

    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    rec_opt = comparison.get("recommended_option", "cash_purchase")
    lowest_cost = comparison.get("lowest_total_cost")

    trail.append({
        "agent": "financial_engine",
        "action": "financial_analysis_completed",
        "recommended_option": rec_opt,
        "lowest_total_cost": str(lowest_cost),
        "note": (
            f"Deterministic reducing balance and comparison completed. "
            f"Cash: RM {cash_result['total_cash_cost']}, "
            f"HP: RM {hp_total_cost}, "
            f"Lease: RM {lease_result['total_lease_cost']}. "
            f"Selected: {rec_opt}."
        ),
    })

    classifications.extend([
        {"field": "cash_purchase", "classification": "derived_value"},
        {"field": "hire_purchase", "classification": "derived_value"},
        {"field": "leasing", "classification": "derived_value"},
        {"field": "comparison", "classification": "derived_value"},
    ])

    return {
        "financial_analysis": financial_analysis,
        "current_step": "financial_analysis_completed",
        "audit_trail": trail,
        "warnings": warnings,
        "data_classifications": classifications,
    }


async def cfo_recommendation_node(
    state: CFOState,
) -> Dict[str, Any]:
    """
    CFO Recommendation Agent.

    Uses deterministic financial analysis and legal validation
    as inputs to the NVIDIA LLM.
    """

    financial_analysis = state.get("financial_analysis")
    legal_validation = state.get("legal_validation")
    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    if not financial_analysis:
        trail.append({
            "agent": "cfo_committee",
            "action": "cfo_recommendation_failed",
            "note": "Cannot generate recommendation without financial analysis.",
        })
        return {
            "recommendation": None,
            "recommendation_reason": (
                "CFO recommendation cannot be generated "
                "without financial analysis."
            ),
            "current_step": "cfo_recommendation_failed",
            "audit_trail": trail,
            "warnings": warnings,
            "data_classifications": classifications,
        }

    if not legal_validation:
        trail.append({
            "agent": "cfo_committee",
            "action": "cfo_recommendation_failed",
            "note": "Cannot generate recommendation without legal validation.",
        })
        return {
            "recommendation": None,
            "recommendation_reason": (
                "CFO recommendation cannot be generated "
                "without legal validation."
            ),
            "current_step": "cfo_recommendation_failed",
            "audit_trail": trail,
            "warnings": warnings,
            "data_classifications": classifications,
        }

    try:
        result = await generate_cfo_recommendation(
            financial_analysis=financial_analysis,
            legal_validation=legal_validation,
        )

        rec = result.get("recommendation")
        trail.append({
            "agent": "cfo_committee",
            "action": "cfo_recommendation_formulated",
            "recommendation": rec,
            "status": result.get("status", "success"),
            "note": f"Optimal strategy formulated: {rec}.",
        })
        classifications.append({
            "field": "cfo_recommendation",
            "classification": "cfo_synthesis",
        })

        return {
            "recommendation": rec,
            "recommendation_reason": result.get("reason"),
            "cfo_recommendation": result,
            "current_step": "cfo_recommendation_completed",
            "audit_trail": trail,
            "warnings": warnings,
            "data_classifications": classifications,
        }

    except Exception as exc:
        print(
            "CFO RECOMMENDATION ERROR: "
            f"{type(exc).__name__}: {exc}"
        )
        trail.append({
            "agent": "cfo_committee",
            "action": "cfo_recommendation_failed",
            "error": str(exc),
            "note": f"CFO recommendation failed: {str(exc)}",
        })
        warnings.append(f"CFO recommendation generation error: {str(exc)}")

        return {
            "recommendation": None,
            "recommendation_reason": (
                f"CFO recommendation generation failed: "
                f"{str(exc)}"
            ),
            "current_step": "cfo_recommendation_failed",
            "audit_trail": trail,
            "warnings": warnings,
            "data_classifications": classifications,
        }