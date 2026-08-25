"""Small synthetic fixtures that make the Chapter 2 boundary executable."""

from datetime import datetime, time
from decimal import Decimal

from .operational_model import (
    Availability, BusinessDate, DomainEvidence, InventoryRecord, Location,
    LocationMapping, Product, ProductMapping, Provenance, SourceIdentity,
    aggregate_inventory, resolve_product,
)

RRK = Location("JRH-001", "River & Rail Kitchen")
CST = Location("JRH-002", "Canal Street Tacos")
OYSTERS = Product("JRH-P-001", "James River Oysters", "food")

LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity("HarborTill RRK", "POS-WBG-14"), RRK),
    LocationMapping(SourceIdentity("ShiftHarbor", "WILLIAMSBURG_MAIN"), RRK),
    LocationMapping(SourceIdentity("StockPilot", "Store 014"), RRK),
    LocationMapping(SourceIdentity("HarborTill CST", "CST-02"), CST),
)
PRODUCT_MAPPINGS = (
    ProductMapping(SourceIdentity("HarborTill RRK", "MENU-771"), OYSTERS),
    ProductMapping(SourceIdentity("HarborTill CST", "ITEM-OYS"), OYSTERS),
    ProductMapping(SourceIdentity("StockPilot", "SKU-4401"), OYSTERS),
)

TIMESTAMP = datetime(2026, 8, 25, 0, 30)
PREVIOUS_BUSINESS_DATE = BusinessDate.from_local_timestamp(TIMESTAMP, time(4))
CALENDAR_BUSINESS_DATE = BusinessDate.from_local_timestamp(TIMESTAMP, time(0))
RESERVATION_EVIDENCE = {
    RRK: DomainEvidence(Availability.AVAILABLE, 0),
    CST: DomainEvidence(Availability.NOT_APPLICABLE),
}

_rrk_provenance = Provenance("StockPilot", "Store 014", "COUNT-1", "synthetic API fixture")
_cst_provenance = Provenance("CST Count Sheet", "CST", "ROW-8", "synthetic spreadsheet fixture")
INVENTORY = (
    InventoryRecord(RRK, PREVIOUS_BUSINESS_DATE, SourceIdentity("StockPilot", "SKU-4401"),
                    Decimal("6"), "case", "on_hand", _rrk_provenance, OYSTERS),
    InventoryRecord(CST, PREVIOUS_BUSINESS_DATE, SourceIdentity("CST Count Sheet", "Oysters"),
                    Decimal("144"), "each", "on_hand", _cst_provenance, OYSTERS),
)


def model_report() -> str:
    unknown = resolve_product("HarborTill BHO", "MIGRATED-UNKNOWN", PRODUCT_MAPPINGS)
    try:
        aggregate_inventory(INVENTORY)
    except ValueError as error:
        unit_status = str(error)
    lines = [
        "SHARED OPERATIONAL MODEL", "SYNTHETIC LAB EVIDENCE — NOT A SOURCE INTEGRATION", "",
        "CANONICAL LOCATIONS",
        "JRH-001 <- HarborTill RRK: POS-WBG-14; ShiftHarbor: WILLIAMSBURG_MAIN; StockPilot: Store 014",
        "JRH-002 <- HarborTill CST: CST-02", "",
        "PRODUCT IDENTITY", "Canonical product: JRH-P-001 — James River Oysters",
        "  HarborTill RRK: MENU-771", "  HarborTill CST: ITEM-OYS", "  StockPilot: SKU-4401", "",
        "UNRESOLVED MAPPINGS", f"Source product: {unknown.source.source_system} / {unknown.source.source_identifier}",
        f"Status: {unknown.reason}", "",
        "BUSINESS DATE", f"Timestamp: {TIMESTAMP.isoformat()}",
        f"04:00 operational-day start: {PREVIOUS_BUSINESS_DATE}",
        f"00:00 operational-day start: {CALENDAR_BUSINESS_DATE}", "",
        "DOMAIN AVAILABILITY", "JRH-001 Reservations: AVAILABLE (0 records)",
        "JRH-002 Reservations: NOT APPLICABLE (no count asserted)", "",
        "UNIT COMPATIBILITY", "JRH-001: 6 case", "JRH-002: 144 each", f"Status: {unit_status}", "",
        "PROVENANCE", "Inventory count COUNT-1 <- StockPilot / Store 014 / synthetic API fixture", "",
        "OBSERVED LAB RESULTS",
        "OBSERVED LAB RESULT: Canonical location identity requires explicit translation from source identifiers.",
        "OBSERVED LAB RESULT: A shared product concept does not imply a shared source product identifier.",
        "OBSERVED LAB RESULT: Missing reservation evidence cannot safely be represented as zero reservations.",
        "OBSERVED LAB RESULT: Inventory quantities cannot be aggregated across incompatible units without explicit conversion.",
        "Synthetic fixtures demonstrate canonical concepts, not adapter implementation reuse.", "",
        "MODEL PRINCIPLE", "Canonicalization preserves differences; it does not erase them.",
    ]
    return "\n".join(lines)
