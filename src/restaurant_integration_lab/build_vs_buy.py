"""Chapter 15: deterministic, fictional build-versus-buy hypotheses."""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


OBSERVED = "OBSERVED LAB RESULT"
FICTIONAL = "FICTIONAL ALTERNATIVE ASSUMPTION"


class Importance(StrEnum):
    REQUIRED = "REQUIRED"
    IMPORTANT = "IMPORTANT"
    OPTIONAL = "OPTIONAL"


class Coverage(StrEnum):
    STRONG = "STRONG"
    PARTIAL = "PARTIAL"
    WEAK = "WEAK"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class Differentiation(StrEnum):
    COMMODITY = "COMMODITY CAPABILITY"
    CONFIGURABLE = "CONFIGURABLE CAPABILITY"
    CUSTOM = "CUSTOM DIFFERENTIATOR"
    QUESTIONABLE = "QUESTIONABLE VALUE"
    SUPPORT_HEAVY = "SUPPORT-HEAVY DIFFERENTIATOR"


class Decision(StrEnum):
    BUY = "BUY / CONFIGURE"
    NARROW = "NARROW CUSTOM"
    FULL = "FULL CUSTOM"
    STANDARDIZE = "STANDARDIZE FIRST"
    INVESTIGATE = "INVESTIGATE"
    DEFER = "DO NOTHING / DEFER"


@dataclass(frozen=True)
class Capability:
    key: str
    name: str
    evidence: str
    implementation: str
    differentiation: Differentiation


@dataclass(frozen=True)
class Requirement:
    key: str
    name: str
    importance: Importance


@dataclass(frozen=True)
class Alternative:
    key: str
    name: str
    assumption: str
    coverage: Mapping[str, Coverage]


CUSTOM_CAPABILITIES = (
    Capability("identity", "Cross-location canonical identity", "location/source identities and namespaced mapping registry", "operational_model.py; normalization.py; exceptions.py", Differentiation.CUSTOM),
    Capability("sales", "Normalized POS sales", "HarborTill, CSV, and MillLedger records produce canonical sales", "location1.py; location2.py; onboarding.py; stress_test.py", Differentiation.CONFIGURABLE),
    Capability("reservations", "Reservation demand context", "TableCurrent evidence and explicit availability enter the briefing", "reservations.py; briefing.py", Differentiation.COMMODITY),
    Capability("labor", "Labor context", "worked/scheduled hours, roles, and safe cost completeness", "labor.py; stress_test.py", Differentiation.CONFIGURABLE),
    Capability("inventory", "Inventory evidence", "stock identity, units, pack conversion, and reconciliation boundaries", "inventory.py; onboarding.py", Differentiation.CONFIGURABLE),
    Capability("exceptions", "Cross-system exceptions and data-quality visibility", "typed mapping, schema, duplicate, late, and completeness evidence", "exceptions.py; briefing.py", Differentiation.CUSTOM),
    Capability("briefing", "Group management briefing", "one deterministic briefing combines compatible multi-domain evidence", "briefing.py", Differentiation.COMMODITY),
    Capability("onboarding", "Standardization-aware onboarding", "JRH-006 reuse and JRH-007 stress paths expose marginal change", "onboarding.py; stress_test.py", Differentiation.QUESTIONABLE),
    Capability("operations", "Operational run tracking, idempotency, and retry behavior", "configured jobs, fingerprints, replay outcomes, logs, and readiness", "operations.py", Differentiation.CONFIGURABLE),
    Capability("legacy", "Source-specific irregular-source handling", "strict MillLedger/manual boundaries and explicit schema drift", "stress_test.py", Differentiation.SUPPORT_HEAVY),
)

REQUIREMENTS = (
    Requirement("group_sales", "Combine sales across locations", Importance.REQUIRED),
    Requirement("multi_system", "Combine evidence from operational systems", Importance.REQUIRED),
    Requirement("authority", "Preserve source authority and provenance", Importance.REQUIRED),
    Requirement("identity", "Normalize identifiers and support mappings", Importance.REQUIRED),
    Requirement("quality", "Expose incomplete data and exceptions", Importance.REQUIRED),
    Requirement("briefing", "Provide group management visibility", Importance.REQUIRED),
    Requirement("recurring", "Operate recurrently without replacing source systems", Importance.IMPORTANT),
    Requirement("onboarding", "Onboard additional locations", Importance.IMPORTANT),
    Requirement("legacy", "Handle irregular legacy sources", Importance.OPTIONAL),
)

_ROWS = tuple(r.key for r in REQUIREMENTS)


def _coverage(*values: Coverage) -> Mapping[str, Coverage]:
    return MappingProxyType(dict(zip(_ROWS, values, strict=True)))


