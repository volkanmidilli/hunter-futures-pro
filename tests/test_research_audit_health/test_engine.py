"""Tests for the research_audit_health engine module."""

import pytest

from hunter.research_audit_health import (
    ForbiddenPhraseLeakageError,
    HealthArtifactSummary,
    HealthConfig,
    HealthFinding,
    HealthInput,
    HealthReasonCode,
    HealthReport,
    HealthSeverity,
    HealthState,
    evaluate_research_audit_health,
    validate_no_forbidden_modules,
)


def _ok_summary(artifact_id: str, family: str = "research_audit_snapshot") -> HealthArtifactSummary:
    return HealthArtifactSummary(
        artifact_id=artifact_id,
        family=family,
        source_state="OK",
        mvp="MVP-48",
        spec="SPEC-049",
        score=95.0,
    )


def test_empty_input_allowed() -> None:
    config = HealthConfig(allow_empty=True)
    report = evaluate_research_audit_health(HealthInput(summaries=(), config=config))
    assert report.state == HealthState.NOT_APPLICABLE
    assert report.aggregate_score.value == 0.0
    assert report.data_quality.summary_count == 0
    assert any(f.reason_code == HealthReasonCode.NO_ARTIFACTS for f in report.findings)


def test_empty_input_not_allowed() -> None:
    config = HealthConfig(allow_empty=False, strict=True)
    report = evaluate_research_audit_health(HealthInput(summaries=(), config=config))
    assert report.state == HealthState.BLOCKED
    no_artifacts = [f for f in report.findings if f.reason_code == HealthReasonCode.NO_ARTIFACTS]
    assert len(no_artifacts) == 1
    assert no_artifacts[0].severity == HealthSeverity.BLOCKING


def test_single_ok_summary() -> None:
    summary = _ok_summary("snap-1")
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.OK
    assert any(f.reason_code == HealthReasonCode.OK for f in report.findings)
    assert report.reason_code_counts.get("OK", 0) >= 1


def test_duplicate_artifact_id_blocked() -> None:
    a = _ok_summary("snap-1")
    b = _ok_summary("snap-1")
    report = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    assert report.state == HealthState.BLOCKED
    duplicate_findings = [
        f for f in report.findings if f.reason_code == HealthReasonCode.DUPLICATE_ARTIFACT_ID
    ]
    assert len(duplicate_findings) == 1
    assert duplicate_findings[0].severity == HealthSeverity.BLOCKING


def test_unsupported_family_strict() -> None:
    summary = HealthArtifactSummary(
        artifact_id="x-1",
        family="unknown_family",
        source_state="OK",
    )
    config = HealthConfig(strict=True)
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,), config=config))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.UNSUPPORTED_ARTIFACT_FAMILY]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.BLOCKING


def test_unsupported_family_non_strict() -> None:
    summary = HealthArtifactSummary(
        artifact_id="x-1",
        family="unknown_family",
        source_state="OK",
    )
    config = HealthConfig(strict=False)
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,), config=config))
    assert report.state == HealthState.DEGRADED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.UNSUPPORTED_ARTIFACT_FAMILY]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.WARNING


def test_missing_required_family_strict() -> None:
    summary = _ok_summary("snap-1", family="research_audit_snapshot")
    config = HealthConfig(required_families=("research_audit_snapshot", "research_audit_catalog"), strict=True)
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,), config=config))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.MISSING_REQUIRED_FAMILY]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.BLOCKING


def test_missing_required_family_non_strict() -> None:
    summary = _ok_summary("snap-1", family="research_audit_snapshot")
    config = HealthConfig(required_families=("research_audit_catalog",), strict=False)
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,), config=config))
    assert report.state == HealthState.DEGRADED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.MISSING_REQUIRED_FAMILY]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.WARNING


def test_blocking_source_state() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="BLOCKED",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.BLOCKING_SOURCE_STATE]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.BLOCKING


def test_degraded_source_state() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="DEGRADED",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.DEGRADED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.DEGRADED_SOURCE_STATE]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.WARNING


def test_stale_source_state() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="STALE",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.DEGRADED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.STALE_SOURCE_STATE]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.WARNING


def test_inconsistent_score_input() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        score=10.0,
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.INCONSISTENT_SCORE_INPUT]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.BLOCKING
    assert findings[0].artifact_ids == ("snap-1",)

def test_contradictory_metadata() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        mvp="MVP-48",
        spec="SPEC-999",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.DEGRADED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.CONTRADICTORY_METADATA]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.WARNING


def test_forbidden_phrase_leakage() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        metadata={"note": "This artifact shows production readiness"},
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE]
    assert len(findings) == 1
    assert findings[0].severity == HealthSeverity.BLOCKING


