# Chapter 0 — The Hypothesis

> **Fiction notice:** James River Hospitality Group, its restaurants, systems, datasets, vendors, financial figures, and operational assumptions are fictional. Nothing below is an actual customer result or an endorsement of a real system.

## 0.1 The casebook claim

Three earlier conceptual projects culminated in a cookbook opportunity: a shared operational data layer for **James River Hospitality Group**, a fictional five-restaurant owner. The claim to test is not simply that software can be built. It is that shared ownership, management needs, systems, and workflows might let recoverable value scale faster than delivery effort.

| Fictional economic case | Recoverable value | Engineering hours | Implementation price | Customer payback | Verdict |
|---|---:|---:|---:|---:|---|
| Case 1 — independent restaurant | $10,392 | 150 | $15,000 | 24.4 months | NO DEAL |
| Case 2 — five-location group | $67,070 | 234 | $42,000 | 8.7 months | PROMISING — VALIDATE IN DISCOVERY |

Every value in this table is a **MODELED ASSUMPTION** inherited from the fictional case. The group looked different because modeled value rose about 6.45× while effort rose 1.56×, but no integration has established that relationship.

## 0.2 The fictional locations

The group has common ownership and a need for cross-location briefing, but it is not a collection of clones.

| Name | Code | Concept | Operating description | Likely system/configuration differences (fictional) |
|---|---|---|---|---|
| River & Rail Kitchen | `RRK` | Full-service New American | Dinner-led flagship with reservations, bar service, and private dining | Most detailed POS menu hierarchy; reservation events; separate private-event spreadsheet |
| Canal Street Tacos | `CST` | Fast casual | Counter service, high lunch volume, delivery, and limited catering | Quick-service POS layout; delivery-channel tenders; no reservation system; compact labor roles |
| Blue Heron Oyster House | `BHO` | Seafood and raw bar | Full service with volatile ingredient costs and seasonal patio demand | Catch-weight inventory units; raw-bar modifiers; weather-sensitive staffing; patio sections |
| Manchester Bake & Coffee | `MBC` | Bakery café | Early-day service with retail bakery, preorders, and wholesale batches | SKU-heavy retail catalog; preorder exports; production shifts; wholesale sales categories |
| James River Smokehouse | `JRS` | Barbecue and taproom | Counter ordering plus table tabs, long-cook production, and event nights | Hybrid service modes; keg and batch inventory; production-yield sheets; entertainment/event flags |

The descriptions identify future discovery risks, not implemented integrations or verified configurations.

## 0.3 System boundary

```text
EXISTING SYSTEMS
        ↓
ADAPTERS / IMPORTS
        ↓
VALIDATION
        ↓
NORMALIZATION
        ↓
SHARED OPERATIONAL MODEL
        ↓
DETERMINISTIC CALCULATIONS
        ↓
CROSS-LOCATION MANAGEMENT BRIEFING
        ↓
LOGGING / EXCEPTIONS / OBSERVABILITY
```

Existing systems remain authoritative. Later experiments may integrate evidence from fictional POS, reservations, scheduling, inventory, customer feedback, and spreadsheets/exports. The boundary excludes replacing a POS, ERP, scheduling platform, inventory platform, CRM, or general restaurant-management system.

## 0.4 What is unvalidated

Discovery has not established source accessibility, export stability, semantic consistency, identity matching, data quality, common management definitions, exception frequency, adapter portability, operational reliability, maintenance load, user adoption, or realized value. It has not established that five locations accept one normalized model—or that SaaS/configuration would not solve the need more cheaply and safely.

There are currently **no OBSERVED LAB RESULTS about implementation reuse**. The repository contains no fabricated implementation evidence.

## 0.5 The modeled delivery assumptions

The original fictional Case 2 estimate decomposes as follows:

| Evidence category | Modeled hours |
|---|---:|
| SHARED WORK | 100 |
| LOCATION-SPECIFIC WORK | 50 |
| CUSTOMER-SPECIFIC WORK | 30 |
| TESTING | 24 |
| DEPLOYMENT | 10 |
| REWORK | 20 |
| **Total** | **234** |

These are **MODELED ASSUMPTIONS**, not targets. The implementation must not be selected, scoped, classified, or manipulated to reproduce them. Future collection also includes **SYSTEM-SPECIFIC WORK** and **SUPPORT OBLIGATION**, even though the original model did not separately allocate hours to those categories.

## 0.6 How the lab will test the claim

Later chapters should preserve source artifacts and measure actual adapter reuse, mappings, validation rules, location-specific code/configuration, tests, deployments, rework, exceptions, reliability, and support obligations. Each measurement must be labeled **OBSERVED LAB RESULT**, with a reproducible method and enough context to avoid confusing theoretical reuse with demonstrated reuse.

Modeled and observed evidence will remain separate, then be compared explicitly: category by category, location by location, and system by system. Variance should update delivery estimates and economics rather than be explained away. Code that could theoretically be reused is not automatically demonstrated reuse.

Even a reliable, highly reused implementation would prove only technical feasibility. A build-versus-buy decision must still compare SaaS/configuration coverage, switching and integration costs, time to value, strategic differentiation, vendor risk, ongoing ownership, support burden, and opportunity cost.

## 0.7 Engineering principles

1. **Integration first.** Improve decisions around authoritative systems rather than replace them.
2. **Narrow scope.** Test the operational briefing use case, not restaurant management in general.
3. **Deterministic before intelligent.** Prefer inspectable rules before probabilistic features.
4. **Evidence before abstraction.** Generalize only after concrete variation is observed.
5. **Make variation visible.** Do not hide location and system differences behind premature interfaces.
6. **Reliability matters.** Correctness, traceability, failure handling, and freshness are product behavior.
7. **Keep human exceptions.** Surface ambiguous cases for review rather than silently inventing certainty.
8. **Measure reuse honestly.** Count demonstrated unchanged reuse and the work required to achieve it.
9. **Keep economics connected to engineering.** Feed measured delivery and support work back into the case.
10. **Build versus buy remains open.** Working custom code is not, by itself, a business justification.

This project should try to break the original opportunity hypothesis, not prove it. Chapter 0 makes the premise executable; it does not begin discovery or implement an integration.
