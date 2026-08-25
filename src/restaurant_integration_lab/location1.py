"""Location #1's deliberately source-specific HarborTill JSON integration.

Nothing here is a generic adapter.  Chapter 4 must supply evidence before any
part of this implementation can be described as reused across locations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from importlib.resources import files
import json
from pathlib import Path
from typing import Any, Mapping

from .model_demo import LOCATION_MAPPINGS, OYSTERS, PRODUCT_MAPPINGS, RRK
from .operational_model import (
    BusinessDate, Product, ProductMapping, Provenance, Sale, SourceIdentity,
    resolve_location, resolve_product,
)

SOURCE_SYSTEM = "HarborTill RRK"
SOURCE_INTERFACE = "synthetic REST API JSON v3 fixture"
LOCATION_ONE_FIXTURE = files("restaurant_integration_lab").joinpath(
    "fixtures/location1_harbortill_sales.synthetic.json"
)
DAY_START = time(4)

STEAK = Product("JRH-P-002", "Bistro Steak", "food")
RUM_PUNCH = Product("JRH-P-003", "River Rum Punch", "beverage")
LOCATION_ONE_PRODUCT_MAPPINGS = PRODUCT_MAPPINGS + (
    ProductMapping(SourceIdentity(SOURCE_SYSTEM, "MENU-204"), STEAK),
    ProductMapping(SourceIdentity(SOURCE_SYSTEM, "MENU-910"), RUM_PUNCH),
)


class ExceptionCategory(StrEnum):
    MALFORMED_RECORD = "MALFORMED RECORD"
    UNKNOWN_LOCATION = "UNKNOWN LOCATION"
    UNKNOWN_PRODUCT = "UNKNOWN PRODUCT"
    DUPLICATE = "DUPLICATE"
    VALIDATION_FAILURE = "VALIDATION FAILURE"


@dataclass(frozen=True)
class IngestionException:
    source: str
    row_number: int
    source_record_id: str
    category: ExceptionCategory
    reason: str
    human_action_required: bool


@dataclass(frozen=True)
class IngestionEvent:
    event: str
    row_number: int | None
    detail: str


@dataclass(frozen=True)
class LocationOneSourceRecord:
    row_number: int
    transaction_id: str
    line_id: str
    transaction_timestamp: datetime
    supplied_business_date: date
    location_id: str
    item_id: str
    item_name: str
    quantity: Decimal
    gross_sales: Decimal
    discounts: Decimal
    net_sales: Decimal
    category: str

    @property
    def source_record_id(self) -> str:
        return f"{self.transaction_id}:{self.line_id}"


@dataclass(frozen=True)
class SalesMeasures:
    accepted_sale_lines: int
    total_quantity: Decimal
    gross_sales: Decimal
    discounts: Decimal
    net_sales: Decimal
    sales_by_product: tuple[tuple[str, Decimal], ...]
    sales_by_business_date: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class IngestionResult:
    rows_read: int
    sales: tuple[Sale, ...]
    exceptions: tuple[IngestionException, ...]
    events: tuple[IngestionEvent, ...]
    measures: SalesMeasures

    @property
    def duplicate_rows(self) -> int:
        return sum(item.category is ExceptionCategory.DUPLICATE for item in self.exceptions)

    @property
    def rejected_rows(self) -> int:
        return len(self.exceptions) - self.duplicate_rows


class LocationOneHarborTillJsonParser:
    """Parse the exact JSON v3 fixture shape discovered for RRK."""

    required_fields = (
        "transaction_id", "line_id", "transaction_timestamp", "business_date",
        "location_id", "item_id", "item_name", "quantity", "gross_sales",
        "discounts", "net_sales", "category",
    )

    def load(self, path: str | Path = LOCATION_ONE_FIXTURE) -> list[Mapping[str, Any]]:
        with Path(path).open(encoding="utf-8") as source:
            payload = json.load(source)
        if payload.get("fixture_notice") != "SYNTHETIC LAB DATA — NOT A REAL HARBORTILL EXPORT":
            raise ValueError("fixture must carry its synthetic-data notice")
        if payload.get("source_system") != SOURCE_SYSTEM or not isinstance(payload.get("records"), list):
            raise ValueError("unexpected Location #1 HarborTill JSON envelope")
        return payload["records"]

    def parse_row(self, row: Mapping[str, Any], row_number: int) -> LocationOneSourceRecord:
        missing = [field for field in self.required_fields if field not in row or str(row[field]).strip() == ""]
        if missing:
            raise ValueError(f"missing required field(s): {', '.join(missing)}")
        try:
            timestamp = datetime.fromisoformat(str(row["transaction_timestamp"]))
        except ValueError as error:
            raise ValueError("malformed transaction_timestamp") from error
        try:
            business_date = date.fromisoformat(str(row["business_date"]))
        except ValueError as error:
            raise ValueError("malformed business_date") from error
        try:
            quantity, gross, discounts, net = (
                Decimal(str(row[field])) for field in ("quantity", "gross_sales", "discounts", "net_sales")
            )
        except InvalidOperation as error:
            raise ValueError("malformed decimal value") from error
        if not all(value.is_finite() for value in (quantity, gross, discounts, net)):
            raise ValueError("non-finite decimal value")
        if quantity < 0 or gross < 0 or discounts < 0 or net < 0:
            raise ValueError("negative numeric value")
        if gross - discounts != net:
            raise ValueError("gross_sales - discounts must equal net_sales")
        return LocationOneSourceRecord(
            row_number, str(row["transaction_id"]), str(row["line_id"]), timestamp,
            business_date, str(row["location_id"]), str(row["item_id"]),
            str(row["item_name"]), quantity, gross, discounts, net, str(row["category"]),
        )


def calculate_sales(sales: tuple[Sale, ...]) -> SalesMeasures:
    """Calculate exact measures exclusively from accepted canonical records."""

    by_product: dict[str, Decimal] = {}
    by_date: dict[str, Decimal] = {}
    for sale in sales:
        assert sale.product is not None
        by_product[sale.product.canonical_id] = by_product.get(sale.product.canonical_id, Decimal("0")) + sale.net_amount
        day = str(sale.business_date)
        by_date[day] = by_date.get(day, Decimal("0")) + sale.net_amount
    return SalesMeasures(
        len(sales), sum((sale.quantity for sale in sales), Decimal("0")),
        sum((sale.gross_amount for sale in sales), Decimal("0")),
        sum((sale.discount_amount for sale in sales), Decimal("0")),
        sum((sale.net_amount for sale in sales), Decimal("0")),
        tuple(sorted(by_product.items())), tuple(sorted(by_date.items())),
    )


class LocationOneSalesImporter:
    """Normalize RRK records and retain accepted identities for in-memory idempotency."""

    def __init__(self) -> None:
        self.parser = LocationOneHarborTillJsonParser()
        self._accepted_source_ids: set[str] = set()

    def ingest(self, path: str | Path = LOCATION_ONE_FIXTURE) -> IngestionResult:
        rows = self.parser.load(path)
        sales: list[Sale] = []
        exceptions: list[IngestionException] = []
        events = [IngestionEvent("IMPORT_STARTED", None, f"rows={len(rows)}")]
        run_ids: set[str] = set()
        for row_number, row in enumerate(rows, start=1):
            raw_id = f"{row.get('transaction_id', '<missing>')}:{row.get('line_id', '<missing>')}"
            try:
                record = self.parser.parse_row(row, row_number)
            except (TypeError, ValueError) as error:
                exception = IngestionException(SOURCE_SYSTEM, row_number, raw_id,
                    ExceptionCategory.MALFORMED_RECORD, str(error), True)
                exceptions.append(exception)
                events.append(IngestionEvent("ROW_REJECTED", row_number, exception.category.value))
                continue
            if record.source_record_id in run_ids or record.source_record_id in self._accepted_source_ids:
                exception = IngestionException(SOURCE_SYSTEM, row_number, record.source_record_id,
                    ExceptionCategory.DUPLICATE, "source transaction_id + line_id already accepted", False)
                exceptions.append(exception)
                events.append(IngestionEvent("DUPLICATE_DETECTED", row_number, record.source_record_id))
                continue
            location = resolve_location(SOURCE_SYSTEM, record.location_id, LOCATION_MAPPINGS)
            if not location.resolved:
                exception = IngestionException(SOURCE_SYSTEM, row_number, record.source_record_id,
                    ExceptionCategory.UNKNOWN_LOCATION, location.reason or "unknown location", True)
                exceptions.append(exception)
                events.extend((IngestionEvent("UNKNOWN_MAPPING", row_number, "location"),
                               IngestionEvent("ROW_REJECTED", row_number, exception.category.value)))
                continue
            product = resolve_product(SOURCE_SYSTEM, record.item_id, LOCATION_ONE_PRODUCT_MAPPINGS)
            if not product.resolved:
                exception = IngestionException(SOURCE_SYSTEM, row_number, record.source_record_id,
                    ExceptionCategory.UNKNOWN_PRODUCT, product.reason or "unknown product", True)
                exceptions.append(exception)
                events.extend((IngestionEvent("UNKNOWN_MAPPING", row_number, "product"),
                               IngestionEvent("ROW_REJECTED", row_number, exception.category.value)))
                continue
            computed_day = BusinessDate.from_local_timestamp(record.transaction_timestamp, DAY_START)
            if computed_day.value != record.supplied_business_date:
                exception = IngestionException(SOURCE_SYSTEM, row_number, record.source_record_id,
                    ExceptionCategory.VALIDATION_FAILURE,
                    f"supplied business_date {record.supplied_business_date} conflicts with 04:00 cutoff {computed_day}", True)
                exceptions.append(exception)
                events.append(IngestionEvent("ROW_REJECTED", row_number, exception.category.value))
                continue
            sale = Sale(
                location.value, computed_day, SourceIdentity(SOURCE_SYSTEM, record.item_id),
                record.quantity, record.gross_sales, record.discounts, record.net_sales,
                Provenance(SOURCE_SYSTEM, record.location_id, record.source_record_id,
                           SOURCE_INTERFACE, f"synthetic fixture row {row_number}"),
                product.value, record.transaction_timestamp,
            )
            sales.append(sale)
            run_ids.add(record.source_record_id)
            self._accepted_source_ids.add(record.source_record_id)
            events.append(IngestionEvent("ROW_ACCEPTED", row_number, record.source_record_id))
        events.append(IngestionEvent("IMPORT_COMPLETED", None,
            f"accepted={len(sales)} rejected={len(exceptions) - sum(e.category is ExceptionCategory.DUPLICATE for e in exceptions)} duplicates={sum(e.category is ExceptionCategory.DUPLICATE for e in exceptions)}"))
        canonical = tuple(sales)
        return IngestionResult(len(rows), canonical, tuple(exceptions), tuple(events), calculate_sales(canonical))


def location1_report() -> str:
    result = LocationOneSalesImporter().ingest()
    lines = [
        "LOCATION #1 — POS INGESTION", "SYNTHETIC LAB DATA", "", "SOURCE",
        "HarborTill Cloud — RRK / REST API JSON v3",
        "Fixture: location1_harbortill_sales.synthetic.json",
        f"Location: {RRK.canonical_id} — {RRK.name}", "",
        f"ROWS READ: {result.rows_read}", f"ACCEPTED: {len(result.sales)}",
        f"REJECTED: {result.rejected_rows}", f"DUPLICATES: {result.duplicate_rows}", "",
        "CANONICAL SALES",
    ]
    lines.extend(
        f"{sale.provenance.source_record_id} | {sale.product.canonical_id} {sale.product.name} | business date {sale.business_date} | net ${sale.net_amount:.2f}"
        for sale in result.sales if sale.product is not None
    )
    lines.extend(["", "DETERMINISTIC CALCULATIONS",
        f"Sale lines: {result.measures.accepted_sale_lines}",
        f"Total quantity: {result.measures.total_quantity}",
        f"Gross sales: ${result.measures.gross_sales:.2f}",
        f"Discounts: ${result.measures.discounts:.2f}",
        f"Net sales: ${result.measures.net_sales:.2f}", "Sales by canonical product:"])
    lines.extend(f"  {key}: ${value:.2f}" for key, value in result.measures.sales_by_product)
    lines.append("Sales by business date:")
    lines.extend(f"  {key}: ${value:.2f}" for key, value in result.measures.sales_by_business_date)
    lines.extend(["", "EXCEPTIONS"])
    lines.extend(
        f"{item.category.value} | row {item.row_number} | {item.source_record_id} | human action: {'YES' if item.human_action_required else 'NO'} | {item.reason}"
        for item in result.exceptions
    )
    first = result.sales[0]
    lines.extend(["", "PROVENANCE CHECK",
        f"Canonical sale {first.provenance.source_record_id} <- {first.provenance.source_system} / {first.provenance.source_location_id} / {first.provenance.source_interface} / {first.provenance.reference}",
        "", "REUSE CANDIDATES — NOT DEMONSTRATED REUSE",
        "Canonical model; canonical calculations; explicit mapping mechanism; exception representation.",
        "", "OBSERVED LAB RESULTS",
        "OBSERVED LAB RESULT: Location #1 required explicit source-to-canonical product mappings.",
        "OBSERVED LAB RESULT: Malformed source values were isolated without discarding the complete import.",
        "OBSERVED LAB RESULT: Canonical calculations operated only on accepted normalized records.",
        "OBSERVED LAB RESULT: The first source integration required RRK HarborTill JSON-specific parsing logic."])
    return "\n".join(lines)
