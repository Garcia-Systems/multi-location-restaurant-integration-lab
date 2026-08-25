from decimal import Decimal

import pytest

from restaurant_integration_lab.briefing import EvidenceState
from restaurant_integration_lab.normalization import build_dataset
from restaurant_integration_lab.stress_test import (
    COMPARISON, HUMAN_APPROVED_NAME_MAPPINGS, LOCATION, REUSE_EROSION,
    SUPPORT_OBLIGATIONS, MillLedgerWeekOneParser, UnsupportedLegacySchema,
    existing_onboarding_attempt, inventory_assessment, labor_context,
    map_product, operational_config, stress_briefing, stress_dataset,
    stress_test_report, WEEK2,
)


def test_seventh_location_has_unique_canonical_identity():
    previous = {row.canonical_location_id for row in build_dataset().coverage}
    assert LOCATION.canonical_id == "JRH-007" and LOCATION.canonical_id not in previous


def test_existing_path_fails_visibly_before_adapter():
    attempt = dict(existing_onboarding_attempt())
    assert attempt["Location configuration"] == "PASS"
    assert attempt["POS parser"].startswith("FAIL")
    assert attempt["Product mappings"].startswith("BLOCKED")
    assert attempt["Labor parser"].startswith("FAIL")


def test_source_specific_pos_and_schema_instability_are_explicit():
    assert len(MillLedgerWeekOneParser().load()) == 3
    with pytest.raises(UnsupportedLegacySchema, match="explicit week1 schema required"):
        MillLedgerWeekOneParser().load(WEEK2)


def test_product_names_are_never_fuzzy_mapped():
    assert map_product("classic cheeseburger", HUMAN_APPROVED_NAME_MAPPINGS) is None
    assert map_product("Classic Cheeseburge", HUMAN_APPROVED_NAME_MAPPINGS) is None
    assert map_product("Classic Cheeseburger", HUMAN_APPROVED_NAME_MAPPINGS).canonical_id == "JRH-P-010"


def test_partial_sales_remain_safe_but_detail_stays_blocked():
    dataset = stress_dataset()
    coverage = next(row for row in dataset.coverage if row.canonical_location_id == "JRH-007")
    assert coverage.fully_normalized == 2 and coverage.unresolved_product == 1
    assert dict(dataset.sales_by_location())["JRH-007"] == Decimal("37.00")


def test_reservation_labor_and_inventory_limits_remain_visible():
    brief = stress_briefing(); row = next(row for row in brief.locations if row.location_id == "JRH-007")
    assert row.reservation_state is EvidenceState.NOT_APPLICABLE
    assert row.labor is not None and row.labor.labor_cost is None
    assert labor_context().worked_hours == Decimal("14")
    assert inventory_assessment()[0] == "NOT SAFE FOR GROUP RECONCILIATION"


def test_briefing_operations_support_and_report_are_inspectable():
    brief = stress_briefing(); row = next(row for row in brief.locations if row.location_id == "JRH-007")
    assert row.sales_state is EvidenceState.PARTIAL
    assert len(operational_config()) == 3
    assert all(job.location_id == "JRH-007" for job in operational_config())
    assert "week-specific schema monitoring" in SUPPORT_OBLIGATIONS
    report = stress_test_report()
    for phrase in ("STANDARDIZATION STRESS TEST — JRH-007", "reservations: NOT APPLICABLE",
                   "inventory: NOT SAFE FOR GROUP RECONCILIATION", "BUILD-vs-BUY QUESTIONS"):
        assert phrase in report


def test_comparison_and_reuse_erosion_are_deterministic():
    assert COMPARISON == tuple(COMPARISON)
    assert REUSE_EROSION == tuple(REUSE_EROSION)
    assert dict(REUSE_EROSION)["HarborTill POS parser"] == "FAILED TO APPLY"
    assert stress_test_report() == stress_test_report()
