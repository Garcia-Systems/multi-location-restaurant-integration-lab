from datetime import date
from decimal import Decimal

import pytest

from restaurant_integration_lab.ingestion import ExceptionCategory
from restaurant_integration_lab.inventory import (
    CSTSpreadsheetParser, EXPERIMENT_CONVERSION, EvidenceStatus, InventoryImporter,
    InventoryUnit, OYSTER_MEAT, PATTY, ReconciliationStatus, StockPilotParser,
    aggregate_normalized, convert_quantity, inventory_report, reconciliation_assessment,
    require_compatible_sum,
)
from restaurant_integration_lab.location1 import LOCATION_MAPPINGS as POS_LOCATION_MAPPINGS
from restaurant_integration_lab.model_demo import RRK
from restaurant_integration_lab.operational_model import resolve_location


def categories(result):
    return {error.category for error in result.exceptions}


def test_valid_records_and_explicit_weight_units_normalize() -> None:
    result = InventoryImporter().ingest()
    oyster = next(row for row in result.normalized if row.record.provenance.source_record_id == "SP-002")
    assert oyster.source_unit is InventoryUnit.LB
    assert oyster.normalized_quantity == Decimal("48")
    assert oyster.normalized_unit is InventoryUnit.OZ
    cst = next(row for row in result.normalized if row.record.provenance.source_record_id == "CST-002")
    assert cst.normalized_quantity == Decimal("16")
    assert aggregate_normalized((oyster, cst))


def test_bad_quantity_negative_unknown_location_and_duplicates_are_rejected() -> None:
    result = InventoryImporter().ingest_source(StockPilotParser())
    assert ExceptionCategory.MALFORMED_RECORD in categories(result)
    assert ExceptionCategory.UNKNOWN_LOCATION in categories(result)
    assert ExceptionCategory.DUPLICATE in categories(result)
    reasons = " ".join(error.reason for error in result.exceptions)
    assert "malformed quantity" in reasons
    assert "cannot be negative" in reasons


def test_unknown_items_units_and_conflicts_remain_inspectable_and_are_not_guessed() -> None:
    result = InventoryImporter().ingest()
    assert result.unresolved_rows == 6
    assert ExceptionCategory.UNKNOWN_INVENTORY_ITEM in categories(result)
    assert ExceptionCategory.UNKNOWN_UNIT in categories(result)
    assert ExceptionCategory.CONFLICTING_MAPPING in categories(result)
    missing = next(error for error in result.exceptions if error.source_record_id == "CST-003")
    assert missing.category is ExceptionCategory.UNKNOWN_UNIT
    assert "no default" in missing.reason
    mystery = next(error for error in result.exceptions if error.source_record_id == "CST-004")
    assert mystery.category is ExceptionCategory.UNKNOWN_INVENTORY_ITEM


def test_case_conversion_is_product_and_source_item_specific_configuration() -> None:
    before = InventoryImporter().ingest_source(StockPilotParser())
    case = next(row for row in before.unresolved if row.record.source_product.source_identifier == "PATTY-CASE")
    assert case.unresolved_reason == "MISSING PRODUCT-SPECIFIC PACK CONVERSION"
    after = InventoryImporter((EXPERIMENT_CONVERSION,)).ingest_source(StockPilotParser())
    converted = next(row for row in after.normalized if row.record.source_product.source_identifier == "PATTY-CASE")
    assert converted.normalized_quantity == Decimal("80")
    assert converted.normalized_unit is InventoryUnit.EACH
    quantity, reason = convert_quantity(Decimal("2"), InventoryUnit.CASE, InventoryUnit.EACH,
                                        OYSTER_MEAT, "PATTY-CASE", (EXPERIMENT_CONVERSION,))
    assert quantity is None and reason == "MISSING PRODUCT-SPECIFIC PACK CONVERSION"


def test_incompatible_or_unresolved_quantities_cannot_be_silently_summed() -> None:
    result = InventoryImporter().ingest_source(StockPilotParser())
    patty = next(row for row in result.normalized if row.inventory_item == PATTY)
    oyster = next(row for row in result.normalized if row.inventory_item == OYSTER_MEAT)
    with pytest.raises(ValueError, match="incompatible"):
        require_compatible_sum((patty, oyster))
    unresolved = next(row for row in result.evidence if row.status is EvidenceStatus.UNRESOLVED)
    with pytest.raises(ValueError, match="unresolved"):
        require_compatible_sum((unresolved,))


def test_effective_count_date_is_distinct_from_late_arrival() -> None:
    result = InventoryImporter().ingest_source(StockPilotParser())
    row = next(row for row in result.normalized if row.record.provenance.source_record_id == "SP-001")
    assert row.record.business_date.value == date(2026, 8, 24)
    assert row.record.evidence_arrived_at.date() == date(2026, 8, 26)
    assert row.record.business_date.value != row.record.evidence_arrived_at.date()


def test_inventory_item_is_not_silently_a_menu_product() -> None:
    assert OYSTER_MEAT.related_menu_product is not None
    assert "not a recipe" in OYSTER_MEAT.relationship_note.lower()
    row = InventoryImporter().ingest_source(StockPilotParser()).normalized[0]
    assert row.record.product is None
    assert row.record.inventory_item is not None


def test_reconciliation_is_refused_and_location_identity_is_reused() -> None:
    assessment = reconciliation_assessment()
    assert assessment.status is ReconciliationStatus.NOT_RECONCILABLE
    assert "receipts absent" in assessment.reasons
    inventory_location = resolve_location("StockPilot", "Store 014", __import__(
        "restaurant_integration_lab.inventory", fromlist=["LOCATION_MAPPINGS"]).LOCATION_MAPPINGS)
    pos_location = resolve_location("HarborTill RRK", "POS-WBG-14", POS_LOCATION_MAPPINGS)
    assert inventory_location.value == pos_location.value == RRK


def test_report_and_cli_sections_are_deterministic(capsys) -> None:
    from restaurant_integration_lab.cli import main
    report = inventory_report()
    assert report == inventory_report()
    for section in ("PRODUCT / ITEM IDENTITY", "UNIT NORMALIZATION", "LATE DATA EXAMPLE",
                    "RECONCILIATION STATUS", "CANONICAL MODEL STRESS TEST", "REWORK"):
        assert section in report
    assert main(["inventory"]) == 0
    assert capsys.readouterr().out == report + "\n"
