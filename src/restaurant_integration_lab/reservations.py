"""Chapter 6 TableCurrent evidence ingestion and deterministic demand context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from enum import StrEnum
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from .ingestion import ExceptionCategory, IngestionEvent, IngestionException
from .location1 import LocationOneSalesImporter
from .model_demo import CST, RRK
from .operational_model import (Availability, BusinessDate, DomainEvidence, Location,
    LocationMapping, Provenance, Reservation, SourceIdentity, resolve_location)

SOURCE_SYSTEM = "TableCurrent"
SOURCE_INTERFACE = "synthetic REST API JSON response"
FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/tablecurrent_reservations.synthetic.json")
DAY_START = time(4)
BHO = Location("JRH-003", "Blue Heron Oyster House")
MBC = Location("JRH-004", "Manchester Bake & Coffee")
JRS = Location("JRH-005", "James River Smokehouse")
LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity(SOURCE_SYSTEM, "14"), RRK),
    LocationMapping(SourceIdentity(SOURCE_SYSTEM, "BHO-RVA"), BHO),
)

class ReservationStatus(StrEnum):
    BOOKED = "BOOKED"
    SEATED = "SEATED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    NO_SHOW = "NO SHOW"

STATUS_MAPPINGS = {
    "confirmed": ReservationStatus.BOOKED,
    "seated": ReservationStatus.SEATED,
    "finished": ReservationStatus.COMPLETED,
    "cancelled_by_guest": ReservationStatus.CANCELED,
    "did_not_arrive": ReservationStatus.NO_SHOW,
}

@dataclass(frozen=True)
class ReservationIngestionResult:
    rows_read: int
    reservations: tuple[Reservation, ...]
    exceptions: tuple[IngestionException, ...]
    events: tuple[IngestionEvent, ...]
    @property
    def duplicate_rows(self) -> int:
        return sum(e.category is ExceptionCategory.DUPLICATE for e in self.exceptions)
    @property
    def rejected_rows(self) -> int:
        return len(self.exceptions) - self.duplicate_rows

@dataclass(frozen=True)
class ReservationMeasures:
    location_id: str
    business_date: BusinessDate
    reservation_count: int
    booked_covers: int
    completed_covers: int
    canceled_covers: int
    no_show_covers: int
    average_party_size: Decimal
    demand_label: str = "RESERVATION DEMAND CONTEXT — NOT TOTAL RESTAURANT COVERS"

@dataclass(frozen=True)
class SalesReservationContext:
    location_id: str
    business_date: BusinessDate
    net_sales: Decimal
    reservation: ReservationMeasures

@dataclass(frozen=True)
class ReuseEvidence:
    demonstrated_cross_system_reuse: tuple[str, ...]
    domain_specific_reuse: tuple[str, ...]
    configuration_reuse: tuple[str, ...]
    new_system_specific_work: tuple[str, ...]
    rework: tuple[str, ...]

REUSE_EVIDENCE = ReuseEvidence(
    ("canonical Location and BusinessDate", "SourceIdentity resolution", "Provenance", "IngestionException and IngestionEvent"),
    ("POS sales calculations and POS parsers",),
    ("explicit namespaced location-mapping mechanism with TableCurrent venue mappings",),
    ("TableCurrent JSON parser", "reservation status translation", "party-size validation", "reservation demand measures"),
    ("generic IngestionResult was retained as Sales-specific; a ReservationIngestionResult was added rather than forcing reservations into sales semantics",),
)

EVIDENCE_AVAILABILITY = {
    RRK: DomainEvidence(Availability.AVAILABLE, 3),
    CST: DomainEvidence(Availability.NOT_APPLICABLE),
    BHO: DomainEvidence(Availability.AVAILABLE, 2),
    MBC: DomainEvidence(Availability.NOT_CONFIGURED), # BakeAhead is not table reservations.
    JRS: DomainEvidence(Availability.UNAVAILABLE),
}

class TableCurrentParser:
    required = ("booking_id", "venue_id", "reserved_at", "party_size", "state")
    def parse(self, raw: dict[str, Any]) -> tuple[str, str, datetime, int, ReservationStatus]:
        missing = [key for key in self.required if key not in raw or raw[key] in (None, "")]
        if missing:
            raise ValueError("missing required field(s): " + ", ".join(missing))
        try:
            timestamp = datetime.fromisoformat(str(raw["reserved_at"]))
        except ValueError as error:
            raise ValueError("malformed reservation timestamp") from error
        try:
            party_size = int(str(raw["party_size"]))
        except ValueError as error:
            raise ValueError("malformed party size") from error
        if party_size <= 0:
            raise ValueError("party size must be positive")
        status = STATUS_MAPPINGS.get(str(raw["state"]))
        if status is None:
            raise LookupError(f"unknown reservation status: {raw['state']}")
        return str(raw["booking_id"]), str(raw["venue_id"]), timestamp, party_size, status

class TableCurrentImporter:
    def ingest(self, path: str | Path = FIXTURE) -> ReservationIngestionResult:
        payload = json.loads(Path(path).read_text())
        rows = payload["records"]
        accepted: list[Reservation] = []
        exceptions: list[IngestionException] = []
        events = [IngestionEvent("IMPORT_STARTED", None, f"rows={len(rows)}")]
        seen: set[tuple[str, str]] = set()
        parser = TableCurrentParser()
        for number, raw in enumerate(rows, 1):
            record_id = str(raw.get("booking_id", "<unknown>"))
            try:
                booking, venue, timestamp, party, status = parser.parse(raw)
            except LookupError as error:
                self._reject(exceptions, events, number, record_id, ExceptionCategory.UNKNOWN_STATUS, str(error), True); continue
            except (ValueError, TypeError) as error:
                self._reject(exceptions, events, number, record_id, ExceptionCategory.MALFORMED_RECORD, str(error), True); continue
            identity = (venue, booking) # booking IDs are venue-local by discovered contract.
            if identity in seen:
                self._reject(exceptions, events, number, booking, ExceptionCategory.DUPLICATE, "venue_id + booking_id already accepted", False); continue
            location = resolve_location(SOURCE_SYSTEM, venue, LOCATION_MAPPINGS)
            if not location.resolved:
                self._reject(exceptions, events, number, booking, ExceptionCategory.UNKNOWN_LOCATION, location.reason or "unknown", True); continue
            seen.add(identity)
            accepted.append(Reservation(location.value, BusinessDate.from_local_timestamp(timestamp, DAY_START),
                timestamp, party, status.value, Provenance(SOURCE_SYSTEM, venue, booking, SOURCE_INTERFACE, "synthetic fixture")))
            events.append(IngestionEvent("ROW_ACCEPTED", number, booking))
        events.append(IngestionEvent("IMPORT_COMPLETED", None, f"accepted={len(accepted)} rejected={len(exceptions)-sum(e.category is ExceptionCategory.DUPLICATE for e in exceptions)} duplicates={sum(e.category is ExceptionCategory.DUPLICATE for e in exceptions)}"))
        return ReservationIngestionResult(len(rows), tuple(accepted), tuple(exceptions), tuple(events))
    @staticmethod
    def _reject(errors, events, row, record, category, reason, human):
        errors.append(IngestionException(SOURCE_SYSTEM, row, record, category, reason, human))
        events.append(IngestionEvent("DUPLICATE_DETECTED" if category is ExceptionCategory.DUPLICATE else "ROW_REJECTED", row, category.value))

def calculate_reservation_measures(records: tuple[Reservation, ...]) -> tuple[ReservationMeasures, ...]:
    groups: dict[tuple[str, BusinessDate], list[Reservation]] = {}
    for record in records:
        groups.setdefault((record.location.canonical_id, record.business_date), []).append(record)
    output = []
    for (location, day), items in sorted(groups.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        covers = lambda statuses: sum(r.party_size for r in items if r.status in statuses)
        output.append(ReservationMeasures(location, day, len(items), covers({"BOOKED"}),
            covers({"SEATED", "COMPLETED"}), covers({"CANCELED"}), covers({"NO SHOW"}),
            Decimal(sum(r.party_size for r in items)) / Decimal(len(items))))
    return tuple(output)

def sales_context(result: ReservationIngestionResult | None = None) -> tuple[SalesReservationContext, ...]:
    result = result or TableCurrentImporter().ingest()
    measures = {(m.location_id, str(m.business_date)): m for m in calculate_reservation_measures(result.reservations)}
    sales = LocationOneSalesImporter().ingest().sales
    totals: dict[tuple[str, str], Decimal] = {}
    for sale in sales:
        key = (sale.location.canonical_id, str(sale.business_date)); totals[key] = totals.get(key, Decimal()) + sale.net_amount
    return tuple(SalesReservationContext(k[0], m.business_date, totals[k], m) for k, m in measures.items() if k in totals)

def reservations_report() -> str:
    result = TableCurrentImporter().ingest(); measures = calculate_reservation_measures(result.reservations)
    lines = ["RESERVATIONS + DEMAND CONTEXT", "SYNTHETIC LAB EVIDENCE", "", "RESERVATION SOURCES",
        "TableCurrent synthetic REST API JSON: RRK and BHO only", "BakeAhead preorders and JRS events are not treated as table reservations", "", "INGESTION",
        f"Rows read: {result.rows_read}", f"Accepted: {len(result.reservations)}", f"Rejected: {result.rejected_rows}", f"Duplicates: {result.duplicate_rows}", "",
        "LOCATION IDENTITY", "TableCurrent / 14 -> JRH-001", "HarborTill RRK / POS-WBG-14 -> JRH-001", "Same canonical location; different namespaced identifiers", "TableCurrent / BHO-RVA -> JRH-003", "",
        "RESERVATION STATUS NORMALIZATION"]
    lines += [f"{source} -> {target.value}" for source, target in STATUS_MAPPINGS.items()]
    lines += ["", "RESERVATION DEMAND CONTEXT"]
    for m in measures:
        lines += [f"Location: {m.location_id}", f"Business date: {m.business_date}", f"Reservation count: {m.reservation_count}", f"Booked covers: {m.booked_covers}", f"Completed/seated covers: {m.completed_covers}", f"Canceled covers: {m.canceled_covers}", f"No-show covers: {m.no_show_covers}", f"Average party size: {m.average_party_size:.2f}", m.demand_label, ""]
    lines += ["SALES CONTEXT"]
    for c in sales_context(result): lines += [f"Location: {c.location_id}", f"Business date: {c.business_date}", f"Net sales: ${c.net_sales:.2f}", f"Completed reservation covers: {c.reservation.completed_covers}", "Reservation evidence is context, not a causal explanation or total demand."]
    lines += ["", "EVIDENCE AVAILABILITY"]
    for loc, ev in EVIDENCE_AVAILABILITY.items(): lines.append(f"{loc.canonical_id} Sales: AVAILABLE; Reservations: {'NOT INTEGRATED' if ev.availability is Availability.NOT_CONFIGURED else ev.availability.value}" + (f" ({ev.record_count} accepted records)" if ev.record_count is not None else " (no zero implied)"))
    lines += ["", "CROSS-SYSTEM REUSE", "DEMONSTRATED"] + [f"- {x}" for x in REUSE_EVIDENCE.demonstrated_cross_system_reuse]
    lines += ["DOMAIN-SPECIFIC"] + [f"- {x}" for x in REUSE_EVIDENCE.domain_specific_reuse] + ["CONFIGURATION"] + [f"- {x}" for x in REUSE_EVIDENCE.configuration_reuse] + ["SYSTEM-SPECIFIC"] + [f"- {x}" for x in REUSE_EVIDENCE.new_system_specific_work] + ["REWORK"] + [f"- {x}" for x in REUSE_EVIDENCE.rework]
    lines += ["", "EXCEPTIONS"] + [f"Row {e.row_number}: {e.category.value} — {e.reason}" for e in result.exceptions]
    lines += ["", "OBSERVED LAB RESULTS", "OBSERVED LAB RESULT: Namespaced canonical location mappings aligned different POS and reservation identifiers.", "OBSERVED LAB RESULT: A 01:00 reservation aligned to the prior 04:00-start business date.", "OBSERVED LAB RESULT: Reservation status and party-size semantics required system-specific work.", "OBSERVED LAB RESULT: Reservation evidence supplied demand context without being labeled total restaurant demand."]
    return "\n".join(lines)
