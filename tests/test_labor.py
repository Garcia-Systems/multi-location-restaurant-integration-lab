from datetime import date
from decimal import Decimal

from restaurant_integration_lab.ingestion import ExceptionCategory
from restaurant_integration_lab.labor import (
    LOCATION_MAPPINGS, REUSE_EVIDENCE, ShiftHarborImporter,
    calculate_labor_measures, labor_demand_context,
)
from restaurant_integration_lab.operational_model import resolve_location


def test_valid_records_normalize_roles_dates_and_distinct_hour_types():
    result = ShiftHarborImporter().ingest()
    assert result.rows_read == 12
    assert len(result.records) == 5
    overnight = result.records[0]
    assert overnight.business_date.value == date(2026, 8, 24)
    assert overnight.hours == Decimal("7.50")
    assert overnight.scheduled_hours == Decimal("8.00")
    assert overnight.role == "FRONT_OF_HOUSE"
    assert overnight.labor_cost == Decimal("150.00")


def test_invalid_rows_unknowns_and_duplicates_are_inspectable():
    result = ShiftHarborImporter().ingest()
    assert result.rejected_rows == 6
    assert result.duplicate_rows == 1
    by_row = {e.row_number: e for e in result.exceptions}
    assert by_row[6].category is ExceptionCategory.DUPLICATE
    assert by_row[7].category is ExceptionCategory.MALFORMED_RECORD
    assert by_row[8].category is ExceptionCategory.MALFORMED_RECORD
    assert by_row[9].category is ExceptionCategory.UNKNOWN_LOCATION
    assert by_row[10].category is ExceptionCategory.VALIDATION_FAILURE
    assert "explicit" in by_row[10].reason
    assert by_row[11].category is ExceptionCategory.MALFORMED_RECORD
    assert by_row[12].category is ExceptionCategory.MALFORMED_RECORD


def test_exact_measures_preserve_missing_cost_instead_of_zero():
    measures = calculate_labor_measures(ShiftHarborImporter().ingest().records)
    rrk, cst = measures
    assert (rrk.worked_hours, rrk.scheduled_hours, rrk.labor_cost) == (Decimal("12.00"), Decimal("13.00"), Decimal("275.00"))
    assert rrk.hours_by_role == (("BACK_OF_HOUSE", Decimal("4.00")), ("FRONT_OF_HOUSE", Decimal("7.50")), ("MANAGEMENT", Decimal("0.50")))
    assert cst.worked_hours == Decimal("8.00")
    assert cst.labor_cost is None
    assert not cst.labor_cost_complete


def test_namespaced_labor_and_pos_ids_resolve_to_same_location():
    labor = resolve_location("ShiftHarbor", "WILLIAMSBURG_MAIN", LOCATION_MAPPINGS)
    assert labor.value.canonical_id == "JRH-001"
    assert resolve_location("ShiftHarbor", "POS-WBG-14", LOCATION_MAPPINGS).value is None


def test_three_domain_context_and_ratios_are_deterministic():
    contexts = labor_demand_context()
    assert tuple(c.location_id for c in contexts) == ("JRH-001", "JRH-002")
    rrk, cst = contexts
    assert rrk.net_sales == Decimal("83.60")
    assert rrk.sales_per_worked_hour == Decimal("83.60") / Decimal("12.00")
    assert rrk.completed_reservation_covers == 2
    assert rrk.covers_per_worked_hour == Decimal("2") / Decimal("12.00")
    assert rrk.labor_cost_percent == Decimal("275.00") / Decimal("83.60") * Decimal("100")
    assert cst.net_sales == Decimal("39.00")
    assert cst.labor_cost is None and cst.labor_cost_percent is None
    assert cst.completed_reservation_covers is None and cst.covers_per_worked_hour is None


def test_reuse_evidence_is_deterministic_and_explicit_about_rework():
    assert tuple(REUSE_EVIDENCE) == ("DEMONSTRATED CROSS-SYSTEM REUSE", "CONFIGURATION REUSE", "SYSTEM-SPECIFIC WORK", "REWORK", "REJECTED REUSE CANDIDATE")
    assert "scheduled hours" in REUSE_EVIDENCE["REWORK"][0]
