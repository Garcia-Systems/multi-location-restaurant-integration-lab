"""Location #2's explicit scheduled-CSV implementation and reuse experiment."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from pathlib import Path

from .ingestion import (
    ExceptionCategory, IngestionEvent, IngestionException, IngestionResult,
    calculate_sales,
)
from .location1 import LocationOneSalesImporter
from .model_demo import CST, OYSTERS
from .operational_model import (
    BusinessDate, Location, LocationMapping, Product, ProductMapping, Provenance,
    Sale, SourceIdentity, resolve_location, resolve_product,
)

SOURCE_SYSTEM = "HarborTill CST"
SOURCE_INTERFACE = "synthetic scheduled CSV export; MM/DD/YYYY"
LOCATION_TWO_FIXTURE = files("restaurant_integration_lab").joinpath(
    "fixtures/location2_harbortill_sales.synthetic.csv"
)
HORCHATA = Product("JRH-P-004", "Horchata", "beverage")
CHIPS = Product("JRH-P-005", "Chips", "food")
LOCATION_TWO_LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity(SOURCE_SYSTEM, "CST-02"), CST),
)
LOCATION_TWO_PRODUCT_MAPPINGS = (
    ProductMapping(SourceIdentity(SOURCE_SYSTEM, "ENTREE-044"), OYSTERS),
    ProductMapping(SourceIdentity(SOURCE_SYSTEM, "DRINK-010"), HORCHATA),
    ProductMapping(SourceIdentity(SOURCE_SYSTEM, "SIDE-003"), CHIPS),
)


@dataclass(frozen=True)
class LocationTwoSourceRecord:
    row_number: int
    store_code: str
    business_date: date
    timestamp: datetime
    ticket_line: str
    sku: str
    label: str
    department: str | None
    quantity: Decimal
    gross: Decimal
    signed_discount: Decimal
    net: Decimal
    voided: bool


class LocationTwoHarborTillCsvParser:
    """Parse CST's discovered CSV shape; it intentionally does not parse RRK JSON."""

    required = ("StoreCode", "SaleDate", "LocalTime", "TicketLine", "SKU",
                "MenuLabel", "Units", "Gross", "DiscountSigned", "Net", "IsVoided")

    def load(self, path: str | Path = LOCATION_TWO_FIXTURE) -> list[dict[str, str]]:
        with Path(path).open(encoding="utf-8", newline="") as source:
            notice = source.readline().strip()
            if notice != "# SYNTHETIC LAB DATA — NOT A REAL HARBORTILL EXPORT":
                raise ValueError("fixture must carry its synthetic-data notice")
            return list(csv.DictReader(source))

    def parse_row(self, row: dict[str, str], row_number: int) -> LocationTwoSourceRecord:
        missing = [field for field in self.required if not row.get(field, "").strip()]
        if missing:
            raise ValueError(f"missing required field(s): {', '.join(missing)}")
        try:
            day = datetime.strptime(row["SaleDate"], "%m/%d/%Y").date()
            timestamp = datetime.strptime(
                f"{row['SaleDate']} {row['LocalTime']}", "%m/%d/%Y %I:%M %p"
            )
        except ValueError as error:
            raise ValueError("malformed CST date or local time") from error
        try:
            quantity, gross, discount, net = (Decimal(row[key]) for key in
                ("Units", "Gross", "DiscountSigned", "Net"))
        except InvalidOperation as error:
            raise ValueError("malformed decimal value") from error
        if not all(value.is_finite() for value in (quantity, gross, discount, net)):
            raise ValueError("non-finite decimal value")
        if quantity < 0 or gross < 0 or discount > 0 or net < 0:
            raise ValueError("CST expects nonnegative sales and a nonpositive signed discount")
        if gross + discount != net:
            raise ValueError("Gross + DiscountSigned must equal Net")
        status = row["IsVoided"].upper()
        if status not in {"Y", "N"}:
            raise ValueError("IsVoided must be Y or N")
        return LocationTwoSourceRecord(
            row_number, row["StoreCode"], day, timestamp, row["TicketLine"],
            row["SKU"], row["MenuLabel"], row.get("Department") or None,
            quantity, gross, discount, net, status == "Y",
        )


