# Chapter 15 — Build vs. Buy Revisited

Technical success does not settle procurement. Chapters 2–14 show that a custom integration can normalize synthetic operational evidence and produce a useful briefing; they do not show that a customer should purchase it. Chapter 15 therefore treats custom software as one competitor and makes it earn its scope. Run the deterministic hypothesis with:

```bash
python -m restaurant_integration_lab build-vs-buy
```

## 1. Actual custom capability, not aspiration

The executable inventory is: cross-location canonical identity; normalized POS sales; reservation demand context; labor context; inventory evidence; typed cross-system exceptions and data-quality visibility; a group briefing; standardization-aware onboarding; operational runs, idempotency, retries, readiness, and provenance; and strict source-specific handling for JRH-007. Every CLI inventory row names its implementing modules and is labeled **OBSERVED LAB RESULT**.

This inventory is deliberately narrower than a restaurant-management product. Source systems remain authoritative; the lab does not replace POS, scheduling, reservations, or inventory. Chapter 1 also creates existing-capability pressure: fictional HarborTill may have group sales, TableCurrent may have pacing, and confirmed ShiftHarbor, StockPilot, and EchoGuest reports cover portions of the briefing. Those synthetic findings require product/licensing review, but already forbid assuming every report needs code.

## 2. Buyer requirements

Required outcomes are cross-location sales, multi-system evidence, source authority/provenance, normalized identifiers/mappings, visible incompleteness/exceptions, and group visibility. Recurring operation without replacing authoritative systems and repeatable onboarding are **IMPORTANT**. Irregular legacy-source support is **OPTIONAL**: it must not force every buyer into the most expensive design.

## 3. Seven alternatives

The model compares **MULTI-LOCATION RESTAURANT SAAS**, **BI CONFIGURATION**, **AUTOMATION / INTEGRATION PLATFORM**, **IMPROVED SPREADSHEETS + PROCESS**, **NARROW CUSTOM**, **FULL CUSTOM**, and **DO NOTHING / DEFER**. SaaS may centralize supported-vendor reporting and absorb operations; BI may join structured exports; automation may move and retry supported data; and disciplined spreadsheets may be sufficient at low scale. These are all **FICTIONAL ALTERNATIVE ASSUMPTION**, not claims about real products. Narrow and full custom alone describe observed repository scope.

## 4. Deterministic capability matrix

The executable matrix uses only `STRONG`, `PARTIAL`, `WEAK`, `UNSUPPORTED`, and `UNKNOWN`. Full custom is strong across the modeled requirements because the lab demonstrated those boundaries, but the matrix does not rank options or excuse its cost. SaaS/BI are structurally strong for standard reporting; automation is stronger at movement than briefing semantics; spreadsheets remain partially capable with manual burden; narrow custom intentionally excludes legacy support; defer supports none. Coverage for purchased alternatives remains hypothetical.

## 5. Commodity versus differentiation

Reservation context and the group briefing are classified **COMMODITY CAPABILITY**. POS, labor, inventory, and operational behavior are **CONFIGURABLE CAPABILITY** because plausible tools can provide much of their ordinary shape. Canonical identity and customer-specific exception semantics are **CUSTOM DIFFERENTIATOR**. Standardization-aware onboarding is **QUESTIONABLE VALUE** as a purchased feature: it is evidence about delivery, not necessarily buyer value. Irregular legacy support is a **SUPPORT-HEAVY DIFFERENTIATOR**—genuinely unusual, but costly to own.

## 6. Standardization paradox and two-axis fit

JRH-006 reused four parsers and joined the briefing without shared-code changes. Its buyer value fit is strong, but SaaS/BI delivery and operating fit is modeled **VERY STRONG**, while custom is merely strong. The result is **BUY / CONFIGURE** pending vendor validation: the easiest custom customer also faces the strongest existing-tool competition.

