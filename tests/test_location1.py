import json
from datetime import date
from decimal import Decimal

from restaurant_integration_lab.cli import main
from restaurant_integration_lab.location1 import (
    ExceptionCategory, LOCATION_ONE_FIXTURE, LocationOneSalesImporter,
    location1_report,
)


def ingest():
    return LocationOneSalesImporter().ingest()


def test_valid_rows_become_canonical_sales_with_exact_calculations() -> None:
    result = ingest()
    assert len(result.sales) == 4
    assert result.measures.total_quantity == Decimal("6")
    assert result.measures.gross_sales == Decimal("87.80")
    assert result.measures.discounts == Decimal("4.20")
    assert result.measures.net_sales == Decimal("83.60")
    assert result.measures.sales_by_business_date == (("2026-08-24", Decimal("83.60")),)


def test_malformed_money_missing_identity_and_timestamp_are_inspectable() -> None:
    errors = ingest().exceptions
    malformed = [error for error in errors if error.category is ExceptionCategory.MALFORMED_RECORD]
    assert [(error.row_number, error.reason) for error in malformed] == [
        (6, "malformed decimal value"),
        (7, "missing required field(s): transaction_id"),
        (10, "malformed transaction_timestamp"),
    ]
    assert all(error.human_action_required for error in malformed)


def test_unknown_location_and_product_are_rejected_not_guessed() -> None:
    result = ingest()
    assert [(error.row_number, error.category) for error in result.exceptions if error.category in {
        ExceptionCategory.UNKNOWN_LOCATION, ExceptionCategory.UNKNOWN_PRODUCT
    }] == [(5, ExceptionCategory.UNKNOWN_PRODUCT), (8, ExceptionCategory.UNKNOWN_LOCATION)]
    assert all(sale.source_product.source_identifier != "MENU-NEW" for sale in result.sales)


def test_authoritative_product_id_allows_harmless_name_variation() -> None:
    result = ingest()
    varied = next(sale for sale in result.sales if sale.provenance.source_record_id == "CHK-1003:1")
    assert varied.product is not None
    assert varied.product.canonical_id == "JRH-P-001"
    assert varied.product.name == "James River Oysters"


def test_duplicates_are_deterministic_and_importer_is_idempotent() -> None:
    importer = LocationOneSalesImporter()
    first = importer.ingest()
    second = importer.ingest()
    assert first.duplicate_rows == 1
    assert next(error for error in first.exceptions if error.category is ExceptionCategory.DUPLICATE).row_number == 9
    assert second.sales == ()
    assert second.duplicate_rows == 5  # four prior accepted identities plus fixture row 9


def test_business_date_differs_from_after_midnight_timestamp() -> None:
    sale = ingest().sales[0]
    assert sale.transaction_timestamp is not None
    assert sale.transaction_timestamp.date() == date(2026, 8, 25)
    assert sale.business_date.value == date(2026, 8, 24)


def test_provenance_retains_source_and_fixture_row() -> None:
    provenance = ingest().sales[0].provenance
    assert provenance.source_system == "HarborTill RRK"
    assert provenance.source_location_id == "POS-WBG-14"
    assert provenance.source_record_id == "CHK-1001:1"
    assert provenance.source_interface == "synthetic REST API JSON v3 fixture"
    assert provenance.reference == "synthetic fixture row 1"


def test_rejected_records_do_not_enter_calculations() -> None:
    result = ingest()
    raw = json.loads(LOCATION_ONE_FIXTURE.read_text(encoding="utf-8"))
    assert len(raw["records"]) == 10
    assert result.rows_read == len(result.sales) + result.rejected_rows + result.duplicate_rows
    assert result.measures.net_sales != Decimal("102.60")  # excludes the unknown $19 product


def test_events_expose_pipeline_outcomes_in_order() -> None:
    events = ingest().events
    assert events[0].event == "IMPORT_STARTED"
    assert events[-1].event == "IMPORT_COMPLETED"
    assert any(event.event == "UNKNOWN_MAPPING" for event in events)
    assert any(event.event == "DUPLICATE_DETECTED" for event in events)


def test_exception_and_cli_output_are_deterministic(capsys) -> None:
    assert ingest().exceptions == ingest().exceptions
    report = location1_report()
    assert report == location1_report()
    assert "REJECTED: 5" in report and "DUPLICATES: 1" in report
    assert "REUSE CANDIDATES — NOT DEMONSTRATED REUSE" in report
    assert main(["location1"]) == 0
    assert capsys.readouterr().out == report + "\n"
