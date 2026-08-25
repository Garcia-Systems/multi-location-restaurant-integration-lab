# Multi-Location Restaurant Integration Lab

## Purpose

This repository is a completed 17-chapter executable textbook. It uses a small synthetic integration laboratory to test whether technical reuse, integration complexity, and delivery economics support a custom-software opportunity. It is a teaching artifact, not a production restaurant platform, market study, or industry benchmark.

## Original hypothesis

The fictional source case contrasted an independent restaurant (**Case 1: NO DEAL**) with a five-location group (**Case 2: PROMISING — VALIDATE IN DISCOVERY**). It proposed that recoverable value could scale faster than delivery when locations share ownership, systems, workflows, and management needs. Case 2's $67,070 recoverable value, **234 modeled engineering hours**, $42,000 price, and 8.7-month payback are **MODELED ASSUMPTIONS**, never observed implementation time or validated commercial results.

## Central experimental question

Does reuse actually survive source parsing, explicit mappings, normalization, additional operational domains, production-operation concerns, standardized onboarding, and a non-standard acquisition strongly enough to support the modeled opportunity?

## Architecture

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

The code deliberately preserves the boundary `SOURCE-SPECIFIC PARSING → EXPLICIT NORMALIZATION → SHARED OPERATIONAL MODEL`. Existing systems remain authoritative; this lab is not a POS, ERP, scheduler, inventory system, CRM, dashboard, or real infrastructure deployment.

## Evidence vocabulary

- **MODELED ASSUMPTION** — a fictional economic or delivery value inherited from the original case, including the 234-hour estimate.
- **OBSERVED LAB RESULT** — behavior demonstrated by the executable synthetic fixtures and deterministic calculations.
- **OBSERVED IMPLEMENTATION STRUCTURE** — repository evidence such as adapters, mappings, tests, jobs, exception paths, and reuse classifications; it is not measured human effort.
- **SENSITIVITY ASSUMPTION** — a hypothetical changed value used only to examine an economic scenario.
- **FICTIONAL ALTERNATIVE ASSUMPTION** — an unverified capability attributed to a hypothetical buy/configure alternative, not vendor research.

## Fictional environment

James River Hospitality Group (JRH), all seven restaurants, every named operational system and SaaS alternative, all exports and datasets, financial values, engineering assumptions, and operational scenarios are fictional or synthetic. Results describe these fixtures only and must not be read as restaurant-industry benchmarks.

## Chapters

All chapters are complete; there is no Chapter 17.

**Chapter 16 — Capstone: Project, Product, or Bad Idea? COMPLETE**

| Chapter | Experiment | Status |
|---:|---|---|
| 0 | The Hypothesis | Complete |
| 1 | Discovery Before Architecture | Complete |
| 2 | Define the Shared Operational Model | Complete |
| 3 | Build Location #1 | Complete |
| 4 | Add Location #2 | Complete |
| 5 | Normalize Across Locations | Complete |
| 6 | Reservations and Demand Context | Complete |
| 7 | Add Labor | Complete |
| 8 | Add Inventory | Complete |
| 9 | Exceptions and Data Quality | Complete |
| 10 | Group Management Briefing | Complete |
| 11 | Production Integration Engineering | Complete |
| 12 | Onboard Another Restaurant (JRH-006) | Complete |
| 13 | Standardization Stress Test (JRH-007) | Complete |
| 14 | Delivery Economics From Engineering Evidence | Complete |
| 15 | Build vs. Buy Revisited | Complete |
| 16 | Capstone: Project, Product, or Bad Idea? | Complete |

Chapter documents are in [`docs/chapters`](docs/chapters), in numbered reading order. Structural evidence ledgers are in [`docs/evidence`](docs/evidence).

## Quick start

