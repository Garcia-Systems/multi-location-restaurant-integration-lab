"""Synthetic Chapter 1 discovery evidence.

This module records interfaces and constraints; it does not connect to any system.
All names and findings are fictional lab fixtures, not market evidence.
"""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum


class DataDomain(StrEnum):
    SALES = "sales / POS"
    RESERVATIONS = "reservations"
    LABOR = "labor / scheduling"
    INVENTORY = "inventory"
    FEEDBACK = "customer feedback"
    MANUAL = "spreadsheets / manual exports"


class AccessMethod(StrEnum):
    REST_API = "REST API"
    SCHEDULED_CSV = "scheduled CSV export"
    MANUAL_CSV = "manual CSV export"
    SFTP = "SFTP"
    SPREADSHEET = "spreadsheet"
    EMAIL = "email attachment"
    LOCAL_DROP = "local file drop"
    UNAVAILABLE = "unavailable / unknown"


class DiscoveryStatus(StrEnum):
    CONFIRMED = "confirmed"
    NEEDS_SAMPLE = "needs sample"
    NEEDS_VENDOR_REVIEW = "needs vendor review"


class EvidenceKind(StrEnum):
    MODELED_ASSUMPTION = "MODELED ASSUMPTION"
    OBSERVED_LAB_RESULT = "OBSERVED LAB RESULT"


class CapabilityStatus(StrEnum):
    CONFIRMED = "confirmed"
    ABSENT = "absent"
    REQUIRES_REVIEW = "requires vendor review"


@dataclass(frozen=True)
class IdentifierScheme:
    name: str
    scope: str
    stable: bool
    concern: str = ""


@dataclass(frozen=True)
class SystemInterface:
    access_method: AccessMethod
    format: str
    frequency: str
    permission_owner: str | None
    sample_available: bool
    schema_documented: bool


@dataclass(frozen=True)
class ExistingCapability:
    name: str
    status: CapabilityStatus
    could_reduce_custom_scope: bool
    detail: str


@dataclass(frozen=True)
class CapabilityReview:
    """Build-versus-buy checklist recorded for every discovered system."""

    system_key: str
    native_reports: CapabilityStatus
    group_reporting: CapabilityStatus
    configurable_exports: CapabilityStatus
    scheduled_reports: CapabilityStatus
    multi_location: CapabilityStatus
    bi_connectors: CapabilityStatus


@dataclass(frozen=True)
class OperationalSystem:
    key: str
    name: str
    category: DataDomain
    location_codes: tuple[str, ...]
    authoritative_data: tuple[str, ...]
    interface: SystemInterface
    identifiers: tuple[IdentifierScheme, ...]
    data_quality_concerns: tuple[str, ...]
    historical_data: str
    capabilities: tuple[ExistingCapability, ...]
    status: DiscoveryStatus


@dataclass(frozen=True)
class RestaurantLocation:
    code: str
    name: str
    concept: str
    system_keys: tuple[str, ...]
    explicitly_absent_domains: tuple[DataDomain, ...] = ()


@dataclass(frozen=True)
class ManagementQuestion:
    question: str
    required_domains: tuple[DataDomain, ...]


@dataclass(frozen=True)
class DiscoveryRisk:
    key: str
    description: str
    open: bool = True


@dataclass(frozen=True)
class EvidenceEntry:
    kind: EvidenceKind
    statement: str
    context: str


@dataclass(frozen=True)
class ReadinessAssessment:
    status: str
    unresolved: tuple[str, ...]


def _interface(method: AccessMethod, format: str, frequency: str, owner: str | None,
               sample: bool = True, docs: bool = True) -> SystemInterface:
    return SystemInterface(method, format, frequency, owner, sample, docs)


GROUP_CODES = ("RRK", "CST", "BHO", "MBC", "JRS")
GROUP_LOCATION_ID = IdentifierScheme("HarborTill location_id", "shared group namespace", True)
LOCAL_ITEM_ID = IdentifierScheme("menu_item_id", "location-local", True)
EMPLOYEE_ID = IdentifierScheme("ShiftHarbor employee_uuid", "shared group namespace", True)

NATIVE_POS_REPORT = ExistingCapability(
    "HarborTill multi-location sales dashboard", CapabilityStatus.REQUIRES_REVIEW, True,
    "May already answer the proposed cross-location sales comparison; license and category alignment need review.",
)
LABOR_REPORT = ExistingCapability(
    "ShiftHarbor labor-to-sales report", CapabilityStatus.CONFIRMED, True,
    "Scheduled group report exists, although its POS feed omits late adjustments.",
)
NO_GROUP_REPORT = ExistingCapability(
    "group-level reporting", CapabilityStatus.ABSENT, False, "Only location-level reports are available.",
)

