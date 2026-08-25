from datetime import date
import pytest
from restaurant_integration_lab.exceptions import (CompletenessStatus, DuplicateKind, MappingRegistry,
    ResolutionState, RetryClass, SchemaStatus, SourceSystem, classify_duplicate,
    configuration_resolution_experiment, exception_report, lab_batches, support_evidence, validate_schema)
from restaurant_integration_lab.ingestion import ExceptionCategory


def test_all_systems_emit_unified_representation_and_preserve_reason():
    batches = lab_batches(); rows = [e for b in batches for e in b.exceptions]
    assert {e.source_system for e in rows} == set(SourceSystem)
    assert any(e.reason == "malformed party size" for e in rows)
    assert all(e.detected_at.isoformat() == "2026-08-27T09:00:00" for e in rows)


def test_schema_change_and_missing_identifier_are_visible():
    error = validate_schema()
    assert error.category is ExceptionCategory.SCHEMA_CHANGE
    assert "transaction_id" in error.reason and "check_number" in error.reason
    missing = [e for b in lab_batches() for e in b.exceptions if "transaction_id" in e.reason]
    assert missing and missing[0].source_record_id != "<generated>"


def test_exact_and_conflicting_duplicates_are_distinct():
    exact = classify_duplicate("A", {"money": "1"}, {"money": "1"})
    conflict = classify_duplicate("A", {"money": "1"}, {"money": "2"})
    assert exact.duplicate_kind is DuplicateKind.EXACT_REPLAY and exact.resolution is ResolutionState.NOT_ACTIONABLE
    assert conflict.duplicate_kind is DuplicateKind.CONFLICTING_DUPLICATE
    assert conflict.category is ExceptionCategory.CONFLICTING_IDENTIFIER and conflict.human_action_required


def test_late_dates_and_valid_but_incomplete_batch_remain_distinct():
    batches = lab_batches()
    late = next(e for b in batches for e in b.exceptions if e.category is ExceptionCategory.LATE_DATA)
    assert late.effective_date == date(2026, 8, 24) and late.observed_at.date() == date(2026, 8, 26)
    incomplete = next(b for b in batches if b.completeness_status is CompletenessStatus.INCOMPLETE)
    invalid = next(b for b in batches if b.schema_status is SchemaStatus.INVALID)
    assert incomplete.schema_status is SchemaStatus.VALID
    assert invalid.completeness_status is CompletenessStatus.COMPLETE


def test_configuration_resolution_unknown_retry_and_mapping_conflict():
    before, after = configuration_resolution_experiment()
    assert before.retry is RetryClass.CORRECTION_REQUIRED and before.resolution is ResolutionState.OPEN
    assert after.resolution is ResolutionState.RESOLVED_BY_CONFIGURATION
    registry = MappingRegistry({"P-100": "CANONICAL-A"}); registry.add("P-100", "CANONICAL-A")
    with pytest.raises(ValueError, match="already maps"): registry.add("P-100", "CANONICAL-B")


def test_malformed_values_require_source_correction_and_action_is_deterministic():
    rows = [e for b in lab_batches() for e in b.exceptions]
    malformed = [e for e in rows if e.category is ExceptionCategory.MALFORMED_RECORD]
    assert malformed and all(e.source_correction_required for e in malformed)
    assert all(e.retry is RetryClass.CORRECTION_REQUIRED and not e.configuration_resolvable for e in malformed)
    assert [(e.category, e.human_action_required) for e in rows] == [(e.category, e.human_action_required) for b in lab_batches() for e in b.exceptions]


def test_batch_counts_grouping_support_and_cli_are_deterministic(capsys):
    batches = lab_batches(); pos = batches[0]
    assert (pos.records_read, pos.records_accepted, pos.records_rejected, pos.duplicate_count, pos.unresolved_mapping_count) == (10, 4, 5, 1, 2)
    support = support_evidence(e for b in batches for e in b.exceptions)
    assert support.human_mapping_categories > 0 and support.source_format_or_schema_problems == 1
    assert support.retryable_operational_failures == 0 and support.code_changes_required == 1
    report = exception_report(); assert report == exception_report()
    for heading in ("EXCEPTION COUNTS BY SYSTEM", "EXCEPTION COUNTS BY CATEGORY", "SCHEMA CHANGE EXAMPLE",
                    "DUPLICATE CONFLICT EXAMPLE", "INCOMPLETE BATCHES", "SUPPORT OBLIGATION EVIDENCE"):
        assert heading in report
    from restaurant_integration_lab.cli import main
    assert main(["exceptions"]) == 0 and capsys.readouterr().out == report + "\n"
