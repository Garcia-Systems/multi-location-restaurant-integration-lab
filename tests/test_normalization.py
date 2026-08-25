from datetime import date
from decimal import Decimal

from restaurant_integration_lab.cli import main
from restaurant_integration_lab.normalization import (
    CATEGORY_MAPPINGS, LOCATION_MAPPINGS, PRODUCT_MAPPINGS, MissingValue,
    NormalizationStatus, ProductMappingStatus, build_dataset, mapping_change_experiment,
    normalization_report, normalize_category, normalize_discount,
    resolve_canonical_product,
)
from restaurant_integration_lab.operational_model import resolve_location, resolve_product
from restaurant_integration_lab.operational_model import Product, ProductMapping, SourceIdentity


def test_location_identity_is_explicit_and_unknown_is_unresolved() -> None:
    assert resolve_location("SOURCE SYSTEM A", "store_14", LOCATION_MAPPINGS).value.canonical_id == "JRH-001"
    assert resolve_location("SOURCE SYSTEM B", "WBG02", LOCATION_MAPPINGS).value.canonical_id == "JRH-002"
    assert not resolve_location("SOURCE SYSTEM A", "restaurant name", LOCATION_MAPPINGS).resolved


def test_products_converge_only_through_explicit_mapping() -> None:
    one = resolve_product("HarborTill RRK", "MENU-771", PRODUCT_MAPPINGS)
    two = resolve_product("HarborTill CST", "ENTREE-044", PRODUCT_MAPPINGS)
    assert one.value == two.value
    assert not resolve_product("HarborTill CST", "Charred Oysters", PRODUCT_MAPPINGS).resolved
    assert resolve_canonical_product("HarborTill CST", "NEW-777").status is ProductMappingStatus.EXPLICITLY_UNMAPPED
    conflict = PRODUCT_MAPPINGS + (ProductMapping(SourceIdentity("HarborTill CST", "ENTREE-044"),
                                                   Product("CONFLICT", "Not the same item")),)
    assert resolve_canonical_product("HarborTill CST", "ENTREE-044", conflict).status is ProductMappingStatus.CONFLICT


def test_category_and_missing_semantics_are_explicit() -> None:
    assert CATEGORY_MAPPINGS[("HarborTill RRK", "Entrees")] == "MAIN"
    assert normalize_category("HarborTill CST", "MAINS") == ("MAIN", "RESOLVED")
    assert normalize_category("HarborTill RRK", "Raw Bar")[0] is None
    assert normalize_category("HarborTill CST", "")[1] == "NOT PROVIDED"
    assert normalize_discount("HarborTill RRK", None) is MissingValue.NOT_PROVIDED


def test_money_signs_normalize_to_positive_reductions_exactly() -> None:
    assert normalize_discount("HarborTill RRK", Decimal("2.00")) == Decimal("2.00")
    assert normalize_discount("HarborTill CST", Decimal("-2.00")) == Decimal("2.00")


def test_dataset_is_deterministic_safe_and_keeps_exclusions_visible() -> None:
    data = build_dataset()
    assert data == build_dataset()
    assert data.sales_by_location() == (("JRH-001", Decimal("83.60")), ("JRH-002", Decimal("39.00")))
    assert data.sales_by_business_date() == (("2026-08-24", Decimal("83.60")), ("2026-08-25", Decimal("39.00")))
    assert data.product_totals().excluded_count == 2
    assert {item.source_record_id for item in data.product_totals().excluded} == {"CHK-1005:1", "9005/01"}
    assert all(item.sale is None for item in data.product_totals().excluded)
    assert any(item.status is NormalizationStatus.PARTIAL for item in data.outcomes)


def test_mapping_change_is_configuration_not_parser_work() -> None:
    assert mapping_change_experiment() == ("EXPLICITLY UNMAPPED", "JRH-P-006")


def test_coverage_and_cli_are_deterministic(capsys) -> None:
    data = build_dataset()
    assert [(c.rows_parsed, c.fully_normalized, c.partial, c.rejected_structurally,
             c.unresolved_product, c.unresolved_location, c.duplicate) for c in data.coverage] == [
        (10, 2, 4, 3, 1, 1, 1), (9, 3, 3, 2, 1, 1, 1)]
    report = normalization_report()
    assert report == normalization_report()
    assert "After: resolved through configuration -> JRH-P-006" in report
    assert main(["normalize"]) == 0
    assert capsys.readouterr().out == report + "\n"
