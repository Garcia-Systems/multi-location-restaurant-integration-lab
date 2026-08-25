"""Chapter 13: deliberately non-standard seventh-location experiment."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from enum import StrEnum
from importlib.resources import files
from pathlib import Path

from .briefing import EvidenceState, ManagementBriefing, build_management_briefing
from .labor import LaborDemandContext
from .location2 import LocationTwoHarborTillCsvParser
from .normalization import (Completeness, CrossLocationDataset, LocationCoverage,
                            NormalizationOutcome, NormalizationStatus, build_dataset)
from .operational_model import (BusinessDate, Location, Product, Provenance, Sale,
                                SourceIdentity)
from .operations import SourceConfiguration, load_config

LOCATION = Location("JRH-007", "Old Dominion Roadhouse")
POS_SOURCE = "MillLedger Legacy POS"
WEEK1 = files("restaurant_integration_lab").joinpath("fixtures/jrh007_legacy_pos_week1.synthetic.csv")
WEEK2 = files("restaurant_integration_lab").joinpath("fixtures/jrh007_legacy_pos_week2.synthetic.csv")
LABOR = files("restaurant_integration_lab").joinpath("fixtures/jrh007_labor.synthetic.csv")
INVENTORY = files("restaurant_integration_lab").joinpath("fixtures/jrh007_inventory.synthetic.csv")
OPERATIONS = files("restaurant_integration_lab").joinpath("fixtures/jrh007_operations.synthetic.json")


@dataclass(frozen=True)
class RestaurantProfile:
    canonical_location_id: str = "JRH-007"
    name: str = "Old Dominion Roadhouse"
    concept: str = "recently acquired roadside grill with counter lunch and late table-service dinner"
    operating_characteristics: tuple[str, ...] = ("closed Mondays", "service after midnight belongs to the prior trading day")
    legacy_systems: tuple[str, ...] = ("MillLedger Legacy POS", "manager labor workbook", "manual inventory workbook")
    access_methods: tuple[str, ...] = ("manager-uploaded CSV files", "irregular weekly shared-folder delivery")
    source_identifiers: tuple[str, ...] = ("OLD-MILL", "workbook has no stable shift or inventory record IDs")
    reservation_behavior: str = "walk-in only; reservations are NOT APPLICABLE"
    labor_process: str = "worked and scheduled hours spreadsheet; one row lacks cost; local roles"
    inventory_process: str = "manually edited counts with variable names/units and no pack table"
    reporting_limits: tuple[str, ...] = ("three weeks history", "item names replace stable product IDs", "schema changed between exports")
    known_quality_issues: tuple[str, ...] = ("unstable headers", "missing labor cost", "mixed inventory units", "incomplete count")
    discovery_gaps: tuple[str, ...] = ("pack conversions", "receipt uniqueness across resets", "source correction owner")


PROFILE = RestaurantProfile()


class Gap(StrEnum):
    SAME_INTERFACE = "SAME SYSTEM / SAME INTERFACE"
    SAME_DIFFERENT_CONFIG = "SAME SYSTEM / DIFFERENT CONFIGURATION"
    DIFFERENT_COMPATIBLE = "DIFFERENT SYSTEM / COMPATIBLE DATA"
    NEW_ADAPTER = "DIFFERENT SYSTEM / NEW ADAPTER REQUIRED"
    MANUAL = "MANUAL PROCESS"
    UNAVAILABLE = "DATA UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


DISCOVERY = (
    ("Canonical location identity", Gap.SAME_DIFFERENT_CONFIG, "new explicit JRH-007 mapping"),
    ("POS", Gap.NEW_ADAPTER, "different family, headers, date and name-only products"),
    ("Reservations", Gap.UNAVAILABLE, "walk-in concept; NOT APPLICABLE rather than zero"),
    ("Labor", Gap.NEW_ADAPTER, "manual workbook is compatible only after a strict parser and role mapping"),
    ("Inventory", Gap.MANUAL, "mixed units, names and missing pack evidence"),
    ("Delivery", Gap.MANUAL, "irregular manager uploads"),
    ("Business date", Gap.DIFFERENT_COMPATIBLE, "MM/DD/YYYY trading day translates to canonical date"),
    ("Receipt reset behavior", Gap.UNKNOWN, "discovery has not established durable uniqueness"),
)


class UnsupportedLegacySchema(ValueError):
    pass


@dataclass(frozen=True)
class LegacyPosRow:
    business_date: BusinessDate
    receipt: str
    item_name: str
    quantity: Decimal
    net: Decimal


class MillLedgerWeekOneParser:
    """Minimum source-specific parser; deliberately does not guess future headers."""
    required = ("Trading Day", "Outlet", "Receipt", "Item Name", "Qty", "Net")

    def load(self, path: str | Path = WEEK1) -> tuple[LegacyPosRow, ...]:
        with Path(path).open(newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != self.required:
                raise UnsupportedLegacySchema(
                    f"explicit week1 schema required; received {tuple(reader.fieldnames or ())}"
                )
            return tuple(LegacyPosRow(BusinessDate(datetime.strptime(r["Trading Day"], "%m/%d/%Y").date()),
                                      r["Receipt"], r["Item Name"], Decimal(r["Qty"]), Decimal(r["Net"]))
                         for r in reader)


CHEESEBURGER = Product("JRH-P-010", "Classic Cheeseburger", "MAIN")
SWEET_TEA = Product("JRH-P-011", "Sweet Tea", "BEVERAGE")
# Exact strings are approvals, not a fuzzy/normalization algorithm.
HUMAN_APPROVED_NAME_MAPPINGS = {"Classic Cheeseburger": CHEESEBURGER, "Sweet Tea": SWEET_TEA}
LABOR_ROLE_MAPPINGS = {"Floor": "FRONT_OF_HOUSE", "Cook I": "BACK_OF_HOUSE"}


def map_product(item_name: str, approvals: dict[str, Product] | None = None) -> Product | None:
    """Resolve only an exact, human-approved legacy name."""
    return (approvals or {}).get(item_name)


def existing_onboarding_attempt() -> tuple[tuple[str, str], ...]:
    try:
        LocationTwoHarborTillCsvParser().load(WEEK1)
        pos = "PASS"  # pragma: no cover - existing parser currently rejects
    except (KeyError, ValueError) as error:
        pos = f"FAIL — unsupported source schema ({type(error).__name__})"
    return (("Location configuration", "PASS"), ("POS parser", pos),
            ("Product mappings", "BLOCKED — no stable source IDs"),
            ("Labor parser", "FAIL — unsupported manual spreadsheet schema"),
            ("Operations scheduling", "PARTIAL — files are manually delivered"),
            ("Management briefing", "BLOCKED until canonical evidence exists"))


def stress_dataset() -> CrossLocationDataset:
    base = build_dataset(); outcomes = list(base.outcomes); accepted = 0; unresolved = 0
    for row in MillLedgerWeekOneParser().load():
        product = map_product(row.item_name, HUMAN_APPROVED_NAME_MAPPINGS)
        if product is None:
            unresolved += 1
            outcomes.append(NormalizationOutcome(POS_SOURCE, "OLD-MILL", row.receipt,
                NormalizationStatus.PARTIAL, "HUMAN-MAINTAINED NAME MAPPING REQUIRED", None, None, "UNRESOLVED", "ITEM"))
            continue
        accepted += 1
        sale = Sale(LOCATION, row.business_date, SourceIdentity(POS_SOURCE, row.item_name), row.quantity,
                    row.net, Decimal(), row.net,
                    Provenance(POS_SOURCE, "OLD-MILL", row.receipt, "manual week1 CSV", "synthetic acquisition fixture"), product)
        outcomes.append(NormalizationOutcome(POS_SOURCE, "OLD-MILL", row.receipt,
            NormalizationStatus.NORMALIZED, None, sale, product.category, "RESOLVED BY HUMAN-APPROVED EXACT NAME", "ITEM"))
    coverage = base.coverage + (LocationCoverage("JRH-007", 3, accepted, unresolved, 0, unresolved, 0, 0, Completeness.PARTIAL),)
    return CrossLocationDataset(tuple(outcomes), coverage)


def labor_context() -> LaborDemandContext:
    with Path(LABOR).open(newline="") as handle: rows = tuple(csv.DictReader(handle))
    if any(row["Role"] not in LABOR_ROLE_MAPPINGS for row in rows):
        raise ValueError("unknown local labor role; explicit mapping required")
    # The workbook has no shift ID. This composite is inspectable but vulnerable
    # to manager edits, so operations must monitor it as unstable identity.
    source_record_ids = tuple(f'{row["Employee"]}|{row["Clock In"]}' for row in rows)
    assert len(source_record_ids) == len(set(source_record_ids))
    worked = sum((Decimal(row["Worked Hours"]) for row in rows), Decimal())
    sales = sum((sale.net_amount for sale in stress_dataset().accepted_sales if sale.location == LOCATION), Decimal())
    # Timestamp parsing proves the overnight row is explicit; clock-out is not guessed.
    assert datetime.fromisoformat(rows[0]["Clock Out"]) > datetime.fromisoformat(rows[0]["Clock In"])
    return LaborDemandContext("JRH-007", BusinessDate.from_local_timestamp(datetime.fromisoformat(rows[0]["Clock In"]), time(4)),
                              sales, worked, sales / worked, None, None, None, None)


def inventory_assessment() -> tuple[str, tuple[str, ...]]:
    return "NOT SAFE FOR GROUP RECONCILIATION", ("missing stable SKU", "Burger Patties/burger patty vary by row",
        "case-to-each and jug conversions unavailable", "one count missing", "categories conflict")


def stress_briefing() -> ManagementBriefing:
    return build_management_briefing(dataset=stress_dataset(), labor=(labor_context(),))


def operational_config() -> tuple[SourceConfiguration, ...]:
    return load_config(OPERATIONS)


REUSE_EROSION = (
    ("Canonical location identity", "SURVIVED WITH CONFIGURATION"),
    ("Canonical BusinessDate", "SURVIVED WITH CONFIGURATION"),
    ("Canonical sales calculation", "SURVIVED UNCHANGED"),
    ("HarborTill POS parser", "FAILED TO APPLY"),
    ("Stable source-ID product resolution", "FAILED TO APPLY"),
    ("Canonical labor context", "REQUIRED EXTENSION"),
    ("Inventory normalization/reconciliation", "FAILED TO APPLY"),
    ("Management briefing", "REQUIRED EXTENSION"),
    ("Automated operational delivery", "CAUSED REWORK"),
)

SUPPORT_OBLIGATIONS = ("manual file delivery monitoring", "week-specific schema monitoring",
    "human-maintained exact-name mappings", "missing-unit and pack investigations",
    "missing labor-cost follow-up", "recurring source-correction workflow")

COMPARISON = (
    ("systems reused unchanged", "JRH-006: 4", "JRH-007: 0"),
    ("parsers reused unchanged", "JRH-006: 4", "JRH-007: 0"),
    ("new parsers required", "JRH-006: 0", "JRH-007: 2"),
    ("mappings required", "JRH-006: stable ID/configuration mappings", "JRH-007: location, roles, exact names"),
    ("unstable mappings", "JRH-006: none", "JRH-007: 2 human-maintained product names"),
    ("validation rules added", "JRH-006: 0", "JRH-007: strict week1 POS schema"),
    ("shared code modified", "JRH-006: no", "JRH-007: reservation availability + CLI"),
    ("canonical model modified", "JRH-006: no", "JRH-007: no"),
    ("operational jobs/configuration", "JRH-006: 4", "JRH-007: 3 manual-drop jobs"),
    ("unresolved evidence", "JRH-006: none after mapping", "JRH-007: product, labor cost, inventory"),
    ("briefing limitations", "JRH-006: none location-specific", "JRH-007: partial sales/labor; no reservation; unsafe inventory"),
    ("support obligations", "JRH-006: mappings/path/schema", "JRH-007: 6 recurring manual/instability surfaces"),
)


def stress_test_report() -> str:
    attempt = existing_onboarding_attempt(); dataset = stress_dataset(); briefing = stress_briefing()
    row = next(x for x in briefing.locations if x.location_id == "JRH-007")
    try: MillLedgerWeekOneParser().load(WEEK2)
    except UnsupportedLegacySchema as error: schema = f"DETECTED — {error}"
    else: schema = "MISSED"  # pragma: no cover
    lines = ["STANDARDIZATION STRESS TEST — JRH-007", "Old Dominion Roadhouse — recently acquired roadside grill", "SYNTHETIC LAB EVIDENCE", "", "DISCOVERY"]
    lines += [f"{domain}: {gap.value} — {note}" for domain, gap, note in DISCOVERY]
    lines += ["", "STANDARDIZATION GAPS", "POS/labor require source-specific parsers; reservation data is not applicable; inventory remains manual and unsafe.",
              "Canonical location is compatible; canonical business date and management evidence survive after explicit translation.", "", "EXISTING ONBOARDING ATTEMPT"]
    lines += [f"{name}: {result}" for name, result in attempt]
    sections = {
        "WORKED UNCHANGED": ("canonical Sale calculations after ingestion", "canonical location aggregation", "evidence limitation presentation"),
        "CONFIGURATION ONLY": ("JRH-007 canonical identity", "manual-drop paths and credential reference"),
        "NEW MAPPINGS": ("local labor roles Floor/Cook I",),
        "UNSTABLE / HUMAN-MAINTAINED MAPPINGS": tuple(f'exact name "{name}" -> {product.canonical_id}' for name, product in HUMAN_APPROVED_NAME_MAPPINGS.items()),
        "NEW SOURCE-SPECIFIC CODE": ("YES", "MillLedgerWeekOneParser", "manual labor workbook parser boundary"),
        "REWORK": ("week 2 header change requires explicit parser/configuration work", "briefing reservation availability extended for JRH-007"),
        "PARTIAL / UNAVAILABLE EVIDENCE": (f"net sales: AVAILABLE/PARTIAL (${row.net_sales:.2f})", "product comparison: LIMITED — one unresolved exact name", "reservations: NOT APPLICABLE (never zero)", "labor: PARTIAL — worked hours available; cost unavailable", "inventory: NOT SAFE FOR GROUP RECONCILIATION"),
        "OPERATIONAL BURDEN": tuple(f"{c.job_id}: {c.interface_type}; {c.cadence.value}" for c in operational_config()),
        "SUPPORT OBLIGATION": SUPPORT_OBLIGATIONS,
        "MANAGEMENT BRIEFING RESULT": ("JRH-007 present: YES", f"sales coverage: {row.sales_state.value}", f"reservations: {row.reservation_state.value}", "labor cost percentage: OMITTED", "data-quality investigation: HIGH", "inventory reconciliation: NOT SUPPORTED"),
    }
    for title, values in sections.items(): lines += ["", title] + [f"- {value}" for value in values]
    lines += ["", "SCHEMA INSTABILITY", schema, "No alternate header inference or fuzzy matching is performed.", "", "JRH-006 vs JRH-007"]
    lines += [f"{category} | {six} | {seven}" for category, six, seven in COMPARISON]
    lines += ["", "REUSE EROSION"] + [f"{component}: {result}" for component, result in REUSE_EROSION]
    lines += ["", "BUILD-vs-BUY QUESTIONS", "- Would moving JRH-007 onto the group SaaS systems cost less than recurring adapter maintenance?", "- Could a BI/import tool safely handle the compatible high-level legacy exports?", "- Should inventory and product comparison be excluded from custom integration scope?", "- Is process standardization more valuable here than another software abstraction?", "These questions are recorded, not resolved.", "", "OBSERVED LAB RESULTS",
        "OBSERVED LAB RESULT: Canonical location and business-date concepts survived although source parsers did not.",
        "OBSERVED LAB RESULT: A different POS family required strict source-specific parsing code.",
        "OBSERVED LAB RESULT: Missing product IDs required human-maintained exact-name mappings; no fuzzy mapping was used.",
        "OBSERVED LAB RESULT: Partial canonical net sales remained usable while detailed product comparison and inventory reconciliation stayed limited.",
        "OBSERVED LAB RESULT: A changed export header was rejected and added a recurring support obligation."]
    return "\n".join(lines)
