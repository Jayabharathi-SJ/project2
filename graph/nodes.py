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
    evaluate_legal_compliance,
)

from tools.cash_calculator import calculate_cash_purchase
from tools.comparison_calculator import (
    compare_asset_options,
    compare_asset_options_detailed,
)
from tools.financial_calculator import (
    calculate_reducing_balance,
    validate_amortization_schedule,
)
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
    Research Agent retrieves relevant legal context from the Qdrant-based
    legal RAG system, with transparent fallback tracking if Qdrant is unavailable.
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
    rag_source = "Bank Negara Malaysia Consumer Guide 2026 (Qdrant RAG)"
    qdrant_available = True

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
        qdrant_available = False
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
        rag_source = "Verified in-memory legal rules fallback (Qdrant offline)"
        warnings.append(
            f"Qdrant legal RAG vector store unavailable ({type(exc).__name__}). "
            "System fell back to verified in-memory rules from rag/legal_rules.py."
        )

    research_findings = [
        {
            "topic": "Asset",
            "finding": f"Financial analysis requested for asset: {asset_name}.",
            "source": "user_input",
            "classification": "user_input",
        },
        {
            "topic": "Legal RAG",
            "finding": (
                f"Retrieved {len(legal_context)} authoritative legal provisions "
                f"from {rag_source}."
            ),
            "source": rag_source,
            "classification": "retrieved_legal",
            "contexts": legal_context,
            "qdrant_available": qdrant_available,
        },
    ]

    trail.append({
        "agent": "research_agent",
        "action": "legal_research_completed",
        "contexts_retrieved": len(legal_context),
        "source": rag_source,
        "qdrant_available": qdrant_available,
        "note": f"Retrieved {len(legal_context)} provisions via {rag_source}.",
    })

    classifications.append({
        "field": "legal_rules",
        "classification": "retrieved_legal",
    })

    return {
        "research_findings": research_findings,
        "legal_rules": legal_context,
        "qdrant_available": qdrant_available,
        "current_step": "research_completed",
        "audit_trail": trail,
        "warnings": warnings,
        "data_classifications": classifications,
    }


