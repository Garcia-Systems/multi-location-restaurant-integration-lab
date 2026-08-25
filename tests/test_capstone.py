from dataclasses import replace

from restaurant_integration_lab.build_vs_buy import Decision
from restaurant_integration_lab.capstone import (
    BEST_FIT, HYPOTHESIS_COMPONENTS, LAB_EVIDENCE, MODELED, OBSERVED,
    POOR_FIT, REUSE_INVENTORY, STANDARDIZATION_FITS, ComponentAssessment,
    ProductClass, Verdict, capstone_report, classify_delivery, final_verdict,
)
from restaurant_integration_lab.economics import ONBOARDING_COMPARISON, SUPPORT_SURFACES


def test_capstone_consumes_prior_evidence_and_keeps_types_separate():
    report = capstone_report()
    assert "JRH-006" in report and "JRH-007" in report
    assert str(Decision.INVESTIGATE) in report
    assert f"234 modeled hours — {MODELED}" in report
    assert "Actual engineering time: UNMEASURED" in report
    assert OBSERVED in report and "No implementation time or real customer value was measured" in report


def test_assessments_and_reuse_are_deterministic():
    assert capstone_report() == capstone_report()
    assert all(isinstance(value[0], ComponentAssessment) for value in HYPOTHESIS_COMPONENTS.values())
    assert tuple(REUSE_INVENTORY) == tuple(REUSE_INVENTORY)


def test_onboarding_support_and_standardization_remain_evidence_based():
    assert all(a != b for a, b in ONBOARDING_COMPARISON.values())
    assert set(STANDARDIZATION_FITS) == {"STANDARDIZED FIT", "PARTIAL FIT", "NON-STANDARD FIT"}
    assert all(surface in capstone_report() for surface in SUPPORT_SURFACES)
    assert "MEANINGFUL SUPPORT SURFACE" in capstone_report()


def test_project_product_classification_uses_explicit_inputs():
    assert classify_delivery(LAB_EVIDENCE) is ProductClass.SERVICE
    assert classify_delivery(replace(LAB_EVIDENCE, shared_core_demonstrated=False)) is ProductClass.PROJECT
    product = replace(LAB_EVIDENCE, repeatable_interfaces=True, mostly_standardized=True,
                      stable_identifiers=True, support_acceptable=True)
    assert classify_delivery(product) is ProductClass.PRODUCT


def test_final_verdict_is_not_protected_and_poor_profiles_change_it():
    assert final_verdict(LAB_EVIDENCE) is Verdict.INVESTIGATE
    assert final_verdict(replace(LAB_EVIDENCE, alternative_capabilities_verified=True,
                                 material_custom_gap=False)) is Verdict.BUY
    assert final_verdict(replace(LAB_EVIDENCE, management_need=False,
                                 value_validated=False)) is Verdict.NO_DEAL
    assert final_verdict(replace(LAB_EVIDENCE, location_count=1)) is Verdict.POOR
    assert "PRIMARY VERDICT: PROMISING" not in capstone_report()


def test_profiles_are_lab_derived_and_unsupported_claims_are_excluded():
    assert BEST_FIT and POOR_FIT
    report = capstone_report()
    assert "NOT MARKET VALIDATION" in report
    assert "no real vendor was validated" in report
    assert "actual restaurant customer value" in report
    assert "actual engineering hours" in report


def test_readme_finding_tracks_executable_verdict():
    readme = open("README.md", encoding="utf-8").read()
    assert f"Primary verdict: **{final_verdict(LAB_EVIDENCE)}**" in readme
    assert "Chapter 16 — Capstone: Project, Product, or Bad Idea? COMPLETE" in readme
