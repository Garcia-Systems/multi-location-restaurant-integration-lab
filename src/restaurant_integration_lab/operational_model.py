"""Chapter 2's small canonical boundary and synthetic evidence fixtures.

This module translates no real source data.  Its maps are explicit lab fixtures
that demonstrate the boundary a later, source-specific translation must cross.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Generic, TypeVar


def _required(value: str, label: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{label} cannot be empty")


def _decimal(value: Decimal, label: str, *, nonnegative: bool = True) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    if nonnegative and value < 0:
        raise ValueError(f"{label} cannot be negative")


@dataclass(frozen=True)
class Location:
    canonical_id: str
    name: str

    def __post_init__(self) -> None:
        _required(self.canonical_id, "canonical location ID")
        _required(self.name, "location name")


@dataclass(frozen=True)
class BusinessDate:
    """An operational date, deliberately distinct from a timestamp."""

    value: date

    def __post_init__(self) -> None:
        if not isinstance(self.value, date) or isinstance(self.value, datetime):
            raise TypeError("business date must be a date")

    @classmethod
    def from_local_timestamp(cls, timestamp: datetime, day_starts_at: time) -> "BusinessDate":
        if not isinstance(timestamp, datetime) or not isinstance(day_starts_at, time):
            raise TypeError("timestamp and day start must be datetime and time")
        operational_date = timestamp.date()
        if timestamp.time() < day_starts_at:
            operational_date -= timedelta(days=1)
        return cls(operational_date)

    def __str__(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True)
class Product:
    canonical_id: str
    name: str
    category: str | None = None

    def __post_init__(self) -> None:
        _required(self.canonical_id, "canonical product ID")
        _required(self.name, "product name")


@dataclass(frozen=True)
class SourceIdentity:
    source_system: str
    source_identifier: str

    def __post_init__(self) -> None:
        _required(self.source_system, "source system")
        _required(self.source_identifier, "source identifier")


@dataclass(frozen=True)
class Provenance:
    source_system: str
    source_location_id: str
    source_record_id: str
    source_interface: str
    reference: str | None = None

    def __post_init__(self) -> None:
        for value, label in ((self.source_system, "source system"),
                             (self.source_location_id, "source location ID"),
                             (self.source_record_id, "source record ID"),
                             (self.source_interface, "source interface")):
            _required(value, label)


T = TypeVar("T")


@dataclass(frozen=True)
class Resolution(Generic[T]):
    source: SourceIdentity
    value: T | None
    reason: str | None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.reason is None):
            raise ValueError("resolution must be either successful or explicitly unresolved")

    @property
    def resolved(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class LocationMapping:
    source: SourceIdentity
    location: Location


@dataclass(frozen=True)
class ProductMapping:
    source: SourceIdentity
    product: Product


def resolve_location(source_system: str, source_location_id: str,
                     mappings: tuple[LocationMapping, ...]) -> Resolution[Location]:
    source = SourceIdentity(source_system, source_location_id)
    match = next((item.location for item in mappings if item.source == source), None)
    return Resolution(source, match, None if match else "UNKNOWN LOCATION — EXPLICIT MAPPING REQUIRED")


def resolve_product(source_system: str, source_product_id: str,
                    mappings: tuple[ProductMapping, ...]) -> Resolution[Product]:
    source = SourceIdentity(source_system, source_product_id)
    match = next((item.product for item in mappings if item.source == source), None)
    return Resolution(source, match, None if match else "HUMAN MAPPING REQUIRED")


@dataclass(frozen=True)
class Sale:
    location: Location
    business_date: BusinessDate
    source_product: SourceIdentity
    quantity: Decimal
    gross_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    provenance: Provenance
    product: Product | None = None
    transaction_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        for value, label in ((self.quantity, "quantity"), (self.gross_amount, "gross amount"),
                             (self.discount_amount, "discount amount"), (self.net_amount, "net amount")):
            _decimal(value, label)


@dataclass(frozen=True)
class Reservation:
    location: Location
    business_date: BusinessDate
    reservation_timestamp: datetime
    party_size: int
    status: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.party_size, int) or isinstance(self.party_size, bool):
            raise TypeError("party size must be an integer")
        if self.party_size < 0:
            raise ValueError("party size cannot be negative")
        _required(self.status, "reservation status")


@dataclass(frozen=True)
class LaborRecord:
    location: Location
    business_date: BusinessDate
    hours: Decimal
    provenance: Provenance
    role: str | None = None
    labor_cost: Decimal | None = None

    def __post_init__(self) -> None:
        _decimal(self.hours, "labor hours")
        if self.labor_cost is not None:
            _decimal(self.labor_cost, "labor cost")


@dataclass(frozen=True)
class InventoryRecord:
    location: Location
    business_date: BusinessDate
    source_product: SourceIdentity
    quantity: Decimal
    unit: str
    record_type: str
    provenance: Provenance
    product: Product | None = None

    def __post_init__(self) -> None:
        _decimal(self.quantity, "inventory quantity")
        _required(self.unit, "inventory unit")
        _required(self.record_type, "inventory record type")


@dataclass(frozen=True)
class FeedbackRecord:
    location: Location
    business_date: BusinessDate
    source: str
    provenance: Provenance
    rating: Decimal | None = None
    category: str | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        _required(self.source, "feedback source")
        if self.rating is not None:
            _decimal(self.rating, "rating")


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT APPLICABLE"
    NOT_CONFIGURED = "NOT CONFIGURED"


@dataclass(frozen=True)
class DomainEvidence:
    availability: Availability
    record_count: int | None = None

    def __post_init__(self) -> None:
        if self.availability is Availability.AVAILABLE:
            if not isinstance(self.record_count, int) or isinstance(self.record_count, bool) or self.record_count < 0:
                raise ValueError("available evidence requires a nonnegative record count")
        elif self.record_count is not None:
            raise ValueError("unavailable evidence cannot imply a record count")


def aggregate_inventory(records: tuple[InventoryRecord, ...]) -> tuple[Decimal, str]:
    if not records:
        raise ValueError("inventory records cannot be empty")
    units = {record.unit for record in records}
    products = {record.product for record in records}
    if len(units) != 1 or len(products) != 1 or None in products:
        raise ValueError("NOT COMBINABLE WITHOUT EXPLICIT CONVERSION OR PRODUCT MAPPING")
    return sum((record.quantity for record in records), Decimal("0")), next(iter(units))
