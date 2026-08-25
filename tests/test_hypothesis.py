from decimal import Decimal

from restaurant_integration_lab.cli import comparison_report, main
from restaurant_integration_lab.models import CASE_1, CASE_2


def test_case_1_modeled_values() -> None:
    assert CASE_1.recoverable_value == 10_392
    assert CASE_1.modeled_engineering_hours == 150
    assert CASE_1.implementation_price == 15_000
    assert CASE_1.customer_payback_months == Decimal("24.4")
    assert CASE_1.verdict == "NO DEAL"


def test_case_2_modeled_values() -> None:
    assert CASE_2.recoverable_value == 67_070
    assert CASE_2.implementation_price == 42_000
    assert CASE_2.customer_payback_months == Decimal("8.7")
    assert CASE_2.verdict == "PROMISING — VALIDATE IN DISCOVERY"


def test_case_2_work_categories_total_234_hours() -> None:
    assert CASE_2.work_category_hours is not None
    assert sum(CASE_2.work_category_hours.values()) == 234
    assert CASE_2.modeled_engineering_hours == 234


def test_help_indexes_all_chapters_and_verify_runs_every_report(capsys) -> None:
    assert main(["--help"]) == 0
    help_output = capsys.readouterr().out
    assert "hypothesis" in help_output and "capstone" in help_output
    assert "fictional or synthetic" in help_output

    assert main(["verify"]) == 0
    verification = capsys.readouterr().out
    assert "OVERALL: PASS" in verification
    assert "not a replacement for pytest" in verification


def test_group_has_greater_modeled_recoverable_value() -> None:
    assert CASE_2.recoverable_value > CASE_1.recoverable_value


def test_report_separates_assumptions_from_results() -> None:
    report = comparison_report()
    assert report.count("MODELED ASSUMPTION") >= 3
    assert "not a validated result" in report
    assert "OBSERVED LAB RESULT: none yet for implementation reuse" in report