ALTERNATIVES = (
    Alternative("saas", "MULTI-LOCATION RESTAURANT SAAS", "May provide supported-vendor dashboards, standardized models, UI, integrations, and operational support; unusual exports and custom identity/exception rules may be limited.", _coverage(Coverage.STRONG, Coverage.STRONG, Coverage.STRONG, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.STRONG, Coverage.STRONG, Coverage.STRONG, Coverage.WEAK)),
    Alternative("bi", "BUSINESS INTELLIGENCE / BI CONFIGURATION", "May ingest structured exports and provide joins, metrics, dashboards, and scheduled refresh; complex normalization and operational exception handling may require maintenance.", _coverage(Coverage.STRONG, Coverage.STRONG, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.WEAK, Coverage.STRONG, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.WEAK)),
    Alternative("automation", "AUTOMATION / INTEGRATION PLATFORM", "May provide supported connectors, schedules, transformations, and retries; legacy formats and complex customer semantics may be difficult to maintain.", _coverage(Coverage.PARTIAL, Coverage.STRONG, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.WEAK, Coverage.STRONG, Coverage.PARTIAL, Coverage.WEAK)),
    Alternative("spreadsheet", "IMPROVED SPREADSHEETS + PROCESS", "May use weekly exports, templates, manual maps, manager review, and an exception checklist at low initial engineering cost but with recurring manual and audit risk.", _coverage(Coverage.PARTIAL, Coverage.PARTIAL, Coverage.WEAK, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.PARTIAL, Coverage.WEAK, Coverage.WEAK, Coverage.WEAK)),
    Alternative("narrow", "NARROW CUSTOM INTEGRATION", "Observed custom POS + labor normalization and briefing, bounded to stable sources; excludes reservations, inventory, acquired-location adapters, and broad exception automation.", _coverage(Coverage.STRONG, Coverage.PARTIAL, Coverage.STRONG, Coverage.STRONG, Coverage.PARTIAL, Coverage.STRONG, Coverage.STRONG, Coverage.PARTIAL, Coverage.UNSUPPORTED)),
    Alternative("full", "FULL CUSTOM INTEGRATION", "Observed executable Chapter 2–14 capability set, including its source-specific code and support obligations.", _coverage(*(Coverage.STRONG for _ in _ROWS))),
    Alternative("defer", "DO NOTHING / DEFER", "May be rational when native reporting is sufficient, value is unproven, or standardization should precede investment.", _coverage(*(Coverage.UNSUPPORTED for _ in _ROWS))),
)

CAPABILITY_MATRIX = MappingProxyType({alternative.key: alternative.coverage for alternative in ALTERNATIVES})

REMOVED_AS_CONFIGURABLE = tuple(c.key for c in CUSTOM_CAPABILITIES if c.differentiation in {Differentiation.COMMODITY, Differentiation.CONFIGURABLE})
REMAINING_CUSTOM_GAP = tuple(c.key for c in CUSTOM_CAPABILITIES if c.key not in REMOVED_AS_CONFIGURABLE)

FULL_SCOPE = MappingProxyType({
    "capabilities": tuple(c.key for c in CUSTOM_CAPABILITIES),
    "sources": ("POS", "reservations", "labor", "inventory"),
    "support_surfaces": ("credentials", "schedules/manual drops", "schemas", "mappings", "pack conversions", "retries/replays", "source corrections"),
    "onboarding": "STANDARD AND ACQUIRED-LOCATION PATHS",
    "exceptions": ("mapping", "schema", "duplicate", "late", "incomplete", "source correction"),
    "jobs": ("POS", "reservations", "labor", "inventory"),
    "variability": "HIGH WHEN SOURCES/PROCESSES DIVERGE",
})
NARROW_SCOPE = MappingProxyType({
    "capabilities": ("identity", "sales", "labor", "briefing"),
    "sources": ("POS", "labor"),
    "support_surfaces": ("credentials", "schedules", "stable mappings", "retries/replays"),
    "onboarding": "STANDARD SOURCES ONLY",
    "exceptions": ("mapping", "schema", "duplicate"),
    "jobs": ("POS", "labor"),
    "variability": "BOUNDED BY COMPATIBILITY GATE",
})


def decide(*, value_proven: bool = True, assumptions_resolved: bool = True,
           variation_primary: bool = False, commodity_sufficient: bool = False,
           custom_gap_material: bool = False, gap_bounded: bool = False,
           standardized: bool = True, support_acceptable: bool = True) -> Decision:
    """Apply ordered procurement rules; full custom must earn explicit differentiation."""
    if not value_proven:
        return Decision.DEFER
    if not assumptions_resolved:
        return Decision.INVESTIGATE
    if variation_primary:
        return Decision.STANDARDIZE
    if commodity_sufficient and not custom_gap_material:
        return Decision.BUY
    if custom_gap_material and gap_bounded:
        return Decision.NARROW
    if custom_gap_material and standardized and support_acceptable:
        return Decision.FULL
    return Decision.INVESTIGATE


DECISION_MATRIX = MappingProxyType({
    "JRH-006-LIKE STANDARDIZED GROUP": MappingProxyType({"buyer_value_fit": "STRONG", "delivery_operating_fit": "VERY STRONG FOR SAAS/BI; STRONG FOR CUSTOM", "decision": Decision.BUY}),
    "JRH-007-LIKE NON-STANDARD ENVIRONMENT": MappingProxyType({"buyer_value_fit": "PARTIAL UNTIL EVIDENCE GAPS CLOSE", "delivery_operating_fit": "WEAK FOR MORE ADAPTERS; STRONGER AFTER MIGRATION", "decision": Decision.STANDARDIZE}),
    "JAMES RIVER HOSPITALITY GROUP": MappingProxyType({"buyer_value_fit": "PLAUSIBLE, NOT VALIDATED", "delivery_operating_fit": "MIXED BY LOCATION", "decision": Decision.INVESTIGATE}),
})