Python 3.12 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest
python -m restaurant_integration_lab --help
python -m restaurant_integration_lab verify
```

The complete CLI index is:

```bash
python -m restaurant_integration_lab hypothesis
python -m restaurant_integration_lab discovery
python -m restaurant_integration_lab model
python -m restaurant_integration_lab location1
python -m restaurant_integration_lab location2
python -m restaurant_integration_lab normalize
python -m restaurant_integration_lab reservations
python -m restaurant_integration_lab labor
python -m restaurant_integration_lab inventory
python -m restaurant_integration_lab exceptions
python -m restaurant_integration_lab briefing
python -m restaurant_integration_lab operations
python -m restaurant_integration_lab readiness
python -m restaurant_integration_lab onboard
python -m restaurant_integration_lab stress-test
python -m restaurant_integration_lab economics
python -m restaurant_integration_lab build-vs-buy
python -m restaurant_integration_lab capstone
```

The installed `restaurant-integration-lab` script accepts the same command names. `verify` runs every deterministic report twice and checks stable, nonempty output; it explicitly does not replace `pytest`.

# Suggested Study Path

1. Run `hypothesis`; read Chapter 0.
2. Run `discovery`; read Chapter 1.
3. Run `model`; read Chapter 2.
4. Run `location1`; read Chapter 3.
5. Run `location2`; read Chapter 4.
6. Run `normalize`; read Chapter 5.
7. Run `reservations`; read Chapter 6.
8. Run `labor`; read Chapter 7.
9. Run `inventory`; read Chapter 8.
10. Run `exceptions`; read Chapter 9.
11. Run `briefing`; read Chapter 10.
12. Run `operations` and `readiness`; read Chapter 11.
13. Run `onboard`; read Chapter 12.
14. Run `stress-test`; read Chapter 13.
15. Run `economics`; read Chapter 14.
16. Run `build-vs-buy`; read Chapter 15.
17. Run `capstone`; read Chapter 16.

## Key experiments

- **Location #1 → Location #2:** tests which canonical types, calculations, and mapping machinery are demonstrated reuse while keeping each POS parser source-specific.
- **Cross-system integration:** adds reservations, labor, and inventory without treating incomplete evidence as zero or erasing domain limitations.
- **JRH-006 onboarding:** demonstrates a mostly standardized marginal onboarding dominated by configuration, explicit mappings, tests, and operational setup—not measured hours.
- **JRH-007 stress test:** adds a non-standard acquisition whose new parsers, weak identifiers, manual delivery, briefing limits, and support surfaces visibly erode reuse.
- **Delivery economics:** compares fictional modeled delivery with observed implementation structure and separately labeled sensitivity assumptions.
- **Build versus buy:** keeps BUY / CONFIGURE, NARROW CUSTOM, FULL CUSTOM, STANDARDIZE FIRST, INVESTIGATE, and DO NOTHING / DEFER reachable; alternative capabilities remain fictional assumptions.
- **Capstone:** derives the final verdict and delivery classification from explicit evidence and rules rather than retaining the original modeled verdict.

## Final findings

Primary verdict: **INVESTIGATE**. The executable capstone classifies the demonstrated shape as a **repeatable custom service / productized delivery**, not a demonstrated software product. Shared identity, provenance, exceptions, calculations, and briefing structure survived; parser, mapping, operational, inventory, and support work remained conditional on standardization. A standardized group should test **BUY / CONFIGURE** first and reserve **NARROW CUSTOM** for a verified bounded gap; a fragmented acquired group points toward **STANDARDIZE FIRST**.

## What remains unvalidated

- actual engineering hours, including whether 234 hours is realistic;
- real customer value and realized operational benefit;
- real willingness to pay;
- real support frequency and cost;
- actual SaaS capabilities and pricing;
- real sales-cycle and customer-acquisition economics;
- real restaurant data quality;
- production behavior, adoption, security, scale, and on-call operations.

## Real-world validation

Next discovery should verify that real multi-location operators experience the management problem, quantify current decision and exception costs, inspect representative schemas and identifier stability, test source access and ownership, review native reporting and real vendor alternatives, assess willingness to standardize, and measure delivery/support effort. Those questions qualify the hypothesis; they do not turn this synthetic lab into a sales claim.
