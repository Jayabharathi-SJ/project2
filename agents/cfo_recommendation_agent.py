from typing import Any, Dict

from services.llm_service import ask_nvidia


RECOMMENDATION_MAP = {
    "cash_purchase": "Cash Purchase",
    "hire_purchase": "Hire Purchase",
    "lease": "Lease",
    "insufficient_data": "Insufficient Data",
}


async def generate_cfo_recommendation(
    financial_analysis: Dict[str, Any],
    legal_validation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a CFO recommendation.

    The recommendation itself is taken from the deterministic
    financial comparison engine.

    NVIDIA is used only to generate a concise explanation.
    This prevents an LLM output-format failure from changing
    the financial decision.
    """

    if not financial_analysis:
        raise ValueError(
            "Financial analysis is required."
        )

    if not legal_validation:
        raise ValueError(
            "Legal validation is required."
        )

    if legal_validation.get("passed") is not True:
        return {
            "recommendation": "Insufficient Data",
            "reason": (
                "Recommendation cannot be generated because "
                "legal validation failed."
            ),
            "key_financial_consideration": (
                "Legal validation must pass before a financial "
                "option can be recommended."
            ),
            "status": "blocked",
        }

    comparison = financial_analysis.get(
        "comparison",
        {},
    )

    raw_recommendation = comparison.get(
        "recommended_option"
    )

    recommendation = RECOMMENDATION_MAP.get(
        str(raw_recommendation).lower()
        if raw_recommendation is not None
        else ""
    )

    if recommendation is None:
        recommendation = "Insufficient Data"

    if recommendation == "Insufficient Data":
        return {
            "recommendation": "Insufficient Data",
            "reason": (
                "The financial comparison does not contain "
                "a valid recommendation."
            ),
            "key_financial_consideration": (
                "A valid deterministic comparison is required "
                "before making a financial recommendation."
            ),
            "status": "blocked",
        }

    # Extract only the relevant deterministic values for the
    # explanation prompt.
    cash_cost = comparison.get(
        "cash_purchase_cost"
    )

    hp_cost = comparison.get(
        "hire_purchase_cost"
    )

    lease_cost = comparison.get(
        "leasing_cost"
    )

    prompt = f"""
You are the explanation component of a Virtual CFO system.

The financial recommendation has ALREADY been determined by
a deterministic financial calculation engine.

Your task is ONLY to explain that existing recommendation.

Do not change the recommendation.
Do not calculate anything.
Do not perform new financial analysis.
Do not provide chain-of-thought.
Do not provide a thinking process.
Do not add headings.
Do not use bullet points.

Return exactly ONE short sentence explaining the recommendation.

Deterministic Recommendation:
{recommendation}

Cash Purchase Total Cost:
{cash_cost}

Hire Purchase Total Cost:
{hp_cost}

Lease Total Cost:
{lease_cost}

Legal Validation:
{legal_validation}
"""

    llm_narrative_available = True
    try:
        llm_response = await ask_nvidia(prompt)

        reason = llm_response.strip()

        if not reason:
            raise RuntimeError(
                "NVIDIA returned an empty explanation."
            )

        # Remove accidental code fences.
        if reason.startswith("```"):
            reason = reason.replace(
                "```text",
                ""
            )
            reason = reason.replace(
                "```",
                ""
            )
            reason = reason.strip()

    except Exception:
        # The financial recommendation must remain available
        # even if the explanation service fails (Req 15).
        llm_narrative_available = False
        reason = (
            f"{recommendation} has the lowest total cost "
            "among the compared options (Deterministic calculation)."
        )

    # Contradiction guard: verify LLM text does not contradict deterministic choice
    other_terms = []
    for opt in ["Cash Purchase", "Cash", "Hire Purchase", "Leasing", "Lease"]:
        if opt.lower() != recommendation.lower() and opt.lower() not in recommendation.lower():
            other_terms.append(opt.lower())

    conflicting_action_words = [
        "recommend", "recommends", "recommending", "recommended",
        "prefer", "prefers", "preferring", "preferred",
        "choose", "chooses", "choosing",
        "better to", "advise", "advises",
    ]
    reason_lower = reason.lower()
    contradiction_found = False
    for other in other_terms:
        for action in conflicting_action_words:
            if f"{action} {other}" in reason_lower or f"{other} is {action}" in reason_lower:
                reason = (
                    f"{recommendation} has the lowest total cost "
                    "among the compared options (Deterministic calculation)."
                )
                contradiction_found = True
                break
        if contradiction_found:
            break

    key_financial_consideration = (
        f"The deterministic comparison identifies "
        f"{recommendation} as the selected option based on "
        f"the provided total costs."
    )

    if llm_narrative_available:
        executive_summary = (
            f"Deterministic financial analysis confirms {recommendation} provides "
            f"the most cost-effective capital allocation under Malaysian Hire-Purchase "
            f"Act 2026 regulations."
        )
    else:
        executive_summary = (
            f"Deterministic financial analysis confirms {recommendation} provides "
            f"the lowest total ownership cost. [AI Executive Narrative Unavailable: External LLM Offline]"
        )

    return {
        "recommendation": recommendation,
        "reason": reason,
        "executive_summary": executive_summary,
        "key_financial_consideration": key_financial_consideration,
        "llm_narrative_available": llm_narrative_available,
        "status": "success",
    }