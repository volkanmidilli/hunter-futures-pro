"""Tests for the Cross-Artifact Consistency Engine models."""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from src.hunter.cross_artifact_consistency.models import (
    ArtifactRef,
    ArtifactSummary,
    ConsistencyDataQuality,
    ConsistencyFinding,
    ConsistencyReasonCode,
    ConsistencyRule,
    ConsistencySafetyFlags,
    ConsistencySeverity,
    ConsistencyState,
    CrossArtifactConsistencyConfig,
    CrossArtifactConsistencyInput,
)


def test_consistency_state_values() -> None:
    assert ConsistencyState.OK.value == "OK"
    assert ConsistencyState.DEGRADED.value == "DEGRADED"
    assert ConsistencyState.BLOCKED.value == "BLOCKED"
    assert ConsistencyState.NOT_APPLICABLE.value == "NOT_APPLICABLE"


def test_consistency_severity_values() -> None:
    assert ConsistencySeverity.INFO.value == "INFO"
    assert ConsistencySeverity.WARNING.value == "WARNING"
    assert ConsistencySeverity.BLOCKING.value == "BLOCKING"


def test_consistency_reason_codes() -> None:
    assert ConsistencyReasonCode.OK.value == "OK"
    assert ConsistencyReasonCode.DUPLICATE_ARTIFACT_ID.value == "DUPLICATE_ARTIFACT_ID"
    assert ConsistencyReasonCode.MISSING_UPSTREAM_REFERENCE.value == "MISSING_UPSTREAM_REFERENCE"
    assert ConsistencyReasonCode.STALE_PROJECT_MEMORY.value == "STALE_PROJECT_MEMORY"
    assert ConsistencyReasonCode.FORBIDDEN_PHRASE_LEAKAGE.value == "FORBIDDEN_PHRASE_LEAKAGE"


def test_artifact_ref_default_metadata_is_none() -> None:
    ref = ArtifactRef(ref_id="r1", ref_kind="path", opaque_value="data/x.json")
    assert ref.metadata is None


def test_artifact_summary_default_fields_are_tuples() -> None:
    summary = ArtifactSummary(
        artifact_id="a1",
        artifact_kind="observation",
        artifact_state="READY",
    )
    assert summary.upstream_ids == ()
    assert summary.downstream_ids == ()
    assert summary.decision_ids == ()
    assert summary.review_ids == ()
    assert summary.report_ids == ()


def test_dataclasses_are_frozen() -> None:
    summary = ArtifactSummary(
        artifact_id="a1",
        artifact_kind="observation",
        artifact_state="READY",
    )
    with pytest.raises(FrozenInstanceError):
        summary.artifact_id = "a2"  # type: ignore[misc]


def test_consistency_rule_defaults() -> None:
    rule = ConsistencyRule(
        rule_id="R1",
        description="test",
        severity=ConsistencySeverity.WARNING,
        reason_code=ConsistencyReasonCode.OK,
    )
    assert rule.enabled is True


def test_consistency_finding_immutability() -> None:
    finding = ConsistencyFinding(
        finding_id="f1",
        rule_id="R1",
        artifact_ids=("a1",),
        severity=ConsistencySeverity.INFO,
        reason_code=ConsistencyReasonCode.OK,
        title="title",
        description="desc",
    )
    with pytest.raises(FrozenInstanceError):
        finding.title = "new"  # type: ignore[misc]


def test_data_quality_defaults() -> None:
    dq = ConsistencyDataQuality()
    assert dq.artifact_count == 0
    assert dq.finding_count == 0
    assert dq.checks_performed == 0


def test_safety_flags_assert_audit_only_boundaries() -> None:
    flags = ConsistencySafetyFlags()
    assert flags.audit_only is True
    assert flags.opaque_refs_only is True
    assert flags.filesystem_access is False
    assert flags.network_access is False
    assert flags.runtime_execution is False
    assert flags.trading_signal is False


def test_default_config_includes_allowed_kinds_and_forbidden_terms() -> None:
    config = CrossArtifactConsistencyConfig()
    assert "observation" in config.allowed_artifact_kinds
    assert "audit_bundle_export_verification" in config.allowed_artifact_kinds
    assert "production readiness" in config.forbidden_terms


def test_input_defaults() -> None:
    artifacts = (
        ArtifactSummary(
            artifact_id="a1",
            artifact_kind="observation",
            artifact_state="READY",
        ),
    )
    inp = CrossArtifactConsistencyInput(artifacts=artifacts)
    assert inp.config.strict is True
    assert inp.config.allow_empty is True
    assert inp.metadata is None


def test_artifact_ref_opaque_value_is_not_path() -> None:
    ref = ArtifactRef(
        ref_id="ref1",
        ref_kind="opaque",
        opaque_value="/not/a/path/just/a/string",
    )
    assert isinstance(ref.opaque_value, str)
    assert not hasattr(ref, "resolve")  # not a pathlib object
