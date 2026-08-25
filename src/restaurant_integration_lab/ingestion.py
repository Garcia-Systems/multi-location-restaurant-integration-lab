"""Shared ingestion outcomes extracted after two concrete POS implementations existed."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from .operational_model import Sale


class ExceptionCategory(StrEnum):
    MALFORMED_RECORD = "MALFORMED RECORD"
    UNKNOWN_LOCATION = "UNKNOWN LOCATION"
    UNKNOWN_PRODUCT = "UNKNOWN PRODUCT"
    UNKNOWN_STATUS = "UNKNOWN STATUS"
    DUPLICATE = "DUPLICATE"
    VALIDATION_FAILURE = "VALIDATION FAILURE"
    UNKNOWN_INVENTORY_ITEM = "UNKNOWN INVENTORY ITEM"
    UNKNOWN_UNIT = "UNKNOWN UNIT"
    INCOMPATIBLE_UNIT = "INCOMPATIBLE UNIT"
    MISSING_CONVERSION = "MISSING CONVERSION"
    CONFLICTING_MAPPING = "CONFLICTING MAPPING"
    SCHEMA_CHANGE = "SCHEMA CHANGE"
    MISSING_REQUIRED_VALUE = "MISSING REQUIRED VALUE"
    LATE_DATA = "LATE DATA"
    CONFLICTING_IDENTIFIER = "CONFLICTING IDENTIFIER"
    INCOMPLETE_BATCH = "INCOMPLETE BATCH"


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


def calculate_sales(sales: tuple[Sale, ...]) -> SalesMeasures:
    """Calculate exact measures exclusively from accepted canonical records."""

    by_product: dict[str, Decimal] = {}
    by_date: dict[str, Decimal] = {}
    for sale in sales:
        assert sale.product is not None
        product_id = sale.product.canonical_id
        by_product[product_id] = by_product.get(product_id, Decimal("0")) + sale.net_amount
        day = str(sale.business_date)
        by_date[day] = by_date.get(day, Decimal("0")) + sale.net_amount
    return SalesMeasures(
        len(sales), sum((sale.quantity for sale in sales), Decimal("0")),
        sum((sale.gross_amount for sale in sales), Decimal("0")),
        sum((sale.discount_amount for sale in sales), Decimal("0")),
        sum((sale.net_amount for sale in sales), Decimal("0")),
        tuple(sorted(by_product.items())), tuple(sorted(by_date.items())),
    )
