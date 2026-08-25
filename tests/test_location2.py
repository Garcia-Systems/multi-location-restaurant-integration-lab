from datetime import date
from decimal import Decimal
import json

from restaurant_integration_lab.cli import main
from restaurant_integration_lab.ingestion import ExceptionCategory, calculate_sales
from restaurant_integration_lab.location1 import LocationOneSalesImporter
from restaurant_integration_lab.location2 import (
    LOCATION_TWO_FIXTURE, REUSE_CLASSIFICATION, LocationTwoHarborTillCsvParser,
    LocationTwoSalesImporter, location2_report, net_sales_by_location,
)
from restaurant_integration_lab.operational_model import Sale


def ingest():
    return LocationTwoSalesImporter().ingest()


def test_location_one_remains_unchanged() -> None:
    result = LocationOneSalesImporter().ingest()
    assert len(result.sales) == 4
    assert result.measures.net_sales == Decimal("83.60")


def test_location_two_normalizes_valid_rows_and_deliberate_csv_shape() -> None:
    result = ingest()
    assert (result.rows_read, len(result.sales), result.rejected_rows, result.duplicate_rows) == (9, 4, 4, 1)
    assert result.measures.net_sales == Decimal("39.00")
    header = LOCATION_TWO_FIXTURE.read_text(encoding="utf-8").splitlines()[1]
    assert header.startswith("StoreCode,SaleDate,LocalTime,TicketLine,SKU")
    assert "transaction_id" not in header and "business_date" not in header


def test_malformed_unknown_duplicate_and_void_are_inspectable() -> None:
    result = ingest()
    categories = [(item.row_number, item.category) for item in result.exceptions]
    assert categories == [
        (5, ExceptionCategory.UNKNOWN_PRODUCT), (6, ExceptionCategory.MALFORMED_RECORD),
        (7, ExceptionCategory.DUPLICATE), (8, ExceptionCategory.VALIDATION_FAILURE),
        (9, ExceptionCategory.UNKNOWN_LOCATION),
    ]
    assert all(sale.source_product.source_identifier != "NEW-777" for sale in result.sales)


def test_source_business_date_is_authoritative_and_deterministic() -> None:
    first = ingest().sales[0]
    assert first.transaction_timestamp.date() == date(2026, 8, 25)
    assert first.transaction_timestamp.hour == 1
    assert first.business_date.value == date(2026, 8, 25)
    assert ingest().sales == ingest().sales


def test_both_locations_share_canonical_type_calculation_and_product_identity() -> None:
    one, two = LocationOneSalesImporter().ingest(), ingest()
    assert all(type(sale) is Sale for sale in one.sales + two.sales)
    assert calculate_sales(one.sales) == one.measures
    assert calculate_sales(two.sales) == two.measures
    assert one.sales[0].product.canonical_id == "JRH-P-001"
    assert two.sales[0].product.canonical_id == "JRH-P-001"
    assert one.sales[0].source_product.source_identifier != two.sales[0].source_product.source_identifier


def test_combined_calculation_uses_only_canonical_location_identity() -> None:
    one, two = LocationOneSalesImporter().ingest(), ingest()
    assert net_sales_by_location(one.sales + two.sales) == (
        ("JRH-001", Decimal("83.60")), ("JRH-002", Decimal("39.00")),
    )
    assert {sale.location.canonical_id for sale in two.sales} == {"JRH-002"}
    assert all(sale.location.canonical_id != sale.provenance.source_location_id for sale in two.sales)


def test_reuse_classification_and_evidence_are_deterministic_and_real() -> None:
    assert REUSE_CLASSIFICATION == dict(REUSE_CLASSIFICATION)
    assert REUSE_CLASSIFICATION["UNCHANGED REUSE"]
    assert REUSE_CLASSIFICATION["SOURCE-SPECIFIC DIFFERENCE"]
    ledger = json.loads(open("docs/evidence/chapter-04-reuse-ledger.json", encoding="utf-8").read())
    assert ledger["notice"].startswith("SYNTHETIC LAB")
    results = {item["result"] for item in ledger["reuse_candidates"]}
    assert "DEMONSTRATED REUSE" in results and "REJECTED REUSE CANDIDATE" in results
    assert "percentage" not in json.dumps(ledger).lower()


def test_location_two_cli_is_deterministic(capsys) -> None:
    report = location2_report()
    assert report == location2_report()
    assert "LOCATION #1 CODE MODIFIED\nYES" in report
    assert "CANONICAL MODEL MODIFIED\nNO" in report
    assert main(["location2"]) == 0
    assert capsys.readouterr().out == report + "\n"
