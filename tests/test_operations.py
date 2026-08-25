from datetime import datetime
import json

import pytest

from restaurant_integration_lab.operations import (
    CUSTOMER_ID, FailureCategory, FakeCredentialProvider, InMemoryOperationalStore,
    ConflictingReplayError, RetryPolicy, RunStatus, due_jobs, execute_with_retry,
    load_config, operations_report, readiness_checks, readiness_report,
)


def test_configuration_is_scoped_and_contains_references_not_secrets():
    configs = load_config()
    assert configs and {c.customer_id for c in configs} == {CUSTOMER_ID}
    assert all(c.source_system and c.credential_ref.startswith("secret://") for c in configs)
    serialized = json.dumps([c.__dict__ for c in configs], default=str)
    assert "password" not in serialized and "api_key" not in serialized


def test_credentials_are_resolved_but_redacted_from_deterministic_report():
    secret = "synthetic-secret-never-log"
    ref = load_config()[0].credential_ref
    assert FakeCredentialProvider({ref: secret}).resolve(ref) == secret
    report = operations_report()
    assert secret not in report and "[REDACTED]" in report
    assert report == operations_report()


def test_due_jobs_are_deterministic_and_weekly_job_is_not_due():
    configs = load_config()
    now = datetime(2026, 8, 25, 9)
    result = due_jobs(configs, now, {"inventory-weekly": datetime(2026, 8, 24, 9)})
    assert [c.job_id for c in result] == ["labor-daily", "pos-rrk-daily", "reservations-daily"]


def test_record_and_batch_replay_are_idempotent_and_conflict_is_rejected():
    config = load_config()[0]
    store = InMemoryOperationalStore()
    first = store.ingest(config, "batch", ({"id": "one"},), "run-1")
    replay = store.ingest(config, "batch", ({"id": "one"},), "run-2")
    assert first.status is RunStatus.SUCCEEDED
    assert replay.status is RunStatus.SAFE_REPLAY and len(store.evidence) == 1
    # A new batch containing an identical source record also creates no evidence.
    duplicate_record = store.ingest(config, "batch-2", ({"id": "one"},), "run-3")
    assert duplicate_record.records_accepted == 0 and len(store.evidence) == 1
    with pytest.raises(ConflictingReplayError):
        store.ingest(config, "batch", ({"id": "one", "changed": True},), "run-4")


def test_partial_recovery_and_correlation_do_not_duplicate_evidence():
    config = load_config()[0]
    store = InMemoryOperationalStore()
    before = store.ingest(config, "before", ({"id": "known"}, {"id": "new", "valid": False}), "run-before")
    after = store.ingest(config, "after", ({"id": "known"}, {"id": "new"}), "run-after")
    assert before.status is RunStatus.PARTIAL and after.status is RunStatus.SUCCEEDED
    assert len(store.evidence) == 2
    assert store.evidence[-1].run_id == "run-after" and store.evidence[-1].batch_id == "after"


def test_retry_policy_uses_failure_semantics_and_success_is_unique():
    config = load_config()[0]
    store = InMemoryOperationalStore()
    result, decisions = execute_with_retry(
        lambda attempt: FailureCategory.TEMPORARY_SOURCE_UNAVAILABLE if attempt < 3 else
        store.ingest(config, "retry-batch", ({"id": "only"},), "retry-run"), RetryPolicy())
    assert result and result.retry_attempt == 3 and len(store.evidence) == 1
    assert [d.retry for d in decisions] == [True, True]
    result, decisions = execute_with_retry(lambda _: FailureCategory.SCHEMA_CHANGE, RetryPolicy())
    assert result is None and len(decisions) == 1 and not decisions[0].retry


def test_readiness_finds_missing_configuration_and_normal_config_is_ready():
    provider = FakeCredentialProvider({})
    assert any(c.result == "FAIL" for c in readiness_checks((), provider))
    assert "NOT READY FOR LAB OPERATION" in readiness_report(())
    assert "READY FOR LAB OPERATION" in readiness_report()


def test_failure_isolation_and_operational_outcomes_are_visible():
    report = operations_report()
    assert "pos-rrk-daily: SUCCEEDED" in report
    assert "labor-daily: FAILED (independent scenario)" in report
    assert "reservations-daily: PARTIAL" in report
    assert "SAFE REPLAY" in report and "CONFLICTING REPLAY" in report

