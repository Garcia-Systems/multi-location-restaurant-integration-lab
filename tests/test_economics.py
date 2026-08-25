from restaurant_integration_lab.economics import (
    EVIDENCE_MATRIX, ONBOARDING_COMPARISON, REUSE_ASSESSMENT, SCENARIOS,
    SUPPORT_SURFACES, Assessment, ReuseClass, economics_report,
)
from restaurant_integration_lab.models import CASE_2, WorkCategory


def test_original_values_are_preserved_and_labeled_modeled():
    report = economics_report()
    assert CASE_2.modeled_engineering_hours == 234
    assert "TOTAL: 234 modeled hours — MODELED ASSUMPTION" in report
    assert "Observed engineering hours" not in report
    assert "No engineering time was measured by this lab" in report


def test_matrix_has_every_original_category_and_is_deterministic():
    assert {row.category for row in EVIDENCE_MATRIX} == set(WorkCategory)
    assert all(isinstance(row.assessment, Assessment) for row in EVIDENCE_MATRIX)
    assert economics_report() == economics_report()


def test_standardized_and_nonstandard_onboarding_are_distinct():
    assert all(six != seven for six, seven in ONBOARDING_COMPARISON.values())
    report = economics_report()
    assert "JRH-006 — MOSTLY STANDARDIZED ONBOARDING" in report
    assert "JRH-007 — NON-STANDARD ACQUISITION" in report


def test_reuse_and_repository_support_evidence_are_explicit():
    assert tuple(REUSE_ASSESSMENT) == ("canonical identity", "business date", "POS", "reservations", "labor", "inventory", "exceptions", "briefing", "operations")
    assert set(REUSE_ASSESSMENT.values()) <= set(ReuseClass)
    assert "credential references" in SUPPORT_SURFACES
    assert "manual files and irregular arrival" in SUPPORT_SURFACES


def test_customer_and_provider_economics_remain_separate():
    report = economics_report()
    customer = report.index("CUSTOMER ECONOMICS")
    provider = report.index("PROVIDER ECONOMICS")
    sensitivity = report.index("SENSITIVITY SCENARIOS")
    assert customer < provider < sensitivity
    assert "Implementation contribution: NOT CALCULABLE" in report


def test_scenarios_are_assumptions_and_do_not_mutate_original():
    original = SCENARIOS[0]
    assert original.total_hours == 234
    assert original.label == "MODELED ASSUMPTION"
    assert [scenario.total_hours for scenario in SCENARIOS] == [234, 204, 334]
    assert all(s.label == "SENSITIVITY ASSUMPTION" for s in SCENARIOS[1:])
    assert CASE_2.modeled_engineering_hours == 234


def test_break_even_boundary_uses_price_without_inventing_rate():
    report = economics_report()
    assert "Maximum delivery cost before implementation contribution reaches zero: $42,000" in report
    assert "Maximum delivery hours: NOT CALCULABLE" in report


def test_chapter_14_does_not_protect_old_verdict_or_resolve_build_buy():
    report = economics_report()
    assessment = report[report.index("DELIVERY-ECONOMIC ASSESSMENT"):]
    assert "PROMISING — VALIDATE IN DISCOVERY" not in assessment
    assert "Original 234-hour estimate: NOT VALIDATED" in assessment
    assert "Build versus buy: UNRESOLVED — reserved for Chapter 15." in assessment
