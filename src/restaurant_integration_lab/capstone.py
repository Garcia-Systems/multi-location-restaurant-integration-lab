"""Chapter 16: a deterministic final assessment of the Case 2 hypothesis."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .build_vs_buy import CUSTOM_CAPABILITIES, DECISION_MATRIX, Differentiation
from .economics import ONBOARDING_COMPARISON, SUPPORT_SURFACES
from .models import CASE_1, CASE_2

MODELED = "MODELED ASSUMPTION"
OBSERVED = "OBSERVED LAB RESULT"
FICTIONAL = "FICTIONAL ALTERNATIVE ASSUMPTION"


class ComponentAssessment(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIALLY SUPPORTED"
    WEAK = "WEAK"
    NOT_SUPPORTED = "NOT SUPPORTED"


class ReuseAssessment(StrEnum):
    STRONG = "STRONG DEMONSTRATED REUSE"
    CONFIGURATION = "CONFIGURATION REUSE"
    CONDITIONAL = "CONDITIONAL REUSE"
    DOMAIN = "DOMAIN-SPECIFIC"
    SOURCE = "SOURCE-SPECIFIC"
    ERODED = "REUSE ERODED BY VARIATION"


class ProductClass(StrEnum):
    PROJECT = "ONE-OFF PROJECT"
    SERVICE = "REPEATABLE CUSTOM SERVICE / PRODUCTIZED DELIVERY"
    PRODUCT = "SOFTWARE PRODUCT"


class Verdict(StrEnum):
    PROMISING = "PROMISING — VALIDATE IN DISCOVERY"
    PROJECT = "ONE-OFF CUSTOM PROJECT"
    SERVICE = "REPEATABLE CUSTOM SERVICE"
    NARROW = "NARROW CUSTOM"
    BUY = "BUY / CONFIGURE"
    STANDARDIZE = "STANDARDIZE FIRST"
    INVESTIGATE = "INVESTIGATE"
    POOR = "POOR TARGET CUSTOMER"
    NO_DEAL = "NO DEAL"


@dataclass(frozen=True)
class OpportunityEvidence:
    """Qualification evidence, not a fake score or market measurement."""

    management_need: bool
    value_validated: bool
    mostly_standardized: bool
    stable_identifiers: bool
    accessible_sources: bool
    material_custom_gap: bool
    alternative_capabilities_verified: bool
    support_acceptable: bool
    shared_core_demonstrated: bool
    repeatable_interfaces: bool
    location_count: int


LAB_EVIDENCE = OpportunityEvidence(
    management_need=True, value_validated=False, mostly_standardized=False,
    stable_identifiers=False, accessible_sources=True, material_custom_gap=False,
    alternative_capabilities_verified=False, support_acceptable=False,
    shared_core_demonstrated=True, repeatable_interfaces=False, location_count=7,
)


def final_verdict(e: OpportunityEvidence) -> Verdict:
    """Apply explicit multi-dimensional rules; no single technical fact wins."""
    if not e.management_need and not e.value_validated:
        return Verdict.NO_DEAL
    if e.location_count < 2 and not e.value_validated:
        return Verdict.POOR
    if not e.alternative_capabilities_verified:
        return Verdict.INVESTIGATE
    if not e.material_custom_gap:
        return Verdict.BUY
    if not e.mostly_standardized or not e.stable_identifiers:
        return Verdict.STANDARDIZE
    if e.material_custom_gap and e.shared_core_demonstrated and e.support_acceptable:
        return Verdict.NARROW
    return Verdict.INVESTIGATE


def classify_delivery(e: OpportunityEvidence) -> ProductClass:
    if not e.shared_core_demonstrated or not e.repeatable_interfaces:
        return ProductClass.SERVICE if e.shared_core_demonstrated else ProductClass.PROJECT
    if e.mostly_standardized and e.stable_identifiers and e.support_acceptable:
        return ProductClass.PRODUCT
    return ProductClass.SERVICE


HYPOTHESIS_COMPONENTS = MappingProxyType({
    "Shared ownership": (ComponentAssessment.SUPPORTED, "one group briefing answered cross-location management questions"),
    "Shared systems": (ComponentAssessment.PARTIAL, "JRH-006 reused existing parsers; JRH-007 reused no source parser unchanged"),
    "Shared workflows": (ComponentAssessment.PARTIAL, "canonical concepts and calculations survived, but inventory, statuses, units, and exceptions differed"),
    "Shared management needs": (ComponentAssessment.SUPPORTED, "the same briefing accepted JRH-006 unchanged and retained explicitly limited JRH-007 evidence"),
    "Value scaling": (ComponentAssessment.WEAK, "technical usefulness became more plausible; recoverable value was not measured"),
})

REUSE_INVENTORY = MappingProxyType({
    "canonical location identity": ReuseAssessment.STRONG,
    "business date": ReuseAssessment.STRONG,
    "product/item identity": ReuseAssessment.ERODED,
    "canonical sales": ReuseAssessment.STRONG,
    "reservation context": ReuseAssessment.DOMAIN,
    "labor context": ReuseAssessment.CONDITIONAL,
    "inventory": ReuseAssessment.ERODED,
    "exception model": ReuseAssessment.STRONG,
    "provenance": ReuseAssessment.STRONG,
    "management briefing": ReuseAssessment.STRONG,
    "operations": ReuseAssessment.CONFIGURATION,
    "onboarding": ReuseAssessment.CONDITIONAL,
})

STANDARDIZATION_FITS = MappingProxyType({
    "STANDARDIZED FIT": ("existing source family and known schema", "stable identifiers", "existing mappings and operational workflow"),
    "PARTIAL FIT": ("some new mappings or source differences", "limited code extension", "bounded new exceptions"),
    "NON-STANDARD FIT": ("new source family or recurring schema instability", "unstable/manual identifiers and processes", "significant exceptions and operational variation"),
})

STRONG_SIGNALS = ("multiple commonly owned locations", "mostly standardized systems", "clear cross-location management questions", "accessible exports/APIs", "stable source identifiers", "verified native-reporting gap", "willingness to standardize")
WARNING_SIGNALS = ("different or manual systems at every location", "unstable identifiers or spreadsheets", "unclear management need", "native SaaS already closes the gap", "refusal to standardize", "frequent incompatible acquisitions")

BEST_FIT = ("common ownership and enough locations for shared infrastructure", "mostly standardized accessible systems and stable identifiers", "meaningful cross-location need with a verified, bounded SaaS gap", "willingness to use configuration, mappings, and standardization")
POOR_FIT = ("a single/small operator or highly fragmented acquired group", "manual, inconsistent processes and unstable identity", "weak management need or high exception burden", "a strong existing SaaS alternative or refusal to standardize")

UNKNOWNS = ("actual engineering hours", "actual restaurant customer value", "real buyer willingness to pay", "real support incident frequency", "actual SaaS capabilities and pricing", "real sales cycle", "actual customer acquisition cost", "real restaurant data quality")

VALIDATION_QUESTIONS = ("Do real 5–20 location operators have the demonstrated cross-system management problem?", "How standardized are their systems, identifiers, and workflows?", "Which native SaaS/BI reports already answer the management questions?", "Can representative exports/APIs be inspected before pricing?", "How many mappings, exceptions, and manual corrections occur in real data?", "Is the differentiated gap bounded enough for narrow custom work?", "What implementation price and support model will buyers accept?")


def capstone_report() -> str:
    verdict = final_verdict(LAB_EVIDENCE)
    product_class = classify_delivery(LAB_EVIDENCE)
    chapter_15 = DECISION_MATRIX["JAMES RIVER HOSPITALITY GROUP"]["decision"]
    lines = ["MULTI-LOCATION RESTAURANT INTEGRATION LAB", "FINAL EVIDENCE REVIEW", "", "ORIGINAL HYPOTHESIS",
             "CASE 2 HYPOTHESIS", "Customer: Five-location restaurant group",
             "Economic idea: Recoverable value increases faster than delivery cost.",
             "Technical mechanism: shared ownership + shared systems + shared workflows + shared management needs = reusable integration infrastructure",
             f"Recoverable value: ${CASE_2.recoverable_value:,.0f} — {MODELED}",
             f"Engineering hours: {CASE_2.modeled_engineering_hours} modeled hours — {MODELED}",
             f"Implementation price: ${CASE_2.implementation_price:,.0f} — {MODELED}",
             f"Customer payback: {CASE_2.customer_payback_months} months — {MODELED}",
             "RECOVERABLE VALUE: Still a modeled assumption.", "Actual engineering time: UNMEASURED.",
             "", "WHAT WAS BUILT", "Canonical multi-system evidence, deterministic briefing, exception handling, production-like operations, and two contrasting onboarding paths.",
             "", "WHAT WAS OBSERVED",
             f"{OBSERVED}: Shared canonical identity and management calculations survived broader source variation better than individual source parsers.",
             f"{OBSERVED}: JRH-006 produced configuration/mapping reuse; JRH-007 required new boundaries and retained only safe partial evidence.",
             f"{OBSERVED}: Reliability and support responsibilities extended well beyond the visible briefing.",
             f"{OBSERVED}: No implementation time or real customer value was measured.",
             "", "HYPOTHESIS COMPONENTS"]
    lines += [f"{name}: {assessment} — {reason}" for name, (assessment, reason) in HYPOTHESIS_COMPONENTS.items()]
    lines += ["", "TECHNICAL REUSE", "Reuse is not REUSABLE vs CUSTOM; the observed continuum is:",
              "SHARED CORE + CONFIGURATION + MAPPINGS + SOURCE-SPECIFIC EDGES + CUSTOMER EXCEPTIONS"]
    lines += [f"- {name}: {assessment}" for name, assessment in REUSE_INVENTORY.items()]
    lines += ["", "STANDARDIZATION EFFECT"]
    for fit, traits in STANDARDIZATION_FITS.items():
        lines += [fit, *(f"- {trait}" for trait in traits)]
    lines += ["Marginal delivery cost appears structurally low only when location standardization remains high.",
              "", "JRH-006 vs JRH-007"]
    lines += [f"- {dimension}: JRH-006 = {six}; JRH-007 = {seven}" for dimension, (six, seven) in ONBOARDING_COMPARISON.items()]
    lines += ["", "SUPPORT SURFACE", *(f"- {item}" for item in SUPPORT_SURFACES),
              "Assessment: MEANINGFUL SUPPORT SURFACE. It is not negligible; frequency and labor remain unknown.",
              "", "DISCOVERY BURDEN", "Assessment: SUBSTANTIAL AND QUALIFICATION-CRITICAL.",
              "Before pricing: inventory systems/interfaces/schema samples, identifiers, existing reports, reservation applicability, labor semantics, inventory processes, SaaS coverage, data quality, and standardization level.",
              "", "OPPORTUNITY QUALIFICATION", "STRONG TARGET SIGNALS", *(f"- {x}" for x in STRONG_SIGNALS), "WARNING SIGNALS", *(f"- {x}" for x in WARNING_SIGNALS),
              "", "BUILD VS BUY", f"Chapter 15 overall result incorporated: {chapter_15}."]
    for category in Differentiation:
        names = [c.name for c in CUSTOM_CAPABILITIES if c.differentiation is category]
        lines.append(f"- {category}: {', '.join(names)}")
    lines += [f"Purchased-alternative coverage remains {FICTIONAL}; no real vendor was validated.",
              "Conclusion: FULL CUSTOM is not supported. NARROW CUSTOM is a candidate only if discovery verifies a material bounded identity/exception gap; otherwise BUY / CONFIGURE.",
              "", "PROJECT vs PRODUCT", f"Classification: {product_class}",
              "Reusable code alone is insufficient for SOFTWARE PRODUCT. The shared core is productizable; discovery, adapters, mappings, exceptions, and standardization remain a service edge.",
              "PRODUCTIZABLE CORE: canonical identity; mapping mechanisms; exception workflow; operational run framework; briefing structures.",
              "SERVICE / IMPLEMENTATION EDGE: discovery; source adapters; mappings; source-specific exceptions; customer standardization.",
              "", "BEST-FIT CUSTOMER HYPOTHESIS", "LAB-DERIVED TARGET PROFILE HYPOTHESIS — NOT MARKET VALIDATION", *(f"- {x}" for x in BEST_FIT),
              "", "POOR-FIT CUSTOMER HYPOTHESIS", "LAB-DERIVED POOR-FIT PROFILE — NOT MARKET VALIDATION", *(f"- {x}" for x in POOR_FIT),
              "", "CASE 1 vs CASE 2",
              f"Case 1: independent restaurant; ${CASE_1.recoverable_value:,.0f} value, {CASE_1.modeled_engineering_hours} hours, ${CASE_1.implementation_price:,.0f} price, {CASE_1.customer_payback_months} months — all {MODELED}; verdict {CASE_1.verdict}.",
              f"Case 2: five-location group; ${CASE_2.recoverable_value:,.0f} value, {CASE_2.modeled_engineering_hours} hours, ${CASE_2.implementation_price:,.0f} price, {CASE_2.customer_payback_months} months — all {MODELED}; original verdict {CASE_2.verdict}.",
              "Case 2 is structurally different because one core and briefing served multiple locations, but the numerical advantage remains unvalidated and depends on standardization.",
              "", "WHAT THE LAB STRENGTHENED", "- shared canonical identity, provenance, exception semantics, and calculations", "- one reusable management briefing", "- configuration-heavy onboarding for a standardized location", "- safe higher-level usefulness despite some source variation",
              "", "WHAT THE LAB WEAKENED", "- simplistic parser-reuse assumptions", "- inventory and product identity as universally shared semantics", "- negligible operations/support assumptions", "- stable marginal-location work and the adequacy of a simple 234-hour model",
              "", "WHAT REMAINS UNKNOWN", *(f"- {x}" for x in UNKNOWNS),
              "", "ECONOMICS CONCLUSION", "Original 234 hours: UNVALIDATED MODELED ASSUMPTION.", "Customer recoverable value: UNVALIDATED MODELED ASSUMPTION.", "Standardized delivery is structurally more favorable; non-standard delivery is variable; operations/support are material.", "Assessment: TECHNICAL PREMISE STRENGTHENED; ECONOMIC MODEL WEAKENED, BECAME MORE CONDITIONAL, AND REMAINS INSUFFICIENTLY VALIDATED.",
              "", "FINAL VERDICT", f"PRIMARY VERDICT: {verdict}", "QUALIFIER: NARROW CUSTOM is plausible only for a standardized operator with a verified material gap.", "STANDARDIZED MULTI-LOCATION GROUP: BUY / CONFIGURE first; consider NARROW CUSTOM for the residual gap.", "HIGHLY FRAGMENTED / ACQUIRED GROUP: STANDARDIZE FIRST.", "SINGLE INDEPENDENT RESTAURANT: POOR TARGET CUSTOMER absent exceptional validated value.", "REAL-WORLD STATUS: VALIDATE IN DISCOVERY.",
              "", "REAL-WORLD VALIDATION REQUIRED", *(f"{i}. {q}" for i, q in enumerate(VALIDATION_QUESTIONS, 1))]
    return "\n".join(lines)
