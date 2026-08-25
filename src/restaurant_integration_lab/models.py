"""Fictional modeled assumptions inherited from the opportunity casebook.

Nothing in this module is an observed implementation result.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class WorkCategory(StrEnum):
    """Evidence categories used by the modeled Case 2 delivery estimate."""

    SHARED_WORK = "SHARED WORK"
    LOCATION_SPECIFIC_WORK = "LOCATION-SPECIFIC WORK"
    CUSTOMER_SPECIFIC_WORK = "CUSTOMER-SPECIFIC WORK"
    TESTING = "TESTING"
    DEPLOYMENT = "DEPLOYMENT"
    REWORK = "REWORK"


@dataclass(frozen=True)
class OpportunityScenario:
    """An economic scenario consisting only of modeled assumptions."""

    case_number: int
    name: str
    recoverable_value: int
    modeled_engineering_hours: int
    implementation_price: int
    customer_payback_months: Decimal
    verdict: str
    work_category_hours: Mapping[WorkCategory, int] | None = None


CASE_1 = OpportunityScenario(
    case_number=1,
    name="Independent Restaurant",
    recoverable_value=10_392,
    modeled_engineering_hours=150,
    implementation_price=15_000,
    customer_payback_months=Decimal("24.4"),
    verdict="NO DEAL",
)

CASE_2_WORK_CATEGORY_HOURS: Mapping[WorkCategory, int] = MappingProxyType(
    {
        WorkCategory.SHARED_WORK: 100,
        WorkCategory.LOCATION_SPECIFIC_WORK: 50,
        WorkCategory.CUSTOMER_SPECIFIC_WORK: 30,
        WorkCategory.TESTING: 24,
        WorkCategory.DEPLOYMENT: 10,
        WorkCategory.REWORK: 20,
    }
)

CASE_2 = OpportunityScenario(
    case_number=2,
    name="Five-Location Restaurant Group",
    recoverable_value=67_070,
    modeled_engineering_hours=sum(CASE_2_WORK_CATEGORY_HOURS.values()),
    implementation_price=42_000,
    customer_payback_months=Decimal("8.7"),
    verdict="PROMISING — VALIDATE IN DISCOVERY",
    work_category_hours=CASE_2_WORK_CATEGORY_HOURS,
)

