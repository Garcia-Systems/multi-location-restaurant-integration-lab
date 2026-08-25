from dataclasses import replace
from pathlib import Path

import pytest

from restaurant_integration_lab.briefing import briefing_report
from restaurant_integration_lab.discovery import LOCATIONS
from restaurant_integration_lab.labor import ShiftHarborParser
from restaurant_integration_lab.location2 import LocationTwoHarborTillCsvParser
from restaurant_integration_lab.onboarding import (
    LOCATION, MANIFEST, MAPPING_COUNTS, OPERATIONS_FIXTURE, PRODUCT_MAPPINGS,
    Classification, OnboardingInputs, ReadinessStatus, _pos_sales,
    assess_onboarding_readiness, first_attempt, onboarded_dataset,
    onboarding_briefing, operational_run,
)
from restaurant_integration_lab.operations import FakeCredentialProvider, load_config, readiness_checks
from restaurant_integration_lab.reservations import TableCurrentParser


def test_jrh006_has_unique_canonical_identity():
    assert LOCATION.canonical_id == "JRH-006"
    assert LOCATION.canonical_id not in {f"JRH-{number:03}" for number in range(1, 6)}
    assert len(LOCATIONS) == 5  # Chapter 1 remains its original discovery snapshot.


def test_readiness_is_deterministic_and_rule_based():
    assert assess_onboarding_readiness() == assess_onboarding_readiness()
    assert assess_onboarding_readiness().status is ReadinessStatus.READY_WITH_CONFIGURATION
    complete = replace(OnboardingInputs(), mappings_complete=True)
    assert assess_onboarding_readiness(complete).status is ReadinessStatus.READY


@pytest.mark.parametrize("field", ["canonical_location_configured", "schema_known", "sample_fixture_present", "credential_reference_present"])
def test_missing_hard_requirement_blocks_onboarding(field):
    assert assess_onboarding_readiness(replace(OnboardingInputs(), **{field: False})).status is ReadinessStatus.BLOCKED


def test_known_parsers_work_unchanged_on_samples():
    result = first_attempt()
    assert result["POS parser"] == result["Reservation parser"] == "WORKED UNCHANGED"
    assert "ROLE MAPPING REQUIRED" in result["Labor parser"]
    assert LocationTwoHarborTillCsvParser.__module__.endswith("location2")
    assert TableCurrentParser.__module__.endswith("reservations")
    assert ShiftHarborParser.__module__.endswith("labor")


def test_unknown_products_fail_explicitly_then_mapping_resolves_without_parser_change():
    before, missing = _pos_sales(())
    after, resolved = _pos_sales(PRODUCT_MAPPINGS)
    assert not before and missing == ("TGC-MAIN-01", "TGC-DRINK-02", "TGC-NEW-99")
    assert len(after) == 3 and not resolved


def test_mapping_burden_and_exception_resolution_are_explicit():
    assert sum(MAPPING_COUNTS.values()) == 12
    assert ("Inventory item/pack conversion", Classification.NEW_MAPPINGS) in MANIFEST
    assert not any(value is Classification.NEW_SOURCE_CODE for _, value in MANIFEST)


def test_no_fixed_five_location_assumption_and_group_calculation_includes_sixth():
    data = onboarded_dataset()
    assert len(data.coverage) == 3
    assert dict(data.sales_by_location())["JRH-006"] == 38
    assert {row.canonical_location_id for row in data.coverage} >= {"JRH-001", "JRH-002", "JRH-006"}


def test_sixth_location_appears_through_unchanged_briefing_implementation():
    briefing = onboarding_briefing()
    assert any(row.location_id == "JRH-006" for row in briefing.locations)
    assert "JRH-006: net=$38.00" in briefing_report(briefing)
    assert onboarding_briefing.__module__.endswith("onboarding")
    assert briefing_report.__module__.endswith("briefing")


def test_operational_configuration_is_scoped_scheduled_and_redacted():
    configs = load_config(OPERATIONS_FIXTURE)
    assert len(configs) == 4 and {c.location_id for c in configs} == {"JRH-006"}
    assert all(c.credential_ref.startswith("secret://") for c in configs)
    assert "synthetic-runtime" not in Path(OPERATIONS_FIXTURE).read_text()


def test_required_credentials_must_exist_before_run():
    configs = load_config(OPERATIONS_FIXTURE)
    checks = readiness_checks(configs, FakeCredentialProvider({}))
    assert next(c for c in checks if c.name == "Credential references").result == "FAIL"


def test_first_run_safe_replay_and_conflict_detection_are_inherited():
    assert operational_run() == ("SUCCEEDED", "SAFE REPLAY", "DETECTED")


def test_previous_location_suite_inputs_are_not_modified():
    assert [location.code for location in LOCATIONS] == ["RRK", "CST", "BHO", "MBC", "JRS"]
