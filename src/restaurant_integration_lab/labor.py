"""Chapter 7 ShiftHarbor evidence and deterministic labor-versus-demand context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from importlib.resources import files
import json
from pathlib import Path
from typing import Any

from .ingestion import ExceptionCategory, IngestionEvent, IngestionException
from .location1 import LocationOneSalesImporter
from .location2 import LocationTwoSalesImporter
from .model_demo import CST, RRK
from .operational_model import BusinessDate, LaborRecord, LocationMapping, Provenance, SourceIdentity, resolve_location
from .reservations import TableCurrentImporter, calculate_reservation_measures

SOURCE_SYSTEM = "ShiftHarbor"
SOURCE_INTERFACE = "synthetic group labor API JSON response"
FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/shiftharbor_labor.synthetic.json")
DAY_START = time(4)
LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity(SOURCE_SYSTEM, "WILLIAMSBURG_MAIN"), RRK),
    LocationMapping(SourceIdentity(SOURCE_SYSTEM, "CST_RVA_02"), CST),
)
ROLE_MAPPINGS = {
    ("WILLIAMSBURG_MAIN", "SERV"): "FRONT_OF_HOUSE",
    ("WILLIAMSBURG_MAIN", "COOK"): "BACK_OF_HOUSE",
    ("WILLIAMSBURG_MAIN", "MGR"): "MANAGEMENT",
    ("CST_RVA_02", "SERVER"): "FRONT_OF_HOUSE",
    ("CST_RVA_02", "KITCHEN"): "BACK_OF_HOUSE",
}

@dataclass(frozen=True)
class LaborIngestionResult:
    rows_read: int
    records: tuple[LaborRecord, ...]
    exceptions: tuple[IngestionException, ...]
    events: tuple[IngestionEvent, ...]
    @property
    def duplicate_rows(self) -> int:
        return sum(e.category is ExceptionCategory.DUPLICATE for e in self.exceptions)
    @property
    def rejected_rows(self) -> int:
        return len(self.exceptions) - self.duplicate_rows

@dataclass(frozen=True)
class LaborMeasures:
    location_id: str
    business_date: BusinessDate
    worked_hours: Decimal
    scheduled_hours: Decimal
    labor_cost: Decimal | None
    labor_cost_complete: bool
    hours_by_role: tuple[tuple[str, Decimal], ...]

@dataclass(frozen=True)
class LaborDemandContext:
    location_id: str
    business_date: BusinessDate
    net_sales: Decimal
    worked_hours: Decimal
    sales_per_worked_hour: Decimal
    labor_cost: Decimal | None
    labor_cost_percent: Decimal | None
    completed_reservation_covers: int | None
    covers_per_worked_hour: Decimal | None

class ShiftHarborParser:
    required = ("shift_id", "location_id", "worker_id", "job_code", "clock_in", "clock_out", "scheduled_hours", "worked_hours", "status")
    def parse(self, raw: dict[str, Any]):
        missing = [k for k in self.required if raw.get(k) in (None, "")]
        if missing:
            raise ValueError("missing required field(s): " + ", ".join(missing))
        try:
            clock_in = datetime.fromisoformat(str(raw["clock_in"])); clock_out = datetime.fromisoformat(str(raw["clock_out"]))
            scheduled = Decimal(str(raw["scheduled_hours"])); worked = Decimal(str(raw["worked_hours"]))
            cost = None if raw.get("labor_cost") is None else Decimal(str(raw["labor_cost"]))
        except (ValueError, InvalidOperation) as error:
            raise ValueError("malformed timestamp, hours, or labor cost") from error
        if not scheduled.is_finite() or not worked.is_finite() or scheduled < 0 or worked < 0:
            raise ValueError("hours must be finite and nonnegative")
        if cost is not None and (not cost.is_finite() or cost < 0):
            raise ValueError("labor cost must be finite and nonnegative")
        if clock_out <= clock_in:
            raise ValueError("clock-out must follow clock-in; overnight timestamps require the following date")
        return str(raw["shift_id"]), str(raw["location_id"]), str(raw["job_code"]), clock_in, scheduled, worked, cost

class ShiftHarborImporter:
    def ingest(self, path: str | Path = FIXTURE) -> LaborIngestionResult:
        rows = json.loads(Path(path).read_text())["records"]
        records, errors = [], []
        events = [IngestionEvent("IMPORT_STARTED", None, f"rows={len(rows)}")]
        seen: set[str] = set(); parser = ShiftHarborParser()
        for number, raw in enumerate(rows, 1):
            source_id = str(raw.get("shift_id", "<unknown>"))
            try:
                shift, source_location, role_code, clock_in, scheduled, worked, cost = parser.parse(raw)
            except (ValueError, TypeError) as error:
                self._reject(errors, events, number, source_id, ExceptionCategory.MALFORMED_RECORD, str(error)); continue
            if shift in seen:
                self._reject(errors, events, number, shift, ExceptionCategory.DUPLICATE, "source shift ID already accepted", False); continue
            location = resolve_location(SOURCE_SYSTEM, source_location, LOCATION_MAPPINGS)
            if not location.resolved:
                self._reject(errors, events, number, shift, ExceptionCategory.UNKNOWN_LOCATION, location.reason or "unknown"); continue
            role = ROLE_MAPPINGS.get((source_location, role_code))
            if role is None:
                self._reject(errors, events, number, shift, ExceptionCategory.VALIDATION_FAILURE, "unknown role; explicit location/role mapping required"); continue
            seen.add(shift)
            records.append(LaborRecord(location.value, BusinessDate.from_local_timestamp(clock_in, DAY_START), worked,
                Provenance(SOURCE_SYSTEM, source_location, shift, SOURCE_INTERFACE, "synthetic fixture"), role, cost, scheduled))
            events.append(IngestionEvent("ROW_ACCEPTED", number, shift))
        events.append(IngestionEvent("IMPORT_COMPLETED", None, f"accepted={len(records)} rejected={len(errors)-sum(e.category is ExceptionCategory.DUPLICATE for e in errors)} duplicates={sum(e.category is ExceptionCategory.DUPLICATE for e in errors)}"))
        return LaborIngestionResult(len(rows), tuple(records), tuple(errors), tuple(events))
    @staticmethod
    def _reject(errors, events, row, record, category, reason, human=True):
        errors.append(IngestionException(SOURCE_SYSTEM, row, record, category, reason, human))
        events.append(IngestionEvent("DUPLICATE_DETECTED" if category is ExceptionCategory.DUPLICATE else "ROW_REJECTED", row, category.value))

def calculate_labor_measures(records: tuple[LaborRecord, ...]) -> tuple[LaborMeasures, ...]:
    groups: dict[tuple[str, BusinessDate], list[LaborRecord]] = {}
    for record in records: groups.setdefault((record.location.canonical_id, record.business_date), []).append(record)
    output = []
    for (location, day), items in sorted(groups.items(), key=lambda item: (item[0][0], str(item[0][1]))):
        roles: dict[str, Decimal] = {}
        for item in items: roles[item.role or "UNKNOWN"] = roles.get(item.role or "UNKNOWN", Decimal()) + item.hours
        complete = all(item.labor_cost is not None for item in items)
        output.append(LaborMeasures(location, day, sum((i.hours for i in items), Decimal()),
            sum((i.scheduled_hours or Decimal() for i in items), Decimal()),
            sum((i.labor_cost for i in items if i.labor_cost is not None), Decimal()) if complete else None,
            complete, tuple(sorted(roles.items()))))
    return tuple(output)

def labor_demand_context(result: LaborIngestionResult | None = None) -> tuple[LaborDemandContext, ...]:
    result = result or ShiftHarborImporter().ingest()
    labor = {(m.location_id, str(m.business_date)): m for m in calculate_labor_measures(result.records)}
    sales = (*LocationOneSalesImporter().ingest().sales, *LocationTwoSalesImporter().ingest().sales)
    totals: dict[tuple[str, str], Decimal] = {}
    for sale in sales:
        key = sale.location.canonical_id, str(sale.business_date); totals[key] = totals.get(key, Decimal()) + sale.net_amount
    reservations = {(m.location_id, str(m.business_date)): m.completed_covers for m in calculate_reservation_measures(TableCurrentImporter().ingest().reservations)}
    output = []
    for key, measure in labor.items():
        if key not in totals or measure.worked_hours == 0: continue
        sales_total = totals[key]; covers = reservations.get(key)
        output.append(LaborDemandContext(key[0], measure.business_date, sales_total, measure.worked_hours,
            sales_total / measure.worked_hours, measure.labor_cost,
            None if measure.labor_cost is None or sales_total == 0 else measure.labor_cost / sales_total * Decimal("100"),
            covers, None if covers is None else Decimal(covers) / measure.worked_hours))
    return tuple(sorted(output, key=lambda item: (item.location_id, str(item.business_date))))

REUSE_EVIDENCE = {
    "DEMONSTRATED CROSS-SYSTEM REUSE": ("canonical Location and BusinessDate align POS, reservations, and labor", "namespaced SourceIdentity resolution", "Provenance and inspectable exceptions"),
    "CONFIGURATION REUSE": ("location mapping mechanism with two ShiftHarbor IDs", "five explicit location-specific role mappings"),
    "SYSTEM-SPECIFIC WORK": ("ShiftHarbor JSON parsing", "worked versus scheduled semantics", "role and overnight-shift validation", "labor-versus-demand calculations"),
    "REWORK": ("LaborRecord extended to preserve scheduled hours separately from worked hours",),
    "REJECTED REUSE CANDIDATE": ("sales-shaped and reservation-shaped ingestion results do not represent labor evidence",),
}

def labor_report() -> str:
    result = ShiftHarborImporter().ingest(); measures = calculate_labor_measures(result.records); contexts = labor_demand_context(result)
    overnight = result.records[0]
    lines = ["LABOR INTEGRATION", "SYNTHETIC LAB EVIDENCE", "", "SOURCE", "ShiftHarbor group labor API synthetic JSON export; existing system remains authoritative", "", "ROWS READ", str(result.rows_read), "ACCEPTED", str(len(result.records)), "REJECTED", str(result.rejected_rows), "DUPLICATES", str(result.duplicate_rows), "", "LOCATION NORMALIZATION", "ShiftHarbor / WILLIAMSBURG_MAIN -> JRH-001", "ShiftHarbor / CST_RVA_02 -> JRH-002", "HarborTill identifiers remain separate namespaced evidence", "", "ROLE NORMALIZATION"]
    lines += [f"{loc} / {role} -> {canonical}" for (loc, role), canonical in ROLE_MAPPINGS.items()]
    lines += ["", "OVERNIGHT SHIFT EXAMPLE", "Clock in: 2026-08-24T18:00:00", "Clock out: 2026-08-25T01:30:00", f"Canonical business date: {overnight.business_date}", "Policy: assign the whole worked shift from clock-in using the established 04:00 operational-day cutoff; do not split it.", "", "LABOR EVIDENCE"]
    for m in measures:
        lines += [f"Location: {m.location_id}", f"Business date: {m.business_date}", f"Scheduled hours: {m.scheduled_hours}", f"Worked hours: {m.worked_hours}", f"Labor cost: {'Unavailable — evidence incomplete' if m.labor_cost is None else f'${m.labor_cost:.2f}'}", "Hours by canonical role: " + ", ".join(f"{r}={h}" for r,h in m.hours_by_role), ""]
    lines += ["LABOR-vs-DEMAND CONTEXT", "CROSS-LOCATION COMPARISON — differences are investigation signals, not staffing conclusions"]
    for c in contexts:
        lines += [c.location_id, f"Business date: {c.business_date}", f"Net sales: ${c.net_sales:.2f}", f"Worked labor hours: {c.worked_hours}", f"Sales / worked hour: ${c.sales_per_worked_hour:.2f}", f"Labor cost: {'Unavailable' if c.labor_cost is None else f'${c.labor_cost:.2f}'}", f"Labor cost % of sales: {'Unavailable — labor cost evidence incomplete' if c.labor_cost_percent is None else f'{c.labor_cost_percent:.2f}%'}", f"Completed reservation covers: {'Unavailable — reservation evidence not integrated/applicable' if c.completed_reservation_covers is None else c.completed_reservation_covers}", f"Completed covers / worked hour: {'Unavailable' if c.covers_per_worked_hour is None else f'{c.covers_per_worked_hour:.2f}'}", ""]
    lines += ["EVIDENCE LIMITS", "Ratios provide deterministic comparison context only; they do not prove overstaffing or understaffing.", "Reservation covers exclude walk-ins. Missing cost or reservation evidence never becomes zero."]
    for section, evidence in REUSE_EVIDENCE.items(): lines += ["", section] + [f"- {item}" for item in evidence]
    lines += ["", "EXCEPTIONS"] + [f"Row {e.row_number}: {e.category.value} — {e.reason}" for e in result.exceptions]
    lines += ["", "OBSERVED LAB RESULTS", "OBSERVED LAB RESULT: Canonical location and business date aligned sales, reservation, and labor evidence without shared source identifiers.", "OBSERVED LAB RESULT: Labor roles required explicit system/location mappings.", "OBSERVED LAB RESULT: An overnight shift remained on the clock-in operational business date.", "OBSERVED LAB RESULT: Missing labor cost prevented a labor-cost percentage from being calculated safely."]
    return "\n".join(lines)
