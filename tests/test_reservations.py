from datetime import date
from decimal import Decimal

from restaurant_integration_lab.ingestion import ExceptionCategory
from restaurant_integration_lab.model_demo import LOCATION_MAPPINGS as POS_LOCATION_MAPPINGS
from restaurant_integration_lab.operational_model import Availability, BusinessDate, resolve_location
from restaurant_integration_lab.reservations import (BHO, CST, EVIDENCE_AVAILABILITY, LOCATION_MAPPINGS,
    REUSE_EVIDENCE, RRK, ReservationStatus, TableCurrentImporter, calculate_reservation_measures,
    reservations_report, sales_context)


def result(): return TableCurrentImporter().ingest()

def test_valid_records_statuses_and_business_dates_normalize():
    records = result().reservations
    assert len(records) == 5
    assert {r.status for r in records} == {s.value for s in ReservationStatus}
    canceled = next(r for r in records if r.status == "CANCELED")
    assert canceled.reservation_timestamp.date() == date(2026, 8, 25)
    assert canceled.business_date == BusinessDate(date(2026, 8, 24))

def test_malformed_party_unknown_status_location_duplicate_and_timestamp_are_inspectable():
    errors = result().exceptions
    assert [(e.row_number, e.category) for e in errors] == [
        (6, ExceptionCategory.DUPLICATE), (7, ExceptionCategory.MALFORMED_RECORD),
        (8, ExceptionCategory.UNKNOWN_STATUS), (9, ExceptionCategory.UNKNOWN_LOCATION),
        (10, ExceptionCategory.MALFORMED_RECORD)]
    assert "party size" in errors[1].reason
    assert "status" in errors[2].reason
    assert "timestamp" in errors[4].reason

def test_namespaces_prevent_collisions_and_different_ids_align():
    assert resolve_location("TableCurrent", "14", LOCATION_MAPPINGS).value == RRK
    assert not resolve_location("HarborTill RRK", "14", LOCATION_MAPPINGS).resolved
    assert resolve_location("HarborTill RRK", "POS-WBG-14", POS_LOCATION_MAPPINGS).value == RRK

def test_measures_keep_canceled_and_no_show_out_of_completed_covers():
    measures = {m.location_id: m for m in calculate_reservation_measures(result().reservations)}
    assert (measures["JRH-001"].completed_covers, measures["JRH-001"].canceled_covers) == (2, 3)
    assert (measures["JRH-003"].completed_covers, measures["JRH-003"].no_show_covers) == (5, 2)
    assert "NOT TOTAL RESTAURANT COVERS" in measures["JRH-001"].demand_label

def test_availability_distinguishes_zero_missing_not_applicable_and_not_integrated():
    assert EVIDENCE_AVAILABILITY[RRK].record_count == 3
    assert EVIDENCE_AVAILABILITY[CST].availability is Availability.NOT_APPLICABLE
    assert EVIDENCE_AVAILABILITY[BHO].record_count == 2
    assert all(e.record_count is None for location, e in EVIDENCE_AVAILABILITY.items() if location not in (RRK, BHO))

def test_sales_join_uses_canonical_location_and_business_date():
    joined = sales_context(result())
    assert len(joined) == 1
    assert (joined[0].location_id, str(joined[0].business_date), joined[0].net_sales) == ("JRH-001", "2026-08-24", Decimal("83.60"))

def test_reuse_classification_and_cli_report_are_deterministic(capsys):
    assert REUSE_EVIDENCE.demonstrated_cross_system_reuse == ("canonical Location and BusinessDate", "SourceIdentity resolution", "Provenance", "IngestionException and IngestionEvent")
    assert reservations_report() == reservations_report()
    assert "TOTAL DEMAND" not in reservations_report()
    from restaurant_integration_lab.cli import main
    assert main(["reservations"]) == 0
    assert "NOT INTEGRATED (no zero implied)" in capsys.readouterr().out
