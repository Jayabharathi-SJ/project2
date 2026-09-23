import sys
import asyncio
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional


# Windows + Psycopg async compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )


from database.checkpointer import create_resilient_async_checkpointer
from graph.workflow import build_cfo_graph


async def analyze_asset_financial_options_async(
    asset_price: Decimal,
    down_payment: Decimal,
    hp_period_months: int,
    hp_interest_rate: Decimal,
    lease_period_months: int,
    lease_monthly_payment: Decimal,
    asset_name: str = "Unknown Asset",
    cash_discount: Decimal = Decimal("0.00"),
    thread_id: Optional[str] = None,
    hp_rate_type: str = "fixed",
    document_extraction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    # Upfront financial input validation
    if asset_price <= Decimal("0"):
        raise ValueError("Asset price must be greater than zero.")

    if down_payment < Decimal("0"):
        raise ValueError("Down payment cannot be negative.")

    if down_payment > asset_price:
        raise ValueError("Down payment cannot exceed asset price.")

    if hp_period_months <= 0:
        raise ValueError("Hire-purchase period must be greater than zero.")

    if hp_interest_rate < Decimal("0"):
        raise ValueError("Hire-purchase interest rate cannot be negative.")

    if lease_period_months <= 0:
        raise ValueError("Lease period must be greater than zero.")

    if lease_monthly_payment <= Decimal("0"):
        raise ValueError("Lease monthly payment must be greater than zero.")

    # Create a unique thread ID if not provided
    if thread_id is None:
        thread_id = f"cfo-{uuid.uuid4().hex[:12]}"

    # Initial LangGraph state
    initial_state = {
        "asset_name": asset_name,
        "asset_price": asset_price,
        "down_payment": down_payment,
        "hp_period_months": hp_period_months,
        "hp_interest_rate": hp_interest_rate,
        "hp_rate_type": hp_rate_type,
        "lease_period_months": lease_period_months,
        "lease_monthly_payment": lease_monthly_payment,
        "cash_discount": cash_discount,
        "document_extraction": document_extraction,
        "thread_id": thread_id,
        "current_step": "analysis_started",
        "errors": [],
        "warnings": [],
        "audit_trail": [
            {
                "agent": "orchestrator",
                "action": "analysis_initiated",
                "thread_id": thread_id,
                "asset_name": asset_name,
                "note": f"Initiated analysis pipeline with thread ID: {thread_id}",
            }
        ],
    }

    # LangGraph checkpoint configuration
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Create async checkpointer with graceful fallback (Req 14 & 15)
    async with create_resilient_async_checkpointer() as (checkpointer, is_persisted):
        if not is_persisted:
            initial_state["warnings"].append(
                "PostgreSQL state persistence is unavailable. Running in ephemeral state mode."
            )

        # Build LangGraph with checkpointer
        graph = build_cfo_graph(
            checkpointer=checkpointer
        )

        # Execute graph asynchronously
        result = await graph.ainvoke(
            initial_state,
            config=config,
        )

        if not is_persisted and "audit_trail" in result:
            result["audit_trail"].append({
                "agent": "checkpoint_manager",
                "action": "persistence_status",
                "persisted_to_postgres": False,
                "note": "PostgreSQL unavailable; executed with in-memory checkpointer without pretending persistence succeeded.",
            })

    # Process final graph result
    return _process_result(
        result=result,
        thread_id=thread_id,
    )



def analyze_asset_financial_options(
    asset_price: Decimal,
    down_payment: Decimal,
    hp_period_months: int,
    hp_interest_rate: Decimal,
    lease_period_months: int,
    lease_monthly_payment: Decimal,
    asset_name: str = "Unknown Asset",
    cash_discount: Decimal = Decimal("0.00"),
    hp_rate_type: str = "fixed",
) -> Dict[str, Any]:
    """
    Synchronous wrapper for environments that do not
    already have a running asyncio event loop.
    Uses SelectorEventLoop on Windows for Psycopg async compatibility.
    """

    coro = analyze_asset_financial_options_async(
        asset_price=asset_price,
        down_payment=down_payment,
        hp_period_months=hp_period_months,
        hp_interest_rate=hp_interest_rate,
        lease_period_months=lease_period_months,
        lease_monthly_payment=lease_monthly_payment,
        asset_name=asset_name,
        cash_discount=cash_discount,
        hp_rate_type=hp_rate_type,
    )


    if sys.platform == "win32":
        try:
            return asyncio.run(
                coro,
                loop_factory=asyncio.SelectorEventLoop,
            )
        except TypeError:
            pass

    return asyncio.run(coro)


def _process_result(
    result: Dict[str, Any],
    thread_id: str,
) -> Dict[str, Any]:

    financial_analysis = result.get("financial_analysis") or {}

    return {
        "thread_id": thread_id,

        "status": (
            "success"
            if result.get("validation_passed") is not False
            else "failed"
        ),

        "current_step": result.get(
            "current_step"
        ),

        "validation_passed": result.get(
            "validation_passed"
        ),

        "validation_errors": result.get(
            "validation_errors",
            []
        ),

        "research_findings": result.get(
            "research_findings",
            []
        ),

        "legal_rules": result.get(
            "legal_rules",
            []
        ),

        "legal_validation": result.get(
            "legal_validation",
            {}
        ),

        "financial_analysis": financial_analysis,

        # Independent Validation stage (Req 12)
        "independent_validation": result.get("independent_validation", {}),

        # Top-level financial keys for direct access and test compatibility
        "financed_amount": financial_analysis.get("financed_amount"),
        "cash_purchase": financial_analysis.get("cash_purchase"),
        "hire_purchase": financial_analysis.get("hire_purchase"),
        "leasing": financial_analysis.get("leasing"),
        "comparison": financial_analysis.get("comparison"),

        "cfo_recommendation": result.get(
            "cfo_recommendation",
            {}
        ),

        "recommendation": result.get(
            "recommendation"
        ),

        "recommendation_reason": result.get(
            "recommendation_reason"
        ),

        "audit_trail": result.get(
            "audit_trail",
            [],
        ),

        "warnings": result.get(
            "warnings",
            [],
        ),

        "data_classifications": result.get(
            "data_classifications",
            [],
        ),
    }