SYSTEMS: tuple[OperationalSystem, ...] = (
    OperationalSystem("rrk-pos", "HarborTill Cloud — RRK", DataDomain.SALES, ("RRK",),
        ("checks", "payments", "menu items", "business date"),
        _interface(AccessMethod.REST_API, "JSON v3", "hourly", "group IT"),
        (GROUP_LOCATION_ID, LOCAL_ITEM_ID), (), "36 months online", (NATIVE_POS_REPORT,), DiscoveryStatus.CONFIRMED),
    OperationalSystem("cst-pos", "HarborTill Cloud — CST", DataDomain.SALES, ("CST",),
        ("checks", "payments", "menu items", "business date"),
        _interface(AccessMethod.SCHEDULED_CSV, "CSV; MM/DD/YYYY dates", "nightly 03:00", "finance administrator", sample=False),
        (GROUP_LOCATION_ID, LOCAL_ITEM_ID), ("delivery tenders are sometimes recategorized after close",),
        "24 months exportable", (NATIVE_POS_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("bho-pos", "HarborTill Cloud — BHO", DataDomain.SALES, ("BHO",),
        ("checks", "payments", "menu items", "business date"),
        _interface(AccessMethod.SCHEDULED_CSV, "CSV; ISO dates", "nightly 04:00", "finance administrator"),
        (GROUP_LOCATION_ID, IdentifierScheme("menu_item_id", "location-local", False, "duplicates remain after 2024 menu migration")),
        ("duplicate product IDs after menu migration", "after-midnight checks use service-day close"),
        "18 months exportable", (NATIVE_POS_REPORT,), DiscoveryStatus.CONFIRMED),
    OperationalSystem("mbc-pos", "HarborTill Legacy — MBC", DataDomain.SALES, ("MBC",),
        ("tickets", "tenders", "retail SKUs", "business date"),
        _interface(AccessMethod.SFTP, "tab-delimited text; YYYYMMDD", "nightly 01:30", "managed service desk", docs=False),
        (IdentifierScheme("store_number", "legacy local value 04", True), IdentifierScheme("retail_sku", "location-local", True)),
        ("wholesale batches share a tender category with catering",), "13 months on SFTP", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_VENDOR_REVIEW),
    OperationalSystem("jrs-pos", "HarborTill Cloud — JRS", DataDomain.SALES, ("JRS",),
        ("checks", "payments", "menu items", "business date"),
        _interface(AccessMethod.MANUAL_CSV, "CSV; ISO timestamps", "manager download each Monday", "JRS general manager", sample=False),
        (GROUP_LOCATION_ID, LOCAL_ITEM_ID), ("weekly export can be skipped", "table tabs cross midnight"),
        "unknown", (NATIVE_POS_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("reservations", "TableCurrent", DataDomain.RESERVATIONS, ("RRK", "BHO"),
        ("bookings", "covers", "cancellations", "guest reference"),
        _interface(AccessMethod.REST_API, "JSON", "on demand", None, sample=False),
        (IdentifierScheme("venue_id", "vendor account", True), IdentifierScheme("booking_id", "venue-local", True)),
        ("API entitlement is not confirmed",), "vendor states 12 months", (ExistingCapability("multi-venue pacing report", CapabilityStatus.REQUIRES_REVIEW, True, "Could replace a custom reservations comparison."),), DiscoveryStatus.NEEDS_VENDOR_REVIEW),
    OperationalSystem("mbc-preorders", "BakeAhead", DataDomain.RESERVATIONS, ("MBC",),
        ("preorders", "pickup slots"), _interface(AccessMethod.EMAIL, "CSV attachment", "daily 18:00", "MBC bakery manager", docs=False),
        (IdentifierScheme("order_number", "MBC only", True),), ("not equivalent to table reservations",), "90 days", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("jrs-events", "JRS Event Calendar", DataDomain.RESERVATIONS, ("JRS",),
        ("event bookings",), _interface(AccessMethod.SPREADSHEET, "cloud sheet", "manual / live", "JRS events lead", docs=False),
        (IdentifierScheme("event row number", "sheet-local", False, "changes when rows are sorted"),), ("no stable booking identifier",), "since 2025", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("labor", "ShiftHarbor", DataDomain.LABOR, GROUP_CODES,
        ("scheduled shifts", "worked shifts", "roles", "labor cost"),
        _interface(AccessMethod.REST_API, "JSON v2", "daily", "HR systems owner"),
        (EMPLOYEE_ID, IdentifierScheme("worksite_code", "shared; matches restaurant code", True)),
        ("terminated employees disappear from default report",), "4 years", (LABOR_REPORT,), DiscoveryStatus.CONFIRMED),
    OperationalSystem("stockpilot", "StockPilot", DataDomain.INVENTORY, ("RRK", "BHO"),
        ("purchases", "counts", "waste", "units"), _interface(AccessMethod.REST_API, "JSON", "nightly", "culinary director", sample=False),
        (IdentifierScheme("ingredient_id", "shared account but venue-specific", True),), ("BHO catch-weight units need vendor explanation",),
        "2 years", (ExistingCapability("multi-location variance report", CapabilityStatus.CONFIRMED, True, "Already compares food-cost variance for RRK and BHO."),), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("cst-inventory", "CST Weekly Count", DataDomain.INVENTORY, ("CST",),
        ("weekly counts", "waste notes"), _interface(AccessMethod.SPREADSHEET, "cloud sheet", "weekly", "CST kitchen manager", docs=False),
        (IdentifierScheme("ingredient name", "CST free text", False, "names are edited"),), ("free-text units and names",), "8 months", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("mbc-inventory", "BatchBook", DataDomain.INVENTORY, ("MBC",),
        ("production batches", "ingredient usage", "waste"), _interface(AccessMethod.SCHEDULED_CSV, "CSV", "daily 15:00", "MBC production manager", docs=False),
        (IdentifierScheme("recipe_sku", "MBC only", True),), ("inventory day ends at 15:00",), "1 year", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("jrs-inventory", "Pit Ledger", DataDomain.INVENTORY, ("JRS",),
        ("meat yields", "keg counts", "waste"), _interface(AccessMethod.UNAVAILABLE, "unknown", "unknown", None, sample=False, docs=False),
        (IdentifierScheme("item label", "JRS local", False, "hand-entered labels"),), ("workflow observed but export route is unknown",), "paper archive uncertain", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_VENDOR_REVIEW),
    OperationalSystem("feedback", "EchoGuest", DataDomain.FEEDBACK, GROUP_CODES,
        ("survey ratings", "comments", "location attribution"), _interface(AccessMethod.SCHEDULED_CSV, "CSV", "weekly", "marketing director"),
        (IdentifierScheme("EchoGuest site_code", "shared; mapped to restaurant code", True),), ("low response volume at CST",), "2 years", (ExistingCapability("portfolio sentiment email", CapabilityStatus.CONFIRMED, True, "Native weekly email may satisfy the initial feedback summary."),), DiscoveryStatus.CONFIRMED),
    OperationalSystem("rrk-events-sheet", "RRK Private Dining Tracker", DataDomain.MANUAL, ("RRK",),
        ("private-event minimums", "manager notes"), _interface(AccessMethod.SPREADSHEET, "cloud sheet", "manual / live", "RRK events lead", docs=False),
        (IdentifierScheme("event code", "RRK only", True),), ("event code is not stored in POS",), "since 2023", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
    OperationalSystem("jrs-category-map", "JRS Category Override", DataDomain.MANUAL, ("JRS",),
        ("management category overrides",), _interface(AccessMethod.LOCAL_DROP, "XLSX", "changed without schedule", "JRS general manager", docs=False),
        (IdentifierScheme("menu_item_id", "references JRS POS IDs", True),), ("mapping changes have no version history",), "current file only", (NO_GROUP_REPORT,), DiscoveryStatus.NEEDS_SAMPLE),
)

# A complete checklist avoids interpreting "an export exists" as proof that all
# SaaS alternatives were considered.  REQUIRES_REVIEW is an explicit finding.
CAPABILITY_REVIEWS: tuple[CapabilityReview, ...] = tuple(
    CapabilityReview(
        system.key,
        CapabilityStatus.CONFIRMED,
        (
            CapabilityStatus.REQUIRES_REVIEW
            if any(cap.could_reduce_custom_scope for cap in system.capabilities)
            else CapabilityStatus.ABSENT
        ),
        CapabilityStatus.CONFIRMED if system.interface.access_method is not AccessMethod.UNAVAILABLE else CapabilityStatus.REQUIRES_REVIEW,
        (
            CapabilityStatus.CONFIRMED
            if "scheduled" in system.interface.access_method.value or system.interface.frequency not in {"unknown", "manual / live"}
            else CapabilityStatus.ABSENT
        ),
        CapabilityStatus.CONFIRMED if len(system.location_codes) > 1 else CapabilityStatus.ABSENT,
        CapabilityStatus.REQUIRES_REVIEW,
    )
    for system in SYSTEMS
)

LOCATIONS: tuple[RestaurantLocation, ...] = (
    RestaurantLocation("RRK", "River & Rail Kitchen", "full-service New American", ("rrk-pos", "reservations", "labor", "stockpilot", "feedback", "rrk-events-sheet")),
    RestaurantLocation("CST", "Canal Street Tacos", "fast casual", ("cst-pos", "labor", "cst-inventory", "feedback"), (DataDomain.RESERVATIONS, DataDomain.MANUAL)),
    RestaurantLocation("BHO", "Blue Heron Oyster House", "seafood and raw bar", ("bho-pos", "reservations", "labor", "stockpilot", "feedback"), (DataDomain.MANUAL,)),
    RestaurantLocation("MBC", "Manchester Bake & Coffee", "bakery café", ("mbc-pos", "mbc-preorders", "labor", "mbc-inventory", "feedback"), (DataDomain.MANUAL,)),
    RestaurantLocation("JRS", "James River Smokehouse", "barbecue and taproom", ("jrs-pos", "jrs-events", "labor", "jrs-inventory", "feedback", "jrs-category-map")),
)

MANAGEMENT_QUESTIONS: tuple[ManagementQuestion, ...] = (
    ManagementQuestion("Which locations materially differ in sales performance?", (DataDomain.SALES,)),
    ManagementQuestion("Where is labor unusually high relative to demand?", (DataDomain.SALES, DataDomain.LABOR)),
    ManagementQuestion("Which locations show inventory or waste anomalies?", (DataDomain.SALES, DataDomain.INVENTORY)),
    ManagementQuestion("Which locations have incomplete operational evidence?", tuple(DataDomain)),
    ManagementQuestion("Which cross-location exceptions require management attention?", (DataDomain.SALES, DataDomain.LABOR, DataDomain.INVENTORY)),
)

RISKS: tuple[DiscoveryRisk, ...] = (
    DiscoveryRisk("pos-samples", "CST and JRS POS samples have not been received."),
    DiscoveryRisk("reservation-entitlement", "TableCurrent API entitlement and credential owner are unknown."),
    DiscoveryRisk("jrs-inventory", "Pit Ledger has no confirmed interface, permission owner, sample, or schema."),
    DiscoveryRisk("native-reports", "HarborTill and TableCurrent group reporting require license/vendor review."),
    DiscoveryRisk("identifier-collision", "BHO menu migration produced duplicate location-local product IDs."),
)

EVIDENCE_LOG: tuple[EvidenceEntry, ...] = (
    EvidenceEntry(EvidenceKind.MODELED_ASSUMPTION, "Shared ownership will make delivery reuse economical.", "Inherited fictional Case 2 hypothesis; not validated."),
    EvidenceEntry(EvidenceKind.OBSERVED_LAB_RESULT, "Five locations use multiple source-interface patterns.", "Derived only from the synthetic Chapter 1 fixtures."),
    EvidenceEntry(EvidenceKind.OBSERVED_LAB_RESULT, "The shared POS family does not imply identical export schemas.", "Synthetic POS records use JSON, CSV, tab-delimited, and manual delivery."),
    EvidenceEntry(EvidenceKind.OBSERVED_LAB_RESULT, "Reservation data is absent at Canal Street Tacos because the concept does not take reservations.", "Explicit synthetic absence, not missing discovery."),
    EvidenceEntry(EvidenceKind.OBSERVED_LAB_RESULT, "Existing native reports could reduce custom sales, labor, inventory, reservation, and feedback scope.", "Capability review is part of this synthetic discovery result."),
)


def assess_readiness() -> ReadinessAssessment:
    """Apply explicit, deterministic gates before architecture work."""
    unresolved: list[str] = []
    by_key = {system.key: system for system in SYSTEMS}
    for location in LOCATIONS:
        represented = {by_key[key].category for key in location.system_keys} | set(location.explicitly_absent_domains)
        missing = set(DataDomain) - represented
        if missing:
            unresolved.append(f"{location.code}: domains neither owned nor explicitly absent: {', '.join(sorted(d.value for d in missing))}")
    for system in SYSTEMS:
        if not system.authoritative_data:
            unresolved.append(f"{system.key}: authoritative data ownership is unknown")
        if system.interface.access_method is AccessMethod.UNAVAILABLE:
            unresolved.append(f"{system.key}: access method is unknown")
        if not system.interface.sample_available and not system.interface.schema_documented:
            unresolved.append(f"{system.key}: neither a sample nor schema documentation is available")
        if system.interface.permission_owner is None:
            unresolved.append(f"{system.key}: credential or permission owner is unknown")
    if not MANAGEMENT_QUESTIONS:
        unresolved.append("management questions are not defined")
    if any(
        CapabilityStatus.REQUIRES_REVIEW in (
            review.group_reporting,
            review.configurable_exports,
            review.scheduled_reports,
            review.multi_location,
            review.bi_connectors,
        )
        for review in CAPABILITY_REVIEWS
    ):
        unresolved.append("major native/group capabilities still require vendor or license review")
    return ReadinessAssessment("READY" if not unresolved else "NOT READY", tuple(unresolved))


def discovery_metrics() -> dict[str, int]:
    return {
        "locations": len(LOCATIONS),
        "operational systems": len(SYSTEMS),
        "data domains": len({system.category for system in SYSTEMS}),
        "interface patterns": len({(s.interface.access_method, s.interface.format) for s in SYSTEMS}),
        "unknown access methods": sum(s.interface.access_method is AccessMethod.UNAVAILABLE for s in SYSTEMS),
        "identifier schemes": len({(i.name, i.scope) for s in SYSTEMS for i in s.identifiers}),
        "open discovery risks": sum(risk.open for risk in RISKS),
        "capabilities requiring investigation": sum(
            status is CapabilityStatus.REQUIRES_REVIEW
            for review in CAPABILITY_REVIEWS
            for status in (
                review.native_reports,
                review.group_reporting,
                review.configurable_exports,
                review.scheduled_reports,
                review.multi_location,
                review.bi_connectors,
            )
        ),
    }


def discovery_report() -> str:
    """Render deterministic, human-readable discovery evidence."""
    methods = Counter(s.interface.access_method.value for s in SYSTEMS)
    systems_by_domain = {domain: sorted({s.name.split(" — ")[0] for s in SYSTEMS if s.category is domain}) for domain in DataDomain}
    readiness = assess_readiness()
    lines = [
        "JAMES RIVER HOSPITALITY GROUP", "INTEGRATION DISCOVERY", "SYNTHETIC LAB EVIDENCE — NOT MARKET VALIDATION", "",
        "LOCATIONS", str(len(LOCATIONS)), *[f"- {loc.code}: {loc.name} — {loc.concept}" for loc in LOCATIONS], "", "SYSTEM LANDSCAPE",
    ]
    lines.extend(f"- {domain.value}: {', '.join(systems_by_domain[domain])}" for domain in DataDomain)
    lines.extend(["", "ACCESS METHODS"])
    lines.extend(f"- {method.value}: {methods.get(method.value, 0)}" for method in AccessMethod)
    lines.extend(["", "STANDARDIZATION SIGNALS",
        "- All five locations use the HarborTill POS family, though MBC remains on its legacy product.",
        "- ShiftHarbor labor and EchoGuest feedback cover all five locations with shared group identifiers.",
        "", "VARIATION SIGNALS",
        "- POS delivery spans REST JSON, scheduled CSV, SFTP tab-delimited files, and manual CSV.",
        "- Inventory spans a shared API, spreadsheets, scheduled CSV, and one unknown interface.",
        "- Reservations mean table bookings, bakery preorders, event rows, or explicit absence depending on concept.",
        "", "IDENTIFIER RISKS",
        "- Menu item identifiers are location-local; BHO has duplicates from a menu migration.",
        "- MBC uses legacy store_number 04 rather than the shared POS location identifier.",
        "- JRS event row numbers and inventory labels are not stable identifiers.",
        "", "DISCOVERY GAPS", *[f"- {reason}" for reason in readiness.unresolved],
        "", "EXISTING CAPABILITY QUESTIONS",
        "- Can HarborTill's licensed group dashboard answer sales comparison without custom software?",
        "- Can TableCurrent's multi-venue pacing report cover reservation comparison?",
        "- Use confirmed ShiftHarbor, StockPilot, and EchoGuest reports before duplicating them.",
        "", "MANAGEMENT QUESTIONS", *[f"- {item.question}" for item in MANAGEMENT_QUESTIONS],
        "", "EVIDENCE LOG", *[f"{entry.kind.value}: {entry.statement} ({entry.context})" for entry in EVIDENCE_LOG],
        "", "ARCHITECTURE READINESS", readiness.status,
        f"Reason: {len(readiness.unresolved)} deterministic readiness gate(s) remain unresolved.",
        "Architecture is a response to discovered constraints, not a drawing created before discovery.",
        "Evidence before abstraction.",
    ])
    return "\n".join(lines)