def test_forbidden_phrase_leakage_raised_in_description() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        metadata={"description": "recommendation to buy"},
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    assert report.state == HealthState.BLOCKED
    findings = [f for f in report.findings if f.reason_code == HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE]
    assert len(findings) == 1


def test_deterministic_report_id() -> None:
    a = _ok_summary("snap-1")
    b = _ok_summary("snap-2")
    report1 = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    report2 = evaluate_research_audit_health(HealthInput(summaries=(b, a)))
    assert report1.report_id == report2.report_id


def test_deterministic_ordering() -> None:
    a = _ok_summary("snap-a")
    b = _ok_summary("snap-b")
    c = _ok_summary("snap-c")
    report1 = evaluate_research_audit_health(HealthInput(summaries=(c, a, b)))
    report2 = evaluate_research_audit_health(HealthInput(summaries=(a, b, c)))
    assert report1.report_id == report2.report_id
    assert tuple(f.finding_id for f in report1.findings) == tuple(f.finding_id for f in report2.findings)
    assert tuple(r.family for r in report1.family_rollups) == tuple(r.family for r in report2.family_rollups)


def test_score_bounded_zero_to_one_hundred() -> None:
    summaries = tuple(_ok_summary(f"snap-{i}") for i in range(10))
    report = evaluate_research_audit_health(HealthInput(summaries=summaries))
    assert 0.0 <= report.aggregate_score.value <= 100.0


def test_reason_code_counts() -> None:
    a = _ok_summary("snap-1")
    b = HealthArtifactSummary(
        artifact_id="snap-2",
        family="research_audit_snapshot",
        source_state="BLOCKED",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    assert "OK" in report.reason_code_counts
    assert "BLOCKING_SOURCE_STATE" in report.reason_code_counts
    assert report.data_quality.blocking_count >= 1


def test_refs_remain_opaque() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        ref="/data/sensitive/secret.json",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    # The ref is stored but never opened/traversed; the report remains valid.
    assert report.state == HealthState.OK


def test_no_forbidden_modules() -> None:
    validate_no_forbidden_modules()


def test_family_rollup_score_weights() -> None:
    a = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
    )
    b = HealthArtifactSummary(
        artifact_id="snap-2",
        family="research_audit_snapshot",
        source_state="DEGRADED",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    rollup = next(r for r in report.family_rollups if r.family == "research_audit_snapshot")
    assert rollup.finding_count >= 1
    assert rollup.score.weight > 0
    assert 0.0 <= rollup.score.value <= 100.0


def test_metadata_is_preserved() -> None:
    summary = _ok_summary("snap-1")
    report = evaluate_research_audit_health(
        HealthInput(summaries=(summary,), metadata={"run_by": "pytest"})
    )
    assert report.metadata == {"run_by": "pytest"}


def test_multiple_families_aggregate() -> None:
    snap = _ok_summary("snap-1", family="research_audit_snapshot")
    cat = _ok_summary("cat-1", family="research_audit_catalog")
    report = evaluate_research_audit_health(HealthInput(summaries=(snap, cat)))
    assert report.state == HealthState.OK
    families = {r.family for r in report.family_rollups}
    assert families == {"research_audit_catalog", "research_audit_snapshot"}


def test_strict_required_family_empty_input() -> None:
    config = HealthConfig(
        required_families=("research_audit_snapshot",),
        allow_empty=False,
        strict=True,
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(), config=config))
    assert report.state == HealthState.BLOCKED
    assert any(f.reason_code == HealthReasonCode.NO_ARTIFACTS for f in report.findings)
    assert any(f.reason_code == HealthReasonCode.MISSING_REQUIRED_FAMILY for f in report.findings)


def test_duplicate_ids_across_families() -> None:
    a = _ok_summary("id-1", family="research_audit_snapshot")
    b = HealthArtifactSummary(
        artifact_id="id-1",
        family="research_audit_catalog",
        source_state="OK",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    assert report.state == HealthState.BLOCKED


def test_forbidden_phrase_scan_does_not_open_ref() -> None:
    summary = HealthArtifactSummary(
        artifact_id="snap-1",
        family="research_audit_snapshot",
        source_state="OK",
        ref="production readiness.txt",
    )
    report = evaluate_research_audit_health(HealthInput(summaries=(summary,)))
    # Ref is opaque; forbidden phrase check does not include the ref value.
    assert report.state == HealthState.OK


def test_findings_sorted_by_id() -> None:
    a = HealthArtifactSummary(artifact_id="z-1", family="research_audit_snapshot", source_state="DEGRADED")
    b = HealthArtifactSummary(artifact_id="a-1", family="research_audit_snapshot", source_state="BLOCKED")
    report = evaluate_research_audit_health(HealthInput(summaries=(a, b)))
    ids = [f.finding_id for f in report.findings]
    assert ids == sorted(ids)