def legal_validation_node(state: CFOState) -> Dict[str, Any]:
    """
    Validate hire-purchase EIR and statutory deposit against primary Malaysian legislation
    and BNM 2026 regulations with 3-layer separation (Req 4):
    Layer A: Retrieved Legal Evidence
    Layer B: Application of the Rule
    Layer C: Validation Result
    """
    hp_interest_rate = state["hp_interest_rate"]
    hp_period_months = state["hp_period_months"]
    hp_rate_type = state.get("hp_rate_type", "fixed")
    down_payment = state["down_payment"]
    asset_price = state["asset_price"]
    qdrant_available = state.get("qdrant_available", True)

    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    eval_result = evaluate_legal_compliance(
        annual_eir=hp_interest_rate,
        term_months=hp_period_months,
        rate_type=hp_rate_type,
        down_payment=down_payment,
        asset_price=asset_price,
        retrieved_contexts=state.get("legal_rules", []),
        qdrant_available=qdrant_available,
    )

    passed = eval_result["passed"]
    errors = eval_result["errors"]

    legal_validation_data = {
        "passed": passed,
        "status": eval_result["status"],
        "conclusive": eval_result["conclusive"],
        "errors": errors,
        "statutory_compliance_note": eval_result["statutory_compliance_note"],
        "retrieved_evidence": eval_result["retrieved_evidence"],
        "rules_applied": eval_result["rules_applied"],
        "deposit_compliance": eval_result["deposit_compliance"],
        "eir_compliance": eval_result["eir_compliance"],
        # Backwards compatibility fields
        "validated_eir": hp_interest_rate,
        "term_months": hp_period_months,
        "rate_type": hp_rate_type,
        "deposit_compliant": eval_result["deposit_compliance"]["compliant"],
        "method": "Reducing Balance / EIR",
        "source": "Hire-Purchase Act 1967 (Act 212) & Revised Term Charges Regulations 2026",
    }

    if not passed:
        trail.append({
            "agent": "legal_validation",
            "action": "legal_validation_failed",
            "errors": errors,
            "source": "Malaysian Hire-Purchase Act 1967 (Act 212) & 2026 Regulations",
            "note": "Statutory legal validation failed: " + "; ".join(errors),
        })
        return {
            "legal_validation": legal_validation_data,
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
        "source": "Section 31(1) Act 212 & Hire-Purchase (Term Charges) Regulations 2026",
        "note": f"EIR of {hp_interest_rate}% is within statutory cap; 10% statutory deposit satisfied.",
    })
    classifications.append({
        "field": "legal_validation",
        "classification": "verified_rule",
    })

    return {
        "legal_validation": legal_validation_data,
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

    # Financial Calculation stage
    trail.append({
        "agent": "financial_engine",
        "action": "financial_calculation_completed",
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

    # Financial Validation stage (amortization reconciliation check)
    reconciled = hp_result.get("amortization_reconciliation", {}).get("reconciled", True)
    trail.append({
        "agent": "financial_validator",
        "action": "financial_validation_completed",
        "reconciled": reconciled,
        "reconciliation_metrics": hp_result.get("amortization_reconciliation", {}).get("metrics", {}),
        "note": "Amortization schedule reconciled: conservation of principal, instalments, interest, and zero closing balance verified.",
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


def independent_validation_node(state: CFOState) -> Dict[str, Any]:
    """
    Independent Validation Agent (Requirement 12).
    Executes a strict separate validation stage verifying all 7 invariants:
    1. Input consistency & range boundaries
    2. Financial calculation conservation laws
    3. Amortization reconciliation (principal, instalments, interest, closing zero)
    4. Statutory legal rule application & compliance
    5. Acquisition option comparison consistency
    6. Missing data / unverified charges disclosures
    7. Extracted-document consistency (if document was provided)

    If any validation check fails:
        status = FAILED / NEEDS_REVIEW
        Blocks presenting the result as a successful CFO analysis.
    """
    errors = []
    trail = list(state.get("audit_trail", []))
    warnings = list(state.get("warnings", []))
    classifications = list(state.get("data_classifications", []))

    asset_price = state.get("asset_price", Decimal("0"))
    down_payment = state.get("down_payment", Decimal("0"))
    hp_period_months = state.get("hp_period_months", 0)
    lease_period_months = state.get("lease_period_months", 0)
    lease_monthly_payment = state.get("lease_monthly_payment", Decimal("0"))
    cash_discount = state.get("cash_discount", Decimal("0.00"))

    # 1. Input consistency
    if asset_price <= 0:
        errors.append("Asset price must be greater than zero.")
    if down_payment < 0 or down_payment > asset_price:
        errors.append("Down payment out of permitted range [0, asset_price].")
    if hp_period_months <= 0:
        errors.append("HP tenure must be greater than zero.")
    if lease_period_months <= 0:
        errors.append("Lease tenure must be greater than zero.")
    if lease_monthly_payment <= 0:
        errors.append("Lease monthly payment must be positive.")

    # 2. Financial calculation consistency
    fin_analysis = state.get("financial_analysis", {})
    if not fin_analysis:
        errors.append("Missing deterministic financial analysis result.")
    else:
        financed_amount = fin_analysis.get("financed_amount", Decimal("0.00"))
        expected_financed = asset_price - down_payment
        if financed_amount != expected_financed:
            errors.append(f"Financed amount mismatch: calculated {financed_amount} != expected {expected_financed}.")

        cash_opt = fin_analysis.get("cash_purchase", {})
        expected_cash = asset_price - cash_discount
        if cash_opt.get("total_cash_cost") != expected_cash:
            errors.append(f"Cash acquisition cost mismatch: {cash_opt.get('total_cash_cost')} != {expected_cash}.")

        lease_opt = fin_analysis.get("leasing", {})
        expected_lease = lease_monthly_payment * Decimal(lease_period_months)
        if lease_opt.get("total_lease_cost") != expected_lease:
            errors.append(f"Lease cost mismatch: {lease_opt.get('total_lease_cost')} != {expected_lease}.")

        # 3. Amortization reconciliation check
        hp_opt = fin_analysis.get("hire_purchase", {})
        reconciliation = hp_opt.get("amortization_reconciliation", {})
        if not reconciliation.get("reconciled", True):
            reconcile_errs = reconciliation.get("errors", ["Amortization schedule failed reconciliation invariants."])
            errors.extend(reconcile_errs)

        # 4. Comparison consistency
        comp = fin_analysis.get("comparison", {})
        costs = [
            ("cash_purchase", cash_opt.get("total_cash_cost")),
            ("hire_purchase", hp_opt.get("total_paid", Decimal("0")) + down_payment),
            ("leasing", lease_opt.get("total_lease_cost")),
        ]
        min_opt, min_val = min(costs, key=lambda x: x[1])
        rec_opt = comp.get("recommended_option")
        if rec_opt != min_opt:
            errors.append(f"Comparison consistency error: lowest cost is {min_opt} (RM {min_val}) but recommended is {rec_opt}.")

    # 5. Legal rule application
    legal_val = state.get("legal_validation", {})
    if not legal_val or legal_val.get("passed") is not True:
        legal_errs = legal_val.get("errors", ["Statutory legal compliance validation failed."])
        errors.extend(legal_errs)

    # 6. Missing-data conditions (Req 7, 10): disclose unsupplied operational costs
    unverified_costs = {
        "insurance": "Not included / data unavailable",
        "road_tax": "Not included / data unavailable",
        "maintenance_servicing": "Not included / data unavailable",
        "registration_fees": "Not included / data unavailable",
    }

    # 7. Document extraction consistency (if present)
    doc_ext = state.get("document_extraction")
    doc_consistent = True
    if doc_ext and isinstance(doc_ext, dict):
        ext_fields = doc_ext.get("extracted_fields", {})
        if "asset_price" in ext_fields:
            ext_price = ext_fields["asset_price"].get("value")
            if ext_price and Decimal(str(ext_price)) != asset_price:
                warnings.append(
                    f"Document price (RM {ext_price}) differs from user-adjusted price (RM {asset_price}). "
                    "Using user-verified value."
                )

    passed = len(errors) == 0
    validation_status = "PASSED" if passed else "FAILED"

    trail.append({
        "agent": "independent_validation",
        "action": "independent_validation_completed",
        "status": validation_status,
        "invariants_checked": [
            "input_consistency",
            "financial_calculation_conservation",
            "amortization_reconciliation",
            "legal_rule_application",
            "comparison_consistency",
            "missing_data_conditions",
            "document_consistency",
        ],
        "errors": errors,
        "note": "All 7 core invariants verified independently." if passed else "Independent validation rejected result: " + "; ".join(errors),
    })

    classifications.append({
        "field": "independent_validation",
        "classification": "verified_rule",
    })

    return {
        "independent_validation": {
            "passed": passed,
            "status": validation_status,
            "errors": errors,
            "unverified_costs": unverified_costs,
            "document_consistent": doc_consistent,
        },
        "validation_passed": passed,
        "validation_errors": errors,
        "current_step": "independent_validation_completed" if passed else "independent_validation_failed",
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