def build_vs_buy_report() -> str:
    lines = ["BUILD VS. BUY REVISITED", "BUILD-vs-BUY HYPOTHESIS — NOT A VERIFIED PROCUREMENT RECOMMENDATION", "", "CUSTOM CAPABILITY INVENTORY"]
    for c in CUSTOM_CAPABILITIES:
        lines += [f"- {c.name}", f"  {OBSERVED}: {c.evidence}", f"  Executable evidence: {c.implementation}"]
    lines += ["", "BUYER REQUIREMENTS", *(f"- {r.importance}: {r.name}" for r in REQUIREMENTS), "", "ALTERNATIVES"]
    for a in ALTERNATIVES:
        label = OBSERVED if a.key in {"narrow", "full"} else FICTIONAL
        lines += [f"- {a.name}", f"  {label}: {a.assumption}"]
    lines += ["", "CAPABILITY MATRIX", "REQUIREMENT | " + " | ".join(a.key.upper() for a in ALTERNATIVES)]
    for r in REQUIREMENTS:
        lines.append(f"{r.name} | " + " | ".join(a.coverage[r.key] for a in ALTERNATIVES))
    lines += ["", "CUSTOM DIFFERENTIATION", *(f"- {c.name}: {c.differentiation}" for c in CUSTOM_CAPABILITIES),
              "", "STANDARDIZED CUSTOMER", "JRH-006: existing SaaS/BI pressure is high because parsers and group reports may cover standard sources.",
              f"Decision: {DECISION_MATRIX['JRH-006-LIKE STANDARDIZED GROUP']['decision']}",
              "", "NON-STANDARD CUSTOMER", "JRH-007: custom legacy handling is more differentiated, but manual delivery, unstable identity, drift, and incomplete evidence weaken operating fit.",
              f"Decision: {DECISION_MATRIX['JRH-007-LIKE NON-STANDARD ENVIRONMENT']['decision']}",
              "The paradox is supported conditionally: easy standardized delivery faces stronger buy/configure competition; irregular demand for adapters raises support burden.",
              "", "SCOPE REDUCTION EXPERIMENT", "FULL CUSTOM CAPABILITY SET: " + ", ".join(c.key for c in CUSTOM_CAPABILITIES),
              "REMOVE AS COMMODITY/CONFIGURABLE: " + ", ".join(REMOVED_AS_CONFIGURABLE),
              "REMAINING CUSTOM GAP: " + ", ".join(REMAINING_CUSTOM_GAP),
              "Result: validate whether identity/exception needs justify bounded custom work; onboarding alone is questionable and legacy handling is support-heavy.",
              "", "FULL vs NARROW CUSTOM"]
    for label, scope in (("FULL CUSTOM", FULL_SCOPE), ("NARROW CUSTOM", NARROW_SCOPE)):
        lines += [label, *(f"- {key}: {', '.join(value) if isinstance(value, tuple) else value}" for key, value in scope.items())]
    lines += ["Result: NARROW CUSTOM is meaningfully smaller and economically preferable if the differentiated gap is material and compatibility can bound it.",
              "", "STANDARDIZE-FIRST OPTION", "JRH-007: migrate processes/systems toward group standards, then reconsider SaaS/BI or narrow integration instead of adding adapters.",
              "", "SUPPORT BURDEN", f"{OBSERVED}: custom ownership includes schemas, credentials, delivery paths, mappings, retries, uptime/recovery, and corrections.",
              f"{FICTIONAL}: a SaaS provider may absorb supported connector/API changes, retries, uptime, credentials, and support; vendor discovery must verify this.",
              "", "DECISION MATRIX"]
    for profile, row in DECISION_MATRIX.items():
        lines += [profile, f"- BUYER VALUE FIT: {row['buyer_value_fit']}", f"- DELIVERY / OPERATING FIT: {row['delivery_operating_fit']}", f"- RESULT: {row['decision']}"]
    lines += ["", "BUILD-vs-BUY ASSESSMENT", "Current assessment: INVESTIGATE for the overall group; BUY / CONFIGURE for a JRH-006-like standardized profile; STANDARDIZE FIRST for JRH-007-like variation.",
              "Custom is not automatically preferred. FULL CUSTOM requires a material differentiated gap, standardization, and acceptable support.",
              "The final opportunity classification remains unresolved until Chapter 16.", "", "REAL-WORLD VALIDATION REQUIRED",
              "No real SaaS product, capability, price, or procurement term was researched.",
              "Validate native HarborTill group sales, TableCurrent pacing, ShiftHarbor/StockPilot/EchoGuest reports, BI exports/connectors, vendor coverage, migration cost, pricing, support, and buyer adoption."]
    return "\n".join(lines)
