from dataclasses import replace
from decimal import Decimal

from restaurant_integration_lab.briefing import (
    BriefingPriority, EvidenceState, SignalCategory, briefing_report,
    build_management_briefing,
)
from restaurant_integration_lab.normalization import build_dataset


def test_group_sales_are_accepted_canonical_evidence_and_exclusions_remain_visible():
    dataset = build_dataset()
    briefing = build_management_briefing(dataset=dataset)
    assert briefing.group_net_sales == sum((sale.net_amount for sale in dataset.accepted_sales), Decimal())
    assert briefing.accepted_sales == len(dataset.accepted_sales) == 8
    assert briefing.excluded_sales == 4
    assert "Excluded/unresolved sales records: 4" in briefing_report(briefing)


def test_reservation_absence_and_missing_labor_are_explicit():
    briefing = build_management_briefing(labor=())
    locations = {row.location_id: row for row in briefing.locations}
    assert locations["JRH-002"].reservation_state is EvidenceState.NOT_APPLICABLE
    output = briefing_report(briefing)
    assert "JRH-002: NOT APPLICABLE" in output
    assert "JRH-001: UNAVAILABLE — required joined canonical evidence missing" in output
    assert "sales/worked hour=$" not in output.split("LABOR CONTEXT", 1)[1].split("INVENTORY CONTEXT", 1)[0]


def test_inventory_limits_and_open_exceptions_are_first_class():
    output = briefing_report()
    assert "Reconciliation: NOT RECONCILABLE WITH AVAILABLE EVIDENCE" in output
    assert "Open human-action exceptions:" in output
    assert "Conflicting duplicates: 1" in output
    assert "Incomplete batches: 1" in output
    assert "No inventory usage or food cost is implied" in output


def test_signal_categories_and_priorities_are_deterministic():
    first = build_management_briefing().signals
    second = build_management_briefing().signals
    assert first == second
    assert {row.category for row in first} == {SignalCategory.OPERATIONAL, SignalCategory.DATA_QUALITY}
    ranks = {BriefingPriority.HIGH: 0, BriefingPriority.MEDIUM: 1, BriefingPriority.LOW: 2}
    assert [ranks[row.priority] for row in first] == sorted(ranks[row.priority] for row in first)


def test_lower_level_incompleteness_blocks_product_not_safe_location_total():
    briefing = build_management_briefing()
    jrh2 = next(row for row in briefing.locations if row.location_id == "JRH-002")
    assert jrh2.sales_state is EvidenceState.PARTIAL
    assert jrh2.net_sales == Decimal("39.00")
    signal = next(row for row in briefing.signals if row.location_id == "JRH-002" and row.signal == "PRODUCT COMPARISON LIMITED")
    assert EvidenceState.BLOCKED.value in signal.limit
    assert "location net sales remains partial but usable" in signal.limit


def test_changing_canonical_input_changes_output_without_raw_source_parsing():
    dataset = build_dataset()
    original = dataset.accepted_sales[0]
    changed_sale = replace(original, net_amount=original.net_amount + Decimal("10.00"),
                           gross_amount=original.gross_amount + Decimal("10.00"))
    changed_outcomes = tuple(replace(row, sale=changed_sale) if row.sale == original else row
                             for row in dataset.outcomes)
    changed = replace(dataset, outcomes=changed_outcomes)
    assert build_management_briefing(dataset=changed).group_net_sales == Decimal("132.60")
    assert "Canonical net sales: $132.60" in briefing_report(build_management_briefing(dataset=changed))


def test_briefing_output_is_deterministic_and_preserves_limits():
    assert briefing_report() == briefing_report()
    output = briefing_report()
    assert "OPERATIONAL INVESTIGATION" in output
    assert "DATA QUALITY INVESTIGATION" in output
    assert "OMITTED — cost evidence incomplete" in output
    assert "Reservation covers are not necessarily total restaurant covers" in output
    assert "What changed: unavailable" in output
    assert "No alert, forecast, staffing recommendation" in output