JRH-007 reused no source parser unchanged, added strict/manual ingestion, unstable names, schema drift, missing evidence, and support surfaces. Custom buyer fit may be stronger at the legacy gap, yet operating fit is weak. SaaS fit may improve if migration is accepted. The result is **STANDARDIZE FIRST**, not “write every adapter.” The evidence conditionally supports both sides of the paradox: irregularity creates differentiation and simultaneously harms delivery economics.

## 7. Executable scope reduction

The first experiment removes reservation context, group briefing, normalized sales/labor/inventory, and ordinary operations because they are classified commodity/configurable. It leaves canonical identity, customer-specific exception semantics, onboarding evidence, and irregular-source handling. The last two weaken the residual case: onboarding is questionable buyer value and legacy handling is support-heavy. The remaining gap might justify bounded code, but does not justify full custom without discovery.

The second experiment compares full and narrow scope structurally. **NARROW CUSTOM** retains POS + labor, identity, and briefing; two job/domain surfaces; stable mappings; and bounded mapping/schema/duplicate exceptions. It excludes reservations, inventory, acquired-location adapters, pack conversion, manual drops, source corrections, and broad exceptions. It has fewer capabilities, sources, support surfaces, exception categories, and jobs, and a compatibility gate bounds variability. It is economically preferable *if* identity/exception differentiation proves material.

## 8. Support is part of the competition

Chapter 11 and later onboarding show that custom ownership includes schemas, API/delivery changes, credential references, schedules and manual drops, retries, replay conflict, observability, recovery, mappings, source corrections, and uptime/support expectations. A fictional SaaS could absorb some supported-connector operations. That is a competitor advantage, not merely missing feature work, and must be verified rather than presumed.

## 9. Standardize first

For JRH-007, process change competes directly with abstraction: move the acquisition toward group-standard POS, scheduling, inventory, identifiers, and delivery, then use existing group reporting, BI, or a narrow integration. If variation is the primary cost driver and migration eliminates adapters, **STANDARDIZE FIRST** wins the deterministic rule.

## 10. Decision rules and matrix

Rules are ordered and executable. Use **DO NOTHING / DEFER** when value is unproven; **INVESTIGATE** when alternative assumptions remain unresolved; **STANDARDIZE FIRST** when variation drives cost; **BUY / CONFIGURE** when commodity coverage suffices and no material custom gap remains; **NARROW CUSTOM** for a material bounded gap; and **FULL CUSTOM** only for a material differentiated gap with sufficient standardization and acceptable support.

The resulting matrix is deliberately non-uniform:

| Profile | Buyer value fit | Delivery / operating fit | Hypothesis |
|---|---|---|---|
| JRH-006-like standardized | Strong | Very strong for SaaS/BI; strong for custom | BUY / CONFIGURE |
| JRH-007-like non-standard | Partial until gaps close | Weak for adapters; stronger after migration | STANDARDIZE FIRST |
| Overall JRH | Plausible, not validated | Mixed by location | INVESTIGATE |

The full-custom option is not selected merely because it has the broadest matrix coverage.

## 11. Assessment and validation boundary

The current result is a **BUILD-vs-BUY HYPOTHESIS**, not a **VERIFIED PROCUREMENT RECOMMENDATION**. No real vendor, feature, price, support level, migration term, or procurement condition was researched. Discovery must validate native group/pacing/labor/inventory/feedback reports, structured exports and BI connectors, connector/source coverage, exception needs, migration cost, pricing, support ownership, adoption, and whether management pain is sufficient. **OBSERVED LAB RESULT** and **FICTIONAL ALTERNATIVE ASSUMPTION** remain visibly separate in code and output.

Chapter 15 does not finalize the opportunity. Chapter 16 must combine **CUSTOMER VALUE + DELIVERY ECONOMICS + TECHNICAL REUSE + SUPPORT + SALES / DISCOVERY EFFORT + STANDARDIZATION + ALTERNATIVES + MARGINAL LOCATION COST**, then decide whether actual engineering strengthened or weakened Case 2. All final classifications remain open; Chapter 16 is not implemented here.
