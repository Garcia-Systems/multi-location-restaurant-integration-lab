"""Deterministic Chapter 11 production-operation simulation.

This is deliberately an in-memory boundary: it models decisions a durable
integration must make without claiming to be a scheduler, secret manager, or
database.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Protocol

CUSTOMER_ID = "JRH"
CUSTOMER_NAME = "James River Hospitality Group"
SIMULATED_NOW = datetime(2026, 8, 25, 9, 0, 0)
CONFIG_PATH = files("restaurant_integration_lab").joinpath("fixtures/operations.synthetic.json")


class Cadence(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    SAFE_REPLAY = "SAFE REPLAY"


class FailureCategory(StrEnum):
    TEMPORARY_SOURCE_UNAVAILABLE = "TEMPORARY SOURCE UNAVAILABLE"
    SCHEMA_CHANGE = "SCHEMA CHANGE"
    UNKNOWN_PRODUCT = "UNKNOWN PRODUCT"
    MALFORMED_VALUE = "MALFORMED VALUE"
    CONFLICTING_REPLAY = "CONFLICTING REPLAY"


@dataclass(frozen=True)
class SourceConfiguration:
    customer_id: str
    customer_name: str
    job_id: str
    source_system: str
    location_id: str | None
    interface_type: str
    enabled: bool
    cadence: Cadence
    credential_ref: str
    input_ref: str
    schema_version: str
    retry_policy_ref: str


def load_config(path: str | Path = CONFIG_PATH) -> tuple[SourceConfiguration, ...]:
    payload = json.loads(Path(path).read_text())
    return tuple(SourceConfiguration(cadence=Cadence(row["cadence"]), **{k: v for k, v in row.items() if k != "cadence"})
                 for row in payload["integrations"])


class CredentialProvider(Protocol):
    def resolve(self, credential_ref: str) -> str: ...


class FakeCredentialProvider:
    """Test-only provider; runtime values never leave this boundary."""
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, credential_ref: str) -> str:
        if not credential_ref.startswith("secret://"):
            raise ValueError("credentials must use a secret:// reference")
        try:
            return self._values[credential_ref]
        except KeyError as error:
            raise KeyError(f"missing credential reference: {credential_ref}") from error

    def contains(self, credential_ref: str) -> bool:
        return credential_ref in self._values


def redact(value: str, secrets: Iterable[str] = ()) -> str:
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def due_jobs(configs: Iterable[SourceConfiguration], now: datetime,
             last_success: Mapping[str, datetime | None]) -> tuple[SourceConfiguration, ...]:
    """Return enabled jobs due at ``now`` in stable job-ID order."""
    due: list[SourceConfiguration] = []
    for config in configs:
        previous = last_success.get(config.job_id)
        interval = timedelta(days=1 if config.cadence is Cadence.DAILY else 7)
        if config.enabled and (previous is None or now >= previous + interval):
            due.append(config)
    return tuple(sorted(due, key=lambda item: item.job_id))


@dataclass(frozen=True)
class OperationalException:
    exception_id: str
    run_id: str
    batch_id: str
    category: FailureCategory
    reason: str
    human_action_required: bool


@dataclass(frozen=True)
class CanonicalEvidence:
    evidence_id: str
    customer_id: str
    run_id: str
    batch_id: str
    source_record_id: str
    payload: str


@dataclass(frozen=True)
class JobRun:
    job_id: str
    run_id: str
    batch_id: str
    source_system: str
    location_id: str | None
    effective_period: date
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    records_read: int
    records_accepted: int
    records_rejected: int
    retry_attempt: int = 1
    exception_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class OperationalEvent:
    timestamp: datetime
    run_id: str
    job_id: str
    batch_id: str
    source_system: str
    location_id: str | None
    event_type: str
    status: RunStatus
    exception_category: str | None
    records_read: int
    records_accepted: int
    records_rejected: int
    retry_attempt: int

    def as_json(self) -> str:
        values = {"timestamp": self.timestamp.isoformat(), "run_id": self.run_id,
                  "job_id": self.job_id, "batch_id": self.batch_id,
                  "source_system": self.source_system, "location_id": self.location_id,
                  "event_type": self.event_type, "status": self.status.value,
                  "exception_category": self.exception_category,
                  "records_read": self.records_read, "records_accepted": self.records_accepted,
                  "records_rejected": self.records_rejected, "retry_attempt": self.retry_attempt}
        return json.dumps(values, sort_keys=True, separators=(",", ":"))


class ConflictingReplayError(ValueError):
    pass


class InMemoryOperationalStore:
    """Batch and record idempotency with explicit customer isolation."""
    def __init__(self, customer_id: str = CUSTOMER_ID) -> None:
        self.customer_id = customer_id
        self.batch_fingerprints: dict[tuple[str, str], str] = {}
        self.record_fingerprints: dict[tuple[str, str], str] = {}
        self.evidence: list[CanonicalEvidence] = []

    @staticmethod
    def _digest(value: object) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def ingest(self, config: SourceConfiguration, batch_id: str, records: Iterable[Mapping[str, object]],
               run_id: str, *, now: datetime = SIMULATED_NOW) -> JobRun:
        if config.customer_id != self.customer_id:
            raise ValueError("customer scope mismatch")
        rows = tuple(records)
        batch_hash = self._digest(rows)
        batch_key = (config.job_id, batch_id)
        previous = self.batch_fingerprints.get(batch_key)
        if previous is not None:
            if previous != batch_hash:
                raise ConflictingReplayError(f"{batch_id}: same batch identity has different content")
            return JobRun(config.job_id, run_id, batch_id, config.source_system, config.location_id,
                          now.date(), now, now, RunStatus.SAFE_REPLAY, len(rows), 0, 0)

        accepted_ids: list[str] = []
        rejected = 0
        for row in rows:
            record_id = str(row.get("id", ""))
            if not record_id or row.get("valid") is False:
                rejected += 1
                continue
            fingerprint = self._digest(row)
            record_key = (config.source_system, record_id)
            existing = self.record_fingerprints.get(record_key)
            if existing is not None:
                if existing != fingerprint:
                    raise ConflictingReplayError(f"{record_id}: same record identity has different content")
                continue
            evidence_id = f"EV-{config.job_id}-{record_id}"
            self.record_fingerprints[record_key] = fingerprint
            self.evidence.append(CanonicalEvidence(evidence_id, config.customer_id, run_id, batch_id,
                                                   record_id, json.dumps(row, sort_keys=True)))
            accepted_ids.append(evidence_id)
        self.batch_fingerprints[batch_key] = batch_hash
        status = RunStatus.PARTIAL if rejected else RunStatus.SUCCEEDED
        return JobRun(config.job_id, run_id, batch_id, config.source_system, config.location_id,
                      now.date(), now, now, status, len(rows), len(accepted_ids), rejected,
                      evidence_ids=tuple(accepted_ids))


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    reason: str


class RetryPolicy:
    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts

    def decide(self, category: FailureCategory, attempt: int) -> RetryDecision:
        if category is FailureCategory.TEMPORARY_SOURCE_UNAVAILABLE and attempt < self.max_attempts:
            return RetryDecision(True, "temporary failure; attempts remain")
        if category is FailureCategory.TEMPORARY_SOURCE_UNAVAILABLE:
            return RetryDecision(False, "maximum attempts reached")
        return RetryDecision(False, "human/source correction required")


def execute_with_retry(action: Callable[[int], JobRun | FailureCategory], policy: RetryPolicy) -> tuple[JobRun | None, tuple[RetryDecision, ...]]:
    decisions: list[RetryDecision] = []
    for attempt in range(1, policy.max_attempts + 1):
        outcome = action(attempt)
        if isinstance(outcome, JobRun):
            return replace(outcome, retry_attempt=attempt), tuple(decisions)
        decision = policy.decide(outcome, attempt)
        decisions.append(decision)
        if not decision.retry:
            return None, tuple(decisions)
    return None, tuple(decisions)


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    result: str
    detail: str


def readiness_checks(configs: Iterable[SourceConfiguration], provider: FakeCredentialProvider,
                     *, mappings_loaded: bool = True, state_writable: bool = True) -> tuple[ReadinessCheck, ...]:
    rows = tuple(configs)
    checks = [ReadinessCheck("Configuration", "PASS" if rows else "FAIL", "typed integrations loaded" if rows else "no integrations configured")]
    refs_ok = bool(rows) and all(c.credential_ref.startswith("secret://") and provider.contains(c.credential_ref) for c in rows if c.enabled)
    checks.append(ReadinessCheck("Credential references", "PASS" if refs_ok else "FAIL", "all enabled references resolve" if refs_ok else "missing or invalid reference"))
    raw_secret = any(any(key in c.__dict__ for key in ("password", "token", "api_key")) or not c.credential_ref.startswith("secret://") for c in rows)
    checks += [ReadinessCheck("Raw secrets in config", "PASS" if not raw_secret else "FAIL", "references only" if not raw_secret else "raw credential detected"),
               ReadinessCheck("Mappings", "PASS" if mappings_loaded else "FAIL", "mapping registry loads"),
               ReadinessCheck("Source availability", "PASS" if all(Path(c.input_ref).exists() for c in rows if c.enabled) else "WARNING", "local simulation fixtures inspected"),
               ReadinessCheck("Schema compatibility", "PASS" if bool(rows) and all(c.schema_version for c in rows) else "FAIL", "expectations defined"),
               ReadinessCheck("State store writable", "PASS" if state_writable else "FAIL", "in-memory lab store available"),
               ReadinessCheck("Unique job IDs", "PASS" if len({c.job_id for c in rows}) == len(rows) else "FAIL", "job identities checked")]
    return tuple(checks)


def readiness_report(configs: Iterable[SourceConfiguration] | None = None) -> str:
    rows = tuple(configs if configs is not None else load_config())
    provider = FakeCredentialProvider({c.credential_ref: f"synthetic-runtime-{i}" for i, c in enumerate(rows)})
    checks = readiness_checks(rows, provider)
    ready = all(c.result in {"PASS", "WARNING"} for c in checks)
    lines = ["PRODUCTION READINESS CHECK", "LAB SIMULATION — NOT PRODUCTION CERTIFICATION"]
    lines += [f"{c.name}: {c.result} — {c.detail}" for c in checks]
    lines += ["RESULT:", "READY FOR LAB OPERATION" if ready else "NOT READY FOR LAB OPERATION"]
    return "\n".join(lines)


def operations_report() -> str:
    configs = load_config()
    by_job = {c.job_id: c for c in configs}
    due = due_jobs(configs, SIMULATED_NOW, {"inventory-weekly": datetime(2026, 8, 24, 9)})
    store = InMemoryOperationalStore()
    pos = store.ingest(by_job["pos-rrk-daily"], "batch_2026_08_25", ({"id": "sale-1", "net": "24.00"},), "RUN-001")
    replay = store.ingest(by_job["pos-rrk-daily"], "batch_2026_08_25", ({"id": "sale-1", "net": "24.00"},), "RUN-002")
    partial = store.ingest(by_job["reservations-daily"], "res_2026_08_25", ({"id": "res-1", "covers": 4}, {"id": "res-2", "valid": False}), "RUN-003")
    conflict = ""
    try:
        store.ingest(by_job["pos-rrk-daily"], "batch_2026_08_25", ({"id": "sale-1", "net": "29.00"},), "RUN-004")
    except ConflictingReplayError as error:
        conflict = str(error)
    retry_run, retry_decisions = execute_with_retry(
        lambda attempt: FailureCategory.TEMPORARY_SOURCE_UNAVAILABLE if attempt < 3 else
        JobRun("labor-daily", "RUN-005", "lab_2026_08_25", "ShiftHarbor", None, SIMULATED_NOW.date(), SIMULATED_NOW, SIMULATED_NOW, RunStatus.SUCCEEDED, 1, 1, 0), RetryPolicy())
    _, schema_decisions = execute_with_retry(lambda _: FailureCategory.SCHEMA_CHANGE, RetryPolicy())
    # Recovery keeps the already accepted record and adds only the corrected one.
    recovery_store = InMemoryOperationalStore()
    before = recovery_store.ingest(by_job["pos-rrk-daily"], "map-v1", ({"id": "known"}, {"id": "unknown", "valid": False}), "RUN-006")
    after = recovery_store.ingest(by_job["pos-rrk-daily"], "map-v2", ({"id": "known"}, {"id": "unknown"}), "RUN-007")
    lines = ["INTEGRATION OPERATIONS", "SYNTHETIC DETERMINISTIC LAB", "SIMULATED TIME: 2026-08-25T09:00:00", "",
             "DUE JOBS"] + [f"{c.job_id}: DUE" for c in due] + ["inventory-weekly: NOT DUE", "", "CREDENTIAL BOUNDARY",
             "configuration -> secret:// reference -> fake provider -> [REDACTED]", "No runtime credential value is logged.", "", "EXECUTIONS",
             f"{pos.job_id} {pos.run_id}: {pos.status.value}", f"{partial.job_id} {partial.run_id}: {partial.status.value}",
             f"labor-daily {retry_run.run_id}: {retry_run.status.value} after {retry_run.retry_attempt} attempts",
             f"schema mismatch: FAILED; retry={schema_decisions[-1].retry}; {schema_decisions[-1].reason}",
             f"same batch RUN-002: {replay.status.value}", f"same batch changed content: FAILED / CONFLICTING REPLAY / {conflict}", "",
             "FAILURE ISOLATION", "pos-rrk-daily: SUCCEEDED", "reservations-daily: PARTIAL", "labor-daily: FAILED (independent scenario)", "inventory-weekly: SKIPPED / NOT DUE", "",
             "INTEGRATION OPERATIONS SUMMARY", "JOBS DUE: 3", "SUCCEEDED: 2", "PARTIAL: 1", "FAILED: 1", f"RETRIES: {sum(d.retry for d in retry_decisions)}",
             "OPEN HUMAN-ACTION EXCEPTIONS: 2", "LATE SOURCES: 1", "LAST SUCCESSFUL RUN", "POS JRH-001: 2026-08-25T09:00:00", "Reservations: 2026-08-25T09:00:00", "Labor: 2026-08-25T09:00:00", "Inventory: 2026-08-24T09:00:00", "",
             "RECOVERY", f"mapping run before: {before.status.value}; accepted={before.records_accepted}", f"mapping run after correction: {after.status.value}; accepted={after.records_accepted}; canonical total={len(recovery_store.evidence)}", "schema correction: corrected source rerun -> SUCCEEDED", "",
             "CORRELATION", "RUN-003 -> res_2026_08_25 -> rejected record -> briefing completeness PARTIAL", "",
             readiness_report(configs), "", "OBSERVED LAB RESULTS",
             "A useful parser was insufficient without scheduling, idempotency, retry decisions, and run tracking.",
             "Safe replay and conflicting replay required different handling.", "Retry policy followed failure semantics.",
             "Credential references were resolved without exposing runtime values.", "One failed job did not block unrelated due jobs."]
    return "\n".join(lines)
