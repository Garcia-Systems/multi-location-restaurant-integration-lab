"""Command-line comparison for Chapter 0."""

from collections.abc import Sequence

from .models import CASE_1, CASE_2, OpportunityScenario


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


def main(argv: Sequence[str] | None = None) -> int:
    """Print Chapter 0. ``argv`` is reserved for future chapter commands."""

    del argv
    print(comparison_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

