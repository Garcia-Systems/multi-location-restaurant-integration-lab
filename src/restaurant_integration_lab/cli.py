"""Command-line reports for completed chapters."""

from collections.abc import Sequence

from .models import CASE_1, CASE_2, OpportunityScenario
from .discovery import discovery_report
from .model_demo import model_report
from .location1 import location1_report
from .location2 import location2_report
from .normalization import normalization_report
from .reservations import reservations_report
from .labor import labor_report
from .inventory import inventory_report
from .exceptions import exception_report
from .briefing import briefing_report
from .operations import operations_report, readiness_report
from .onboarding import onboarding_report
from .stress_test import stress_test_report
from .economics import economics_report
from .build_vs_buy import build_vs_buy_report
from .capstone import capstone_report


def _currency(value: int) -> str:
    return f"${value:,.0f}"


def format_scenario(scenario: OpportunityScenario) -> str:
    """Format one fictional scenario and label its values as assumptions."""

    lines = [
        f"CASE {scenario.case_number} — {scenario.name}",
        "MODELED ASSUMPTION",
        f"Recoverable value: {_currency(scenario.recoverable_value)}",
        f"Engineering hours: {scenario.modeled_engineering_hours}",
        f"Implementation price: {_currency(scenario.implementation_price)}",
        f"Customer payback: {scenario.customer_payback_months} months",
        f"Verdict: {scenario.verdict}",
    ]
    if scenario.work_category_hours:
        lines.extend(
            ["", "Modeled engineering work categories:"]
            + [f"- {category.value}: {hours} hours" for category, hours in scenario.work_category_hours.items()]
        )
    return "\n".join(lines)


def comparison_report() -> str:
    """Return the inspectable Chapter 0 hypothesis report."""

    value_multiple = CASE_2.recoverable_value / CASE_1.recoverable_value
    effort_multiple = CASE_2.modeled_engineering_hours / CASE_1.modeled_engineering_hours
    return "\n\n".join(
        [
            format_scenario(CASE_1),
            format_scenario(CASE_2),
            "\n".join(
                [
                    "HYPOTHESIS",
                    f"Modeled recoverable value increased by {value_multiple:.2f}×.",
                    f"Modeled engineering effort increased by {effort_multiple:.2f}×.",
                    "This relationship is a MODELED ASSUMPTION, not a validated result.",
                    "OBSERVED LAB RESULT: none yet for implementation reuse.",
                ]
            ),
        ]
    )


REPORTS = {
    "hypothesis": comparison_report,
    "discovery": discovery_report,
    "model": model_report,
    "location1": location1_report,
    "location2": location2_report,
    "normalize": normalization_report,
    "reservations": reservations_report,
    "labor": labor_report,
    "inventory": inventory_report,
    "exceptions": exception_report,
    "briefing": briefing_report,
    "operations": operations_report,
    "readiness": readiness_report,
    "onboard": onboarding_report,
    "stress-test": stress_test_report,
    "economics": economics_report,
    "build-vs-buy": build_vs_buy_report,
    "capstone": capstone_report,
}

COMMAND_DESCRIPTIONS = {
    "hypothesis": "Chapter 0 modeled opportunity hypothesis",
    "discovery": "Chapter 1 synthetic source discovery",
    "model": "Chapter 2 shared operational model",
    "location1": "Chapter 3 first source-specific integration",
    "location2": "Chapter 4 second-location reuse experiment",
    "normalize": "Chapter 5 cross-location normalization",
    "reservations": "Chapter 6 reservation demand context",
    "labor": "Chapter 7 labor context",
    "inventory": "Chapter 8 inventory boundaries",
    "exceptions": "Chapter 9 exceptions and data quality",
    "briefing": "Chapter 10 group management briefing",
    "operations": "Chapter 11 operational runtime simulation",
    "readiness": "Chapter 11 simulated readiness checks",
    "onboard": "Chapter 12 standardized JRH-006 onboarding",
    "stress-test": "Chapter 13 non-standard JRH-007 stress test",
    "economics": "Chapter 14 modeled delivery economics",
    "build-vs-buy": "Chapter 15 fictional-alternative analysis",
    "capstone": "Chapter 16 evidence-derived final verdict",
}


def help_report() -> str:
    """Return a compact index for the completed executable textbook."""

    lines = [
        "Multi-Location Restaurant Integration Lab — command index",
        "usage: python -m restaurant_integration_lab COMMAND",
        "",
    ]
    lines.extend(f"  {command:<13} {description}" for command, description in COMMAND_DESCRIPTIONS.items())
    lines += [
        "  verify        Run deterministic checks for every chapter report",
        "",
        "All people, restaurants, systems, fixtures, and commercial values are fictional or synthetic.",
        "Run `pytest` separately for the complete behavioral test suite.",
    ]
    return "\n".join(lines)


def verification_report() -> str:
    """Execute each deterministic report twice and confirm stable, nonempty output."""

    checks = []
    for command, report in REPORTS.items():
        first = report()
        checks.append(f"{command}: {'PASS' if first and first == report() else 'FAIL'}")
    status = "PASS" if all(line.endswith("PASS") for line in checks) else "FAIL"
    return "\n".join([
        "EXECUTABLE TEXTBOOK VERIFICATION",
        "Deterministic internal report checks (not a replacement for pytest)",
        *checks,
        f"OVERALL: {status}",
        "Complete behavioral suite: pytest",
    ])


def main(argv: Sequence[str] | None = None) -> int:
    """Print the requested chapter report; retain Chapter 0 as the default."""

    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    command = arguments[0] if arguments else "hypothesis"
    if len(arguments) == 1 and command in {"-h", "--help", "help"}:
        print(help_report())
        return 0
    if len(arguments) > 1 or command not in {*REPORTS, "verify"}:
        print(help_report(), file=sys.stderr)
        return 2
    report = verification_report if command == "verify" else REPORTS[command]
    output = report()
    print(output)
    return 1 if command == "verify" and "OVERALL: FAIL" in output else 0


if __name__ == "__main__":
    raise SystemExit(main())
