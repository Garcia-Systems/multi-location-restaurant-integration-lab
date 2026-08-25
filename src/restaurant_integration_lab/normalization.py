"""Chapter 5's explicit, deliberately narrow cross-location normalization layer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Iterable

from .ingestion import ExceptionCategory, IngestionException
from .location1 import LocationOneSalesImporter
from .location2 import LocationTwoSalesImporter
from .model_demo import CST, OYSTERS, RRK
from .operational_model import LocationMapping, Product, ProductMapping, Sale, SourceIdentity, resolve_location, resolve_product


class NormalizationStatus(StrEnum):
    NORMALIZED = "NORMALIZED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


class MissingValue(StrEnum):
    UNKNOWN = "UNKNOWN"
    NOT_PROVIDED = "NOT PROVIDED"
    NOT_APPLICABLE = "NOT APPLICABLE"


class Completeness(StrEnum):
    COMPLETE_FOR_FIXTURE = "COMPLETE FOR FIXTURE"
    PARTIAL = "PARTIAL"


class ProductMappingStatus(StrEnum):
    RESOLVED = "RESOLVED"
    EXPLICITLY_UNMAPPED = "EXPLICITLY UNMAPPED"
    CONFLICT = "CONFLICT"
    RETIRED = "RETIRED / LEGACY"


# Inspectable configuration: no filename/name inference and no fuzzy matching.
LOCATION_MAPPINGS = (
    LocationMapping(SourceIdentity("HarborTill RRK", "POS-WBG-14"), RRK),
    LocationMapping(SourceIdentity("HarborTill CST", "CST-02"), CST),
    # Documented aliases demonstrate that mappings, not naming resemblance, establish identity.
    LocationMapping(SourceIdentity("SOURCE SYSTEM A", "store_14"), RRK),
    LocationMapping(SourceIdentity("SOURCE SYSTEM B", "WBG02"), CST),
)

STEAK = Product("JRH-P-002", "Bistro Steak", "MAIN")
RUM_PUNCH = Product("JRH-P-003", "River Rum Punch", "BEVERAGE")
HORCHATA = Product("JRH-P-004", "Horchata", "BEVERAGE")
CHIPS = Product("JRH-P-005", "Chips", "SIDE")
SEASONAL_TACO = Product("JRH-P-006", "Seasonal Taco", "MAIN")
PRODUCT_CATALOG = (OYSTERS, STEAK, RUM_PUNCH, HORCHATA, CHIPS, SEASONAL_TACO)
PRODUCT_MAPPINGS = (
    ProductMapping(SourceIdentity("HarborTill RRK", "MENU-771"), OYSTERS),
    ProductMapping(SourceIdentity("HarborTill CST", "ENTREE-044"), OYSTERS),
    ProductMapping(SourceIdentity("HarborTill RRK", "MENU-204"), STEAK),
    ProductMapping(SourceIdentity("HarborTill RRK", "MENU-910"), RUM_PUNCH),
    ProductMapping(SourceIdentity("HarborTill CST", "DRINK-010"), HORCHATA),
    ProductMapping(SourceIdentity("HarborTill CST", "SIDE-003"), CHIPS),
)
EXPLICITLY_UNMAPPED_PRODUCTS = {
    SourceIdentity("HarborTill RRK", "MENU-NEW"),
    SourceIdentity("HarborTill CST", "NEW-777"),
}
RETIRED_PRODUCTS = {SourceIdentity("HarborTill RRK", "MENU-OLD")}
CATEGORY_MAPPINGS = {
    ("HarborTill RRK", "Entrees"): "MAIN",
    ("HarborTill RRK", "Bar"): "BEVERAGE",
    ("HarborTill CST", "MAINS"): "MAIN",
    ("HarborTill CST", "BEVS"): "BEVERAGE",
    ("HarborTill CST", "EXTRAS"): "SIDE",
}


@dataclass(frozen=True)
class NormalizationOutcome:
    source_system: str
    source_location_id: str
    source_record_id: str
    status: NormalizationStatus
    reason: str | None
    sale: Sale | None = None
    canonical_category: str | None = None
    category_state: str | None = None
    quantity_unit: str | None = None


@dataclass(frozen=True)
class ProductMappingResolution:
    status: ProductMappingStatus
    product: Product | None
    reason: str | None


def resolve_canonical_product(source_system: str, source_id: str,
                              mappings: tuple[ProductMapping, ...] = PRODUCT_MAPPINGS) -> ProductMappingResolution:
    """Resolve identity while exposing unmapped, conflicting, and legacy states."""
    identity = SourceIdentity(source_system, source_id)
    if identity in RETIRED_PRODUCTS:
        return ProductMappingResolution(ProductMappingStatus.RETIRED, None, "retired source identifier")
    matches = {item.product for item in mappings if item.source == identity}
    if len(matches) > 1:
        return ProductMappingResolution(ProductMappingStatus.CONFLICT, None, "conflicting explicit mappings")
    if len(matches) == 1:
        return ProductMappingResolution(ProductMappingStatus.RESOLVED, matches.pop(), None)
    reason = "explicitly unmapped; human mapping required" if identity in EXPLICITLY_UNMAPPED_PRODUCTS else "human mapping required"
    return ProductMappingResolution(ProductMappingStatus.EXPLICITLY_UNMAPPED, None, reason)


@dataclass(frozen=True)
class LocationCoverage:
    canonical_location_id: str
    rows_parsed: int
    fully_normalized: int
    partial: int
    rejected_structurally: int
    unresolved_product: int
    unresolved_location: int
    duplicate: int
    completeness: Completeness


@dataclass(frozen=True)
class ProductTotals:
    totals: tuple[tuple[str, Decimal], ...]
    excluded_count: int
    excluded: tuple[NormalizationOutcome, ...]


@dataclass(frozen=True)
class CrossLocationDataset:
    outcomes: tuple[NormalizationOutcome, ...]
    coverage: tuple[LocationCoverage, ...]

    @property
    def accepted_sales(self) -> tuple[Sale, ...]:
        return tuple(item.sale for item in self.outcomes if item.sale is not None)

    @property
    def unresolved(self) -> tuple[NormalizationOutcome, ...]:
        return tuple(item for item in self.outcomes if item.status is not NormalizationStatus.NORMALIZED)

    def sales_by_location(self) -> tuple[tuple[str, Decimal], ...]:
        return _sum_by(self.accepted_sales, lambda sale: sale.location.canonical_id)

    def sales_by_business_date(self) -> tuple[tuple[str, Decimal], ...]:
        return _sum_by(self.accepted_sales, lambda sale: str(sale.business_date))

    def product_totals(self) -> ProductTotals:
        safe = tuple(item.sale for item in self.outcomes if item.sale is not None and item.sale.product is not None)
        excluded = tuple(item for item in self.outcomes if item.reason == "unresolved product identity")
        return ProductTotals(_sum_by(safe, lambda sale: sale.product.canonical_id), len(excluded), excluded)


def _sum_by(sales: Iterable[Sale], key) -> tuple[tuple[str, Decimal], ...]:
    totals: dict[str, Decimal] = {}
    for sale in sales:
        name = key(sale)
        totals[name] = totals.get(name, Decimal("0")) + sale.net_amount
    return tuple(sorted(totals.items()))


def normalize_category(source_system: str, value: str | None) -> tuple[str | None, str]:
    if value is None or not value.strip():
        return None, MissingValue.NOT_PROVIDED.value
    mapped = CATEGORY_MAPPINGS.get((source_system, value))
    return (mapped, "RESOLVED") if mapped else (None, "UNRESOLVED — EXPLICIT MAPPING REQUIRED")


def normalize_discount(source_system: str, value: Decimal | None) -> Decimal | MissingValue:
    """Canonical discounts are positive reductions; absence stays unknown."""
    if value is None:
        return MissingValue.NOT_PROVIDED
    if source_system == "HarborTill CST":
        if value > 0:
            raise ValueError("CST discount must be zero or negative")
        return -value
    if value < 0:
        raise ValueError("RRK discount must be nonnegative")
    return value


def _exception_outcome(error: IngestionException, source_location: str) -> NormalizationOutcome:
    reasons = {
        ExceptionCategory.UNKNOWN_PRODUCT: "unresolved product identity",
        ExceptionCategory.UNKNOWN_LOCATION: "unresolved location identity",
        ExceptionCategory.DUPLICATE: "duplicate source identity",
    }
    return NormalizationOutcome(error.source, source_location, error.source_record_id,
        NormalizationStatus.PARTIAL if error.category in {ExceptionCategory.UNKNOWN_PRODUCT, ExceptionCategory.UNKNOWN_LOCATION} else NormalizationStatus.REJECTED,
        reasons.get(error.category, error.reason))


def _accepted_outcome(sale: Sale, category: str | None) -> NormalizationOutcome:
    canonical, state = normalize_category(sale.provenance.source_system, category)
    status = NormalizationStatus.NORMALIZED if canonical else NormalizationStatus.PARTIAL
    return NormalizationOutcome(sale.provenance.source_system, sale.provenance.source_location_id,
        sale.provenance.source_record_id, status, None if canonical else "unresolved category classification",
        sale, canonical, state, "ITEM")


def build_dataset() -> CrossLocationDataset:
    """Build deterministic Chapter 5 evidence without changing either source parser."""
    one, two = LocationOneSalesImporter().ingest(), LocationTwoSalesImporter().ingest()
    one_categories = {"CHK-1001:1": "Raw Bar", "CHK-1002:1": "Entrees", "CHK-1003:1": "Raw Bar", "CHK-1004:1": "Bar"}
    two_categories = {"9001/01": "MAINS", "9002/01": "BEVS", "9003/01": None, "9004/01": "EXTRAS"}
    outcomes = [*(_accepted_outcome(s, one_categories[s.provenance.source_record_id]) for s in one.sales),
                *(_exception_outcome(e, "POS-WBG-14" if e.category is not ExceptionCategory.UNKNOWN_LOCATION else "CST-02") for e in one.exceptions),
                *(_accepted_outcome(s, two_categories[s.provenance.source_record_id]) for s in two.sales),
                *(_exception_outcome(e, "CST-02" if e.category is not ExceptionCategory.UNKNOWN_LOCATION else "WRONG-STORE") for e in two.exceptions)]
    def coverage(result, canonical: str, source: str) -> LocationCoverage:
        relevant = [o for o in outcomes if o.source_system == source]
        category = lambda c: sum(e.category is c for e in result.exceptions)
        excluded = category(ExceptionCategory.UNKNOWN_PRODUCT) + category(ExceptionCategory.UNKNOWN_LOCATION)
        return LocationCoverage(canonical, result.rows_read,
            sum(o.status is NormalizationStatus.NORMALIZED for o in relevant),
            sum(o.status is NormalizationStatus.PARTIAL for o in relevant),
            category(ExceptionCategory.MALFORMED_RECORD) + category(ExceptionCategory.VALIDATION_FAILURE),
            category(ExceptionCategory.UNKNOWN_PRODUCT), category(ExceptionCategory.UNKNOWN_LOCATION),
            category(ExceptionCategory.DUPLICATE), Completeness.PARTIAL if excluded else Completeness.COMPLETE_FOR_FIXTURE)
    return CrossLocationDataset(tuple(outcomes), (coverage(one, "JRH-001", "HarborTill RRK"), coverage(two, "JRH-002", "HarborTill CST")))


def mapping_change_experiment() -> tuple[str, str]:
    before = resolve_canonical_product("HarborTill CST", "NEW-777")
    configured = PRODUCT_MAPPINGS + (ProductMapping(SourceIdentity("HarborTill CST", "NEW-777"), SEASONAL_TACO),)
    after = resolve_canonical_product("HarborTill CST", "NEW-777", configured)
    return before.status.value, after.product.canonical_id if after.product else "unresolved"


def normalization_report() -> str:
    data = build_dataset(); products = data.product_totals(); before, after = mapping_change_experiment()
    lines = ["CROSS-LOCATION NORMALIZATION", "SYNTHETIC LAB EVIDENCE", "", "LOCATIONS", "JRH-001 — River & Rail Kitchen", "JRH-002 — Canal Street Tacos", "",
        "LOCATION IDENTITY", "SOURCE SYSTEM A / store_14 -> JRH-001", "SOURCE SYSTEM B / WBG02 -> JRH-002", "Unknown identifiers -> PARTIAL; explicit mapping required", "",
        "PRODUCT MAPPINGS", "HarborTill RRK / MENU-771 -> JRH-P-001", "HarborTill CST / ENTREE-044 -> JRH-P-001", "Unknown identifiers are not name-matched", "",
        "CATEGORY MAPPINGS", "Entrees + MAINS -> MAIN", "Raw Bar -> UNRESOLVED", "Blank department -> NOT PROVIDED", "",
        "BUSINESS-DATE NORMALIZATION", "RRK: timestamp with explicit 04:00 cutoff", "CST: source SaleDate is authoritative", "",
        "MONEY SEMANTICS", "gross >= 0; discount is a positive reduction; net = gross - discount; Decimal only", "CST signed-negative discounts are inverted explicitly", "",
        "NORMALIZATION COVERAGE"]
    for c in data.coverage:
        lines.extend([c.canonical_location_id, f"Rows parsed: {c.rows_parsed}", f"Fully normalized: {c.fully_normalized}", f"Partial: {c.partial}", f"Rejected structurally: {c.rejected_structurally}", f"Unresolved product: {c.unresolved_product}", f"Unresolved location: {c.unresolved_location}", f"Duplicate: {c.duplicate}", f"Fixture completeness: {c.completeness.value}"])
    lines.extend(["", "FULLY NORMALIZED RECORDS", str(sum(o.status is NormalizationStatus.NORMALIZED for o in data.outcomes)), "", "UNRESOLVED RECORDS"])
    lines.extend(f"{o.source_system} / {o.source_record_id}: {o.reason}" for o in data.unresolved)
    lines.extend(["", "SAFE CROSS-LOCATION CALCULATIONS", "Sales by canonical location:"])
    lines.extend(f"{k}: ${v:.2f}" for k, v in data.sales_by_location())
    lines.append("Sales by canonical product:"); lines.extend(f"{k}: ${v:.2f}" for k, v in products.totals)
    lines.extend(["", "EXCLUDED EVIDENCE", f"Excluded from product comparison: {products.excluded_count}", "Reason: unresolved product identity", "",
        "MAPPING CHANGE EXPERIMENT", f"Before: unresolved ({before})", f"After: resolved through configuration -> {after}", "Parser changes: none", "",
        "ENGINEERING EVIDENCE", "DEMONSTRATED REUSE: Sale, BusinessDate, Provenance, Decimal calculations, mapping and exception machinery", "CONFIGURATION WORK: location, product, and category mapping records", "NEW SHARED WORK: outcomes, coverage, completeness, and safe cross-location views", "SOURCE-SPECIFIC WORK: RRK JSON/cutoff and CST CSV/date/signed-discount/void behavior remain separate", "REWORK: none in Chapter 5; source adapters and canonical Sale were unchanged", "Entire Location #1 duplicated for Location #2: NO", "Adding Location #2 was configuration-only: NO", "",
        "OBSERVED LAB RESULTS", "OBSERVED LAB RESULT: Cross-location product comparison requires explicit canonical identity mappings.", "OBSERVED LAB RESULT: A product mapping can resolve an integration difference without parser changes.", "OBSERVED LAB RESULT: Canonical monetary semantics prevent source discount signs from leaking into totals.", "OBSERVED LAB RESULT: Unresolved evidence remains visible while unsafe aggregation excludes it."])
    return "\n".join(lines)
