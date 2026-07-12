"""Tests for the research_audit_health models module."""

from datetime import datetime, timezone

import pytest

from hunter.research_audit_health.models import (
    DEFAULT_ALLOWED_FAMILIES,
    DEFAULT_FORBIDDEN_TERMS,
    DEFAULT_REQUIRED_FAMILIES,
    HealthArtifactSummary,
    HealthConfig,
    HealthDataQuality,
    HealthFamilyRollup,
    HealthFinding,
    HealthReasonCode,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
    HealthState,
)


def test_health_state_values() -> None:
    assert HealthState.OK.value == "OK"
    assert HealthState.DEGRADED.value == "DEGRADED"
    assert HealthState.BLOCKED.value == "BLOCKED"
    assert HealthState.NOT_APPLICABLE.value == "NOT_APPLICABLE"


def test_health_severity_values() -> None:
    assert HealthSeverity.INFO.value == "INFO"
    assert HealthSeverity.WARNING.value == "WARNING"
    assert HealthSeverity.BLOCKING.value == "BLOCKING"


def test_health_reason_codes() -> None:
    expected = {
        "OK",
        "NO_ARTIFACTS",
        "DUPLICATE_ARTIFACT_ID",
        "MALFORMED_METADATA",
        "UNSUPPORTED_ARTIFACT_FAMILY",
        "MISSING_REQUIRED_FAMILY",
        "BLOCKING_SOURCE_STATE",
        "DEGRADED_SOURCE_STATE",
        "STALE_SOURCE_STATE",
        "INCONSISTENT_SCORE_INPUT",
        "CONTRADICTORY_METADATA",
        "FORBIDDEN_PHRASE_LEAKAGE",
    }
    actual = {code.value for code in HealthReasonCode}
    assert actual == expected


def test_health_artifact_summary_defaults() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
    )
    assert summary.artifact_id == "snap-1"
    assert summary.family == "research_audit_snapshot"
    assert summary.source_state == "OK"
    assert summary.score is None
    assert summary.mvp is None
    assert summary.spec is None
    assert summary.produced_by is None
    assert summary.generated_at is None
    assert summary.ref is None
    assert summary.metadata is None


def test_health_artifact_summary_frozen() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
    )
    with pytest.raises(AttributeError):
        summary.artifact_id = "snap-2"  # type: ignore[misc]


def test_health_artifact_summary_score_validation() -> None:
    with pytest.raises(TypeError):
        HealthArtifactSummary(
            artifact_id="snap-1",
            family="research_audit_snapshot",
            source_state="OK",
            score="bad",
        )
    with pytest.raises(ValueError):
        HealthArtifactSummary(
            artifact_id="snap-1",
            family="research_audit_snapshot",
            source_state="OK",
            score=101,
        )
    with pytest.raises(ValueError):
        HealthArtifactSummary(
            artifact_id="snap-1",
            family="research_audit_snapshot",
            source_state="OK",
            score=-1,
        )


def test_health_artifact_summary_opaque_ref() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        ref="/data/sensitive/path.json",
    )
    assert summary.ref == "/data/sensitive/path.json"


def test_health_config_defaults() -> None:
    config = HealthConfig()
    assert config.strict is True
    assert config.allow_empty is True
    assert config.allowed_families == DEFAULT_ALLOWED_FAMILIES
    assert config.required_families == DEFAULT_REQUIRED_FAMILIES
    assert config.forbidden_terms == DEFAULT_FORBIDDEN_TERMS
    assert config.degraded_threshold == 75


def test_health_config_frozen() -> None:
    config = HealthConfig()
    with pytest.raises(AttributeError):
        config.strict = False  # type: ignore[misc]


def test_health_config_penalty_validation() -> None:
    with pytest.raises(ValueError, match="missing penalty"):
        HealthConfig(
            severity_penalties={HealthSeverity.INFO: 1},
        )


def test_health_config_weight_validation() -> None:
    with pytest.raises(ValueError, match="missing weight"):
        HealthConfig(
            severity_weights={HealthSeverity.INFO: 1},
        )


def test_health_finding_defaults() -> None:
    finding = HealthFinding(
        finding_id="f-1",
        rule_id="OK",
        family="research_audit_snapshot",
        artifact_ids=("snap-1",),
        severity=HealthSeverity.INFO,
        reason_code=HealthReasonCode.OK,
        title="OK",
        description="All good",
    )
    assert finding.evidence is None


