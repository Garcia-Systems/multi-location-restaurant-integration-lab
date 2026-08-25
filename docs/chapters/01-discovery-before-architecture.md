# Chapter 1 — Discovery Before Architecture

> **Fiction notice:** Every restaurant, vendor, interface, capability, and finding in this chapter is synthetic lab evidence. It is not market validation or a claim about real restaurants.

> Architecture is a response to discovered constraints, not a drawing created before discovery.

## Why discovery comes first

An integration cannot be designed responsibly from a list of desired dashboards. Discovery must establish authoritative sources, actual access paths, identifiers, permissions, samples, schemas, and existing features first. Business questions constrain collection: the group wants comparisons of sales, labor relative to demand, inventory and waste anomalies, evidence gaps, and exceptions—not every available field.

Run the executable evidence:

```bash
python -m restaurant_integration_lab hypothesis
python -m restaurant_integration_lab discovery
pytest
```

## What the synthetic environment revealed

All five locations use the fictional **HarborTill** POS family. That similarity is promising, but it is not a common interface: RRK has REST/JSON, CST receives scheduled CSV with US-style dates, BHO receives scheduled CSV with ISO dates and migrated duplicate product IDs, MBC runs a legacy SFTP tab-delimited export, and JRS relies on a weekly manual CSV. Business-date behavior also differs.

The strongest reuse signals are the group-wide **ShiftHarbor** labor API and **EchoGuest** feedback export. RRK and BHO also share **TableCurrent** reservations and **StockPilot** inventory. Their identifiers still require scrutiny: POS menu IDs remain location-local, BHO has duplicate migrated IDs, MBC uses a legacy store number, and some JRS spreadsheet identifiers are unstable.

Concept differences are legitimate rather than defects. CST takes no reservations. MBC's BakeAhead preorders and JRS event calendar are reservation-like demand signals, but are not equivalent to restaurant bookings. Inventory is less standardized: two locations share StockPilot, CST counts in a sheet, MBC exports production batches, and JRS has an unconfirmed Pit Ledger access path. Manual RRK event data and a mutable JRS category override add narrow, plausible exceptions.

## Build versus buy remains open

Fragmentation does not itself justify custom software. HarborTill may offer a licensed group sales dashboard, TableCurrent may offer multi-venue pacing, and confirmed ShiftHarbor, StockPilot, and EchoGuest reports already cover portions of the proposed briefing. Vendor/licensing review must determine whether configuration, scheduled reports, multi-location features, or BI connectors remove custom requirements. The discovery fixture deliberately records these capabilities next to source details.

## Why readiness is `NOT READY`

The readiness function applies deterministic gates. Every domain at every location is either represented or explicitly absent, authoritative ownership is recorded, location IDs exist, and management questions are defined. Architecture is nevertheless blocked because some intended sources have neither a sample nor schema, TableCurrent's permission owner is unknown, Pit Ledger's access method and owner are unknown, and important native capabilities still require review. The CLI prints every failed gate rather than collapsing them into a fictional complexity score.

No universal adapter can responsibly be inferred from a shared vendor-family label. Chapter 1 implements no adapter, canonical operational record, import pipeline, database, API, dashboard, or calculation.

## Evidence required before Chapter 2

Before defining a shared operational model, obtain and inspect representative CST and JRS POS files, the MBC legacy schema, inventory samples, and the reservation/event shapes. Confirm business-date rules, identifier uniqueness, permissions and credential owners, history windows, export reliability, category semantics, and native report coverage. Only those concrete source fields and management definitions should inform Chapter 2.

The observed results in the CLI are observations of this repository's synthetic fixtures only. They weaken the modeled assumption that shared ownership automatically yields uniform integrations, while the shared labor, feedback, and partial POS footprint leave meaningful reuse plausible. The economic hypothesis remains open.

> Evidence before abstraction.
