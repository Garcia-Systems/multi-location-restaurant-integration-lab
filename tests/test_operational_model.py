from datetime import date, datetime, time
from decimal import Decimal

import pytest

from restaurant_integration_lab.cli import main
from restaurant_integration_lab.model_demo import (
    CST, INVENTORY, LOCATION_MAPPINGS, OYSTERS, PRODUCT_MAPPINGS, RESERVATION_EVIDENCE, RRK, model_report,
)
from restaurant_integration_lab.operational_model import (
    Availability, BusinessDate, DomainEvidence, InventoryRecord, LaborRecord,
    Provenance, Reservation, Sale, SourceIdentity, aggregate_inventory,
    resolve_location, resolve_product,
)


PROVENANCE = Provenance("HarborTill RRK", "POS-WBG-14", "SALE-42", "synthetic JSON fixture")
DAY = BusinessDate(date(2026, 8, 24))


def test_location_resolution_is_explicit_and_unknown_ids_fail() -> None:
    result = resolve_location("HarborTill RRK", "POS-WBG-14", LOCATION_MAPPINGS)
    assert result.resolved and result.value == RRK
    unknown = resolve_location("HarborTill RRK", "JRH-001", LOCATION_MAPPINGS)
    assert not unknown.resolved and unknown.value is None
    assert unknown.reason == "UNKNOWN LOCATION — EXPLICIT MAPPING REQUIRED"


def test_multiple_source_products_resolve_to_one_canonical_product() -> None:
    sources = (("HarborTill RRK", "MENU-771"), ("HarborTill CST", "ITEM-OYS"),
               ("StockPilot", "SKU-4401"))
    assert {resolve_product(*source, PRODUCT_MAPPINGS).value for source in sources} == {OYSTERS}
    unknown = resolve_product("StockPilot", "NEW-SKU", PRODUCT_MAPPINGS)
    assert not unknown.resolved and unknown.reason == "HUMAN MAPPING REQUIRED"


def test_sale_requires_decimal_money_and_retains_provenance() -> None:
    sale = Sale(RRK, DAY, SourceIdentity("HarborTill RRK", "MENU-771"), Decimal("1"),
                Decimal("12.10"), Decimal("2.10"), Decimal("10.00"), PROVENANCE, OYSTERS)
    assert sale.net_amount == Decimal("10.00")
    assert sale.provenance.source_record_id == "SALE-42"
    with pytest.raises(TypeError, match="Decimal"):
        Sale(RRK, DAY, sale.source_product, Decimal("1"), 12.10, Decimal("0"), Decimal("12.10"), PROVENANCE)  # type: ignore[arg-type]


def test_business_date_cutoff_is_deterministic() -> None:
    timestamp = datetime(2026, 8, 25, 0, 30)
    assert BusinessDate.from_local_timestamp(timestamp, time(4)).value == date(2026, 8, 24)
    assert BusinessDate.from_local_timestamp(timestamp, time(0)).value == date(2026, 8, 25)


def test_zero_reservations_is_distinct_from_not_applicable_and_unavailable() -> None:
    assert RESERVATION_EVIDENCE[RRK] == DomainEvidence(Availability.AVAILABLE, 0)
    assert RESERVATION_EVIDENCE[CST] == DomainEvidence(Availability.NOT_APPLICABLE)
    assert DomainEvidence(Availability.UNAVAILABLE).record_count is None
    with pytest.raises(ValueError, match="cannot imply"):
        DomainEvidence(Availability.NOT_CONFIGURED, 0)


def test_incompatible_inventory_units_are_not_aggregated() -> None:
    with pytest.raises(ValueError, match="EXPLICIT CONVERSION"):
        aggregate_inventory(INVENTORY)


def test_compatible_inventory_can_be_aggregated_deterministically() -> None:
    repeated = InventoryRecord(RRK, DAY, INVENTORY[0].source_product, Decimal("2"), "case",
                               "on_hand", INVENTORY[0].provenance, OYSTERS)
    assert aggregate_inventory((INVENTORY[0], repeated)) == (Decimal("8"), "case")


def test_invalid_negative_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="party size"):
        Reservation(RRK, DAY, datetime(2026, 8, 24, 18), -1, "booked", PROVENANCE)
    with pytest.raises(ValueError, match="labor hours"):
        LaborRecord(RRK, DAY, Decimal("-0.1"), PROVENANCE)
    with pytest.raises(ValueError, match="inventory quantity"):
        InventoryRecord(RRK, DAY, INVENTORY[0].source_product, Decimal("-1"), "each", "count", PROVENANCE)


def test_provenance_and_mapping_identifiers_are_required() -> None:
    with pytest.raises(ValueError, match="source system"):
        SourceIdentity("", "42")
    with pytest.raises(ValueError, match="source record ID"):
        Provenance("system", "location", "", "file")


def test_model_report_and_cli_are_deterministic(capsys) -> None:
    assert model_report() == model_report()
    assert "HUMAN MAPPING REQUIRED" in model_report()
    assert "NOT COMBINABLE WITHOUT EXPLICIT CONVERSION" in model_report()
    assert main(["model"]) == 0
    output = capsys.readouterr().out
    assert output == model_report() + "\n"
    assert "not adapter implementation reuse" in output
