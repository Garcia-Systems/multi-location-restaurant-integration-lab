from restaurant_integration_lab.build_vs_buy import (
    ALTERNATIVES, CAPABILITY_MATRIX, CUSTOM_CAPABILITIES, DECISION_MATRIX,
    FICTIONAL, FULL_SCOPE, NARROW_SCOPE, OBSERVED, REMAINING_CUSTOM_GAP,
    REMOVED_AS_CONFIGURABLE, Decision, Differentiation, build_vs_buy_report,
    decide,
)


def test_custom_inventory_names_only_implemented_artifacts():
    assert CUSTOM_CAPABILITIES
    assert all(capability.implementation.endswith(".py") for capability in CUSTOM_CAPABILITIES)
    assert {"briefing", "operations", "legacy"} <= {c.key for c in CUSTOM_CAPABILITIES}
    assert all(OBSERVED in build_vs_buy_report().split("BUYER REQUIREMENTS")[0] for _ in [0])


def test_fictional_alternatives_are_labeled_and_not_vendor_claims():
    report = build_vs_buy_report()
    assert all(FICTIONAL in report[report.index(a.name):] for a in ALTERNATIVES if a.key not in {"narrow", "full"})
    assert "No real SaaS product, capability, price" in report


def test_capability_matrix_and_classification_are_deterministic():
    assert build_vs_buy_report() == build_vs_buy_report()
    assert tuple(CAPABILITY_MATRIX) == tuple(a.key for a in ALTERNATIVES)
    assert all(isinstance(c.differentiation, Differentiation) for c in CUSTOM_CAPABILITIES)


def test_scope_reduction_removes_only_commodity_or_configurable():
    by_key = {c.key: c for c in CUSTOM_CAPABILITIES}
    assert all(by_key[key].differentiation in {Differentiation.COMMODITY, Differentiation.CONFIGURABLE} for key in REMOVED_AS_CONFIGURABLE)
    assert set(REMOVED_AS_CONFIGURABLE).isdisjoint(REMAINING_CUSTOM_GAP)
    assert set(REMOVED_AS_CONFIGURABLE) | set(REMAINING_CUSTOM_GAP) == set(by_key)


def test_narrow_custom_is_meaningfully_smaller_than_full():
    for dimension in ("capabilities", "sources", "support_surfaces", "exceptions", "jobs"):
        assert len(NARROW_SCOPE[dimension]) < len(FULL_SCOPE[dimension])


def test_profiles_differ_and_custom_is_not_automatically_highest():
    decisions = {row["decision"] for row in DECISION_MATRIX.values()}
    assert decisions == {Decision.BUY, Decision.STANDARDIZE, Decision.INVESTIGATE}
    assert Decision.FULL not in decisions


def test_deterministic_decision_rules_cover_procurement_boundaries():
    assert decide(commodity_sufficient=True) is Decision.BUY
    assert decide(variation_primary=True) is Decision.STANDARDIZE
    assert decide(assumptions_resolved=False) is Decision.INVESTIGATE
    assert decide(value_proven=False) is Decision.DEFER
    assert decide(custom_gap_material=True, gap_bounded=True) is Decision.NARROW
    assert decide(custom_gap_material=True, standardized=True, support_acceptable=True) is Decision.FULL


def test_full_custom_requires_explicit_material_differentiation():
    assert decide(custom_gap_material=False, standardized=True, support_acceptable=True) is not Decision.FULL
    assert decide(custom_gap_material=True, standardized=False, support_acceptable=True) is not Decision.FULL
    assert decide(custom_gap_material=True, standardized=True, support_acceptable=False) is not Decision.FULL


def test_observation_and_assumption_sections_remain_explicitly_separate():
    report = build_vs_buy_report()
    assert OBSERVED in report and FICTIONAL in report
    assert "final opportunity classification remains unresolved" in report
