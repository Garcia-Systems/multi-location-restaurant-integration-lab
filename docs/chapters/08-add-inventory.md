# Chapter 8 — Add Inventory

> **Fiction notice:** StockPilot, CST Weekly Count, every restaurant, mapping, count, and exception in this chapter is synthetic lab evidence. Existing fictional sources remain authoritative.

## Run the experiment first

```bash
python -m restaurant_integration_lab inventory
pytest
```

The command ingests a structured StockPilot JSON count for River & Rail Kitchen (`JRH-001`) and a manual CST Weekly Count spreadsheet CSV for Canal Street Tacos (`JRH-002`). This preserves Chapter 1's discovered landscape rather than inventing one uniform inventory interface. Only `PHYSICAL_COUNT` is accepted; a count is never relabeled as usage, waste, an adjustment, or theoretical inventory.

## Why inventory is harder

Sales lines describe sellable menu products in transaction units. Physical counts describe stock items at a point in time, in units that can change the meaning of the number. A menu oyster product and shucked oyster stock can be associated for context, but they are not the same identity. Likewise, `12 EACH`, `2 CASE`, and `3 LB` are not quantities that can be summed merely because their product labels look related.

The executable boundary is deliberately narrow:

```text
AUTHORITATIVE INVENTORY SYSTEM / SHEET
  -> synthetic export -> source parser -> validation
  -> location + inventory-item + count-date + unit normalization
  -> canonical inventory evidence -> safe aggregation or explicit refusal
```

It does not implement purchasing, receiving, vendors, transfers, replenishment, a physical-count workflow, recipes/BOMs, perpetual inventory, food cost, or optimization.

## Product identity was not sufficient

Chapter 2's `Product` described a common operational product and was exercised by POS sales. Inventory exposed a bad universal assumption: a counted ingredient is not automatically a sellable product. Chapter 8 adds `InventoryItem` and lets an inventory item carry a narrowly described, optional menu association. `JRH-I-002` Shucked Oyster Meat has a context-only association to `JRH-P-001` James River Oysters. The note explicitly denies recipe, portion, or usage meaning.

StockPilot SKU `BEEF-PATTY-8OZ` and the mutable spreadsheet name `Beef Patties` map explicitly to `JRH-I-001`. An unknown identifier remains unresolved. The deliberately ambiguous spreadsheet name maps to two items in configuration and produces `CONFLICTING MAPPING`; the importer does not select one.

## Unit semantics and conversions

The small supported vocabulary is `EACH`, `CASE`, `LB`, and `OZ`. Unknown units stay unresolved. CST's blank UOM does not become `EACH`, because the source contract defines no such default.

The generic physical conversion `1 LB = 16 OZ` is explicit. Case packing is different: it depends on the inventory item and source SKU. The CLI runs the same parser before and after adding the configuration `PATTY-CASE: 1 CASE = 40 EACH`. Before configuration, `2 CASE` is unresolved; afterward it becomes `80 EACH`. No universal case factor exists.

Safe aggregation consumes normalized evidence only. It refuses unresolved conversion results, mixed inventory items, and incompatible unit dimensions. Excluded quantities remain visible in exceptions and are never silently included in a total.

## Count date is not arrival time

`BusinessDate` holds the effective count date supplied by the source; `InventoryRecord.evidence_arrived_at` separately preserves when the export arrived. The StockPilot fixture describes August 24 and arrives August 26. It remains August 24 evidence. This is point-in-time count evidence, not transaction activity throughout the sales business day, and the report does not claim timestamp precision the source lacks.

## Missing and unresolved evidence

The fixtures include successful paths plus an unknown item, unknown and missing units, a missing pack conversion, incompatible dimensions, malformed and negative quantities, an unknown location, a duplicate record, and a conflicting mapping. Structural failures are rejected. Mapping, unit, and conversion uncertainty is inspectable through categorized exceptions; conversion-blocked canonical evidence also carries an unresolved status and reason.

Deterministic measures are intentionally modest: normalized quantities by location/item/unit, accepted and unresolved counts, mapping/unit/conversion exceptions, duplicate count, and excluded evidence. They do not calculate theoretical usage or food cost.

## Why sales cannot be reconciled automatically

The report places accepted RRK menu-item sales beside RRK physical-count evidence only as cross-domain context. It returns `NOT RECONCILABLE WITH AVAILABLE EVIDENCE` because recipe/portion relationships, beginning inventory, receipts, waste, and transfers are absent. A context-only menu association is not a recipe. Fabricating those inputs would make a formula executable but false.

## Reuse evidence and forced change

**Demonstrated cross-system reuse:** canonical location and business-date identity, namespaced source identity, provenance, exception/event collection, and deterministic report structures survived.

**Configuration reuse:** location mappings, explicit inventory-item mappings, and product/SKU-specific pack conversion rules use configuration rather than parser edits.

**New system-specific work:** StockPilot JSON parsing, CST spreadsheet parsing, explicit units, count-date/arrival semantics, pack conversion, and safe inventory aggregation.

**Rework:** the canonical model gained `InventoryItem` plus inventory arrival time. **Rejected reuse candidates:** menu `Product` as a universal stock identity, and POS quantity/reconciliation behavior as inventory behavior.

This weakens a simplistic reuse hypothesis while preserving a narrower one: operational infrastructure can survive even when domain identity and measurement semantics do not. The observed results show that location identity reused unchanged, unit semantics were new, case conversion was configuration, late counts retained their effective date, and reconciliation was refused safely.

## Boundary for the next chapter

Chapter 9 remains unimplemented. It should challenge whether the accumulated categorized failures can become an understandable data-quality workflow without erasing unresolved evidence or turning uncertainty into guessed corrections.
