"""Chapter 8 inventory evidence: explicit identity, units, time, and refusal boundaries."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

from .ingestion import ExceptionCategory, IngestionEvent, IngestionException
from .location1 import LocationOneSalesImporter
from .model_demo import CST, OYSTERS, RRK
from .operational_model import (
    BusinessDate, InventoryItem, InventoryRecord, Location, LocationMapping,
    Provenance, SourceIdentity, resolve_location,
)

STOCKPILOT_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/stockpilot_inventory.synthetic.json")
CST_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/cst_inventory.synthetic.csv")
PHYSICAL_COUNT = "PHYSICAL_COUNT"


class InventoryUnit(StrEnum):
    EACH = "EACH"
    CASE = "CASE"
    LB = "LB"
    OZ = "OZ"


class EvidenceStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    UNRESOLVED = "UNRESOLVED"


class ReconciliationStatus(StrEnum):
    RECONCILABLE = "RECONCILABLE"
    PARTIAL = "PARTIALLY RECONCILABLE"
    NOT_RECONCILABLE = "NOT RECONCILABLE WITH AVAILABLE EVIDENCE"


PATTY = InventoryItem("JRH-I-001", "Beef Patty 8 oz", "protein")
OYSTER_MEAT = InventoryItem(
    "JRH-I-002", "Shucked Oyster Meat", "seafood", OYSTERS,
    "Context-only menu association; not a recipe, portion, or usage relationship",
)
SAUCE = InventoryItem("JRH-I-003", "House Sauce", "sauce")

LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity("StockPilot", "Store 014"), RRK),
    LocationMapping(SourceIdentity("CST Weekly Count", "CST"), CST),
)
ITEM_MAPPINGS: tuple[tuple[SourceIdentity, InventoryItem], ...] = (
    (SourceIdentity("StockPilot", "BEEF-PATTY-8OZ"), PATTY),
    (SourceIdentity("StockPilot", "PATTY-CASE"), PATTY),
    (SourceIdentity("StockPilot", "OYSTER-MEAT"), OYSTER_MEAT),
    (SourceIdentity("CST Weekly Count", "Beef Patties"), PATTY),
    (SourceIdentity("CST Weekly Count", "Shucked Oyster Meat"), OYSTER_MEAT),
    # Deliberately conflicting free-text configuration.
    (SourceIdentity("CST Weekly Count", "Ambiguous Patty"), PATTY),
    (SourceIdentity("CST Weekly Count", "Ambiguous Patty"), SAUCE),
)
TARGET_UNITS = {PATTY.canonical_id: InventoryUnit.EACH, OYSTER_MEAT.canonical_id: InventoryUnit.OZ,
                SAUCE.canonical_id: InventoryUnit.EACH}
WEIGHT_CONVERSIONS = {(InventoryUnit.LB, InventoryUnit.OZ): Decimal("16"),
                      (InventoryUnit.OZ, InventoryUnit.LB): Decimal("0.0625")}


@dataclass(frozen=True)
class PackConversion:
    inventory_item_id: str
    from_unit: InventoryUnit
    to_unit: InventoryUnit
    factor: Decimal
    source_item_id: str


@dataclass(frozen=True)
class ParsedInventoryRow:
    record_id: str
    source_location_id: str
    source_item_id: str
    description: str
    quantity: Decimal
    unit_text: str | None
    count_date: date
    record_type: str
    category: str | None
    arrived_at: datetime


@dataclass(frozen=True)
class InventoryEvidence:
    record: InventoryRecord
    inventory_item: InventoryItem
    source_unit: InventoryUnit
    normalized_quantity: Decimal | None
    normalized_unit: InventoryUnit | None
    status: EvidenceStatus
    unresolved_reason: str | None = None


@dataclass(frozen=True)
class InventoryIngestionResult:
    rows_read: int
    evidence: tuple[InventoryEvidence, ...]
    exceptions: tuple[IngestionException, ...]
    events: tuple[IngestionEvent, ...]

    @property
    def normalized(self) -> tuple[InventoryEvidence, ...]:
        return tuple(row for row in self.evidence if row.status is EvidenceStatus.NORMALIZED)

    @property
    def unresolved(self) -> tuple[InventoryEvidence, ...]:
        return tuple(row for row in self.evidence if row.status is EvidenceStatus.UNRESOLVED)

    @property
    def duplicates(self) -> int:
        return sum(error.category is ExceptionCategory.DUPLICATE for error in self.exceptions)

    @property
    def unresolved_rows(self) -> int:
        categories = {ExceptionCategory.UNKNOWN_INVENTORY_ITEM, ExceptionCategory.UNKNOWN_UNIT,
                      ExceptionCategory.MISSING_CONVERSION, ExceptionCategory.CONFLICTING_MAPPING,
                      ExceptionCategory.INCOMPATIBLE_UNIT}
        return sum(error.category in categories for error in self.exceptions)

    @property
    def rejected(self) -> int:
        unresolved = {ExceptionCategory.UNKNOWN_INVENTORY_ITEM, ExceptionCategory.UNKNOWN_UNIT,
                      ExceptionCategory.MISSING_CONVERSION, ExceptionCategory.CONFLICTING_MAPPING,
                      ExceptionCategory.INCOMPATIBLE_UNIT}
        return sum(error.category not in unresolved and error.category is not ExceptionCategory.DUPLICATE
                   for error in self.exceptions)


@dataclass(frozen=True)
class ReconciliationAssessment:
    status: ReconciliationStatus
    reasons: tuple[str, ...]


class StockPilotParser:
    source_system = "StockPilot"
    source_interface = "synthetic nightly API JSON export"

    def read(self, path: str | Path = STOCKPILOT_FIXTURE) -> list[tuple[int, dict[str, Any], datetime]]:
        payload = json.loads(Path(path).read_text())
        if payload.get("synthetic_fixture") is not True:
            raise ValueError("inventory fixture must identify itself as synthetic")
        arrival = datetime.fromisoformat(payload["arrived_at"])
        return [(number, row, arrival) for number, row in enumerate(payload["records"], 1)]

    def parse(self, raw: dict[str, Any], arrived_at: datetime) -> ParsedInventoryRow:
        return _parse_common(raw, arrived_at, "record_id", "venue_id", "ingredient_id", "description",
                             "quantity", "unit", "count_date", "record_type", "category", "%Y-%m-%d")


class CSTSpreadsheetParser:
    source_system = "CST Weekly Count"
    source_interface = "synthetic manual spreadsheet CSV export"

    def read(self, path: str | Path = CST_FIXTURE) -> list[tuple[int, dict[str, Any], datetime]]:
        with Path(path).open(newline="") as handle:
            first = handle.readline().strip()
            if first != "# SYNTHETIC FIXTURE - CST Weekly Count spreadsheet export":
                raise ValueError("inventory fixture must identify itself as synthetic")
            rows = list(csv.DictReader(handle))
        output = []
        for number, row in enumerate(rows, 1):
            arrival = datetime.strptime(row["Exported At"], "%m/%d/%Y %H:%M")
            output.append((number, row, arrival))
        return output

    def parse(self, raw: dict[str, Any], arrived_at: datetime) -> ParsedInventoryRow:
        # There is deliberately no source-level default for a blank UOM.
        return _parse_common(raw, arrived_at, "Row ID", "Store", "Ingredient Name", "Ingredient Name",
                             "Qty", "UOM", "Count Date", "Record Type", "Category", "%m/%d/%Y")


def _parse_common(raw: dict[str, Any], arrived_at: datetime, record_key: str, location_key: str,
                  item_key: str, description_key: str, quantity_key: str, unit_key: str,
                  date_key: str, type_key: str, category_key: str, date_format: str) -> ParsedInventoryRow:
    required = (record_key, location_key, item_key, description_key, quantity_key, date_key, type_key)
    missing = [key for key in required if raw.get(key) in (None, "")]
    if missing:
        raise ValueError("missing required field(s): " + ", ".join(missing))
    try:
        quantity = Decimal(str(raw[quantity_key]))
        count_date = datetime.strptime(str(raw[date_key]), date_format).date()
    except (InvalidOperation, ValueError) as error:
        raise ValueError("malformed quantity or count date") from error
    if not quantity.is_finite():
        raise ValueError("quantity must be finite")
    if quantity < 0:
        raise ValueError("PHYSICAL_COUNT quantity cannot be negative")
    if raw[type_key] != PHYSICAL_COUNT:
        raise ValueError("unsupported record type; Chapter 8 accepts PHYSICAL_COUNT only")
    unit = None if raw.get(unit_key) in (None, "") else str(raw[unit_key]).strip().upper()
    return ParsedInventoryRow(str(raw[record_key]), str(raw[location_key]), str(raw[item_key]),
                              str(raw[description_key]), quantity, unit, count_date, str(raw[type_key]),
                              str(raw.get(category_key) or "") or None, arrived_at)


def resolve_inventory_item(source: SourceIdentity,
                           mappings: tuple[tuple[SourceIdentity, InventoryItem], ...] = ITEM_MAPPINGS
                           ) -> tuple[InventoryItem | None, ExceptionCategory | None, str | None]:
    matches = {item for identity, item in mappings if identity == source}
    if not matches:
        return None, ExceptionCategory.UNKNOWN_INVENTORY_ITEM, "explicit inventory-item mapping required"
    if len(matches) > 1:
        return None, ExceptionCategory.CONFLICTING_MAPPING, "source identity maps to multiple inventory items"
    return next(iter(matches)), None, None


def convert_quantity(quantity: Decimal, source_unit: InventoryUnit, target_unit: InventoryUnit,
                     item: InventoryItem, source_item_id: str,
                     pack_conversions: tuple[PackConversion, ...] = ()) -> tuple[Decimal | None, str | None]:
    if source_unit is target_unit:
        return quantity, None
    generic = WEIGHT_CONVERSIONS.get((source_unit, target_unit))
    if generic is not None:
        return quantity * generic, None
    conversion = next((rule for rule in pack_conversions
                       if rule.inventory_item_id == item.canonical_id
                       and rule.source_item_id == source_item_id
                       and rule.from_unit is source_unit and rule.to_unit is target_unit), None)
    if conversion:
        return quantity * conversion.factor, None
    if {source_unit, target_unit} <= {InventoryUnit.EACH, InventoryUnit.CASE}:
        return None, "MISSING PRODUCT-SPECIFIC PACK CONVERSION"
    return None, "INCOMPATIBLE UNIT DIMENSIONS"


class InventoryImporter:
    def __init__(self, pack_conversions: tuple[PackConversion, ...] = ()) -> None:
        self.pack_conversions = pack_conversions

    def ingest_source(self, parser: StockPilotParser | CSTSpreadsheetParser,
                      path: str | Path | None = None) -> InventoryIngestionResult:
        rows = parser.read(path) if path is not None else parser.read()
        evidence: list[InventoryEvidence] = []
        errors: list[IngestionException] = []
        events = [IngestionEvent("IMPORT_STARTED", None, f"source={parser.source_system} rows={len(rows)}")]
        seen: set[str] = set()
        for row_number, raw, arrived_at in rows:
            record_id = str(raw.get("record_id", raw.get("Row ID", "<unknown>")))
            try:
                parsed = parser.parse(raw, arrived_at)
            except (ValueError, TypeError) as error:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                ExceptionCategory.MALFORMED_RECORD, str(error)); continue
            if parsed.record_id in seen:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                ExceptionCategory.DUPLICATE, "source inventory record ID already seen", False); continue
            seen.add(parsed.record_id)
            location = resolve_location(parser.source_system, parsed.source_location_id, LOCATION_MAPPINGS)
            if not location.resolved:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                ExceptionCategory.UNKNOWN_LOCATION, location.reason or "unknown"); continue
            source_item = SourceIdentity(parser.source_system, parsed.source_item_id)
            item, category, reason = resolve_inventory_item(source_item)
            if item is None:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                category or ExceptionCategory.UNKNOWN_INVENTORY_ITEM, reason or "unresolved")
                continue
            provenance = Provenance(parser.source_system, parsed.source_location_id, parsed.record_id,
                                    parser.source_interface, "synthetic fixture")
            if parsed.unit_text is None:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                ExceptionCategory.UNKNOWN_UNIT, "unit missing; source contract defines no default")
                continue
            try:
                unit = InventoryUnit(parsed.unit_text)
            except ValueError:
                self._exception(errors, events, parser.source_system, row_number, record_id,
                                ExceptionCategory.UNKNOWN_UNIT, f"unknown unit: {parsed.unit_text}")
                continue
            record = InventoryRecord(location.value, BusinessDate(parsed.count_date), source_item,
                                     parsed.quantity, unit.value, parsed.record_type, provenance,
                                     None, item, parsed.arrived_at)
            target = TARGET_UNITS[item.canonical_id]
            quantity, unresolved = convert_quantity(parsed.quantity, unit, target, item,
                                                     parsed.source_item_id, self.pack_conversions)
            status = EvidenceStatus.UNRESOLVED if unresolved else EvidenceStatus.NORMALIZED
            evidence.append(InventoryEvidence(record, item, unit, quantity,
                                               None if unresolved else target, status, unresolved))
            if unresolved:
                category = (ExceptionCategory.MISSING_CONVERSION if "MISSING" in unresolved
                            else ExceptionCategory.INCOMPATIBLE_UNIT)
                self._exception(errors, events, parser.source_system, row_number, record_id, category, unresolved)
            else:
                events.append(IngestionEvent("ROW_ACCEPTED", row_number, record_id))
        events.append(IngestionEvent("IMPORT_COMPLETED", None,
                                     f"normalized={sum(e.status is EvidenceStatus.NORMALIZED for e in evidence)} unresolved={sum(e.status is EvidenceStatus.UNRESOLVED for e in evidence)}"))
        return InventoryIngestionResult(len(rows), tuple(evidence), tuple(errors), tuple(events))

    def ingest(self) -> InventoryIngestionResult:
        results = (self.ingest_source(StockPilotParser()), self.ingest_source(CSTSpreadsheetParser()))
        return InventoryIngestionResult(sum(r.rows_read for r in results),
                                        tuple(e for r in results for e in r.evidence),
                                        tuple(e for r in results for e in r.exceptions),
                                        tuple(e for r in results for e in r.events))

    @staticmethod
    def _exception(errors: list[IngestionException], events: list[IngestionEvent], source: str,
                   row: int, record: str, category: ExceptionCategory, reason: str, human: bool = True) -> None:
        errors.append(IngestionException(source, row, record, category, reason, human))
        events.append(IngestionEvent("DUPLICATE_DETECTED" if category is ExceptionCategory.DUPLICATE else "ROW_UNRESOLVED_OR_REJECTED", row, category.value))


def aggregate_normalized(evidence: Iterable[InventoryEvidence]) -> tuple[tuple[str, str, Decimal, InventoryUnit], ...]:
    totals: dict[tuple[str, str, InventoryUnit], Decimal] = {}
    for row in evidence:
        if row.status is not EvidenceStatus.NORMALIZED or row.normalized_quantity is None or row.normalized_unit is None:
            continue
        key = (row.record.location.canonical_id, row.inventory_item.canonical_id, row.normalized_unit)
        totals[key] = totals.get(key, Decimal()) + row.normalized_quantity
    return tuple((location, item, quantity, unit) for (location, item, unit), quantity in sorted(totals.items()))


def require_compatible_sum(evidence: Iterable[InventoryEvidence]) -> tuple[Decimal, InventoryUnit]:
    rows = tuple(evidence)
    if not rows or any(row.status is not EvidenceStatus.NORMALIZED for row in rows):
        raise ValueError("UNSAFE AGGREGATION: unresolved quantity or conversion")
    identities = {row.inventory_item.canonical_id for row in rows}
    units = {row.normalized_unit for row in rows}
    if len(identities) != 1 or len(units) != 1 or None in units:
        raise ValueError("UNSAFE AGGREGATION: incompatible item or unit")
    return sum((row.normalized_quantity or Decimal() for row in rows), Decimal()), next(iter(units))  # type: ignore[arg-type]


def reconciliation_assessment() -> ReconciliationAssessment:
    return ReconciliationAssessment(ReconciliationStatus.NOT_RECONCILABLE, (
        "no recipe or portion relationship", "beginning inventory absent", "receipts absent",
        "waste absent", "transfers absent",
    ))


EXPERIMENT_CONVERSION = PackConversion(PATTY.canonical_id, InventoryUnit.CASE,
                                       InventoryUnit.EACH, Decimal("40"), "PATTY-CASE")


def inventory_report() -> str:
    result = InventoryImporter().ingest()
    configured = InventoryImporter((EXPERIMENT_CONVERSION,)).ingest()
    before = next(row for row in result.evidence if row.record.source_product.source_identifier == "PATTY-CASE")
    after = next(row for row in configured.evidence if row.record.source_product.source_identifier == "PATTY-CASE")
    late = next(row for row in result.normalized if row.record.provenance.source_record_id == "SP-001")
    sales_units = sum((sale.quantity for sale in LocationOneSalesImporter().ingest().sales), Decimal())
    assessment = reconciliation_assessment()
    lines = ["INVENTORY INTEGRATION", "SYNTHETIC LAB EVIDENCE", "",
             "SOURCES", "StockPilot structured nightly JSON: RRK", "CST Weekly Count manual spreadsheet CSV: CST",
             "Existing sources remain authoritative; only PHYSICAL_COUNT evidence is in scope.", "",
             "ROWS READ", str(result.rows_read), "ACCEPTED", str(len(result.normalized)),
             "REJECTED", str(result.rejected), "UNRESOLVED", str(result.unresolved_rows),
             "DUPLICATES", str(result.duplicates), "",
             "PRODUCT / ITEM IDENTITY",
             "MENU PRODUCT JRH-P-001 James River Oysters != INVENTORY ITEM JRH-I-002 Shucked Oyster Meat",
             "Their context-only association is not a recipe, portion, or usage relationship.",
             "BEEF-PATTY-8OZ and spreadsheet name 'Beef Patties' -> JRH-I-001 Beef Patty 8 oz", "",
             "UNIT NORMALIZATION", "Supported: EACH, CASE, LB, OZ", "Missing and unknown units remain unresolved; EACH is never guessed.", "",
             "KNOWN CONVERSIONS", "Generic weight: 1 LB = 16 OZ", "Product-specific experiment: PATTY-CASE 1 CASE = 40 EACH", "",
             "UNSAFE CONVERSIONS", "CASE -> EACH has no universal factor.", "LB/OZ and EACH/CASE dimensions are not interchangeable.", "",
             "MAPPING-CHANGE EXPERIMENT", "BEFORE", "Inventory SKU: PATTY-CASE", "Unit: CASE",
             f"Status: {before.unresolved_reason}", "ADD CONFIGURATION", "1 CASE = 40 EACH for PATTY-CASE only",
             "Parser changes: NONE", "AFTER", f"Normalized quantity: {after.normalized_quantity} {after.normalized_unit.value}", "",
             "LATE DATA EXAMPLE", f"Effective count date: {late.record.business_date}",
             f"Evidence arrival: {late.record.evidence_arrived_at.isoformat()}",
             "Classification remains on effective count date, not arrival date.", "",
             "NORMALIZED INVENTORY EVIDENCE"]
    lines += [f"{loc} / {item}: {qty} {unit.value}" for loc, item, qty, unit in aggregate_normalized(result.normalized)]
    lines += ["", "EXCLUDED EVIDENCE"] + [f"{error.source} row {error.row_number}: {error.category.value} — {error.reason}" for error in result.exceptions]
    lines += ["", "SALES + INVENTORY CONTEXT", "Location: JRH-001", "Business/count date: 2026-08-24",
              f"POS sales evidence: {sales_units} menu-item units across accepted sale lines",
              "Inventory evidence: physical counts of distinct inventory items",
              "No direct usage reconciliation is implied.", "", "RECONCILIATION STATUS", assessment.status.value, "Reasons:"]
    lines += [f"- {reason}" for reason in assessment.reasons]
    lines += ["", "CANONICAL MODEL STRESS TEST", "Changed: YES",
              "Reason: InventoryItem now distinguishes counted stock from sellable Product; InventoryRecord preserves arrival time.", "",
              "CROSS-SYSTEM REUSE", "DEMONSTRATED CROSS-SYSTEM REUSE",
              "- canonical Location and BusinessDate", "- namespaced identity, Provenance, exceptions, and deterministic report structures",
              "CONFIGURATION REUSE", "- location and explicit inventory-item mappings", "- explicit product-specific pack conversion", "",
              "SYSTEM-SPECIFIC WORK", "- StockPilot JSON parser", "- CST spreadsheet CSV parser", "- unit and count-date semantics", "- conversion and safe aggregation logic", "",
              "REWORK", "- canonical InventoryRecord gained InventoryItem identity and evidence arrival time", "",
              "REJECTED REUSE CANDIDATE", "- canonical menu Product as a universal inventory identity", "- POS sales reconciliation formulas for physical counts", "",
              "OBSERVED LAB RESULTS",
              "OBSERVED LAB RESULT: Canonical location identity survived inventory integration unchanged.",
              "OBSERVED LAB RESULT: Inventory required explicit unit semantics that POS sales did not require.",
              "OBSERVED LAB RESULT: Case-to-each conversion required product-specific configuration.",
              "OBSERVED LAB RESULT: Late evidence retained its effective count date.",
              "OBSERVED LAB RESULT: Inventory evidence could not be reconciled safely to sales without additional operational evidence.",
              "OBSERVED LAB RESULT: Counted inventory items required a distinct identity from sellable menu products."]
    return "\n".join(lines)
