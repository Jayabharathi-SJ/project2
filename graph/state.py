from decimal import Decimal
from typing import Any, Dict, List, Optional, TypedDict


class CFOState(TypedDict, total=False):
    # Asset details (user input)
    asset_name: str
    asset_price: Decimal
    down_payment: Decimal

    # Hire-purchase details (user input)
    hp_period_months: int
    hp_interest_rate: Decimal
    hp_rate_type: Optional[str]

    # Lease details (user input)
    lease_period_months: int
    lease_monthly_payment: Decimal

    # Optional cash purchase details (user input)
    cash_discount: Decimal

    # Research and legal RAG
    research_findings: List[Dict[str, Any]]
    legal_rules: List[Dict[str, Any]]

    # Legal validation
    legal_validation: Dict[str, Any]

    # Financial analysis
    financial_analysis: Dict[str, Any]

    # Validation
    validation_errors: List[str]
    validation_passed: bool

    # CFO recommendation
    cfo_recommendation: Dict[str, Any]
    recommendation: Optional[str]
    recommendation_reason: Optional[str]

    # Audit trail — records each agent's actions and decisions
    audit_trail: List[Dict[str, Any]]

    # Data classification labels for CFO transparency
    # Each entry: {"field": "...", "classification": "user_input|retrieved_legal|
    #              verified_rule|assumption|derived_value|insufficient_data"}
    data_classifications: List[Dict[str, str]]

    # Warnings — non-fatal issues that do not block the analysis
    warnings: List[str]

    # Workflow tracking
    current_step: str
    errors: List[str]