def test_health_finding_frozen() -> None:
    finding = HealthFinding(
        finding_id="f-1",
        rule_id="OK",
        family="research_audit_snapshot",
        artifact_ids=("snap-1",),
        severity=HealthSeverity.INFO,
        reason_code=HealthReasonCode.OK,
        title="OK",
        description="All good",
    )
    with pytest.raises(AttributeError):
        finding.title = "Bad"  # type: ignore[misc]


def test_health_score_defaults() -> None:
    score = HealthScore(value=85.0, weight=10.0, contributing_families=("a", "b"))
    assert score.breakdown is None


def test_health_family_rollup() -> None:
    score = HealthScore(value=85.0, weight=10.0, contributing_families=("a",))
    rollup = HealthFamilyRollup(
        family="a",
        state=HealthState.OK,
        score=score,
        finding_count=0,
        reason_code_counts={"OK": 1},
        summary="family=a; health=OK",
    )
    assert rollup.family == "a"


def test_health_data_quality_defaults() -> None:
    dq = HealthDataQuality()
    assert dq.summary_count == 0
    assert dq.family_count == 0
    assert dq.reason_code_counts is None


def test_health_safety_flags_defaults() -> None:
    flags = HealthSafetyFlags()
    assert flags.audit_only is True
    assert flags.opaque_refs_only is True
    assert flags.filesystem_access is False
    assert flags.network_access is False
    assert flags.runtime_execution is False
    assert flags.trading_signal is False


def test_health_report() -> None:
    score = HealthScore(value=85.0, weight=10.0, contributing_families=("a",))
    rollup = HealthFamilyRollup(
        family="a",
        state=HealthState.OK,
        score=score,
        finding_count=0,
        reason_code_counts={"OK": 1},
        summary="family=a; health=OK",
    )
    report = HealthReport(
        report_id="r1",
        state=HealthState.OK,
        aggregate_score=score,
        family_rollups=(rollup,),
        findings=(),
        reason_code_counts={"OK": 1},
        data_quality=HealthDataQuality(),
        safety_flags=HealthSafetyFlags(),
    )
    assert report.report_id == "r1"


def test_health_report_frozen() -> None:
    report = HealthReport(
        report_id="r1",
        state=HealthState.OK,
        aggregate_score=HealthScore(value=85.0, weight=1.0, contributing_families=()),
        family_rollups=(),
        findings=(),
        reason_code_counts={},
        data_quality=HealthDataQuality(),
        safety_flags=HealthSafetyFlags(),
    )
    with pytest.raises(AttributeError):
        report.state = HealthState.DEGRADED  # type: ignore[misc]


def test_health_artifact_summary_with_datetime() -> None:
    now = datetime.now(timezone.utc)
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        generated_at=now,
    )
    assert summary.generated_at == now


def test_default_allowed_families_include_required_groups() -> None:
    assert "research_audit_snapshot" in DEFAULT_ALLOWED_FAMILIES
    assert "research_audit_catalog" in DEFAULT_ALLOWED_FAMILIES
    assert "research_release_notes" in DEFAULT_ALLOWED_FAMILIES
    assert "research_audit_closure" in DEFAULT_ALLOWED_FAMILIES
    assert "research_quality_gate" in DEFAULT_ALLOWED_FAMILIES
    assert "human_review_queue" in DEFAULT_ALLOWED_FAMILIES
    assert "human_review_decision_log" in DEFAULT_ALLOWED_FAMILIES
    assert "human_review_audit_bundle" in DEFAULT_ALLOWED_FAMILIES
    assert "human_review_audit_bundle_export_verification" in DEFAULT_ALLOWED_FAMILIES
    assert "cross_artifact_consistency" in DEFAULT_ALLOWED_FAMILIES
    assert "project_memory_status" in DEFAULT_ALLOWED_FAMILIES


def test_default_forbidden_terms_nonempty() -> None:
    assert "production readiness" in DEFAULT_FORBIDDEN_TERMS
    assert "recommendation" in DEFAULT_FORBIDDEN_TERMS
    assert "certification" in DEFAULT_FORBIDDEN_TERMS
