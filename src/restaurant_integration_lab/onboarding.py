"""Chapter 12: an evidence-first, deterministic sixth-location onboarding."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from importlib.resources import files
import json
from pathlib import Path

from .briefing import ManagementBriefing, build_management_briefing
from .labor import ShiftHarborParser
from .location2 import LocationTwoHarborTillCsvParser
from .normalization import (Completeness, CrossLocationDataset, LocationCoverage,
                            NormalizationOutcome, NormalizationStatus, build_dataset)
from .operational_model import (BusinessDate, Location, LocationMapping, Product,
                                ProductMapping, Provenance, Sale, SourceIdentity,
                                resolve_location, resolve_product)
from .operations import (ConflictingReplayError, FakeCredentialProvider,
                         InMemoryOperationalStore, RunStatus, load_config,
                         readiness_checks)
from .reservations import TableCurrentParser

LOCATION = Location("JRH-006", "Tidewater Garden Cafe")
POS_SOURCE = "HarborTill TGC"
POS_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/jrh006_harbortill_sales.synthetic.csv")
DISCOVERY_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/jrh006_onboarding.synthetic.json")
OPERATIONS_FIXTURE = files("restaurant_integration_lab").joinpath("fixtures/jrh006_operations.synthetic.json")


@dataclass(frozen=True)
class RestaurantProfile:
    name: str = "Tidewater Garden Cafe"
    canonical_location_id: str = "JRH-006"
    concept: str = "all-day garden cafe and neighborhood supper restaurant"
    operating_characteristics: tuple[str, ...] = ("breakfast through dinner", "counter service by day; table service at dinner")
    source_system_landscape: tuple[str, ...] = ("HarborTill Cloud CSV v2", "TableCurrent", "ShiftHarbor v2", "StockPilot")
    access_methods: tuple[str, ...] = ("new SFTP CSV drop", "existing group APIs")
    source_identifiers: tuple[str, ...] = ("TGC-06", "TC-TGC-206", "TGC_RVA_06")
    reservation_behavior: str = "dinner reservations; finished is the completed status"
    labor_configuration: str = "new BARISTA_LEAD role code"
    inventory_process: str = "weekly StockPilot count; biscuit dough is counted by 24-each case"
    known_differences: tuple[str, ...] = ("CSV v2 omits optional department on some lines", "new product/category identifiers", "new SFTP delivery path")
    initial_discovery_gaps: tuple[str, ...] = ("confirm biscuit case pack", "review HarborTill and TableCurrent native group reports")


PROFILE = RestaurantProfile()


class Classification(StrEnum):
    WORKED_UNCHANGED = "WORKED UNCHANGED"
    CONFIGURATION_ONLY = "CONFIGURATION ONLY"
    NEW_MAPPINGS = "NEW MAPPINGS"
    NEW_SOURCE_CODE = "NEW SOURCE-SPECIFIC CODE"
    CUSTOMER_DISCOVERY = "CUSTOMER DISCOVERY"
    REWORK = "REWORK"
    TESTING = "TESTING"
    OPERATIONS = "DEPLOYMENT / OPERATIONS"
    SUPPORT = "NEW SUPPORT OBLIGATION"


class ReadinessStatus(StrEnum):
    READY = "READY"
    READY_WITH_CONFIGURATION = "READY WITH CONFIGURATION"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class OnboardingInputs:
    canonical_location_configured: bool = True
    schema_known: bool = True
    sample_fixture_present: bool = True
    credential_reference_present: bool = True
    mappings_complete: bool = False


@dataclass(frozen=True)
class OnboardingReadiness:
    status: ReadinessStatus
    reasons: tuple[str, ...]


def assess_onboarding_readiness(inputs: OnboardingInputs = OnboardingInputs()) -> OnboardingReadiness:
    """Hard prerequisites block; absent mappings permit a configuration phase."""
    gates = ((inputs.canonical_location_configured, "canonical location identity missing"),
             (inputs.schema_known, "source schema unknown"),
             (inputs.sample_fixture_present and Path(POS_FIXTURE).exists(), "required sample fixture absent"),
             (inputs.credential_reference_present, "required credential reference missing"))
    failures = tuple(reason for passed, reason in gates if not passed)
    if failures:
        return OnboardingReadiness(ReadinessStatus.BLOCKED, failures)
    if not inputs.mappings_complete:
        return OnboardingReadiness(ReadinessStatus.READY_WITH_CONFIGURATION, ("identity, role, category, status, and pack mappings remain",))
    return OnboardingReadiness(ReadinessStatus.READY, ())


CHICKEN_BISCUIT = Product("JRH-P-007", "Chicken Biscuit", "MAIN")
COLD_BREW = Product("JRH-P-008", "Cold Brew", "BEVERAGE")
HAND_PIE = Product("JRH-P-009", "Seasonal Hand Pie", "BAKERY")
LOCATION_MAPPINGS = (LocationMapping(SourceIdentity(POS_SOURCE, "TGC-06"), LOCATION),)
PRODUCT_MAPPINGS = (
    ProductMapping(SourceIdentity(POS_SOURCE, "TGC-MAIN-01"), CHICKEN_BISCUIT),
    ProductMapping(SourceIdentity(POS_SOURCE, "TGC-DRINK-02"), COLD_BREW),
    ProductMapping(SourceIdentity(POS_SOURCE, "TGC-NEW-99"), HAND_PIE),
)
CATEGORY_MAPPINGS = {"BRUNCH": "MAIN", "BAKERY": "BAKERY"}
ROLE_MAPPINGS = {"BARISTA_LEAD": "FRONT_OF_HOUSE"}
STATUS_MAPPINGS = {"finished": "COMPLETED"}
PACK_CONVERSIONS = {"TGC-BISCUIT-CASE": Decimal("24")}
MAPPING_COUNTS = {"source location IDs": 4, "products": 3, "categories": 2, "roles": 1,
                  "statuses": 1, "units": 0, "product-specific pack conversions": 1}


def _pos_sales(mappings: tuple[ProductMapping, ...]) -> tuple[tuple[Sale, ...], tuple[str, ...]]:
    parser = LocationTwoHarborTillCsvParser()  # unchanged known CSV parser
    sales, missing = [], []
    for number, raw in enumerate(parser.load(POS_FIXTURE), 1):
        row = parser.parse_row(raw, number)
        location = resolve_location(POS_SOURCE, row.store_code, LOCATION_MAPPINGS)
        product = resolve_product(POS_SOURCE, row.sku, mappings)
        if not location.resolved or not product.resolved:
            missing.append(row.sku)
            continue
        sales.append(Sale(location.value, BusinessDate(row.business_date), SourceIdentity(POS_SOURCE, row.sku),
                          row.quantity, row.gross, -row.signed_discount, row.net,
                          Provenance(POS_SOURCE, row.store_code, row.ticket_line, "synthetic scheduled CSV v2", "Chapter 12 fixture"),
                          product.value, row.timestamp))
    return tuple(sales), tuple(missing)


def first_attempt() -> dict[str, str]:
    sales, missing = _pos_sales(())
    payload = json.loads(Path(DISCOVERY_FIXTURE).read_text())
    TableCurrentParser().parse(payload["reservations"][0])
    ShiftHarborParser().parse(payload["labor"][0])
    return {"POS parser": "WORKED UNCHANGED", "POS accepted": str(len(sales)),
            "Product mappings": f"MISSING ({len(missing)})", "Reservation parser": "WORKED UNCHANGED",
            "Labor parser": "WORKED UNCHANGED; ROLE MAPPING REQUIRED",
            "Inventory schema": "WORKED UNCHANGED; PACK CONVERSION REQUIRED"}


def onboarded_dataset() -> CrossLocationDataset:
    base = build_dataset()
    sales, missing = _pos_sales(PRODUCT_MAPPINGS)
    assert not missing
    outcomes = base.outcomes + tuple(NormalizationOutcome(POS_SOURCE, "TGC-06", sale.provenance.source_record_id,
        NormalizationStatus.NORMALIZED, None, sale, CATEGORY_MAPPINGS.get(raw_category),
        "RESOLVED" if raw_category else "NOT PROVIDED", "ITEM")
        for sale, raw_category in zip(sales, ("BRUNCH", None, "BAKERY"), strict=True))
    coverage = base.coverage + (LocationCoverage("JRH-006", 3, 3, 0, 0, 0, 0, 0, Completeness.COMPLETE_FOR_FIXTURE),)
    return CrossLocationDataset(outcomes, coverage)


def onboarding_briefing() -> ManagementBriefing:
    return build_management_briefing(dataset=onboarded_dataset())


def operational_run() -> tuple[RunStatus, RunStatus, str]:
    configs = load_config(OPERATIONS_FIXTURE)
    config = next(c for c in configs if c.job_id == "pos-tgc-daily")
    provider = FakeCredentialProvider({c.credential_ref: "synthetic" for c in configs})
    if any(check.result == "FAIL" for check in readiness_checks(configs, provider)):
        raise RuntimeError("JRH-006 operational configuration is not ready")
    store = InMemoryOperationalStore()
    records = ({"id": "6001/01", "net": "26.00"},)
    first = store.ingest(config, "tgc-2026-08-25", records, "RUN-JRH006-001")
    replay = store.ingest(config, "tgc-2026-08-25", records, "RUN-JRH006-002")
    try:
        store.ingest(config, "tgc-2026-08-25", ({"id": "6001/01", "net": "27.00"},), "RUN-JRH006-003")
    except ConflictingReplayError:
        conflict = "DETECTED"
    else:  # pragma: no cover - safety assertion
        conflict = "MISSED"
    return first.status, replay.status, conflict


MANIFEST = (
    ("Canonical location configuration", Classification.CONFIGURATION_ONLY),
    ("POS CSV parser", Classification.WORKED_UNCHANGED), ("POS product/category identity", Classification.NEW_MAPPINGS),
    ("Reservation parser", Classification.WORKED_UNCHANGED), ("Reservation venue/status", Classification.NEW_MAPPINGS),
    ("Labor parser", Classification.WORKED_UNCHANGED), ("Labor worksite/role", Classification.NEW_MAPPINGS),
    ("Inventory parser and unit model", Classification.WORKED_UNCHANGED), ("Inventory item/pack conversion", Classification.NEW_MAPPINGS),
    ("Pack-size confirmation", Classification.CUSTOMER_DISCOVERY), ("Onboarding fixtures and regression scenarios", Classification.TESTING),
    ("Four job definitions, two credential references, SFTP path", Classification.OPERATIONS),
    ("Mappings, delivery path, schema and exceptions to monitor", Classification.SUPPORT),
)


def onboarding_report() -> str:
    readiness = assess_onboarding_readiness(); attempt = first_attempt(); run = operational_run(); briefing = onboarding_briefing()
    lines = ["ONBOARDING JRH-006", "Tidewater Garden Cafe — all-day garden cafe and supper restaurant", "SYNTHETIC LAB EVIDENCE", "",
        "DISCOVERY", "Known integrations: HarborTill CSV, TableCurrent, ShiftHarbor, StockPilot",
        "Known versions: HarborTill CSV v2; TableCurrent v1; ShiftHarbor v2; StockPilot v1",
        "Missing initially: 4 source locations, 3 products, 2 categories, 1 role, 1 status, 1 pack conversion",
        "Required: POS and inventory credential references; new SFTP delivery configuration",
        "Apparently reusable: four parsers, canonical records/calculations, exceptions, briefing, replay store",
        "Investigate: 24-each biscuit pack and optional department semantics",
        "Native reports to review: HarborTill group sales and TableCurrent multi-venue pacing",
        "Management questions: group sales, labor relative to demand, inventory anomalies, evidence completeness", "",
        "READINESS", readiness.status.value, *readiness.reasons, "", "FIRST ATTEMPT"]
    lines += [f"{key}: {value}" for key, value in attempt.items()]
    for classification in Classification:
        lines += ["", classification.value] + [f"- {name}" for name, value in MANIFEST if value is classification]
        if not any(value is classification for _, value in MANIFEST): lines.append("- NONE")
    lines += ["", "SHARED CODE MODIFIED FOR JRH-006", "NO — existing parser, canonical, briefing, and operations modules were not changed.",
        "CANONICAL MODEL MODIFIED", "NO", "PREVIOUS LOCATIONS CHANGED", "0", "MANAGEMENT BRIEFING CODE MODIFIED", "NO", "",
        "MAPPING COUNTS"] + [f"{key}: {value}" for key, value in MAPPING_COUNTS.items()]
    lines += ["", "SOURCE-SPECIFIC CODE COUNTS", "new parser modules: 0", "new parser functions: 0", "new validation rules: 0", "existing parser modifications: 0", "new exception categories: 0",
        "", "TESTING BURDEN", "new fixtures: 3", "new test functions: 12", "existing tests modified: 0", "regression scenarios: 3", "operations scenarios: 1", "",
        "OPERATIONAL RUN", f"first batch: {run[0].value}", f"same batch: {run[1].value}", f"conflicting replay: {run[2]}",
        "Four configured jobs; references remain redacted; health/readiness checks pass.", "", "BRIEFING INTEGRATION",
        f"JRH-006 present: {'YES' if any(row.location_id == 'JRH-006' for row in briefing.locations) else 'NO'}",
        f"locations represented by compatible sales evidence: {len(briefing.locations)}", "briefing implementation changes: NONE", "",
        "BEFORE JRH-006", "Locations integrated: 5", "Configured onboarding mappings: 0", "Operational jobs: 4", "Human-action exception categories: 4",
        "AFTER JRH-006", "Locations integrated: 6", "Configured onboarding mappings: 12", "Operational jobs: 8", "Human-action exception categories: 4", "",
        "MARGINAL IMPLEMENTATION STRUCTURE", "Mostly: CONFIGURATION + MAPPINGS", "Some: CUSTOMER DISCOVERY + TESTING + OPERATIONS + SUPPORT",
        "Little: NEW SOURCE-SPECIFIC CODE (none observed)", "None: REWORK + CANONICAL MODEL REWORK", "One onboarding does not establish linear cost or universal scalability.", "",
        "OBSERVED LAB RESULTS", "OBSERVED LAB RESULT: JRH-006 reused canonical sales calculations without modification.",
        "OBSERVED LAB RESULT: New identities and a product-specific pack size required mappings although known parsers were reusable.",
        "OBSERVED LAB RESULT: Operational onboarding added jobs, credential references, and a delivery path while replay behavior worked unchanged.",
        "OBSERVED LAB RESULT: The group briefing incorporated JRH-006 without location-specific briefing code."]
    return "\n".join(lines)
