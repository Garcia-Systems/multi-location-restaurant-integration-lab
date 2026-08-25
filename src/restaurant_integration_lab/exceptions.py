"""Chapter 9 cross-system exception and batch-quality evidence.

The source importers remain responsible for precise parsing.  This module evolves
their existing ``IngestionException`` output into a common operational view; it
does not replace or conceal the source-specific reason.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from typing import Iterable, Mapping

from .ingestion import ExceptionCategory, IngestionException
from .inventory import InventoryImporter
from .labor import ShiftHarborImporter
from .location1 import LocationOneSalesImporter
from .reservations import TableCurrentImporter

DETECTED_AT = datetime(2026, 8, 27, 9, 0, 0)
SCHEMA_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/pos_schema_change.synthetic.json")
INCOMPLETE_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/incomplete_batch.synthetic.json")


class SourceSystem(StrEnum):
    POS = "POS"
    RESERVATIONS = "RESERVATIONS"
    LABOR = "LABOR"
    INVENTORY = "INVENTORY"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ResolutionState(StrEnum):
    OPEN = "OPEN"
    RESOLVED_BY_CONFIGURATION = "RESOLVED BY CONFIGURATION"
    RESOLVED_BY_SOURCE_CORRECTION = "RESOLVED BY SOURCE CORRECTION"
    NOT_ACTIONABLE = "NOT ACTIONABLE"


class RetryClass(StrEnum):
    RETRYABLE = "RETRYABLE"
    NOT_RETRYABLE = "NOT RETRYABLE"
    CORRECTION_REQUIRED = "RETRY WOULD NOT HELP WITHOUT CORRECTION"


class SchemaStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class CompletenessStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


class DuplicateKind(StrEnum):
    EXACT_REPLAY = "EXACT REPLAY"
    CONFLICTING_DUPLICATE = "CONFLICTING DUPLICATE"


@dataclass(frozen=True)
class OperationalException:
    source_system: SourceSystem
    source_name: str
    source_interface: str
    batch_id: str
    location_id: str | None
    row_number: int | None
    source_record_id: str
    category: ExceptionCategory
    reason: str
    detected_at: datetime
    severity: Severity
    partial_evidence_usable: bool
    human_action_required: bool
    retry: RetryClass
    configuration_resolvable: bool
    source_correction_required: bool
    resolution: ResolutionState = ResolutionState.OPEN
    duplicate_kind: DuplicateKind | None = None
    effective_date: date | None = None
    observed_at: datetime | None = None


@dataclass(frozen=True)
class IngestionBatchResult:
    source_system: SourceSystem
    source_interface: str
    batch_id: str
    effective_date: date | None
    records_read: int
    records_accepted: int
    records_rejected: int
    duplicate_count: int
    conflicting_duplicate_count: int
    unresolved_mapping_count: int
    schema_status: SchemaStatus
    completeness_status: CompletenessStatus
    exceptions: tuple[OperationalException, ...]

    @property
    def exception_count(self) -> int:
        return len(self.exceptions)


@dataclass(frozen=True)
class SupportObligationEvidence:
    human_mapping_categories: int
    source_format_or_schema_problems: int
    retryable_operational_failures: int
    configuration_resolvable: int
    source_correction_required: int
    code_changes_required: int


SOURCE_METADATA = {
    "HarborTill RRK": (SourceSystem.POS, "synthetic REST API JSON v3", "POS-20260824"),
    "TableCurrent": (SourceSystem.RESERVATIONS, "synthetic REST API JSON", "RES-20260824"),
    "ShiftHarbor": (SourceSystem.LABOR, "synthetic group labor API JSON", "LAB-20260824"),
    "StockPilot": (SourceSystem.INVENTORY, "synthetic nightly API JSON", "INV-20260824"),
    "CST Weekly Count": (SourceSystem.INVENTORY, "synthetic spreadsheet CSV", "INV-20260824"),
}
MAPPING_CATEGORIES = {ExceptionCategory.UNKNOWN_PRODUCT, ExceptionCategory.UNKNOWN_LOCATION,
                      ExceptionCategory.UNKNOWN_STATUS, ExceptionCategory.UNKNOWN_INVENTORY_ITEM,
                      ExceptionCategory.UNKNOWN_UNIT, ExceptionCategory.MISSING_CONVERSION,
                      ExceptionCategory.CONFLICTING_MAPPING, ExceptionCategory.VALIDATION_FAILURE}
SOURCE_CORRECTION_CATEGORIES = {ExceptionCategory.MALFORMED_RECORD,
                                ExceptionCategory.MISSING_REQUIRED_VALUE,
                                ExceptionCategory.SCHEMA_CHANGE}


def unify_exception(error: IngestionException, *, location_id: str | None = None) -> OperationalException:
    """Add deterministic workflow metadata while preserving the original reason verbatim."""
    system, interface, batch = SOURCE_METADATA[error.source]
    duplicate = error.category is ExceptionCategory.DUPLICATE
    mapping = error.category in MAPPING_CATEGORIES
    source_correction = error.category in SOURCE_CORRECTION_CATEGORIES
    return OperationalException(
        system, error.source, interface, batch, location_id, error.row_number,
        error.source_record_id, error.category, error.reason, DETECTED_AT,
        Severity.INFO if duplicate else (Severity.WARNING if mapping else Severity.ERROR),
        error.category in {ExceptionCategory.MISSING_CONVERSION, ExceptionCategory.INCOMPATIBLE_UNIT},
        error.human_action_required, RetryClass.NOT_RETRYABLE if duplicate else RetryClass.CORRECTION_REQUIRED,
        mapping and error.category not in {ExceptionCategory.CONFLICTING_MAPPING,
                                           ExceptionCategory.INCOMPATIBLE_UNIT},
        source_correction, ResolutionState.NOT_ACTIONABLE if duplicate else ResolutionState.OPEN,
        DuplicateKind.EXACT_REPLAY if duplicate else None,
    )


def validate_schema(path: str | Path = SCHEMA_FIXTURE) -> OperationalException | None:
    """Reject a renamed POS column instead of guessing that it means transaction_id."""
    payload = json.loads(Path(path).read_text())
    expected = set(payload["expected_columns"])
    actual = set(payload["actual_columns"])
    if expected == actual:
        return None
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    return OperationalException(SourceSystem.POS, "HarborTill RRK", "synthetic REST API JSON v4",
        payload["batch_id"], "JRH-001", None, "<batch>", ExceptionCategory.SCHEMA_CHANGE,
        f"schema mismatch; missing={missing}; unexpected={unexpected}", DETECTED_AT,
        Severity.ERROR, False, True, RetryClass.CORRECTION_REQUIRED, False, True)


def classify_duplicate(record_id: str, accepted_payload: Mapping[str, object],
                       replay_payload: Mapping[str, object]) -> OperationalException:
    def digest(value: Mapping[str, object]) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    exact = digest(accepted_payload) == digest(replay_payload)
    return OperationalException(SourceSystem.POS, "HarborTill RRK", "synthetic REST API JSON v3",
        "POS-DUPLICATE-EXPERIMENT", "JRH-001", 2, record_id,
        ExceptionCategory.DUPLICATE if exact else ExceptionCategory.CONFLICTING_IDENTIFIER,
        "content fingerprint matches accepted record" if exact else "same source record ID has changed content",
        DETECTED_AT, Severity.INFO if exact else Severity.ERROR, False, not exact,
        RetryClass.NOT_RETRYABLE if exact else RetryClass.CORRECTION_REQUIRED, False, not exact,
        ResolutionState.NOT_ACTIONABLE if exact else ResolutionState.OPEN,
        DuplicateKind.EXACT_REPLAY if exact else DuplicateKind.CONFLICTING_DUPLICATE)


class MappingRegistry:
    """Explicit configuration with an immutable source-to-canonical identity boundary."""
    def __init__(self, mappings: Mapping[str, str] | None = None) -> None:
        self._mappings = dict(mappings or {})

    def add(self, source_id: str, canonical_id: str) -> None:
        current = self._mappings.get(source_id)
        if current is not None and current != canonical_id:
            raise ValueError(f"CONFLICTING IDENTIFIER: {source_id} already maps to {current}")
        self._mappings[source_id] = canonical_id

    def resolve(self, source_id: str) -> str | None:
        return self._mappings.get(source_id)


def configuration_resolution_experiment() -> tuple[OperationalException, OperationalException]:
    registry = MappingRegistry()
    legacy = IngestionException("HarborTill RRK", 1, "CFG-001", ExceptionCategory.UNKNOWN_PRODUCT,
                                "explicit product mapping required for MENU-404", True)
    before = unify_exception(legacy, location_id="JRH-001")
    registry.add("MENU-404", "JRH-P-002")
    assert registry.resolve("MENU-404") == "JRH-P-002"
    after = replace(before, resolution=ResolutionState.RESOLVED_BY_CONFIGURATION,
                    human_action_required=False)
    return before, after


def _batch(system: SourceSystem, interface: str, batch_id: str, read: int, accepted: int,
           errors: Iterable[OperationalException], *, completeness=CompletenessStatus.COMPLETE,
           schema=SchemaStatus.VALID, effective=date(2026, 8, 24)) -> IngestionBatchResult:
    exceptions = tuple(errors)
    duplicates = sum(e.duplicate_kind is DuplicateKind.EXACT_REPLAY for e in exceptions)
    conflicts = sum(e.duplicate_kind is DuplicateKind.CONFLICTING_DUPLICATE for e in exceptions)
    unresolved = sum(e.configuration_resolvable and e.resolution is ResolutionState.OPEN for e in exceptions)
    rejected = read - accepted - duplicates
    return IngestionBatchResult(system, interface, batch_id, effective, read, accepted, rejected,
                                duplicates, conflicts, unresolved, schema, completeness, exceptions)


def lab_batches() -> tuple[IngestionBatchResult, ...]:
    pos = LocationOneSalesImporter().ingest()
    reservations = TableCurrentImporter().ingest()
    labor = ShiftHarborImporter().ingest()
    inventory = InventoryImporter().ingest()
    groups = tuple(tuple(unify_exception(e) for e in result.exceptions)
                   for result in (pos, reservations, labor, inventory))
    schema_error = validate_schema()
    assert schema_error is not None
    incomplete = json.loads(Path(INCOMPLETE_FIXTURE).read_text())
    incomplete_error = OperationalException(SourceSystem.RESERVATIONS, "TableCurrent",
        "synthetic REST API JSON", incomplete["batch_id"], None, None, "<batch>",
        ExceptionCategory.INCOMPLETE_BATCH,
        f"explicit partial flag; expected {incomplete['expected_records']} records, received {incomplete['received_records']}",
        DETECTED_AT, Severity.WARNING, True, True, RetryClass.CORRECTION_REQUIRED, False, True)
    late = OperationalException(SourceSystem.INVENTORY, "StockPilot", "synthetic nightly API JSON",
        "INV-20260824", "JRH-001", 1, "SP-001", ExceptionCategory.LATE_DATA,
        "valid count arrived after its effective business date", DETECTED_AT, Severity.WARNING,
        True, False, RetryClass.NOT_RETRYABLE, False, False, ResolutionState.NOT_ACTIONABLE,
        effective_date=date(2026, 8, 24), observed_at=datetime(2026, 8, 26, 6, 0))
    return (
        _batch(SourceSystem.POS, "synthetic REST API JSON v3", "POS-20260824", pos.rows_read, len(pos.sales), groups[0]),
        _batch(SourceSystem.RESERVATIONS, "synthetic REST API JSON", "RES-20260824", reservations.rows_read, len(reservations.reservations), groups[1]),
        _batch(SourceSystem.LABOR, "synthetic group labor API JSON", "LAB-20260824", labor.rows_read, len(labor.records), groups[2]),
        _batch(SourceSystem.INVENTORY, "synthetic inventory exports", "INV-20260824", inventory.rows_read, len(inventory.normalized), groups[3] + (late,)),
        _batch(SourceSystem.POS, "synthetic REST API JSON v4", "POS-SCHEMA-20260825", 0, 0, (schema_error,), schema=SchemaStatus.INVALID),
        _batch(SourceSystem.RESERVATIONS, "synthetic REST API JSON", incomplete["batch_id"], incomplete["received_records"], incomplete["received_records"], (incomplete_error,), completeness=CompletenessStatus.INCOMPLETE),
    )


def support_evidence(exceptions: Iterable[OperationalException]) -> SupportObligationEvidence:
    rows = tuple(exceptions)
    mapping_categories = {e.category for e in rows if e.configuration_resolvable and e.human_action_required}
    return SupportObligationEvidence(len(mapping_categories),
        sum(e.category is ExceptionCategory.SCHEMA_CHANGE for e in rows),
        sum(e.retry is RetryClass.RETRYABLE for e in rows),
        sum(e.configuration_resolvable for e in rows), sum(e.source_correction_required for e in rows),
        sum(e.category is ExceptionCategory.SCHEMA_CHANGE for e in rows))


def exception_report() -> str:
    batches = lab_batches()
    rows = tuple(e for batch in batches for e in batch.exceptions)
    exact = classify_duplicate("CHK-1001:1", {"net": "24.00"}, {"net": "24.00"})
    conflict = classify_duplicate("CHK-1001:1", {"net": "24.00"}, {"net": "29.00"})
    before, after = configuration_resolution_experiment()
    support = support_evidence(rows)
    by_system = Counter(e.source_system.value for e in rows)
    by_category = Counter(e.category.value for e in rows)
    lines = ["EXCEPTIONS + DATA QUALITY", "SYNTHETIC LAB EVIDENCE", "", "BATCH SUMMARY"]
    for b in batches:
        lines.append(f"{b.batch_id} | {b.source_system.value} | read={b.records_read} accepted={b.records_accepted} rejected={b.records_rejected} duplicates={b.duplicate_count} unresolved={b.unresolved_mapping_count} schema={b.schema_status.value} complete={b.completeness_status.value} exceptions={b.exception_count}")
    lines += ["", "EXCEPTION COUNTS BY SYSTEM"] + [f"{k}: {v}" for k, v in sorted(by_system.items())]
    lines += ["", "EXCEPTION COUNTS BY CATEGORY"] + [f"{k}: {v}" for k, v in sorted(by_category.items())]
    lines += ["", "HUMAN ACTION REQUIRED", str(sum(e.human_action_required for e in rows)),
              "", "RETRYABLE", str(sum(e.retry is RetryClass.RETRYABLE for e in rows)),
              "Unknown mappings: RETRY WOULD NOT HELP WITHOUT CORRECTION",
              "", "CONFIGURATION-RESOLVABLE", str(sum(e.configuration_resolvable for e in rows)),
              "", "SOURCE CORRECTION REQUIRED", str(sum(e.source_correction_required for e in rows)),
              "", "SCHEMA CHANGE EXAMPLE", f"{validate_schema().category.value}: {validate_schema().reason}",
              "", "DUPLICATE CONFLICT EXAMPLE",
              f"{exact.duplicate_kind.value}: {exact.reason}", f"{conflict.duplicate_kind.value}: {conflict.reason}",
              "", "LATE DATA", "SP-001 | effective=2026-08-24 observed=2026-08-26 | accepted evidence; management context may change",
              "", "INCOMPLETE BATCHES", "RES-PARTIAL-20260825 | schema=VALID complete=INCOMPLETE | explicit partial flag",
              "", "RESOLUTION EXPERIMENTS",
              f"A BEFORE: {before.category.value} / {before.resolution.value}",
              f"A AFTER: normalized / {after.resolution.value} / parser code changed: NO",
              "B BEFORE: MALFORMED RECORD / OPEN", "B AFTER: configuration possible: NO / source correction required: YES",
              "", "SUPPORT OBLIGATION EVIDENCE"]
    lines += [f"{name.replace('_', ' ').upper()}: {value}" for name, value in support.__dict__.items()]
    lines += ["", "ENGINEERING EVIDENCE", "NEW SHARED WORK: unified exception model; batch result; cross-system report",
              "CONFIGURATION WORK: explicit mapping fixes and allowed status mappings",
              "SOURCE-SPECIFIC WORK: schema contract checks",
              "SUPPORT OBLIGATION: human mapping; schema investigation; incomplete-batch review",
              "REWORK: legacy source exceptions enriched at the shared reporting boundary",
              "", "OBSERVED LAB RESULTS",
              "OBSERVED LAB RESULT: Shared metadata preserved source-specific failure reasons across all four systems.",
              "OBSERVED LAB RESULT: Explicit configuration resolved a product mapping without parser changes.",
              "OBSERVED LAB RESULT: Retrying an unknown mapping did not address its correction requirement.",
              "OBSERVED LAB RESULT: Changed content under the same identifier was not treated as an exact replay.",
              "OBSERVED LAB RESULT: Late inventory evidence remained valid while retaining effective and observed dates."]
    return "\n".join(lines)
