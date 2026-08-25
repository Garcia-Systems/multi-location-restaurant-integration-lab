from restaurant_integration_lab.cli import main
from restaurant_integration_lab.discovery import (
    AccessMethod,
    CapabilityStatus,
    CAPABILITY_REVIEWS,
    DataDomain,
    EVIDENCE_LOG,
    EvidenceKind,
    LOCATIONS,
    SYSTEMS,
    assess_readiness,
    discovery_report,
)


def test_all_locations_have_explicit_unique_identifiers() -> None:
    assert len(LOCATIONS) == 5
    assert len({location.code for location in LOCATIONS}) == 5
    assert all(location.code and location.system_keys for location in LOCATIONS)


def test_every_required_domain_is_owned_or_explicitly_absent_per_location() -> None:
    systems = {system.key: system for system in SYSTEMS}
    for location in LOCATIONS:
        represented = {systems[key].category for key in location.system_keys}
        assert represented | set(location.explicitly_absent_domains) == set(DataDomain)


def test_shared_pos_family_still_has_material_interface_variation() -> None:
    pos = [system for system in SYSTEMS if system.category is DataDomain.SALES]
    assert len(pos) == 5
    assert all(system.name.startswith("HarborTill") for system in pos)
    assert len({system.interface.access_method for system in pos}) >= 4
    assert len({system.interface.format for system in pos}) == len(pos)


def test_reservation_behavior_follows_concept_not_forced_uniformity() -> None:
    cst = next(location for location in LOCATIONS if location.code == "CST")
    assert DataDomain.RESERVATIONS in cst.explicitly_absent_domains
    reservation_systems = [system for system in SYSTEMS if system.category is DataDomain.RESERVATIONS]
    assert {system.name for system in reservation_systems} == {"TableCurrent", "BakeAhead", "JRS Event Calendar"}


def test_identifiers_include_shared_local_and_unstable_schemes() -> None:
    identifiers = [identifier for system in SYSTEMS for identifier in system.identifiers]
    assert any(identifier.scope == "shared group namespace" for identifier in identifiers)
    assert any("local" in identifier.scope for identifier in identifiers)
    assert any(not identifier.stable for identifier in identifiers)


def test_existing_capabilities_apply_build_versus_buy_pressure() -> None:
    capabilities = [capability for system in SYSTEMS for capability in system.capabilities]
    assert any(capability.could_reduce_custom_scope for capability in capabilities)
    assert any(capability.status is CapabilityStatus.CONFIRMED and capability.could_reduce_custom_scope for capability in capabilities)
    assert any(capability.status is CapabilityStatus.REQUIRES_REVIEW for capability in capabilities)
    assert {review.system_key for review in CAPABILITY_REVIEWS} == {system.key for system in SYSTEMS}
    assert all(review.bi_connectors is CapabilityStatus.REQUIRES_REVIEW for review in CAPABILITY_REVIEWS)


def test_readiness_rules_explain_why_architecture_is_not_ready() -> None:
    assessment = assess_readiness()
    assert assessment.status == "NOT READY"
    assert any("jrs-inventory: access method is unknown" in reason for reason in assessment.unresolved)
    assert any("permission owner is unknown" in reason for reason in assessment.unresolved)
    assert any("native/group capabilities" in reason for reason in assessment.unresolved)
    assert all("domains neither owned" not in reason for reason in assessment.unresolved)


def test_report_is_deterministic_and_exposes_raw_findings() -> None:
    first = discovery_report()
    assert first == discovery_report()
    assert "ARCHITECTURE READINESS\nNOT READY" in first
    assert "REST API" in first and "manual CSV export" in first
    assert "SYNTHETIC LAB EVIDENCE — NOT MARKET VALIDATION" in first


def test_evidence_log_keeps_assumptions_and_lab_results_distinct() -> None:
    kinds = {entry.kind for entry in EVIDENCE_LOG}
    assert kinds == {EvidenceKind.MODELED_ASSUMPTION, EvidenceKind.OBSERVED_LAB_RESULT}
    assert all("synthetic" in entry.context.lower() for entry in EVIDENCE_LOG if entry.kind is EvidenceKind.OBSERVED_LAB_RESULT)


def test_cli_dispatch_and_invalid_command(capsys) -> None:
    assert main(["discovery"]) == 0
    assert "INTEGRATION DISCOVERY" in capsys.readouterr().out
    assert main(["future-chapter"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_unknown_access_is_explicit_not_an_implemented_adapter() -> None:
    assert any(system.interface.access_method is AccessMethod.UNAVAILABLE for system in SYSTEMS)
