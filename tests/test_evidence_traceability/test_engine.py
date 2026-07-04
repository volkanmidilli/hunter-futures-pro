"""Tests for hunter.evidence_traceability.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.evidence_traceability.engine import build_evidence_traceability_report
from hunter.evidence_traceability.models import (
    EvidenceArtifactRef,
    EvidenceCheck,
    EvidenceLink,
    EvidenceRequirement,
    EvidenceSectionRef,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityInput,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilityReport,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
    FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS,
)


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def minimal_requirement() -> EvidenceRequirement:
    return EvidenceRequirement(requirement_id="req_1", description="A requirement")


@pytest.fixture
def minimal_input(minimal_requirement: EvidenceRequirement, generated_at: datetime) -> EvidenceTraceabilityInput:
    return EvidenceTraceabilityInput(
        requirements=(minimal_requirement,),
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_empty_requirements_blocked() -> None:
    inp = EvidenceTraceabilityInput(generated_at=datetime.now(timezone.utc))
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.MISSING_REQUIRED_DECLARATION in report.reason_codes


def test_duplicate_requirement_ids_blocked(minimal_input: EvidenceTraceabilityInput) -> None:
    inp = EvidenceTraceabilityInput(
        requirements=(
            EvidenceRequirement(requirement_id="dup", description="A"),
            EvidenceRequirement(requirement_id="dup", description="B"),
        ),
        generated_at=datetime.now(timezone.utc),
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID in report.reason_codes


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_missing_blocking_requirement_coverage_blocked(generated_at: datetime) -> None:
    inp = EvidenceTraceabilityInput(
        requirements=(EvidenceRequirement(requirement_id="req_1", description="Desc"),),
        checks=(),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    result = report.results[0]
    assert result.reason_code is EvidenceTraceabilityReasonCode.MISSING_COVERAGE
    assert result.coverage_state is EvidenceTraceabilityCoverageState.MISSING


def test_missing_advisory_requirement_coverage_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Advisory",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED


def test_partial_coverage_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Need both covered_by and supports",
        required_link_types=("covered_by", "supports"),
    )
    check = EvidenceCheck(check_id="check_1", description="C")
    link = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.PARTIAL_COVERAGE
        for r in report.results
    )


def test_covered_requirement_ok(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    link = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(link,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.OK
    result = report.results[0]
    assert result.coverage_state is EvidenceTraceabilityCoverageState.COVERED


# ---------------------------------------------------------------------------
# Orphans
# ---------------------------------------------------------------------------


def test_orphan_check_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Desc",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    check = EvidenceCheck(check_id="check_1", description="C")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_CHECK
        for r in report.results
    )
    assert all(r.coverage_state is EvidenceTraceabilityCoverageState.NOT_APPLICABLE for r in report.results if r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_CHECK)


def test_orphan_artifact_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Desc",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    art = EvidenceArtifactRef(artifact_id="art_1", reference="data/a.json")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        artifacts=(art,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT
        for r in report.results
    )


def test_orphan_section_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Desc",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    sec = EvidenceSectionRef(section_id="sec_1", reference="reports/s.md")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        sections=(sec,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_SECTION
        for r in report.results
    )


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------


def test_conflicting_links_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    l1 = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    l2 = EvidenceLink(
        link_id="l2",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.CONTRADICTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        links=(l1, l2),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.CONFLICTING_LINK
        for r in report.results
    )


# ---------------------------------------------------------------------------
# Stale evidence
# ---------------------------------------------------------------------------


def test_stale_evidence_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    covered = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/a.json",
        generated_at=generated_at - timedelta(seconds=3601),
    )
    supports = EvidenceLink(
        link_id="l2",
        source_id="check_1",
        target_id="art_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        links=(covered, supports),
        config=EvidenceTraceabilityConfig(staleness_threshold_seconds=3600),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.STALE_EVIDENCE
        for r in report.results
    )


# ---------------------------------------------------------------------------
# Manual review
# ---------------------------------------------------------------------------


def test_missing_manual_review_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    covered = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/a.json",
        requires_manual_review=True,
    )
    supports = EvidenceLink(
        link_id="l2",
        source_id="check_1",
        target_id="art_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        links=(covered, supports),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    assert any(
        r.reason_code is EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW
        for r in report.results
    )


def test_manual_review_present_ok(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    covered = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    art = EvidenceArtifactRef(
        artifact_id="art_1",
        reference="data/a.json",
        requires_manual_review=True,
    )
    supports = EvidenceLink(
        link_id="l2",
        source_id="check_1",
        target_id="art_1",
        link_type=EvidenceTraceabilityLinkType.SUPPORTS,
    )
    reviewed = EvidenceLink(
        link_id="l3",
        source_id="auditor",
        target_id="art_1",
        link_type=EvidenceTraceabilityLinkType.MANUALLY_REVIEWED,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        artifacts=(art,),
        links=(covered, supports, reviewed),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.OK
    assert not any(
        r.reason_code is EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW
        for r in report.results
    )


# ---------------------------------------------------------------------------
# Unsafe / forbidden content
# ---------------------------------------------------------------------------


def test_unsafe_metadata_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        metadata={"note": "This is production ready"},
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.UNSAFE_CONTENT in report.reason_codes


def test_forbidden_term_in_description_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="This is production ready",
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.BLOCKED
    assert EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes


# ---------------------------------------------------------------------------
# Aggregation / strict mode
# ---------------------------------------------------------------------------


def test_non_strict_mode_preserves_degraded(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Advisory",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp, strict=False)
    assert report.state is EvidenceTraceabilityState.DEGRADED


def test_strict_mode_promotes_degraded_to_blocked(generated_at: datetime) -> None:
    req = EvidenceRequirement(
        requirement_id="req_1",
        description="Advisory",
        severity=EvidenceTraceabilitySeverity.ADVISORY,
    )
    inp = EvidenceTraceabilityInput(requirements=(req,), generated_at=generated_at)
    report = build_evidence_traceability_report(inp, strict=True)
    assert report.state is EvidenceTraceabilityState.BLOCKED


def test_not_applicable_does_not_block(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    check = EvidenceCheck(check_id="check_1", description="C")
    covered = EvidenceLink(
        link_id="l1",
        source_id="check_1",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    sec = EvidenceSectionRef(section_id="sec_1", reference="reports/s.md")
    # Section is not linked, so orphan -> NOT_APPLICABLE does not block
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(check,),
        sections=(sec,),
        links=(covered,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.state is EvidenceTraceabilityState.DEGRADED
    # Requirement is OK; section is DEGRADED orphan
    assert any(r.state is EvidenceTraceabilityState.OK for r in report.results)


# ---------------------------------------------------------------------------
# Determinism and links
# ---------------------------------------------------------------------------


def test_report_links_copied_and_sorted(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    c1 = EvidenceCheck(check_id="c", description="C")
    l2 = EvidenceLink(
        link_id="z",
        source_id="c",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    l1 = EvidenceLink(
        link_id="a",
        source_id="c",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(c1,),
        links=(l2, l1),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    assert report.links == (l1, l2)


def test_build_report_is_deterministic(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    c1 = EvidenceCheck(check_id="c", description="C")
    l1 = EvidenceLink(
        link_id="a",
        source_id="c",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp1 = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(c1,),
        links=(l1,),
        generated_at=generated_at,
    )
    inp2 = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(c1,),
        links=(l1,),
        generated_at=generated_at,
    )
    r1 = build_evidence_traceability_report(inp1)
    r2 = build_evidence_traceability_report(inp2)
    assert r1 == r2


def test_build_report_does_not_mutate_input(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    c1 = EvidenceCheck(check_id="c", description="C")
    l1 = EvidenceLink(
        link_id="a",
        source_id="c",
        target_id="req_1",
        link_type=EvidenceTraceabilityLinkType.COVERED_BY,
    )
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        checks=(c1,),
        links=(l1,),
        generated_at=generated_at,
    )
    original_links = inp.links
    build_evidence_traceability_report(inp)
    assert inp.links is original_links


# ---------------------------------------------------------------------------
# Opaque path references
# ---------------------------------------------------------------------------


def test_artifact_refs_remain_opaque_strings(generated_at: datetime) -> None:
    req = EvidenceRequirement(requirement_id="req_1", description="Desc")
    art = EvidenceArtifactRef(artifact_id="art_1", reference="data/../etc/passwd")
    inp = EvidenceTraceabilityInput(
        requirements=(req,),
        artifacts=(art,),
        generated_at=generated_at,
    )
    report = build_evidence_traceability_report(inp)
    # Engine treats the reference as an opaque string; does not traverse or validate it.
    assert all(r.evidence == ("data/../etc/passwd",) for r in report.results if r.reason_code is EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_public_exports() -> None:
    from hunter.evidence_traceability import (
        build_evidence_traceability_report,
        EvidenceTraceabilityInput,
        EvidenceTraceabilityReport,
        EvidenceTraceabilityState,
        has_unsafe_evidence_traceability_content,
    )

    assert build_evidence_traceability_report is not None
    assert EvidenceTraceabilityInput is not None
    assert EvidenceTraceabilityReport is not None
    assert EvidenceTraceabilityState is not None
    assert has_unsafe_evidence_traceability_content is not None

    import hunter.evidence_traceability as et

    assert hasattr(et, "FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS")
