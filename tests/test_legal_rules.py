from rag.legal_rules import get_legal_rules


def test_legal_rules_are_available():
    rules = get_legal_rules()

    assert isinstance(rules, list)
    assert len(rules) > 0


def test_required_rule_ids_exist():
    rules = get_legal_rules()

    rule_ids = {
        rule["rule_id"]
        for rule in rules
    }

    assert "HP2026-EIR-001" in rule_ids
    assert "HP2026-RB-001" in rule_ids
    assert "HP2026-FIXED-CAP-001" in rule_ids
    assert "HP2026-VARIABLE-CAP-001" in rule_ids


def test_every_rule_has_required_fields():
    rules = get_legal_rules()

    for rule in rules:
        assert "rule_id" in rule
        assert "topic" in rule
        assert "rule" in rule
        assert "source" in rule


def test_reducing_balance_rule_exists():
    rules = get_legal_rules()

    reducing_balance_rules = [
        rule
        for rule in rules
        if rule["rule_id"] == "HP2026-RB-001"
    ]

    assert len(reducing_balance_rules) == 1


def test_fixed_rate_cap_rule_exists():
    rules = get_legal_rules()

    fixed_cap_rule = [
        rule
        for rule in rules
        if rule["rule_id"] == "HP2026-FIXED-CAP-001"
    ]

    assert len(fixed_cap_rule) == 1


def test_newly_hardened_2026_rules_exist():
    rules = get_legal_rules()
    rule_ids = {r["rule_id"] for r in rules}

    assert "HP2026-DEP-001" in rule_ids
    assert "HP2026-RR-001" in rule_ids
    assert "HP2026-SIG-001" in rule_ids
    assert "HP2026-GRACE-001" in rule_ids
    assert "HP2026-KYC-001" in rule_ids


def test_effective_date_and_grace_period_accuracy():
    rules = get_legal_rules()
    trans_rule = next(r for r in rules if r["rule_id"] == "HP2026-TRANS-001")
    grace_rule = next(r for r in rules if r["rule_id"] == "HP2026-GRACE-001")
    rb_rule = next(r for r in rules if r["rule_id"] == "HP2026-RB-002")

    assert "1 June 2026" in trans_rule["rule"]
    assert "1 June 2026" in rb_rule["rule"]
    assert "31 March 2027" in grace_rule["rule"]
    assert grace_rule["status"] == "verified_from_bnm_guide"


def test_early_settlement_rebate_abolition_rule():
    rules = get_legal_rules()
    es_rule = next(r for r in rules if r["rule_id"] == "HP2026-ES-001")

    assert "no longer offer rebates" in es_rule["rule"].lower()
    assert "outstanding principal" in es_rule["rule"].lower()
    assert es_rule["status"] == "verified_from_bnm_guide"


def test_minimum_deposit_rule():
    rules = get_legal_rules()
    dep_rule = next(r for r in rules if r["rule_id"] == "HP2026-DEP-001")

    assert "10%" in dep_rule["rule"]
    assert "Section 31" in dep_rule["source"]
    assert dep_rule["status"] == "verified_from_bnm_guide"


def test_reference_rate_framework_rule():
    rules = get_legal_rules()
    rr_rule = next(r for r in rules if r["rule_id"] == "HP2026-RR-001")

    assert "Reference Rate" in rr_rule["rule"]
    assert "Base Lending Rate" in rr_rule["rule"]
    assert rr_rule["status"] == "verified_from_bnm_guide"