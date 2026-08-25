"""Chapter 14: delivery economics interpreted from structural lab evidence.

Hours in this module are assumptions for a fictional economic model or explicit
sensitivity inputs.  The repository contains no measured engineering time.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from .models import CASE_2, CASE_2_WORK_CATEGORY_HOURS, WorkCategory


class Assessment(StrEnum):
    SUPPORTED = "SUPPORTED IN STRUCTURE"
    PLAUSIBLE = "PLAUSIBLE BUT UNMEASURED"
    UNDERSTATED = "APPEARS UNDERSTATED"
    CUSTOMER_DEPENDENT = "HIGHLY CUSTOMER-DEPENDENT"


class ReuseClass(StrEnum):
    DEMONSTRATED = "DEMONSTRATED REUSE"
    CONFIGURATION = "CONFIGURATION REUSE"
    DOMAIN = "DOMAIN-SPECIFIC REUSE"
    SOURCE = "SOURCE-SPECIFIC"
    REWORKED = "REWORKED"
    FAILED = "FAILED TO REUSE"


@dataclass(frozen=True)
class EvidenceRow:
    category: WorkCategory
    display_name: str
    evidence: tuple[str, ...]
    assessment: Assessment
    reason: str

    @property
    def modeled_hours(self) -> int:
        return CASE_2_WORK_CATEGORY_HOURS[self.category]


EVIDENCE_MATRIX = (
    EvidenceRow(WorkCategory.SHARED_WORK, "SHARED ENGINEERING", (
        "canonical location, business date, provenance, and calculations reused across domains",
        "one deterministic management briefing accepted compatible multi-location evidence",
        "exception and operational run infrastructure served multiple integrations",
    ), Assessment.SUPPORTED, "Shared concepts survived more systems and locations than individual parsers did."),
    EvidenceRow(WorkCategory.LOCATION_SPECIFIC_WORK, "INCREMENTAL LOCATION WORK", (
        "JRH-006 added identity, source IDs, 12 mappings, four jobs, credentials, and a delivery path",
        "JRH-007 added discovery, manual-drop configuration, unstable mappings, and new ingestion boundaries",
    ), Assessment.CUSTOMER_DEPENDENT, "JRH-006 and JRH-007 demonstrate that standardization changes the kinds of marginal work."),
    EvidenceRow(WorkCategory.CUSTOMER_SPECIFIC_WORK, "CUSTOMER-SPECIFIC EXCEPTIONS", (
        "unknown products, status and role mappings, and product-specific pack conversion",
        "JRH-007 exact-name mappings, missing labor cost, unsafe inventory, manual files, and schema drift",
    ), Assessment.CUSTOMER_DEPENDENT, "Exception burden depends on identifiers, processes, delivery, and source stability."),
    EvidenceRow(WorkCategory.TESTING, "QA / TESTING", (
        "parser, normalization, mapping, schema, exception, and briefing tests accumulated by domain",
        "onboarding regression plus safe, identical, and conflicting replay scenarios",
        "JRH-007 failure, partial-evidence, limitation, and determinism tests",
    ), Assessment.UNDERSTATED, "Testing behaved as both reusable regression protection and incremental work for each source and location."),
    EvidenceRow(WorkCategory.DEPLOYMENT, "DEPLOYMENT / OPERATIONS", (
        "typed configuration, credential references, scheduling, and readiness checks",
        "idempotency, semantic retries, structured logs, health summaries, and recovery paths",
        "JRH-006 automated jobs contrasted with JRH-007 irregular manual-drop monitoring",
    ), Assessment.UNDERSTATED, "Operation exposed distinct reliability and support responsibilities beyond copying code."),
    EvidenceRow(WorkCategory.REWORK, "REWORK", (
        "Location #2 prompted extraction of shared ingestion structures",
        "reservations and labor rejected sales-shaped result reuse; inventory changed canonical identity",
        "operations exposed hidden engineering; JRH-007 required availability extension and schema follow-up",
    ), Assessment.PLAUSIBLE, "Rework is demonstrated structurally, but its frequency and elapsed effort are unmeasured."),
)

REUSE_ASSESSMENT = MappingProxyType({
    "canonical identity": ReuseClass.DEMONSTRATED,
    "business date": ReuseClass.DEMONSTRATED,
    "POS": ReuseClass.SOURCE,
    "reservations": ReuseClass.DOMAIN,
    "labor": ReuseClass.REWORKED,
    "inventory": ReuseClass.REWORKED,
    "exceptions": ReuseClass.DEMONSTRATED,
    "briefing": ReuseClass.DEMONSTRATED,
    "operations": ReuseClass.CONFIGURATION,
})

SUPPORT_SURFACES = (
    "credential references", "scheduled and manual-drop jobs", "schema compatibility",
    "source delivery paths", "stable and human-maintained mappings", "human-action exceptions",
    "product-specific pack conversions", "retryable failures and conflicting replays",
    "source corrections", "manual files and irregular arrival",
)

ONBOARDING_COMPARISON = MappingProxyType({
    "discovery burden": ("confirm pack/optional field", "eight gaps and three unresolved questions"),
    "configuration": ("identity and four source IDs", "identity, credentials, paths, three manual jobs"),
    "mappings": ("12 stable mapping records", "role mappings plus unstable exact-name mappings"),
    "new parsers": ("none", "MillLedger POS and manual labor boundaries"),
    "shared-code changes": ("none", "reservation NOT APPLICABLE extension"),
    "tests": ("onboarding, regression, and replay", "failure, partial-usefulness, schema, and limitations"),
    "operations": ("four configured automated jobs", "three irregular manual-drop jobs"),
    "exceptions/support": ("mapping, pack, schema, credentials", "manual delivery, drift, names, units, costs, corrections"),
    "briefing": ("joined unchanged", "partial sales with explicit limitations"),
})


@dataclass(frozen=True)
class SensitivityScenario:
    name: str
    label: str
    category_hours: Mapping[WorkCategory, int]

    @property
    def total_hours(self) -> int:
        return sum(self.category_hours.values())


SCENARIOS = (
    SensitivityScenario("A — ORIGINAL MODEL", "MODELED ASSUMPTION", CASE_2_WORK_CATEGORY_HOURS),
    SensitivityScenario("B — STANDARDIZED DELIVERY", "SENSITIVITY ASSUMPTION", MappingProxyType({
        WorkCategory.SHARED_WORK: 100, WorkCategory.LOCATION_SPECIFIC_WORK: 35,
        WorkCategory.CUSTOMER_SPECIFIC_WORK: 20, WorkCategory.TESTING: 24,
        WorkCategory.DEPLOYMENT: 10, WorkCategory.REWORK: 15,
    })),
    SensitivityScenario("C — NON-STANDARD DELIVERY", "SENSITIVITY ASSUMPTION", MappingProxyType({
        WorkCategory.SHARED_WORK: 100, WorkCategory.LOCATION_SPECIFIC_WORK: 85,
        WorkCategory.CUSTOMER_SPECIFIC_WORK: 65, WorkCategory.TESTING: 34,
        WorkCategory.DEPLOYMENT: 20, WorkCategory.REWORK: 30,
    })),
)


def economics_report() -> str:
    """Render a deterministic assessment without treating structure as time."""
    lines = ["DELIVERY ECONOMICS FROM ENGINEERING EVIDENCE", "", "ORIGINAL CASE 2 MODEL", "MODELED ASSUMPTION"]
    for row in EVIDENCE_MATRIX:
        lines.append(f"{row.display_name}: {row.modeled_hours} modeled hours — MODELED ASSUMPTION")
    lines += [f"TOTAL: {CASE_2.modeled_engineering_hours} modeled hours — MODELED ASSUMPTION",
              f"Recoverable value: ${CASE_2.recoverable_value:,.0f} — MODELED ASSUMPTION",
              f"Implementation price: ${CASE_2.implementation_price:,.0f} — MODELED ASSUMPTION",
              f"Customer payback: {CASE_2.customer_payback_months} months — MODELED ASSUMPTION",
              "", "IMPORTANT LIMIT", "No engineering time was measured by this lab.",
              "OBSERVED IMPLEMENTATION STRUCTURE is not MEASURED ENGINEERING TIME.", "", "EVIDENCE MATRIX"]
    for row in EVIDENCE_MATRIX:
        lines += ["", row.display_name, f"Original assumption: {row.modeled_hours} hours — MODELED ASSUMPTION",
                  "Executable evidence:", *(f"- {item}" for item in row.evidence),
                  f"Assessment: {row.assessment}", f"Reason: {row.reason}", "Measured hours: NONE"]
    lines += ["", "STANDARDIZED vs NON-STANDARD ONBOARDING", "JRH-006 — MOSTLY STANDARDIZED ONBOARDING",
              "JRH-007 — NON-STANDARD ACQUISITION"]
    for dimension, (six, seven) in ONBOARDING_COMPARISON.items():
        lines += [f"{dimension}: JRH-006 = {six}; JRH-007 = {seven}"]
    lines += ["Conclusion: incremental location work is not stable; it is strongly dependent on standardization.",
              "", "MARGINAL DELIVERY SHAPE",
              "STANDARDIZED LOCATION: mostly configuration, mappings, testing, and operational setup; less shared engineering.",
              "NON-STANDARD LOCATION: adds discovery, source parsing, unstable mappings, exceptions, operational variation, and support exposure.",
              "", "REUSE ASSESSMENT"]
    lines += [f"- {name}: {classification}" for name, classification in REUSE_ASSESSMENT.items()]
    lines += ["Code reuse and operational/conceptual reuse are distinct; canonical concepts can survive while parsers differ.",
              "", "SUPPORT EXPOSURE", *(f"- {surface}" for surface in SUPPORT_SURFACES),
              "Assessment: MEANINGFUL NEW SUPPORT SURFACE per location; labor and incident frequency remain unmeasured.",
              "Recurring support model: INSUFFICIENT MODELED FEE/RATE INPUT; REQUIRES FURTHER VALIDATION.",
              "", "SHARED-WORK HYPOTHESIS",
              "SHARED OWNERSHIP: supported a common group briefing.",
              "SHARED SYSTEMS: reduced parser work for JRH-006; the benefit disappeared for JRH-007.",
              "SHARED WORKFLOWS: reduced stable mappings and exceptions only where processes aligned.",
              "SHARED MANAGEMENT NEEDS: the briefing remained useful, but JRH-007 required explicit limitations.",
              "STANDARDIZATION: the JRH-006/JRH-007 contrast makes scale conditional, not universal.",
              "", "CUSTOMER ECONOMICS",
              f"Recoverable value: ${CASE_2.recoverable_value:,.0f} — MODELED ASSUMPTION",
              f"Implementation price: ${CASE_2.implementation_price:,.0f} — MODELED ASSUMPTION",
              f"Customer payback: {CASE_2.customer_payback_months} months — MODELED ASSUMPTION",
              "Customer economics are unchanged by these delivery sensitivities; they are not validated outcomes.",
              "", "PROVIDER ECONOMICS",
              "Delivery effort: UNMEASURED", "Delivery cost/rate: NO MODELED INPUT EXISTS",
              "Other direct cost: NO MODELED INPUT EXISTS", "Implementation contribution: NOT CALCULABLE",
              "Support burden: structurally meaningful, time and incident frequency unmeasured.",
              "", "SENSITIVITY SCENARIOS"]
    for scenario in SCENARIOS:
        lines += [scenario.name, scenario.label,
                  *(f"- {category.value}: {hours} hours — {scenario.label}" for category, hours in scenario.category_hours.items()),
                  f"Total: {scenario.total_hours} hours — {scenario.label}"]
    lines += ["Sensitivity values ask how exposure changes; they are not observed hours and do not overwrite Scenario A.",
              "", "BREAK-EVEN / BOUNDARY ANALYSIS",
              f"Maximum delivery cost before implementation contribution reaches zero: ${CASE_2.implementation_price:,.0f} — MODELED PRICE BOUNDARY",
              "Maximum delivery hours: NOT CALCULABLE because the original case contains no delivery cost per hour.",
              "", "DELIVERY-ECONOMIC ASSESSMENT",
              "Standardized multi-location group: PROMISING STRUCTURE, TIME UNMEASURED",
              "Non-standard acquired locations: HIGH DELIVERY VARIABILITY",
              "Original 234-hour estimate: NOT VALIDATED",
              "Overall: DELIVERY MODEL REQUIRES REVISION AND CUSTOMER-STANDARDIZATION VALIDATION",
              "Build versus buy: UNRESOLVED — reserved for Chapter 15.",
              "", "OBSERVED LAB RESULTS",
              "OBSERVED LAB RESULT: Shared canonical concepts survived more locations and systems than individual source parsers did.",
              "OBSERVED LAB RESULT: JRH-006 and JRH-007 required materially different categories of marginal delivery work.",
              "OBSERVED LAB RESULT: Production-style operation introduced reliability and support responsibilities beyond reporting features.",
              "OBSERVED LAB RESULT: The original 234-hour estimate remains unvalidated because the lab measured no implementation time."]
    return "\n".join(lines)
