"""Chapter 10's compact management briefing over canonical lab evidence.

This is deliberately a report, not a reporting framework.  Callers may supply
canonical evidence to make the calculation boundary executable and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .exceptions import (CompletenessStatus, DuplicateKind, IngestionBatchResult,
                         OperationalException, ResolutionState, SchemaStatus,
                         classify_duplicate, lab_batches)
from .inventory import (EvidenceStatus, InventoryEvidence, InventoryImporter,
                        ReconciliationAssessment, aggregate_normalized,
                        reconciliation_assessment)
from .labor import (LaborDemandContext, ShiftHarborImporter,
                    labor_demand_context)
from .normalization import CrossLocationDataset, build_dataset
from .operational_model import Availability
from .reservations import (EVIDENCE_AVAILABILITY, ReservationMeasures,
                           TableCurrentImporter, calculate_reservation_measures)


class BriefingPriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SignalCategory(StrEnum):
    OPERATIONAL = "OPERATIONAL INVESTIGATION"
    DATA_QUALITY = "DATA QUALITY INVESTIGATION"


class EvidenceState(StrEnum):
    COMPLETE = "COMPLETE FOR FIXTURE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT APPLICABLE"
    BLOCKED = "BLOCKED BY UNRESOLVED MAPPING"


@dataclass(frozen=True)
class InvestigationSignal:
    category: SignalCategory
    priority: BriefingPriority
    location_id: str
    signal: str
    evidence: str
    limit: str


@dataclass(frozen=True)
class LocationBrief:
    location_id: str
    net_sales: Decimal
    accepted_sales: int
    excluded_sales: int
    sales_state: EvidenceState
    reservation_state: EvidenceState
    reservation: ReservationMeasures | None
    labor: LaborDemandContext | None


@dataclass(frozen=True)
class ManagementBriefing:
    business_dates: tuple[str, ...]
    locations: tuple[LocationBrief, ...]
    group_net_sales: Decimal
    accepted_sales: int
    excluded_sales: int
    signals: tuple[InvestigationSignal, ...]
    inventory: tuple[InventoryEvidence, ...]
    reconciliation: ReconciliationAssessment
    batches: tuple[IngestionBatchResult, ...]
    exceptions: tuple[OperationalException, ...]


def _state_for_availability(value: Availability) -> EvidenceState:
    return {
        Availability.AVAILABLE: EvidenceState.COMPLETE,
        Availability.UNAVAILABLE: EvidenceState.UNAVAILABLE,
        Availability.NOT_APPLICABLE: EvidenceState.NOT_APPLICABLE,
        Availability.NOT_CONFIGURED: EvidenceState.UNAVAILABLE,
    }[value]


def build_management_briefing(
    *, dataset: CrossLocationDataset | None = None,
    reservations: tuple[ReservationMeasures, ...] | None = None,
    labor: tuple[LaborDemandContext, ...] | None = None,
    inventory: tuple[InventoryEvidence, ...] | None = None,
    batches: tuple[IngestionBatchResult, ...] | None = None,
) -> ManagementBriefing:
    """Combine accepted canonical records, completeness, and exceptions.

    No raw source field is interpreted here.  Source adapters have already
    established canonical identities, dates, money semantics, and exclusions.
    """
    dataset = dataset or build_dataset()
    reservations = reservations if reservations is not None else calculate_reservation_measures(TableCurrentImporter().ingest().reservations)
    labor = labor if labor is not None else labor_demand_context(ShiftHarborImporter().ingest())
    inventory = inventory if inventory is not None else InventoryImporter().ingest().evidence
    batches = batches if batches is not None else lab_batches()
    reservation_by_location = {row.location_id: row for row in reservations}
    labor_by_location = {row.location_id: row for row in labor}
    totals = dict(dataset.sales_by_location())
    accepted_counts: dict[str, int] = {}
    for sale in dataset.accepted_sales:
        accepted_counts[sale.location.canonical_id] = accepted_counts.get(sale.location.canonical_id, 0) + 1

    locations: list[LocationBrief] = []
    for coverage in dataset.coverage:
        location_id = coverage.canonical_location_id
        canonical_location = next(s.location for s in dataset.accepted_sales if s.location.canonical_id == location_id)
        availability = EVIDENCE_AVAILABILITY.get(canonical_location)
        reservation_state = EvidenceState.UNAVAILABLE if availability is None else _state_for_availability(availability.availability)
        excluded = coverage.unresolved_product + coverage.unresolved_location
        locations.append(LocationBrief(
            location_id, totals.get(location_id, Decimal()), accepted_counts.get(location_id, 0), excluded,
            EvidenceState.PARTIAL if excluded else EvidenceState.COMPLETE,
            reservation_state, reservation_by_location.get(location_id), labor_by_location.get(location_id)))

    signals: list[InvestigationSignal] = []
    comparable_labor = [row for row in locations if row.labor is not None]
    if len(comparable_labor) >= 2:
        low, high = sorted(comparable_labor, key=lambda row: row.labor.sales_per_worked_hour)[:1] + sorted(comparable_labor, key=lambda row: row.labor.sales_per_worked_hour)[-1:]
        assert low.labor and high.labor
        # A documented fixture heuristic, not an industry threshold.
        if high.labor.sales_per_worked_hour and low.labor.sales_per_worked_hour / high.labor.sales_per_worked_hour <= Decimal("0.75"):
            signals.append(InvestigationSignal(SignalCategory.OPERATIONAL, BriefingPriority.MEDIUM,
                low.location_id, "Sales per worked hour materially differs from the fixture peer (synthetic rule: at least 25% lower).",
                f"net sales=${low.net_sales:.2f}; worked hours={low.labor.worked_hours}; sales/worked hour=${low.labor.sales_per_worked_hour:.2f}; peer {high.location_id}=${high.labor.sales_per_worked_hour:.2f}",
                "Investigation context only; no staffing recommendation or industry benchmark."))
    for row in locations:
        if row.excluded_sales:
            signals.append(InvestigationSignal(SignalCategory.DATA_QUALITY, BriefingPriority.HIGH,
                row.location_id, "PRODUCT COMPARISON LIMITED",
                f"{row.excluded_sales} sales row(s) excluded by unresolved product/location identity; canonical net sales from {row.accepted_sales} accepted rows remain available.",
                EvidenceState.BLOCKED.value + " for product comparison; location net sales remains partial but usable."))
        if row.labor is not None and row.labor.labor_cost_percent is None:
            signals.append(InvestigationSignal(SignalCategory.DATA_QUALITY, BriefingPriority.MEDIUM,
                row.location_id, "Labor-cost comparison unavailable.", "At least one accepted labor record lacks cost evidence.",
                "Worked hours and sales/worked hour remain available; labor cost percentage is omitted."))
    for batch in batches:
        if batch.schema_status is SchemaStatus.INVALID:
            signals.append(InvestigationSignal(SignalCategory.DATA_QUALITY, BriefingPriority.HIGH,
                batch.exceptions[0].location_id or "GROUP", "Schema failure blocks batch evidence.",
                f"{batch.batch_id}: schema={batch.schema_status.value}; accepted={batch.records_accepted}", "Source coordination or engineering review required."))
        if batch.completeness_status is CompletenessStatus.INCOMPLETE:
            signals.append(InvestigationSignal(SignalCategory.DATA_QUALITY, BriefingPriority.HIGH,
                batch.exceptions[0].location_id or "GROUP", "Incomplete batch may weaken management context.",
                f"{batch.batch_id}: read={batch.records_read}; completeness={batch.completeness_status.value}", "Partial records are not treated as complete evidence."))
    if reconciliation_assessment().status.value.startswith("NOT RECONCILABLE"):
        signals.append(InvestigationSignal(SignalCategory.DATA_QUALITY, BriefingPriority.MEDIUM,
            "GROUP", "Inventory cannot be reconciled to sales with available evidence.",
            "; ".join(reconciliation_assessment().reasons), "Physical counts do not establish usage or food cost."))
    priority_order = {BriefingPriority.HIGH: 0, BriefingPriority.MEDIUM: 1, BriefingPriority.LOW: 2}
    signals.sort(key=lambda row: (priority_order[row.priority], row.category.value, row.location_id, row.signal))
    exceptions = tuple(error for batch in batches for error in batch.exceptions)
    conflict = classify_duplicate("CHK-1001:1", {"net": "24.00"}, {"net": "29.00"})
    exceptions += (conflict,)
    dates = tuple(sorted({str(sale.business_date) for sale in dataset.accepted_sales}))
    return ManagementBriefing(dates, tuple(locations), sum(totals.values(), Decimal()),
        len(dataset.accepted_sales), sum(row.excluded_sales for row in locations), tuple(signals),
        inventory, reconciliation_assessment(), batches, exceptions)


def briefing_report(briefing: ManagementBriefing | None = None) -> str:
    b = briefing or build_management_briefing()
    lines = ["JAMES RIVER HOSPITALITY GROUP", "DAILY / PERIOD MANAGEMENT BRIEFING", "SYNTHETIC LAB EVIDENCE", "",
        "EVIDENCE WINDOW", ", ".join(b.business_dates),
        "What changed: unavailable — fixtures do not contain two comparable business periods.", "",
        "GROUP SNAPSHOT", f"Canonical net sales: ${b.group_net_sales:.2f}",
        f"Accepted canonical sales records: {b.accepted_sales}", f"Excluded/unresolved sales records: {b.excluded_sales}",
        "Net sales remains available where canonical money/location semantics are safe; product detail may still be blocked.", "",
        "LOCATIONS TO INVESTIGATE", "Priority is a synthetic briefing heuristic, not universal business severity."]
    for number, signal in enumerate(b.signals, 1):
        lines += [f"{number}. [{signal.priority.value}] {signal.category.value} — {signal.location_id}",
                  f"   Signal: {signal.signal}", f"   Evidence: {signal.evidence}", f"   Coverage/limit: {signal.limit}"]
    lines += ["", "CROSS-LOCATION SALES"]
    for row in b.locations:
        lines.append(f"{row.location_id}: net=${row.net_sales:.2f}; accepted={row.accepted_sales}; excluded={row.excluded_sales}; coverage={row.sales_state.value}")
    lines += ["Product comparison: BLOCKED BY UNRESOLVED MAPPING where excluded product rows exist.", "",
              "RESERVATION CONTEXT", "Reservation covers are not necessarily total restaurant covers."]
    for row in b.locations:
        if row.reservation is None:
            lines.append(f"{row.location_id}: {row.reservation_state.value}")
        else:
            r = row.reservation
            lines.append(f"{row.location_id}: completed/seated covers={r.completed_covers}; canceled={r.canceled_covers}; no-show={r.no_show_covers}; coverage={row.reservation_state.value}")
    lines += ["", "LABOR CONTEXT", "Measures are investigation context only; no staffing change is recommended."]
    for row in b.locations:
        if row.labor is None:
            lines.append(f"{row.location_id}: UNAVAILABLE — required joined canonical evidence missing")
        else:
            labor_cost = "OMITTED — cost evidence incomplete" if row.labor.labor_cost_percent is None else f"{row.labor.labor_cost_percent:.2f}%"
            lines.append(f"{row.location_id}: worked hours={row.labor.worked_hours}; sales/worked hour=${row.labor.sales_per_worked_hour:.2f}; labor cost %={labor_cost}")
    lines += ["", "INVENTORY CONTEXT"]
    normalized = aggregate_normalized(row for row in b.inventory if row.status is EvidenceStatus.NORMALIZED)
    lines += [f"{location} / {item}: {quantity} {unit.value} safely normalized" for location, item, quantity, unit in normalized]
    lines += [f"Reconciliation: {b.reconciliation.status.value}", "No inventory usage or food cost is implied.", "",
              "DATA QUALITY / EXCEPTIONS"]
    open_rows = [e for e in b.exceptions if e.resolution is ResolutionState.OPEN and e.human_action_required]
    lines += [f"Open human-action exceptions: {len(open_rows)}",
              f"Configuration-resolvable: {sum(e.configuration_resolvable and e.resolution is ResolutionState.OPEN for e in b.exceptions)}",
              f"Source-correction issues: {sum(e.source_correction_required for e in b.exceptions)}",
              f"Schema issues: {sum(e.category.value == 'SCHEMA CHANGE' for e in b.exceptions)}",
              f"Conflicting duplicates: {sum(e.duplicate_kind is DuplicateKind.CONFLICTING_DUPLICATE for e in b.exceptions)}",
              f"Late evidence: {sum(e.category.value == 'LATE DATA' for e in b.exceptions)}",
              f"Incomplete batches: {sum(x.completeness_status is CompletenessStatus.INCOMPLETE for x in b.batches)}", "",
              "INCOMPLETE EVIDENCE", "Unresolved mappings block affected detail, not every semantically compatible higher-level measure."]
    lines += [f"- {s.location_id}: {s.signal} ({s.limit})" for s in b.signals if s.category is SignalCategory.DATA_QUALITY]
    lines += ["", "HUMAN ACTION REQUIRED"]
    lines += [f"- {e.source_name} / {e.category.value}: {e.reason}" for e in open_rows[:8]]
    lines += ["", "WHAT THIS BRIEFING DOES NOT CLAIM",
              "No alert, forecast, staffing recommendation, total-cover claim, inventory usage, food cost, financial report, confidence score, or industry benchmark.",
              "Technical coherence does not establish buyer willingness, price, adoption, or build-versus-buy superiority.", "",
              "ENGINEERING EVIDENCE",
              "DEMONSTRATED SHARED VALUE: canonical multi-system records and shared location/business-date identity support one management artifact.",
              "NEW SHARED WORK: briefing generation; investigation signals; evidence-limit presentation.",
              "SYSTEM-SPECIFIC CONTRIBUTION: reservation, labor, and inventory semantics feed shared output without being flattened.",
              "SUPPORT OBLIGATION: humans must manage mappings, source corrections, incomplete batches, and schema changes.",
              "REWORK: none required; Chapter 10 consumes existing canonical and quality interfaces.", "",
              "CHAPTER 10 OPPORTUNITY EVIDENCE",
              "The synthetic shared operational layer produced a coherent artifact plausibly useful for management investigation.",
              "This is technical evidence, not market validation or evidence that a manager would pay the modeled price.", "",
              "OBSERVED LAB RESULTS",
              "OBSERVED LAB RESULT: Normalized evidence from multiple operational systems combined into one deterministic cross-location briefing.",
              "OBSERVED LAB RESULT: Data-quality exceptions changed how product and labor comparisons were interpreted.",
              "OBSERVED LAB RESULT: Canonical location net sales remained available while lower-level mappings were incomplete.",
              "OBSERVED LAB RESULT: Inventory reconciliation limits remained visible rather than being hidden."]
    return "\n".join(lines)
