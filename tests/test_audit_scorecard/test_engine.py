"""Tests for hunter.audit_scorecard.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.audit_scorecard import (
    AuditScorecardConfig,
    AuditScorecardDimension,
    AuditScorecardDimensionResult,
    AuditScorecardDimensionState,
    AuditScorecardEvidenceRef,
    AuditScorecardFinding,
    AuditScorecardInput,
    AuditScorecardLink,
    AuditScorecardLinkType,
    AuditScorecardReasonCode,
    AuditScorecardReport,
    AuditScorecardSeverity,
    AuditScorecardState,
    build_audit_scorecard_report,
)


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def minimal_dimension(generated_at: datetime) -> AuditScorecardDimension:
    return AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", generated_at=generated_at
    )


@pytest.fixture
def minimal_input(minimal_dimension: AuditScorecardDimension, generated_at: datetime) -> AuditScorecardInput:
    return AuditScorecardInput(
        dimensions=(minimal_dimension,),
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_empty_dimensions_blocked(generated_at: datetime) -> None:
    inp = AuditScorecardInput(dimensions=(), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.MISSING_REQUIRED_DIMENSION in report.reason_codes


def test_duplicate_dimension_ids_blocked(generated_at: datetime) -> None:
    inp = AuditScorecardInput(
        dimensions=(
            AuditScorecardDimension(dimension_id="dup", title="A", description="A"),
            AuditScorecardDimension(dimension_id="dup", title="B", description="B"),
        ),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID in report.reason_codes


# ---------------------------------------------------------------------------
# Dimension classification
# ---------------------------------------------------------------------------


def test_complete_dimension(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.OK
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.COMPLETE
    assert result.completeness_percent == 100


def test_required_optional_dimension_still_evaluated(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", required=False
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.OK
    assert report.dimension_results[0].dimension_state is AuditScorecardDimensionState.COMPLETE


def test_not_applicable_dimension(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", not_applicable=True
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.OK
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.NOT_APPLICABLE
    assert result.dimension_id in {d.dimension_id for d in report.dimensions}


def test_missing_dimension(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", required=True, expected_evidence_count=1
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.MISSING
    assert result.completeness_percent == 0


def test_partial_dimension(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1",
        title="T",
        description="D",
        expected_evidence_count=2,
        required=True,
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), links=(link,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.PARTIAL
    assert 0 < result.completeness_percent < 100


def test_blocked_dimension_upstream(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1",
        title="T",
        description="D",
        upstream_package_ids=("pkg_1",),
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        upstream_states={"pkg_1": "blocked"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.BLOCKED


def test_degraded_dimension_upstream(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1",
        title="T",
        description="D",
        upstream_report_ids=("report_1",),
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        upstream_states={"report_1": "degraded"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    result = report.dimension_results[0]
    assert result.dimension_state is AuditScorecardDimensionState.DEGRADED


# ---------------------------------------------------------------------------
# Upstream states
# ---------------------------------------------------------------------------


def test_unknown_upstream_state_advisory(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1",
        title="T",
        description="D",
        upstream_package_ids=("pkg_1",),
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        upstream_states={"pkg_1": "weird"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE
        for f in report.findings
    )


def test_case_insensitive_upstream_state(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", upstream_package_ids=("pkg_1",)
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        upstream_states={"pkg_1": "BLOCKED"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.dimension_results[0].dimension_state is AuditScorecardDimensionState.BLOCKED


# ---------------------------------------------------------------------------
# Stale evidence
# ---------------------------------------------------------------------------


def test_stale_evidence_degraded(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_1",
        reference="data/ev.json",
        generated_at=generated_at - timedelta(seconds=3601),
    )
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        config=AuditScorecardConfig(staleness_threshold_seconds=3600),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.STALE_EVIDENCE for f in report.findings
    )


def test_missing_manual_review_for_dimension(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", requires_manual_review=True
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.MISSING_MANUAL_REVIEW for f in report.findings
    )
    assert report.dimension_results[0].dimension_state is AuditScorecardDimensionState.DEGRADED


def test_missing_manual_review_for_evidence(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_1", reference="data/ev.json", requires_manual_review=True
    )
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,),
        evidence_refs=(ev,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.MISSING_MANUAL_REVIEW for f in report.findings
    )


# ---------------------------------------------------------------------------
# Conflicts and orphans
# ---------------------------------------------------------------------------


def test_conflicting_links_blocked(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    l1 = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.SUPPORTS
    )
    l2 = AuditScorecardLink(
        link_id="l2", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.CONTRADICTS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), links=(l1, l2), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert any(
        f.reason_code is AuditScorecardReasonCode.CONFLICTING_LINK for f in report.findings
    )


def test_orphan_evidence_degraded(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", expected_evidence_count=0
    )
    ev = AuditScorecardEvidenceRef(evidence_id="ev_1", reference="data/ev.json")
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_EVIDENCE for f in report.findings
    )


def test_orphan_link_degraded(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", expected_evidence_count=0
    )
    link = AuditScorecardLink(
        link_id="l1", source_id="ev_1", target_id="ev_2", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(dimensions=(dim,), links=(link,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.DEGRADED
    assert any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_LINK for f in report.findings
    )


# ---------------------------------------------------------------------------
# Unsafe / forbidden content
# ---------------------------------------------------------------------------


def test_unsafe_metadata_blocked(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    inp = AuditScorecardInput(
        dimensions=(dim,),
        metadata={"note": "This is production ready"},
        generated_at=generated_at,
    )
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.UNSAFE_CONTENT in report.reason_codes


def test_forbidden_term_in_description_blocked(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="This is production ready"
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.BLOCKED
    assert AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes


# ---------------------------------------------------------------------------
# Aggregation / strict mode
# ---------------------------------------------------------------------------


def test_non_strict_mode_preserves_degraded(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", severity=AuditScorecardSeverity.ADVISORY
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp, strict=False)
    assert report.state is AuditScorecardState.DEGRADED


def test_strict_mode_promotes_degraded_to_blocked(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", severity=AuditScorecardSeverity.ADVISORY
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp, strict=True)
    assert report.state is AuditScorecardState.BLOCKED


def test_not_applicable_does_not_block(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(
        dimension_id="dim_1", title="T", description="D", not_applicable=True
    )
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    report = build_audit_scorecard_report(inp)
    assert report.state is AuditScorecardState.OK


# ---------------------------------------------------------------------------
# Determinism and ordering
# ---------------------------------------------------------------------------


def test_report_links_copied_and_sorted(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    l2 = AuditScorecardLink(
        link_id="z", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    l1 = AuditScorecardLink(
        link_id="a", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), links=(l2, l1), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    assert report.links == (l1, l2)


def test_build_report_is_deterministic(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    inp1 = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    inp2 = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    r1 = build_audit_scorecard_report(inp1)
    r2 = build_audit_scorecard_report(inp2)
    assert r1 == r2


def test_build_report_does_not_mutate_input(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    l1 = AuditScorecardLink(
        link_id="a", source_id="ev_1", target_id="dim_1", link_type=AuditScorecardLinkType.COVERS
    )
    inp = AuditScorecardInput(dimensions=(dim,), links=(l1,), generated_at=generated_at)
    original_links = inp.links
    build_audit_scorecard_report(inp)
    assert inp.links is original_links


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_artifact_refs_remain_opaque_strings(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    ev = AuditScorecardEvidenceRef(
        evidence_id="ev_1", reference="data/../etc/passwd"
    )
    inp = AuditScorecardInput(
        dimensions=(dim,), evidence_refs=(ev,), generated_at=generated_at
    )
    report = build_audit_scorecard_report(inp)
    orphan = next(f for f in report.findings if f.reason_code is AuditScorecardReasonCode.ORPHAN_EVIDENCE)
    assert orphan.evidence == ("data/../etc/passwd",)


def test_report_id_deterministic(generated_at: datetime) -> None:
    dim = AuditScorecardDimension(dimension_id="dim_1", title="T", description="D")
    inp = AuditScorecardInput(dimensions=(dim,), generated_at=generated_at)
    r1 = build_audit_scorecard_report(inp)
    r2 = build_audit_scorecard_report(inp)
    assert r1.report_id == r2.report_id
    assert r1.report_id.startswith("audit_scorecard_")


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_public_exports() -> None:
    from hunter.audit_scorecard import (
        build_audit_scorecard_report,
        AuditScorecardInput,
        AuditScorecardReport,
        AuditScorecardState,
        has_unsafe_audit_scorecard_content,
        FORBIDDEN_AUDIT_SCORECARD_TERMS,
    )

    assert build_audit_scorecard_report is not None
    assert AuditScorecardInput is not None
    assert AuditScorecardReport is not None
    assert AuditScorecardState is not None
    assert has_unsafe_audit_scorecard_content is not None
    assert FORBIDDEN_AUDIT_SCORECARD_TERMS is not None