class LocationTwoSalesImporter:
    def __init__(self) -> None:
        self.parser = LocationTwoHarborTillCsvParser()
        self._accepted_source_ids: set[str] = set()

    def ingest(self, path: str | Path = LOCATION_TWO_FIXTURE) -> IngestionResult:
        rows = self.parser.load(path)
        sales: list[Sale] = []
        exceptions: list[IngestionException] = []
        events = [IngestionEvent("IMPORT_STARTED", None, f"rows={len(rows)}")]
        run_ids: set[str] = set()
        for row_number, row in enumerate(rows, start=1):
            raw_id = row.get("TicketLine", "<missing>")
            try:
                record = self.parser.parse_row(row, row_number)
            except (TypeError, ValueError) as error:
                self._reject(exceptions, events, row_number, raw_id,
                             ExceptionCategory.MALFORMED_RECORD, str(error), True)
                continue
            if record.ticket_line in run_ids or record.ticket_line in self._accepted_source_ids:
                self._reject(exceptions, events, row_number, record.ticket_line,
                             ExceptionCategory.DUPLICATE, "TicketLine already accepted", False)
                continue
            if record.voided:
                self._reject(exceptions, events, row_number, record.ticket_line,
                             ExceptionCategory.VALIDATION_FAILURE, "voided CST line is not a sale", False)
                continue
            location = resolve_location(SOURCE_SYSTEM, record.store_code, LOCATION_TWO_LOCATION_MAPPINGS)
            if not location.resolved:
                self._reject(exceptions, events, row_number, record.ticket_line,
                             ExceptionCategory.UNKNOWN_LOCATION, location.reason or "unknown location", True)
                continue
            product = resolve_product(SOURCE_SYSTEM, record.sku, LOCATION_TWO_PRODUCT_MAPPINGS)
            if not product.resolved:
                self._reject(exceptions, events, row_number, record.ticket_line,
                             ExceptionCategory.UNKNOWN_PRODUCT, product.reason or "unknown product", True)
                continue
            sale = Sale(
                location.value, BusinessDate(record.business_date),
                SourceIdentity(SOURCE_SYSTEM, record.sku), record.quantity, record.gross,
                -record.signed_discount, record.net,
                Provenance(SOURCE_SYSTEM, record.store_code, record.ticket_line,
                           SOURCE_INTERFACE, f"synthetic fixture row {row_number}"),
                product.value, record.timestamp,
            )
            sales.append(sale)
            run_ids.add(record.ticket_line)
            self._accepted_source_ids.add(record.ticket_line)
            events.append(IngestionEvent("ROW_ACCEPTED", row_number, record.ticket_line))
        duplicate_count = sum(e.category is ExceptionCategory.DUPLICATE for e in exceptions)
        events.append(IngestionEvent("IMPORT_COMPLETED", None,
            f"accepted={len(sales)} rejected={len(exceptions)-duplicate_count} duplicates={duplicate_count}"))
        canonical = tuple(sales)
        return IngestionResult(len(rows), canonical, tuple(exceptions), tuple(events), calculate_sales(canonical))

    @staticmethod
    def _reject(exceptions: list[IngestionException], events: list[IngestionEvent],
                row: int, record_id: str, category: ExceptionCategory,
                reason: str, human: bool) -> None:
        exceptions.append(IngestionException(SOURCE_SYSTEM, row, record_id, category, reason, human))
        event = "DUPLICATE_DETECTED" if category is ExceptionCategory.DUPLICATE else "ROW_REJECTED"
        events.append(IngestionEvent(event, row, category.value))


REUSE_CLASSIFICATION = {
    "UNCHANGED REUSE": ("canonical Sale and provenance", "canonical calculation function",
                         "explicit mapping mechanism", "exception categories and result representation"),
    "CONFIGURATION DIFFERENCE": ("CST-02 to JRH-002 location mapping",
                                  "CST product mapping data"),
    "SOURCE-SPECIFIC DIFFERENCE": ("scheduled CSV loader", "US date and 12-hour time parser",
                                   "TicketLine identity", "signed-discount and Y/N status interpretation"),
    "LOCATION-SPECIFIC DIFFERENCE": ("source-provided CST business date is authoritative",),
    "BROKEN ASSUMPTION": ("POS-family exports share a schema", "discounts are nonnegative",
                          "business date is validated with RRK's 04:00 cutoff",
                          "record identity has transaction_id and line_id columns"),
}


def net_sales_by_location(sales: tuple[Sale, ...]) -> tuple[tuple[str, Decimal], ...]:
    totals: dict[str, Decimal] = {}
    for sale in sales:
        key = sale.location.canonical_id
        totals[key] = totals.get(key, Decimal("0")) + sale.net_amount
    return tuple(sorted(totals.items()))


def location2_report() -> str:
    one = LocationOneSalesImporter().ingest()
    two = LocationTwoSalesImporter().ingest()
    lines = ["LOCATION #2 — POS INGESTION", "SYNTHETIC LAB DATA", "",
             "SOURCE", "HarborTill Cloud — CST / scheduled CSV with US-style dates",
             "Fixture: location2_harbortill_sales.synthetic.csv",
             f"Location: {CST.canonical_id} — {CST.name}", "",
             f"ROWS READ: {two.rows_read}", f"ACCEPTED: {len(two.sales)}",
             f"REJECTED: {two.rejected_rows}", f"DUPLICATES: {two.duplicate_rows}", ""]
    headings = {"UNCHANGED REUSE": "REUSE EVIDENCE — UNCHANGED",
                "CONFIGURATION DIFFERENCE": "CONFIGURATION ONLY",
                "SOURCE-SPECIFIC DIFFERENCE": "NEW SOURCE-SPECIFIC CODE",
                "LOCATION-SPECIFIC DIFFERENCE": "LOCATION-SPECIFIC DIFFERENCES",
                "BROKEN ASSUMPTION": "BROKEN LOCATION #1 ASSUMPTIONS"}
    for category, values in REUSE_CLASSIFICATION.items():
        lines.append(headings[category])
        lines.extend(f"- {value}" for value in values)
        lines.append("")
    combined = net_sales_by_location(one.sales + two.sales)
    lines.extend(["LOCATION #1 CODE MODIFIED", "YES — shared outcomes and calculations were extracted only after both implementations existed.",
                  "", "CANONICAL MODEL MODIFIED", "NO — CST normalized into the existing Sale and BusinessDate types.", "",
                  "TWO-LOCATION CANONICAL CALCULATION",
                  f"Location #1 net sales: ${one.measures.net_sales:.2f}",
                  f"Location #2 net sales: ${two.measures.net_sales:.2f}"])
    lines.extend(f"{key}: ${value:.2f}" for key, value in combined)
    lines.extend(["", "OBSERVED LAB RESULTS",
        "OBSERVED LAB RESULT: Canonical sales calculations operated unchanged across two source formats.",
        "OBSERVED LAB RESULT: Mapping behavior was reused with location-specific mapping data.",
        "OBSERVED LAB RESULT: The Location #1 JSON parser was a rejected reuse candidate for CST CSV.",
        "OBSERVED LAB RESULT: Canonical representation enabled a calculation spanning both locations."])
    return "\n".join(lines)
