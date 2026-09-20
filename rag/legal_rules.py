from typing import Dict, List


# ---------------------------------------------------------------------------
# IMPORTANT: These rules are derived from the Bank Negara Malaysia (BNM)
# official Consumer Guide:
# "Five Key Highlights of the Hire-Purchase (Amendment) Act 2026"
# (HP Consumer Guide_EN_2026.pdf)
#
# Classification guide used throughout this module:
#   source_type = "official_consumer_guide"   → BNM-published guidance
#   source_type = "statutory_requirement"      → Legislated rule
#   status      = "verified_from_bnm_guide"   → Cross-checked from PDF
#   status      = "requires_authoritative_verification" → Needs primary
#                                                          legislation check
# ---------------------------------------------------------------------------

LEGAL_RULES: List[Dict] = [
    # -----------------------------------------------------------------------
    # HIGHLIGHT 1: Reducing Balance Method replaces Rule of 78
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-RB-001",
        "topic": "Reducing Balance",
        "rule": (
            "Interest is calculated based on the outstanding principal balance. "
            "The principal repayment is the instalment amount less the interest charge."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-RB-002",
        "topic": "Rule of 78 Abolition",
        "rule": (
            "The Rule of 78 method for calculating interest on hire-purchase financing "
            "is abolished. The Reducing Balance Method must be used for all new hire-purchase "
            "agreements from the effective date of 1 June 2026 (subject to a grace period until 31 March 2027)."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },

    # -----------------------------------------------------------------------
    # HIGHLIGHT 2: Effective Interest Rate (EIR) & Term Charges
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-EIR-001",
        "topic": "Effective Interest Rate",
        "rule": (
            "Hire-purchase providers must use the Effective Interest Rate (EIR) "
            "together with the Reducing Balance Method. "
            "The EIR reflects the true cost of credit."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-FIXED-CAP-001",
        "topic": "Fixed Rate EIR Cap",
        "rule": (
            "For fixed-rate hire purchase financing: "
            "EIR is capped at 17% per annum for tenures up to and including 5 years (60 months), "
            "and 16% per annum for tenures above 5 years (more than 60 months)."
        ),
        "source": "Revised Hire-Purchase (Term Charges) Regulations / BNM Consumer Guide 2026",
        "source_type": "statutory_requirement",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-VARIABLE-CAP-001",
        "topic": "Variable Rate EIR Cap",
        "rule": (
            "For variable-rate hire purchase financing: "
            "EIR is capped at 17% per annum for all loan tenures."
        ),
        "source": "Revised Hire-Purchase (Term Charges) Regulations / BNM Consumer Guide 2026",
        "source_type": "statutory_requirement",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-RR-001",
        "topic": "Reference Rate Framework",
        "rule": (
            "The term Base Lending Rate (BLR) is replaced with Reference Rate for variable-rate "
            "hire-purchase financing, aligning with Bank Negara Malaysia's Reference Rate Framework. "
            "Variable rates adjust with movements in the Overnight Policy Rate (OPR)."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },

    # -----------------------------------------------------------------------
    # HIGHLIGHT 3: Early Settlement & Statutory Rebate Treatment
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-ES-001",
        "topic": "Early Settlement Rebate Abolition",
        "rule": (
            "Hire-purchase providers will no longer offer rebates at the point of early settlement "
            "under the Hire-Purchase (Amendment) Act 2026. Because interest is charged on the "
            "outstanding principal balance each month rather than frontloaded, early settlement "
            "payoff is simply the outstanding principal balance (plus any accrued interest to date), "
            "and no further interest charges accrue. Hence statutory rebate calculations do not arise."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-ES-002",
        "topic": "Early Settlement Notice",
        "rule": (
            "Hire-purchase providers must respond to an early settlement request "
            "within 3 business days by providing a settlement quotation."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "requires_authoritative_verification",
    },

    # -----------------------------------------------------------------------
    # HIGHLIGHT 4: Disclosures & Digital Signatures
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-DISC-001",
        "topic": "Pre-Contract Disclosure",
        "rule": (
            "Before entering a hire-purchase agreement, the financier must "
            "disclose the EIR, monthly instalment, total amount payable, and "
            "any applicable fees in the pre-contract Product Disclosure Sheet (PDS)."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-DISC-002",
        "topic": "Monthly Statement Disclosure",
        "rule": (
            "Hire-purchase providers must provide borrowers with a monthly "
            "statement showing outstanding principal, interest charged, "
            "principal repaid, and closing balance."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-SIG-001",
        "topic": "Electronic and Digital Signatures",
        "rule": (
            "Consumers have the flexibility to sign hire-purchase agreements electronically "
            "(under Electronic Commerce Act 2006) or digitally (under Digital Signature Act 1997) "
            "and to receive documents electronically or in hardcopy as mutually agreed in the agreement."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-KYC-001",
        "topic": "Customer Due Diligence",
        "rule": (
            "Hire-purchase providers must verify the identity of prospective customers "
            "prior to entering into agreements using official identification (NRIC/passport) "
            "and verification safeguards such as biometric thumbprint or facial recognition."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },

    # -----------------------------------------------------------------------
    # HIGHLIGHT 5: Statutory Minimum Deposit
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-DEP-001",
        "topic": "Statutory Minimum Deposit",
        "rule": (
            "An owner/financier entering into a hire-purchase agreement must obtain an upfront deposit "
            "of not less than 10% of the cash price of the goods, as prescribed under Section 31(1) "
            "of the Hire-Purchase Act 1967 and Bank Negara Malaysia consumer guidelines."
        ),
        "source": "Hire-Purchase Act 1967 (Section 31) / BNM Consumer Guide 2026",
        "source_type": "statutory_requirement",
        "status": "verified_from_bnm_guide",
    },

    # -----------------------------------------------------------------------
    # HIGHLIGHT 6: Transition & Grace Period
    # -----------------------------------------------------------------------
    {
        "rule_id": "HP2026-TRANS-001",
        "topic": "Transition Date",
        "rule": (
            "The effective date of the Hire-Purchase (Amendment) Act 2026 is 1 June 2026. "
            "The new requirements apply to new hire-purchase agreements signed on or after this date. "
            "Existing agreements signed before this date continue under previous contractual terms."
        ),
        "source": "Ministry of Domestic Trade and Cost of Living (KPDN) / BNM Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-GRACE-001",
        "topic": "System Enhancement Grace Period",
        "rule": (
            "From the effective date of 1 June 2026, hire-purchase providers are given a grace period "
            "until 31 March 2027 to complete necessary systems and infrastructure enhancements. "
            "Providers ready earlier may adopt reducing balance and EIR pricing anytime during this period."
        ),
        "source": "Ministry of Domestic Trade and Cost of Living (KPDN) / BNM Consumer Guide 2026",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
    {
        "rule_id": "HP2026-TRANS-002",
        "topic": "Existing Agreement Variation",
        "rule": (
            "Existing hire-purchase agreements signed under the previous flat rate rules may be varied "
            "to adopt the reducing balance method if the customer and hire-purchase provider mutually agree, "
            "subject to the provider's system readiness."
        ),
        "source": "Bank Negara Malaysia Consumer Guide 2026 (FAQ 8)",
        "source_type": "official_consumer_guide",
        "status": "verified_from_bnm_guide",
    },
]


def get_legal_rules() -> List[Dict]:
    """Return all registered legal rules."""

    return LEGAL_RULES.copy()


def get_rules_by_topic(topic: str) -> List[Dict]:
    """Return all rules matching a given topic keyword (case-insensitive)."""

    topic_lower = topic.lower()
    return [
        r for r in LEGAL_RULES
        if topic_lower in r.get("topic", "").lower()
    ]


def get_verified_rules() -> List[Dict]:
    """Return only rules with verified status from BNM guide."""

    return [
        r for r in LEGAL_RULES
        if r.get("status") == "verified_from_bnm_guide"
    ]


def get_rules_requiring_verification() -> List[Dict]:
    """Return rules that still need confirmation against primary legislation."""

    return [
        r for r in LEGAL_RULES
        if r.get("status") == "requires_authoritative_verification"
    ]